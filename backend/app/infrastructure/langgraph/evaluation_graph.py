from typing import TypedDict, Annotated, Sequence, Dict, Any
from operator import add
import asyncio

from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage

from ...domain.entities import (
    EvaluationRequest,
    EvaluationResult,
    LLMResponse,
    ComparisonSummary,
)
from ...domain.repositories import LLMProviderInterface
from ...application.use_cases import MetricsCalculator
from langgraph.prebuilt import ToolNode
from .tools import evaluation_tools

from typing import AsyncGenerator


class EvaluationState(TypedDict):
    """State for the evaluation graph"""
    query: str
    selections: list[dict]  # List of {provider, model} pairs
    responses: Annotated[list[LLMResponse], add]
    comparison_summary: ComparisonSummary | None
    messages: Annotated[Sequence[BaseMessage], add]
    error: str | None
    retry_count: int
    failed_selections: list[dict]  # track which ones failed
    tools_results: dict # store tool analysis results


class EvaluationGraph:
    """LangGraph-based evaluation workflow"""

    def __init__(
        self,
        providers: Dict[str, LLMProviderInterface],
        metrics_calculator: MetricsCalculator,
    ):
        self.providers = providers
        self.metrics_calculator = metrics_calculator
        self.graph = self._build_graph()

    def _should_retry(self, state: EvaluationState) -> str:
        """Decide whether to retry failed evaluations"""
        failed = [r for r in state["responses"] if r.error]
        retry_count = state.get("retry_count", 0)
        
        if failed and retry_count < 2:
            return "retry_failed"
        return "calculate_metrics"

    def _build_graph(self) -> StateGraph:
        """Build the evaluation workflow graph"""

        # Create the graph
        workflow = StateGraph(EvaluationState)

        # Add nodes
        workflow.add_node("validate_input", self._validate_input)
        workflow.add_node("parallel_evaluation", self._parallel_evaluation)
        workflow.add_node("retry_failed", self._retry_failed)
        workflow.add_node("calculate_metrics", self._calculate_metrics)
        workflow.add_node("run_tools", self._run_tools)
        workflow.add_node("generate_summary", self._generate_summary)

        # Set entry point
        workflow.set_entry_point("validate_input")

        # Add edges
        workflow.add_edge("validate_input", "parallel_evaluation")

        workflow.add_conditional_edges(
            "parallel_evaluation",
            self._should_retry,
            {
                "retry_failed": "retry_failed",
                "calculate_metrics": "calculate_metrics"
            }
        )
        workflow.add_edge("retry_failed", "calculate_metrics")
        workflow.add_edge("calculate_metrics", "run_tools")
        workflow.add_edge("run_tools", "generate_summary")
        workflow.add_edge("generate_summary", END)

        return workflow.compile()
        

    async def _validate_input(self, state: EvaluationState) -> Dict[str, Any]:
        """Validate the evaluation request"""
        errors = []

        if not state["query"] or not state["query"].strip():
            errors.append("Query cannot be empty")

        if not state["selections"]:
            errors.append("At least one model must be selected")

        # Check if providers exist
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

        return {
            "messages": [HumanMessage(content=f"Validating query: {state['query'][:50]}...")]
        }

    async def _parallel_evaluation(self, state: EvaluationState) -> Dict[str, Any]:
        """Run evaluations in parallel across all selected models"""
        if state.get("error"):
            return {}

        async def evaluate_selection(selection: dict) -> LLMResponse:
            provider = self.providers[selection["provider"]]
            return await provider.generate(state["query"], selection["model"])

        # Run all evaluations concurrently
        tasks = [
            evaluate_selection(sel)
            for sel in state["selections"]
            if sel["provider"] in self.providers
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and convert to LLMResponse
        valid_responses = []
        for resp in responses:
            if isinstance(resp, LLMResponse):
                valid_responses.append(resp)
            elif isinstance(resp, Exception):
                # Log the exception but continue
                pass

        return {
            "responses": valid_responses,
            "messages": [HumanMessage(content=f"Completed {len(valid_responses)} evaluations")]
        }
    
    async def _retry_failed(self, state: EvaluationState) -> Dict[str, Any]:
        """Retry failed evaluations"""
        failed_responses = [r for r in state["responses"] if r.error]
        successful_responses = [r for r in state["responses"] if not r.error]
        
        # Find selections that failed
        failed_provider_models = {(r.provider, r.model) for r in failed_responses}
        failed_selections = [
            sel for sel in state["selections"]
            if (sel["provider"], sel["model"]) in failed_provider_models
        ]
        
        # Retry failed ones
        async def evaluate_selection(selection: dict) -> LLMResponse:
            provider = self.providers[selection["provider"]]
            return await provider.generate(state["query"], selection["model"])
        
        tasks = [evaluate_selection(sel) for sel in failed_selections]
        retry_responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process retry results
        new_responses = []
        for resp in retry_responses:
            if isinstance(resp, LLMResponse):
                new_responses.append(resp)
        
        # Combine successful + retried (replacing old failed ones)
        return {
            "responses": successful_responses + new_responses,
            "retry_count": state.get("retry_count", 0) + 1,
            "messages": [HumanMessage(content=f"Retried {len(failed_selections)} failed evaluations")]
        }
    

    async def _calculate_metrics(self, state: EvaluationState) -> Dict[str, Any]:
        """Calculate quality metrics for all responses"""
        if state.get("error"):
            return {}

        updated_responses = []
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
            updated_responses.append(response)

        # Return empty list since responses already updated in place
        # The add operator would duplicate them otherwise
        return {
            "messages": [HumanMessage(content="Calculated quality metrics")]
        }

    async def _generate_summary(self, state: EvaluationState) -> Dict[str, Any]:
        """Generate comparison summary"""
        if state.get("error"):
            return {}

        responses = state["responses"]
        valid = [r for r in responses if not r.error]

        if not valid:
            return {
                "comparison_summary": ComparisonSummary(),
                "messages": [HumanMessage(content="No valid responses to compare")]
            }

        # Find fastest
        fastest = min(valid, key=lambda r: r.metrics.latency_ms)

        # Find highest quality
        highest_quality = max(valid, key=lambda r: r.metrics.quality_score)

        # Find most cost effective
        cost_effective = min(
            [r for r in valid if r.metrics.quality_score > 0.5] or valid,
            key=lambda r: r.metrics.estimated_cost,
        )

        # Calculate best overall
        def overall_score(r: LLMResponse) -> float:
            max_latency = max(resp.metrics.latency_ms for resp in valid) or 1
            latency_score = 1 - (r.metrics.latency_ms / max_latency)
            max_cost = max(resp.metrics.estimated_cost for resp in valid) or 1
            cost_score = 1 - (r.metrics.estimated_cost / max_cost) if max_cost > 0 else 1
            return (
                r.metrics.quality_score * 0.4 +
                latency_score * 0.3 +
                cost_score * 0.3
            )

        best_overall = max(valid, key=overall_score)

        summary = ComparisonSummary(
            fastest=f"{fastest.provider}/{fastest.model}",
            highest_quality=f"{highest_quality.provider}/{highest_quality.model}",
            most_cost_effective=f"{cost_effective.provider}/{cost_effective.model}",
            best_overall=f"{best_overall.provider}/{best_overall.model}",
        )

        return {
            "comparison_summary": summary,
            "messages": [HumanMessage(content="Generated comparison summary")]
        }
    
    async def _run_tools(self, state: EvaluationState) -> Dict[str, Any]:
        """Run analysis tools on responses"""
        from .tools import evaluation_tools
        
        tool_results = {}
        
        for response in state["responses"]:
            if response.error:
                continue
                
            response_key = f"{response.provider}/{response.model}"
            tool_results[response_key] = {}
            
            for tool in evaluation_tools:
                try:
                    if tool.name == "find_key_topics":
                        result = tool.invoke({"query": state["query"], "response": response.response})
                    else:
                        result = tool.invoke({"response": response.response})
                    tool_results[response_key][tool.name] = result
                except Exception as e:
                    tool_results[response_key][tool.name] = f"Error: {str(e)}"
        
        return {
            "tool_results": tool_results,
            "messages": [HumanMessage(content=f"Ran {len(evaluation_tools)} analysis tools")]
        }
    
    async def run_streaming(self, request: EvaluationRequest) -> AsyncGenerator[dict, None]:
        """Execute the evaluation workflow with streaming updates"""
        initial_state: EvaluationState = {
            "query": request.query,
            "selections": [sel.model_dump() for sel in request.selections],
            "responses": [],
            "comparison_summary": None,
            "messages": [],
            "error": None,
            "retry_count": 0,
            "failed_selections": [],
            "tools_results": {},
        }

        # Use astream to get node outputs as they complete
        final_state = initial_state.copy()
        
        async for chunk in self.graph.astream(initial_state, stream_mode="updates"):
            for node_name, node_output in chunk.items():
                # Filter out non-serializable data (like HumanMessage objects)
                serializable_output = {}
                if isinstance(node_output, dict):
                    for key, value in node_output.items():
                        if key == "messages":
                            # Convert messages to strings
                            serializable_output[key] = [str(m.content) if hasattr(m, 'content') else str(m) for m in value]
                        elif key == "responses":
                            # Convert LLMResponse objects to dicts
                            serializable_output[key] = [r.model_dump(mode='json') if hasattr(r, 'model_dump') else r for r in value]
                        elif key == "comparison_summary" and value is not None:
                            serializable_output[key] = value.model_dump(mode='json') if hasattr(value, 'model_dump') else value
                        else:
                            serializable_output[key] = value
                
                yield {
                    "type": "node_complete",
                    "node": node_name,
                    "data": serializable_output
                }
                
                # Merge updates into final state (INSIDE the loop now!)
                if isinstance(node_output, dict):
                    for key, value in node_output.items():
                        if key == "responses" and isinstance(value, list):
                            # Replace responses (the graph accumulates them)
                            final_state[key] = value
                        elif key == "comparison_summary":
                            final_state[key] = value
                        elif key not in ["messages"]:  # Skip messages
                            final_state[key] = value

        # Yield final result
        yield {
            "type": "complete",
            "result": EvaluationResult(
                query=request.query,
                responses=final_state.get("responses", []),
                comparison_summary=final_state.get("comparison_summary") or ComparisonSummary(),
            ).model_dump(mode='json')
        }


    async def run(self, request: EvaluationRequest) -> EvaluationResult:
        """Execute the evaluation workflow"""
        initial_state: EvaluationState = {
            "query": request.query,
            "selections": [sel.model_dump() for sel in request.selections],
            "responses": [],
            "comparison_summary": None,
            "messages": [],
            "error": None,
            "retry_count": 0,
            "failed_selections": [],
        }

        # Run the graph
        final_state = await self.graph.ainvoke(initial_state)

        # Build result
        return EvaluationResult(
            query=request.query,
            responses=final_state["responses"],
            comparison_summary=final_state["comparison_summary"] or ComparisonSummary(),
        )
