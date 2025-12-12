from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel

from ...domain.entities import (
    LLMProvider,
    EvaluationRequest,
    EvaluationResult,
    ChatRequest,
    ChatResponse,
    ChatMessage,
)
from ...config import get_settings, Settings
from ...infrastructure.llm_providers import (
    GroqProvider,
    HuggingFaceProvider,
    OllamaProvider,
    GeminiProvider
)
from ...infrastructure.persistence import (
    PostgresEvaluationRepository,
    PostgresModelRepository,
    get_session_maker,
)
from ...infrastructure.langgraph import EvaluationGraph
from ...application.use_cases import MetricsCalculator
from ...application.services import ChatService
from fastapi.responses import StreamingResponse
import json

router = APIRouter(prefix="/api")

# Dependency injection
_evaluation_repository = None
_model_repository = None
_evaluation_graph = None
_providers_dict = None
_chat_service = None


# Pydantic models for API
class ModelCreate(BaseModel):
    provider: str
    model_name: str
    display_name: Optional[str] = None
    enabled: bool = True


class ModelUpdate(BaseModel):
    display_name: Optional[str] = None
    enabled: Optional[bool] = None


class ModelResponse(BaseModel):
    id: str
    provider: str
    model_name: str
    display_name: Optional[str]
    enabled: bool

    class Config:
        from_attributes = True


def get_evaluation_repository(settings: Settings = Depends(get_settings)) -> PostgresEvaluationRepository:
    global _evaluation_repository
    if _evaluation_repository is None:
        session_maker = get_session_maker(settings.database_url)
        _evaluation_repository = PostgresEvaluationRepository(session_maker)
    return _evaluation_repository


def get_model_repository(settings: Settings = Depends(get_settings)) -> PostgresModelRepository:
    global _model_repository
    if _model_repository is None:
        session_maker = get_session_maker(settings.database_url)
        _model_repository = PostgresModelRepository(session_maker)
    return _model_repository


def get_providers_dict(settings: Settings = Depends(get_settings)):
    global _providers_dict
    if _providers_dict is None:
        _providers_dict = {
            "groq": GroqProvider(settings.groq_api_key),
            "huggingface": HuggingFaceProvider(settings.huggingface_api_key),
            "ollama": OllamaProvider(settings.ollama_base_url),
            "gemini": GeminiProvider(settings.gemini_api_key)
            # Add more providers as needed
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


def get_chat_service(settings: Settings = Depends(get_settings)) -> ChatService:
    global _chat_service, _evaluation_repository
    if _chat_service is None:
        # Ensure evaluation repository is initialized
        if _evaluation_repository is None:
            session_maker = get_session_maker(settings.database_url)
            _evaluation_repository = PostgresEvaluationRepository(session_maker)
        _chat_service = ChatService(
            evaluation_repository=_evaluation_repository,
            ollama_base_url=settings.ollama_base_url,
        )
    return _chat_service


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
    """Evaluate a query across multiple LLM models"""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    if not request.selections:
        raise HTTPException(
            status_code=400, detail="At least one model must be selected"
        )

    graph = get_evaluation_graph(settings)
    repository = get_evaluation_repository(settings)

    try:
        result = await graph.run(request)
        await repository.save(result)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=List[EvaluationResult])
async def get_history(limit: int = 50, settings: Settings = Depends(get_settings)):
    """Get evaluation history"""
    repository = get_evaluation_repository(settings)
    return await repository.get_all(limit)


@router.get("/evaluations/{evaluation_id}", response_model=EvaluationResult)
async def get_evaluation(evaluation_id: str, settings: Settings = Depends(get_settings)):
    """Get a specific evaluation by ID"""
    repository = get_evaluation_repository(settings)
    result = await repository.get_by_id(evaluation_id)

    if result is None:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    return result


