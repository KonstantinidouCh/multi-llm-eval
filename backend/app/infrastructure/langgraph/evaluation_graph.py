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


class EvaluationState(TypedDict):
    """State for the evaluation graph"""
    query: str
    selections: list[dict]  # List of {provider, model} pairs
    responses: Annotated[list[LLMResponse], add]
    comparison_summary: ComparisonSummary | None
    messages: Annotated[Sequence[BaseMessage], add]
    error: str | None


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

    def _build_graph(self) -> StateGraph:
        """Build the evaluation workflow graph"""

        # Create the graph
        workflow = StateGraph(EvaluationState)

        # Add nodes
        workflow.add_node("validate_input", self._validate_input)
        workflow.add_node("parallel_evaluation", self._parallel_evaluation)
        workflow.add_node("calculate_metrics", self._calculate_metrics)
        workflow.add_node("generate_summary", self._generate_summary)

        # Set entry point
        workflow.set_entry_point("validate_input")

        # Add edges
        workflow.add_edge("validate_input", "parallel_evaluation")
        workflow.add_edge("parallel_evaluation", "calculate_metrics")
        workflow.add_edge("calculate_metrics", "generate_summary")
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

    async def run(self, request: EvaluationRequest) -> EvaluationResult:
        """Execute the evaluation workflow"""
        initial_state: EvaluationState = {
            "query": request.query,
            "selections": [sel.model_dump() for sel in request.selections],
            "responses": [],
            "comparison_summary": None,
            "messages": [],
            "error": None,
        }

        # Run the graph
        final_state = await self.graph.ainvoke(initial_state)

        # Build result
        return EvaluationResult(
            query=request.query,
            responses=final_state["responses"],
            comparison_summary=final_state["comparison_summary"] or ComparisonSummary(),
        )
