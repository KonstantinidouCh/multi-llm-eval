from typing import List, Optional
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...domain.entities import (
    EvaluationResult,
    LLMResponse,
    MetricResult,
    ComparisonSummary,
)
from ...domain.repositories import EvaluationRepository
from .models import EvaluationDB, LLMResponseDB, LLMModelDB


class PostgresEvaluationRepository(EvaluationRepository):
    """PostgreSQL implementation of evaluation repository"""

    def __init__(self, session_maker: async_sessionmaker[AsyncSession]):
        self._session_maker = session_maker

    def _db_to_entity(self, db_eval: EvaluationDB) -> EvaluationResult:
        """Convert database model to domain entity"""
        responses = [
            LLMResponse(
                provider=r.provider,
                model=r.model,
                response=r.response,
                error=r.error,
                metrics=MetricResult(
                    latency_ms=r.latency_ms,
                    tokens_per_second=r.tokens_per_second,
                    input_tokens=r.input_tokens,
                    output_tokens=r.output_tokens,
                    estimated_cost=r.estimated_cost,
                    coherence_score=r.coherence_score,
                    relevance_score=r.relevance_score,
                    quality_score=r.quality_score,
                ),
            )
            for r in db_eval.responses
        ]

        return EvaluationResult(
            id=db_eval.id,
            query=db_eval.query,
            timestamp=db_eval.timestamp,
            responses=responses,
            comparison_summary=ComparisonSummary(
                fastest=db_eval.fastest,
                highest_quality=db_eval.highest_quality,
                most_cost_effective=db_eval.most_cost_effective,
                best_overall=db_eval.best_overall,
            ),
        )

    async def save(self, evaluation: EvaluationResult) -> None:
        """Save an evaluation result"""
        async with self._session_maker() as session:
            # Create evaluation record
            db_eval = EvaluationDB(
                id=evaluation.id,
                query=evaluation.query,
                timestamp=evaluation.timestamp,
                fastest=evaluation.comparison_summary.fastest,
                highest_quality=evaluation.comparison_summary.highest_quality,
                most_cost_effective=evaluation.comparison_summary.most_cost_effective,
                best_overall=evaluation.comparison_summary.best_overall,
            )

            # Create response records
            for resp in evaluation.responses:
                db_response = LLMResponseDB(
                    evaluation_id=evaluation.id,
                    provider=resp.provider,
                    model=resp.model,
                    response=resp.response,
                    error=resp.error,
                    latency_ms=resp.metrics.latency_ms,
                    tokens_per_second=resp.metrics.tokens_per_second,
                    input_tokens=resp.metrics.input_tokens,
                    output_tokens=resp.metrics.output_tokens,
                    estimated_cost=resp.metrics.estimated_cost,
                    coherence_score=resp.metrics.coherence_score,
                    relevance_score=resp.metrics.relevance_score,
                    quality_score=resp.metrics.quality_score,
                )
                db_eval.responses.append(db_response)

            session.add(db_eval)
            await session.commit()

    async def get_by_id(self, evaluation_id: str) -> Optional[EvaluationResult]:
        """Get an evaluation by ID"""
        async with self._session_maker() as session:
            result = await session.execute(
                select(EvaluationDB).where(EvaluationDB.id == evaluation_id)
            )
            db_eval = result.scalar_one_or_none()

            if db_eval is None:
                return None

            return self._db_to_entity(db_eval)

    async def get_all(self, limit: int = 50) -> List[EvaluationResult]:
        """Get all evaluations, ordered by timestamp descending"""
        async with self._session_maker() as session:
            result = await session.execute(
                select(EvaluationDB)
                .order_by(EvaluationDB.timestamp.desc())
                .limit(limit)
            )
            db_evals = result.scalars().all()

            return [self._db_to_entity(e) for e in db_evals]

    async def delete(self, evaluation_id: str) -> bool:
        """Delete an evaluation by ID"""
        async with self._session_maker() as session:
            result = await session.execute(
                delete(EvaluationDB).where(EvaluationDB.id == evaluation_id)
            )
            await session.commit()
            return result.rowcount > 0


class PostgresModelRepository:
    """Repository for managing LLM model configurations"""

    def __init__(self, session_maker: async_sessionmaker[AsyncSession]):
        self._session_maker = session_maker

    async def save(self, provider: str, model_name: str, display_name: str = None, enabled: bool = True) -> LLMModelDB:
        """Save or update a model configuration"""
        async with self._session_maker() as session:
            # Check if model already exists
            result = await session.execute(
                select(LLMModelDB).where(
                    LLMModelDB.provider == provider,
                    LLMModelDB.model_name == model_name
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.display_name = display_name or existing.display_name
                existing.enabled = enabled
                await session.commit()
                await session.refresh(existing)
                return existing
            else:
                db_model = LLMModelDB(
                    provider=provider,
                    model_name=model_name,
                    display_name=display_name or model_name,
                    enabled=enabled,
                )
                session.add(db_model)
                await session.commit()
                await session.refresh(db_model)
                return db_model

    async def get_by_id(self, model_id: str) -> Optional[LLMModelDB]:
        """Get a model by ID"""
        async with self._session_maker() as session:
            result = await session.execute(
                select(LLMModelDB).where(LLMModelDB.id == model_id)
            )
            return result.scalar_one_or_none()

    async def get_by_provider(self, provider: str) -> List[LLMModelDB]:
        """Get all models for a provider"""
        async with self._session_maker() as session:
            result = await session.execute(
                select(LLMModelDB)
                .where(LLMModelDB.provider == provider)
                .order_by(LLMModelDB.model_name)
            )
            return list(result.scalars().all())

    async def get_all(self, enabled_only: bool = False) -> List[LLMModelDB]:
        """Get all models"""
        async with self._session_maker() as session:
            query = select(LLMModelDB).order_by(LLMModelDB.provider, LLMModelDB.model_name)
            if enabled_only:
                query = query.where(LLMModelDB.enabled == True)
            result = await session.execute(query)
            return list(result.scalars().all())

    async def delete(self, model_id: str) -> bool:
        """Delete a model by ID"""
        async with self._session_maker() as session:
            result = await session.execute(
                delete(LLMModelDB).where(LLMModelDB.id == model_id)
            )
            await session.commit()
            return result.rowcount > 0

    async def set_enabled(self, model_id: str, enabled: bool) -> Optional[LLMModelDB]:
        """Enable or disable a model"""
        async with self._session_maker() as session:
            result = await session.execute(
                select(LLMModelDB).where(LLMModelDB.id == model_id)
            )
            model = result.scalar_one_or_none()
            if model:
                model.enabled = enabled
                await session.commit()
                await session.refresh(model)
            return model