@router.delete("/evaluations/{evaluation_id}")
async def delete_evaluation(evaluation_id: str, settings: Settings = Depends(get_settings)):
    """Delete a specific evaluation by ID"""
    repository = get_evaluation_repository(settings)
    deleted = await repository.delete(evaluation_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    return {"message": "Evaluation deleted successfully"}


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@router.post("/evaluate/stream")
async def evaluate_stream(
    request: EvaluationRequest,
    settings: Settings = Depends(get_settings),
):
    """Stream evaluation progress"""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    if not request.selections:
        raise HTTPException(status_code=400, detail="At least one model must be selected")

    graph = get_evaluation_graph(settings)
    repository = get_evaluation_repository(settings)

    async def event_generator():
        final_result = None
        try:
            async for event in graph.run_streaming(request):
                # Capture the final result when complete
                if event.get("type") == "complete" and "result" in event:
                    final_result = event["result"]
                yield f"data: {json.dumps(event)}\n\n"

            # Save the result to database after streaming completes
            if final_result:
                try:
                    from ...domain.entities import EvaluationResult
                    result = EvaluationResult(**final_result)
                    await repository.save(result)
                except Exception as save_error:
                    print(f"Error saving result: {save_error}")
        except Exception as e:
            import traceback
            print(f"Streaming error: {e}")
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# ==================== Model Management Endpoints ====================

@router.get("/models", response_model=List[ModelResponse])
async def list_models(
    provider: Optional[str] = None,
    enabled_only: bool = False,
    settings: Settings = Depends(get_settings),
):
    """List all saved models, optionally filtered by provider"""
    repository = get_model_repository(settings)

    if provider:
        models = await repository.get_by_provider(provider)
        if enabled_only:
            models = [m for m in models if m.enabled]
    else:
        models = await repository.get_all(enabled_only=enabled_only)

    return [
        ModelResponse(
            id=m.id,
            provider=m.provider,
            model_name=m.model_name,
            display_name=m.display_name,
            enabled=m.enabled,
        )
        for m in models
    ]


@router.post("/models", response_model=ModelResponse, status_code=201)
async def create_model(
    model: ModelCreate,
    settings: Settings = Depends(get_settings),
):
    """Add a new model to the database"""
    repository = get_model_repository(settings)

    db_model = await repository.save(
        provider=model.provider,
        model_name=model.model_name,
        display_name=model.display_name,
        enabled=model.enabled,
    )

    return ModelResponse(
        id=db_model.id,
        provider=db_model.provider,
        model_name=db_model.model_name,
        display_name=db_model.display_name,
        enabled=db_model.enabled,
    )


@router.get("/models/{model_id}", response_model=ModelResponse)
async def get_model(
    model_id: str,
    settings: Settings = Depends(get_settings),
):
    """Get a specific model by ID"""
    repository = get_model_repository(settings)
    model = await repository.get_by_id(model_id)

    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")

    return ModelResponse(
        id=model.id,
        provider=model.provider,
        model_name=model.model_name,
        display_name=model.display_name,
        enabled=model.enabled,
    )


@router.patch("/models/{model_id}", response_model=ModelResponse)
async def update_model(
    model_id: str,
    update: ModelUpdate,
    settings: Settings = Depends(get_settings),
):
    """Update a model's display name or enabled status"""
    repository = get_model_repository(settings)
    model = await repository.get_by_id(model_id)

    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")

    if update.enabled is not None:
        model = await repository.set_enabled(model_id, update.enabled)

    if update.display_name is not None:
        model = await repository.save(
            provider=model.provider,
            model_name=model.model_name,
            display_name=update.display_name,
            enabled=model.enabled,
        )

    return ModelResponse(
        id=model.id,
        provider=model.provider,
        model_name=model.model_name,
        display_name=model.display_name,
        enabled=model.enabled,
    )


@router.delete("/models/{model_id}")
async def delete_model(
    model_id: str,
    settings: Settings = Depends(get_settings),
):
    """Delete a model from the database"""
    repository = get_model_repository(settings)
    deleted = await repository.delete(model_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Model not found")

    return {"message": "Model deleted successfully"}


@router.post("/models/seed")
async def seed_models(settings: Settings = Depends(get_settings)):
    """Seed the database with default models from providers"""
    repository = get_model_repository(settings)
    providers_dict = get_providers_dict(settings)

    seeded_models = []
    for provider_id, provider in providers_dict.items():
        for model_name in provider.available_models:
            db_model = await repository.save(
                provider=provider_id,
                model_name=model_name,
                display_name=model_name,
                enabled=True,
            )
            seeded_models.append({
                "id": db_model.id,
                "provider": db_model.provider,
                "model_name": db_model.model_name,
            })

    return {"message": f"Seeded {len(seeded_models)} models", "models": seeded_models}


# ==================== Chat Endpoints ====================

@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    settings: Settings = Depends(get_settings),
):
    """Send a message to the chatbot and get a response about evaluation history"""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    chat_service = get_chat_service(settings)
    assistant_message, session_id = await chat_service.chat(
        message=request.message,
        session_id=request.session_id,
    )

    return ChatResponse(message=assistant_message, session_id=session_id)


@router.get("/chat/history/{session_id}", response_model=List[ChatMessage])
async def get_chat_history(
    session_id: str,
    settings: Settings = Depends(get_settings),
):
    """Get chat history for a session"""
    chat_service = get_chat_service(settings)
    history = chat_service.get_session_history(session_id)
    return history


@router.delete("/chat/session/{session_id}")
async def clear_chat_session(
    session_id: str,
    settings: Settings = Depends(get_settings),
):
    """Clear a chat session"""
    chat_service = get_chat_service(settings)
    cleared = chat_service.clear_session(session_id)

    if not cleared:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"message": "Session cleared successfully"}
