from fastapi import APIRouter, HTTPException, Depends
from typing import List

from ...domain.entities import (
    LLMProvider,
    EvaluationRequest,
    EvaluationResult,
)
from ...config import get_settings, Settings
from ...infrastructure.llm_providers import (
    GroqProvider,
    HuggingFaceProvider,
    OllamaProvider,
)
from ...infrastructure.persistence import InMemoryEvaluationRepository
from ...infrastructure.langgraph import EvaluationGraph
from ...application.use_cases import MetricsCalculator

router = APIRouter(prefix="/api")

# Dependency injection
_repository = None
_evaluation_graph = None
_providers_dict = None


def get_repository() -> InMemoryEvaluationRepository:
    global _repository
    if _repository is None:
        _repository = InMemoryEvaluationRepository()
    return _repository


def get_providers_dict(settings: Settings = Depends(get_settings)):
    global _providers_dict
    if _providers_dict is None:
        _providers_dict = {
            "groq": GroqProvider(settings.groq_api_key),
            "huggingface": HuggingFaceProvider(settings.huggingface_api_key),
            "ollama": OllamaProvider(settings.ollama_base_url),
        }
    return _providers_dict


def get_evaluation_graph(
    settings: Settings = Depends(get_settings),
) -> EvaluationGraph:
    global _evaluation_graph
    if _evaluation_graph is None:
        providers = get_providers_dict(settings)
        metrics_calculator = MetricsCalculator()
        _evaluation_graph = EvaluationGraph(providers, metrics_calculator)
    return _evaluation_graph


@router.get("/providers", response_model=List[LLMProvider])
async def get_providers(settings: Settings = Depends(get_settings)):
    """Get list of available LLM providers"""
    providers_dict = get_providers_dict(settings)

    providers_list = []
    for provider_id, provider in providers_dict.items():
        is_available = await provider.is_available()
        providers_list.append(
            LLMProvider(
                id=provider_id,
                name=provider.name,
                models=provider.available_models,
                enabled=is_available,
            )
        )

    return providers_list


@router.post("/evaluate", response_model=EvaluationResult)
async def evaluate(
    request: EvaluationRequest,
    settings: Settings = Depends(get_settings),
):
    """Evaluate a query across multiple LLM providers"""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    if not request.providers:
        raise HTTPException(
            status_code=400, detail="At least one provider must be selected"
        )

    graph = get_evaluation_graph(settings)
    repository = get_repository()

    try:
        result = await graph.run(request)
        await repository.save(result)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=List[EvaluationResult])
async def get_history(limit: int = 50):
    """Get evaluation history"""
    repository = get_repository()
    return await repository.get_all(limit)


@router.get("/evaluations/{evaluation_id}", response_model=EvaluationResult)
async def get_evaluation(evaluation_id: str):
    """Get a specific evaluation by ID"""
    repository = get_repository()
    result = await repository.get_by_id(evaluation_id)

    if result is None:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    return result


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}
