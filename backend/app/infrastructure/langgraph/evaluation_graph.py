from typing import TypedDict, Annotated, Sequence, Dict, Any, AsyncGenerator, Optional
from operator import add
import asyncio
import uuid

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

from ...domain.entities import (
    EvaluationRequest,
    EvaluationResult,
    LLMResponse,
    ComparisonSummary,
)
from ...domain.repositories import LLMProviderInterface
from ...application.use_cases import MetricsCalculator


class JudgeResult(TypedDict):
    """Result from LLM-as-Judge evaluation"""
    model_id: str
    accuracy_score: float
    helpfulness_score: float
    reasoning: str


class EvaluationState(TypedDict):
    """State for the evaluation graph"""
    # Core evaluation data
    query: str
    selections: list[dict]
    responses: Annotated[list[LLMResponse], add]
    comparison_summary: ComparisonSummary | None

    # Messaging
    messages: Annotated[Sequence[BaseMessage], add]

    # Error handling
    error: str | None
    retry_count: int
    failed_selections: list[dict]
    node_errors: dict  # Track errors per node for recovery

    # LLM-as-Judge results
    judge_results: list[JudgeResult]

    # Memory/Context - conversation history for multi-turn
    conversation_history: list[dict]
    session_id: str | None


class EvaluationGraph:
    """LangGraph-based evaluation workflow with persistence, error recovery, LLM-as-Judge, and memory"""

    def __init__(
        self,
        providers: Dict[str, LLMProviderInterface],
        metrics_calculator: MetricsCalculator,
        checkpoint_db: str = "checkpoints.db",
    ):
        self.providers = providers
        self.metrics_calculator = metrics_calculator
        self.checkpoint_db = checkpoint_db
        self.graph = None
        self.checkpointer = None

    async def _get_graph(self):
        """Get or create the compiled graph with checkpointing (persistence)"""
        if self.graph is None:
            # Use MemorySaver for in-memory persistence (survives within app lifetime)
            # For production, consider using SqliteSaver with proper connection management
            self.checkpointer = MemorySaver()
            workflow = self._build_graph_workflow()
            self.graph = workflow.compile(checkpointer=self.checkpointer)
        return self.graph

    def _should_retry(self, state: EvaluationState) -> str:
        """Decide whether to retry failed evaluations"""
        failed = [r for r in state["responses"] if r.error]
        retry_count = state.get("retry_count", 0)

        if failed and retry_count < 2:
            return "retry_failed"
        return "error_recovery"

    def _should_skip_to_end(self, state: EvaluationState) -> str:
        """Check if we should skip due to critical error"""
        if state.get("error"):
            return "generate_summary"
        return "calculate_metrics"

    def _build_graph_workflow(self) -> StateGraph:
        """Build the evaluation workflow graph"""
        workflow = StateGraph(EvaluationState)

        # Add all nodes
        workflow.add_node("validate_input", self._validate_input)
        workflow.add_node("parallel_evaluation", self._parallel_evaluation)
        workflow.add_node("retry_failed", self._retry_failed)
        workflow.add_node("error_recovery", self._error_recovery)
        workflow.add_node("calculate_metrics", self._calculate_metrics)
        workflow.add_node("llm_judge", self._llm_judge)
        workflow.add_node("generate_summary", self._generate_summary)

        # Set entry point
        workflow.set_entry_point("validate_input")

        # Add edges with conditional routing
        workflow.add_edge("validate_input", "parallel_evaluation")

        workflow.add_conditional_edges(
            "parallel_evaluation",
            self._should_retry,
            {
                "retry_failed": "retry_failed",
                "error_recovery": "error_recovery"
            }
        )

        workflow.add_edge("retry_failed", "error_recovery")

        workflow.add_conditional_edges(
            "error_recovery",
            self._should_skip_to_end,
            {
                "calculate_metrics": "calculate_metrics",
                "generate_summary": "generate_summary"
            }
        )

        workflow.add_edge("calculate_metrics", "llm_judge")
        workflow.add_edge("llm_judge", "generate_summary")
        workflow.add_edge("generate_summary", END)

        return workflow

    async def _validate_input(self, state: EvaluationState) -> Dict[str, Any]:
        """Validate the evaluation request"""
        errors = []

        if not state["query"] or not state["query"].strip():
            errors.append("Query cannot be empty")

        if not state["selections"]:
            errors.append("At least one model must be selected")

        invalid_providers = [
            sel["provider"] for sel in state["selections"]
            if sel["provider"] not in self.providers
        ]
        if invalid_providers:
            errors.append(f"Invalid providers: {list(set(invalid_providers))}")

        if errors:
            return {
                "error": "; ".join(errors),
                "messages": [HumanMessage(content=f"Validation failed: {'; '.join(errors)}")]
            }

        # Add to conversation history for memory
        history_entry = {
            "role": "user",
            "content": state["query"],
            "timestamp": asyncio.get_event_loop().time()
        }

        return {
            "messages": [HumanMessage(content=f"Validating query: {state['query'][:50]}...")],
            "conversation_history": [history_entry]
        }

    async def _parallel_evaluation(self, state: EvaluationState) -> Dict[str, Any]:
        """Run evaluations in parallel across all selected models"""
        if state.get("error"):
            return {}

        # Build context from conversation history (memory)
        context_messages = []
        for entry in state.get("conversation_history", [])[:-1]:  # All except current
            if entry["role"] == "user":
                context_messages.append(f"Previous question: {entry['content']}")
            elif entry["role"] == "assistant":
                context_messages.append(f"Previous answer summary: {entry['content'][:200]}...")

        context_prefix = ""
        if context_messages:
            context_prefix = "Context from previous conversation:\n" + "\n".join(context_messages[-3:]) + "\n\nCurrent question: "

        async def evaluate_selection(selection: dict) -> LLMResponse:
            provider = self.providers[selection["provider"]]
            query_with_context = context_prefix + state["query"] if context_prefix else state["query"]
            return await provider.generate(query_with_context, selection["model"])

        tasks = [
            evaluate_selection(sel)
            for sel in state["selections"]
            if sel["provider"] in self.providers
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        valid_responses = []
        node_errors = {}

        for i, resp in enumerate(responses):
            if isinstance(resp, LLMResponse):
                valid_responses.append(resp)
            elif isinstance(resp, Exception):
                sel = state["selections"][i]
                error_key = f"{sel['provider']}/{sel['model']}"
                node_errors[error_key] = str(resp)

        return {
            "responses": valid_responses,
            "node_errors": node_errors,
            "messages": [HumanMessage(content=f"Completed {len(valid_responses)} evaluations")]
        }

    async def _retry_failed(self, state: EvaluationState) -> Dict[str, Any]:
        """Retry failed evaluations"""
        failed_responses = [r for r in state["responses"] if r.error]

        failed_provider_models = {(r.provider, r.model) for r in failed_responses}
        failed_selections = [
            sel for sel in state["selections"]
            if (sel["provider"], sel["model"]) in failed_provider_models
        ]

        async def evaluate_selection(selection: dict) -> LLMResponse:
            provider = self.providers[selection["provider"]]
            return await provider.generate(state["query"], selection["model"])

        tasks = [evaluate_selection(sel) for sel in failed_selections]
        retry_responses = await asyncio.gather(*tasks, return_exceptions=True)

        new_responses = []
        for resp in retry_responses:
            if isinstance(resp, LLMResponse):
                new_responses.append(resp)

        # Only return new responses - the add operator will append them
        return {
            "responses": new_responses,
            "retry_count": state.get("retry_count", 0) + 1,
            "messages": [HumanMessage(content=f"Retried {len(failed_selections)} failed evaluations")]
        }

    async def _error_recovery(self, state: EvaluationState) -> Dict[str, Any]:
        """Error recovery node - handles persistent failures gracefully"""
        node_errors = state.get("node_errors", {})
        responses = state.get("responses", [])

        # Check if we have any successful responses
        successful = [r for r in responses if not r.error]

        if not successful and node_errors:
            # All failed - create error summary
            error_summary = "; ".join([f"{k}: {v}" for k, v in node_errors.items()])
            return {
                "error": f"All evaluations failed: {error_summary}",
                "messages": [HumanMessage(content=f"Error recovery: All {len(node_errors)} evaluations failed")]
            }

        if node_errors:
            # Partial failure - log but continue
            return {
                "messages": [HumanMessage(content=f"Error recovery: {len(successful)} succeeded, {len(node_errors)} failed")]
            }

        return {
            "messages": [HumanMessage(content="Error recovery: No errors to recover from")]
        }

    async def _calculate_metrics(self, state: EvaluationState) -> Dict[str, Any]:
        """Calculate quality metrics for all responses"""
        if state.get("error"):
            return {}

        for response in state["responses"]:
            if not response.error:
                response.metrics.coherence_score = self.metrics_calculator.calculate_coherence(
                    response.response
                )
                response.metrics.relevance_score = self.metrics_calculator.calculate_relevance(
                    state["query"], response.response
                )
                response.metrics.quality_score = self.metrics_calculator.calculate_quality(
                    response.response,
                    state["query"],
                    response.metrics.coherence_score,
                    response.metrics.relevance_score,
                )

        return {
            "messages": [HumanMessage(content="Calculated quality metrics")]
        }

    async def _llm_judge(self, state: EvaluationState) -> Dict[str, Any]:
        """LLM-as-Judge node - uses an LLM to evaluate response quality"""
        if state.get("error"):
            return {"judge_results": []}

        responses = [r for r in state["responses"] if not r.error]
        if not responses:
            return {"judge_results": []}

        judge_results = []

        # Use the first available provider as judge (prefer a capable model)
        judge_provider = None
        judge_model = None

        # Priority: huggingface > groq > ollama
        for provider_id in ["huggingface", "groq", "ollama", "gemini"]:
            if provider_id in self.providers:
                provider = self.providers[provider_id]
                if await provider.is_available():
                    judge_provider = provider
                    # Pick a capable model
                    models = provider.available_models
                    if models:
                        judge_model = models[0]
                        break

        if not judge_provider or not judge_model:
            # Fallback: use heuristic scoring
            for response in responses:
                judge_results.append({
                    "model_id": f"{response.provider}/{response.model}",
                    "accuracy_score": response.metrics.relevance_score,
                    "helpfulness_score": response.metrics.coherence_score,
                    "reasoning": "Heuristic scoring (no judge model available)"
                })
            return {"judge_results": judge_results}

        # Create judge prompt
        for response in responses:
            judge_prompt = f"""You are an expert judge evaluating AI responses.

Question: {state["query"]}

Response to evaluate:
{response.response[:2000]}

Please evaluate this response on:
1. Accuracy (0-1): How factually correct is the response?
2. Helpfulness (0-1): How helpful and complete is the response?

Respond in this exact format:
ACCURACY: [score]
HELPFULNESS: [score]
REASONING: [brief explanation]"""

            try:
                judge_response = await judge_provider.generate(judge_prompt, judge_model)

                # Parse judge response
                accuracy = 0.5
                helpfulness = 0.5
                reasoning = "Could not parse judge response"

                if judge_response.response:
                    lines = judge_response.response.split("\n")
                    for line in lines:
                        if line.startswith("ACCURACY:"):
                            try:
                                accuracy = float(line.split(":")[1].strip())
                            except:
                                pass
                        elif line.startswith("HELPFULNESS:"):
                            try:
                                helpfulness = float(line.split(":")[1].strip())
                            except:
                                pass
                        elif line.startswith("REASONING:"):
                            reasoning = line.split(":", 1)[1].strip() if ":" in line else line

                judge_results.append({
                    "model_id": f"{response.provider}/{response.model}",
                    "accuracy_score": min(max(accuracy, 0), 1),
                    "helpfulness_score": min(max(helpfulness, 0), 1),
                    "reasoning": reasoning
                })
            except Exception as e:
                # Fallback on error
                judge_results.append({
                    "model_id": f"{response.provider}/{response.model}",
                    "accuracy_score": response.metrics.relevance_score,
                    "helpfulness_score": response.metrics.coherence_score,
                    "reasoning": f"Judge error: {str(e)}"
                })

        return {
            "judge_results": judge_results,
            "messages": [HumanMessage(content=f"LLM Judge evaluated {len(responses)} responses")]
        }

    async def _generate_summary(self, state: EvaluationState) -> Dict[str, Any]:
        """Generate comparison summary"""
        if state.get("error"):
            return {
                "comparison_summary": ComparisonSummary(),
                "messages": [HumanMessage(content=f"Error: {state['error']}")]
            }

        responses = state["responses"]
        valid = [r for r in responses if not r.error]

        if not valid:
            return {
                "comparison_summary": ComparisonSummary(),
                "messages": [HumanMessage(content="No valid responses to compare")]
            }

        fastest = min(valid, key=lambda r: r.metrics.latency_ms)
        highest_quality = max(valid, key=lambda r: r.metrics.quality_score)

        cost_effective = min(
            [r for r in valid if r.metrics.quality_score > 0.5] or valid,
            key=lambda r: r.metrics.estimated_cost,
        )

        def overall_score(r: LLMResponse) -> float:
            max_latency = max(resp.metrics.latency_ms for resp in valid) or 1
            latency_score = 1 - (r.metrics.latency_ms / max_latency)
            max_cost = max(resp.metrics.estimated_cost for resp in valid) or 1
            cost_score = 1 - (r.metrics.estimated_cost / max_cost) if max_cost > 0 else 1

            # Include judge scores if available
            judge_bonus = 0
            for jr in state.get("judge_results", []):
                if jr["model_id"] == f"{r.provider}/{r.model}":
                    judge_bonus = (jr["accuracy_score"] + jr["helpfulness_score"]) / 4
                    break

            return (
                r.metrics.quality_score * 0.3 +
                latency_score * 0.2 +
                cost_score * 0.2 +
                judge_bonus * 0.3
            )

        best_overall = max(valid, key=overall_score)

        summary = ComparisonSummary(
            fastest=f"{fastest.provider}/{fastest.model}",
            highest_quality=f"{highest_quality.provider}/{highest_quality.model}",
            most_cost_effective=f"{cost_effective.provider}/{cost_effective.model}",
            best_overall=f"{best_overall.provider}/{best_overall.model}",
        )

        # Add to conversation history (memory)
        history_entry = {
            "role": "assistant",
            "content": f"Best: {best_overall.provider}/{best_overall.model}",
            "timestamp": asyncio.get_event_loop().time()
        }

        return {
            "comparison_summary": summary,
            "conversation_history": [history_entry],
            "messages": [HumanMessage(content="Generated comparison summary")]
        }

    async def run_streaming(
        self,
        request: EvaluationRequest,
        session_id: Optional[str] = None
    ) -> AsyncGenerator[dict, None]:
        """Execute the evaluation workflow with streaming updates"""
        graph = await self._get_graph()

        # Generate or use provided session ID for persistence
        thread_id = session_id or str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}

        initial_state: EvaluationState = {
            "query": request.query,
            "selections": [sel.model_dump() for sel in request.selections],
            "responses": [],
            "comparison_summary": None,
            "messages": [],
            "error": None,
            "retry_count": 0,
            "failed_selections": [],
            "node_errors": {},
            "judge_results": [],
            "conversation_history": [],
            "session_id": thread_id,
        }

        final_state = initial_state.copy()

        async for chunk in graph.astream(initial_state, config=config, stream_mode="updates"):
            for node_name, node_output in chunk.items():
                serializable_output = {}
                if isinstance(node_output, dict):
                    for key, value in node_output.items():
                        if key == "messages":
                            serializable_output[key] = [
                                str(m.content) if hasattr(m, 'content') else str(m)
                                for m in value
                            ]
                        elif key == "responses":
                            serializable_output[key] = [
                                r.model_dump(mode='json') if hasattr(r, 'model_dump') else r
                                for r in value
                            ]
                        elif key == "comparison_summary" and value is not None:
                            serializable_output[key] = (
                                value.model_dump(mode='json') if hasattr(value, 'model_dump') else value
                            )
                        elif key == "judge_results":
                            serializable_output[key] = value
                        else:
                            serializable_output[key] = value

                yield {
                    "type": "node_complete",
                    "node": node_name,
                    "data": serializable_output
                }

                if isinstance(node_output, dict):
                    for key, value in node_output.items():
                        if key == "responses" and isinstance(value, list):
                            # Accumulate responses (matches the Annotated add operator)
                            final_state[key] = final_state.get(key, []) + value
                        elif key == "comparison_summary":
                            final_state[key] = value
                        elif key == "judge_results":
                            final_state[key] = value
                        elif key not in ["messages"]:
                            final_state[key] = value

        # Deduplicate responses - keep the latest response for each provider/model pair
        responses = final_state.get("responses", [])
        seen = {}
        for resp in responses:
            key = (resp.provider, resp.model) if hasattr(resp, 'provider') else (resp.get('provider'), resp.get('model'))
            seen[key] = resp  # Later responses override earlier ones
        unique_responses = list(seen.values())

        yield {
            "type": "complete",
            "result": EvaluationResult(
                query=request.query,
                responses=unique_responses,
                comparison_summary=final_state.get("comparison_summary") or ComparisonSummary(),
            ).model_dump(mode='json'),
            "session_id": thread_id,
            "judge_results": final_state.get("judge_results", [])
        }

    async def run(
        self,
        request: EvaluationRequest,
        session_id: Optional[str] = None
    ) -> EvaluationResult:
        """Execute the evaluation workflow"""
        graph = await self._get_graph()

        thread_id = session_id or str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}

        initial_state: EvaluationState = {
            "query": request.query,
            "selections": [sel.model_dump() for sel in request.selections],
            "responses": [],
            "comparison_summary": None,
            "messages": [],
            "error": None,
            "retry_count": 0,
            "failed_selections": [],
            "node_errors": {},
            "judge_results": [],
            "conversation_history": [],
            "session_id": thread_id,
        }

        final_state = await graph.ainvoke(initial_state, config=config)

        return EvaluationResult(
            query=request.query,
            responses=final_state["responses"],
            comparison_summary=final_state["comparison_summary"] or ComparisonSummary(),
        )

    async def get_conversation_history(self, session_id: str) -> list[dict]:
        """Retrieve conversation history for a session (memory)"""
        if not self.checkpointer:
            return []

        config = {"configurable": {"thread_id": session_id}}
        try:
            state = await self.checkpointer.aget(config)
            if state and "conversation_history" in state:
                return state["conversation_history"]
        except:
            pass
        return []
