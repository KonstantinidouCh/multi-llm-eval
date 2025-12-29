from abc import ABC, abstractmethod
import time
from typing import Optional, Any
from ...domain.entities import LLMResponse, MetricResult
from ..observability import observe_llm_call


class BaseLLMProvider(ABC):
    """Base class for LLM providers"""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def available_models(self) -> list[str]:
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        pass

    @abstractmethod
    async def _call_api(self, prompt: str, model: str) -> tuple[str, int, int]:
        """
        Call the LLM API and return (response_text, input_tokens, output_tokens)
        """
        pass

    def _get_cost_per_token(self, model: str) -> tuple[float, float]:
        """Return (input_cost_per_token, output_cost_per_token)"""
        return (0.0, 0.0)  # Free tier default

    async def generate(
        self,
        prompt: str,
        model: str,
        trace: Optional[Any] = None,
    ) -> LLMResponse:
        """Generate a response from the LLM with metrics and optional Langfuse tracing."""
        start_time = time.perf_counter()

        try:
            response_text, input_tokens, output_tokens = await self._call_api(
                prompt, model
            )
            end_time = time.perf_counter()

            latency_ms = (end_time - start_time) * 1000
            tokens_per_second = (
                output_tokens / (latency_ms / 1000) if latency_ms > 0 else 0
            )

            input_cost, output_cost = self._get_cost_per_token(model)
            estimated_cost = (
                input_tokens * input_cost + output_tokens * output_cost
            )

            metrics = MetricResult(
                latency_ms=latency_ms,
                tokens_per_second=tokens_per_second,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost=estimated_cost,
            )

            # Record in Langfuse if trace is provided
            if trace:
                observe_llm_call(
                    trace=trace,
                    name=f"{self.provider_id}/{model}",
                    provider=self.provider_id,
                    model=model,
                    prompt=prompt,
                    response=response_text,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                    metadata={
                        "tokens_per_second": tokens_per_second,
                        "estimated_cost": estimated_cost,
                    },
                )

            return LLMResponse(
                provider=self.provider_id,
                model=model,
                response=response_text,
                metrics=metrics,
            )

        except Exception as e:
            end_time = time.perf_counter()
            latency_ms = (end_time - start_time) * 1000

            # Record error in Langfuse if trace is provided
            if trace:
                observe_llm_call(
                    trace=trace,
                    name=f"{self.provider_id}/{model}",
                    provider=self.provider_id,
                    model=model,
                    prompt=prompt,
                    response="",
                    input_tokens=0,
                    output_tokens=0,
                    latency_ms=latency_ms,
                    error=str(e),
                )

            return LLMResponse(
                provider=self.provider_id,
                model=model,
                response="",
                error=str(e),
            )
