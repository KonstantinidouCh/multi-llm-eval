from typing import List, Optional
from collections import OrderedDict
from ...domain.entities import EvaluationResult
from ...domain.repositories import EvaluationRepository


class InMemoryEvaluationRepository(EvaluationRepository):
    """In-memory implementation of evaluation repository"""

    def __init__(self, max_size: int = 100):
        self._storage: OrderedDict[str, EvaluationResult] = OrderedDict()
        self._max_size = max_size

    async def save(self, evaluation: EvaluationResult) -> None:
        # Remove oldest if at capacity
        if len(self._storage) >= self._max_size:
            self._storage.popitem(last=False)

        self._storage[evaluation.id] = evaluation

    async def get_by_id(self, evaluation_id: str) -> Optional[EvaluationResult]:
        return self._storage.get(evaluation_id)

    async def get_all(self, limit: int = 50) -> List[EvaluationResult]:
        items = list(self._storage.values())
        items.reverse()  # Most recent first
        return items[:limit]
