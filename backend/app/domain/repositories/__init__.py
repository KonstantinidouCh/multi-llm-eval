from abc import ABC, abstractmethod
from typing import Protocol
from ..entities import EvaluationResult, LLMResponse


class LLMProviderInterface(Protocol):
    """Interface for LLM providers"""

    @property
    def provider_id(self) -> str:
        ...

    @property
    def name(self) -> str:
        ...

    @property
    def available_models(self) -> list[str]:
        ...

    async def is_available(self) -> bool:
        ...

    async def generate(self, prompt: str, model: str) -> LLMResponse:
        ...


class EvaluationRepository(ABC):
    """Interface for evaluation persistence"""

    @abstractmethod
    async def save(self, evaluation: EvaluationResult) -> None:
        pass

    @abstractmethod
    async def get_by_id(self, evaluation_id: str) -> EvaluationResult | None:
        pass

    @abstractmethod
    async def get_all(self, limit: int = 50) -> list[EvaluationResult]:
        pass
