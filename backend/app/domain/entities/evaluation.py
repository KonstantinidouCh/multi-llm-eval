from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid


class LLMProvider(BaseModel):
    id: str
    name: str
    models: list[str]
    enabled: bool = True


class ModelSelection(BaseModel):
    provider: str
    model: str


class EvaluationRequest(BaseModel):
    query: str
    selections: list[ModelSelection]


class MetricResult(BaseModel):
    latency_ms: float = 0.0
    tokens_per_second: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost: float = 0.0
    coherence_score: float = 0.0
    relevance_score: float = 0.0
    quality_score: float = 0.0


class LLMResponse(BaseModel):
    provider: str
    model: str
    response: str = ""
    metrics: MetricResult = Field(default_factory=MetricResult)
    error: Optional[str] = None


class ComparisonSummary(BaseModel):
    fastest: str = ""
    highest_quality: str = ""
    most_cost_effective: str = ""
    best_overall: str = ""


class EvaluationResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    responses: list[LLMResponse] = Field(default_factory=list)
    comparison_summary: ComparisonSummary = Field(default_factory=ComparisonSummary)
