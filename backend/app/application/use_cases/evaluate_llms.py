import asyncio
from typing import Dict, List
from ...domain.entities import (
    EvaluationRequest,
    EvaluationResult,
    LLMResponse,
    ComparisonSummary,
)
from ...domain.repositories import LLMProviderInterface, EvaluationRepository
from .metrics_calculator import MetricsCalculator


class EvaluateLLMsUseCase:
    """Use case for evaluating multiple LLMs on a query"""

    def __init__(
        self,
        providers: Dict[str, LLMProviderInterface],
        repository: EvaluationRepository,
        metrics_calculator: MetricsCalculator,
    ):
        self.providers = providers
        self.repository = repository
        self.metrics_calculator = metrics_calculator

    async def execute(self, request: EvaluationRequest) -> EvaluationResult:
        """Execute the evaluation across selected providers"""

        # Run all LLM calls concurrently
        tasks = []
        for provider_id in request.providers:
            if provider_id in self.providers:
                provider = self.providers[provider_id]
                model = request.models.get(provider_id, provider.available_models[0])
                tasks.append(self._evaluate_single(provider, request.query, model))

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Process responses
        valid_responses: List[LLMResponse] = []
        for resp in responses:
            if isinstance(resp, Exception):
                continue
            if isinstance(resp, LLMResponse):
                # Calculate quality metrics
                resp.metrics.coherence_score = self.metrics_calculator.calculate_coherence(
                    resp.response
                )
                resp.metrics.relevance_score = self.metrics_calculator.calculate_relevance(
                    request.query, resp.response
                )
                resp.metrics.quality_score = self.metrics_calculator.calculate_quality(
                    resp.response,
                    request.query,
                    resp.metrics.coherence_score,
                    resp.metrics.relevance_score,
                )
                valid_responses.append(resp)

        # Generate comparison summary
        summary = self._generate_summary(valid_responses)

        # Create result
        result = EvaluationResult(
            query=request.query,
            responses=valid_responses,
            comparison_summary=summary,
        )

        # Persist result
        await self.repository.save(result)

        return result

    async def _evaluate_single(
        self,
        provider: LLMProviderInterface,
        query: str,
        model: str,
    ) -> LLMResponse:
        """Evaluate a single provider"""
        try:
            return await provider.generate(query, model)
        except Exception as e:
            return LLMResponse(
                provider=provider.provider_id,
                model=model,
                response="",
                error=str(e),
            )

    def _generate_summary(self, responses: List[LLMResponse]) -> ComparisonSummary:
        """Generate comparison summary from responses"""
        if not responses:
            return ComparisonSummary()

        # Filter out error responses
        valid = [r for r in responses if not r.error]
        if not valid:
            return ComparisonSummary()

        # Find fastest
        fastest = min(valid, key=lambda r: r.metrics.latency_ms)

        # Find highest quality
        highest_quality = max(valid, key=lambda r: r.metrics.quality_score)

        # Find most cost effective (lowest cost with decent quality)
        cost_effective = min(
            [r for r in valid if r.metrics.quality_score > 0.5] or valid,
            key=lambda r: r.metrics.estimated_cost,
        )

        # Calculate best overall (weighted score)
        def overall_score(r: LLMResponse) -> float:
            # Normalize latency (lower is better)
            max_latency = max(resp.metrics.latency_ms for resp in valid) or 1
            latency_score = 1 - (r.metrics.latency_ms / max_latency)

            # Normalize cost (lower is better)
            max_cost = max(resp.metrics.estimated_cost for resp in valid) or 1
            cost_score = 1 - (r.metrics.estimated_cost / max_cost) if max_cost > 0 else 1

            return (
                r.metrics.quality_score * 0.4 +
                latency_score * 0.3 +
                cost_score * 0.3
            )

        best_overall = max(valid, key=overall_score)

        return ComparisonSummary(
            fastest=f"{fastest.provider}/{fastest.model}",
            highest_quality=f"{highest_quality.provider}/{highest_quality.model}",
            most_cost_effective=f"{cost_effective.provider}/{cost_effective.model}",
            best_overall=f"{best_overall.provider}/{best_overall.model}",
        )
