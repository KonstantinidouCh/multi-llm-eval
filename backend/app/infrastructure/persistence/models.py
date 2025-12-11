from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from .database import Base


class LLMModelDB(Base):
    """Database model for storing LLM model configurations"""
    __tablename__ = "llm_models"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider = Column(String(50), nullable=False, index=True)
    model_name = Column(String(100), nullable=False)
    display_name = Column(String(100), nullable=True)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Unique constraint on provider + model_name
    __table_args__ = (
        {"sqlite_autoincrement": True},
    )


class EvaluationDB(Base):
    """Database model for storing evaluation results"""
    __tablename__ = "evaluations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    query = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    # Comparison summary
    fastest = Column(String(100), default="")
    highest_quality = Column(String(100), default="")
    most_cost_effective = Column(String(100), default="")
    best_overall = Column(String(100), default="")

    # Relationship to responses
    responses = relationship(
        "LLMResponseDB",
        back_populates="evaluation",
        cascade="all, delete-orphan",
        lazy="selectin"
    )


class LLMResponseDB(Base):
    """Database model for storing individual LLM responses"""
    __tablename__ = "llm_responses"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    evaluation_id = Column(String(36), ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    response = Column(Text, default="")
    error = Column(Text, nullable=True)

    # Metrics
    latency_ms = Column(Float, default=0.0)
    tokens_per_second = Column(Float, default=0.0)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    estimated_cost = Column(Float, default=0.0)
    coherence_score = Column(Float, default=0.0)
    relevance_score = Column(Float, default=0.0)
    quality_score = Column(Float, default=0.0)

    # Relationship back to evaluation
    evaluation = relationship("EvaluationDB", back_populates="responses")
