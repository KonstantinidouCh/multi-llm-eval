from functools import lru_cache
from typing import Optional, Any, Literal
import os

from ...config import get_settings


# Score type definitions
ScoreDataType = Literal["NUMERIC", "BOOLEAN", "CATEGORICAL"]


def _configure_langfuse_env():
    """Configure Langfuse environment variables from settings."""
    settings = get_settings()
    if settings.langfuse_enabled:
        os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key
        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
        os.environ["LANGFUSE_HOST"] = settings.langfuse_host


# Configure environment on module load
_configure_langfuse_env()


@lru_cache()
def get_langfuse() -> Optional[Any]:
    """Get the Langfuse client instance if configured."""
    settings = get_settings()
    if not settings.langfuse_enabled:
        return None

    try:
        from langfuse import get_client
        return get_client()
    except Exception:
        return None


def get_langfuse_low_level() -> Optional[Any]:
    """Get the low-level Langfuse client for API operations like scoring."""
    settings = get_settings()
    if not settings.langfuse_enabled:
        return None

    try:
        from langfuse import Langfuse
        return Langfuse()
    except Exception:
        return None


class LangfuseTrace:
    """A wrapper for Langfuse trace functionality using the SDK v3."""

    def __init__(self, name: str, user_id: Optional[str] = None,
                 session_id: Optional[str] = None, metadata: Optional[dict] = None,
                 tags: Optional[list[str]] = None):
        self.name = name
        self.user_id = user_id
        self.session_id = session_id
        self.metadata = metadata or {}
        self.tags = tags or []
        self._context_manager = None
        self._span = None
        self._client = get_langfuse()
        self._low_level_client = get_langfuse_low_level()
        self._trace_id: Optional[str] = None
        self._scores: list[dict] = []  # Store scores for batch submission

    def start(self):
        """Start the trace observation using context manager."""
        if not self._client:
            return self

        try:
            # Create the context manager
            self._context_manager = self._client.start_as_current_observation(
                as_type="span",
                name=self.name,
                input=self.metadata,
            )
            # Enter the context
            self._span = self._context_manager.__enter__()
            # Try to capture trace ID for scoring
            if self._span and hasattr(self._span, 'trace_id'):
                self._trace_id = self._span.trace_id
            elif self._span and hasattr(self._span, 'id'):
                self._trace_id = self._span.id
        except Exception:
            self._span = None
            self._context_manager = None

        return self

    def end(self):
        """End the trace observation by exiting the context manager."""
        # Submit any pending scores before ending
        self._submit_scores()

        if self._context_manager:
            try:
                self._context_manager.__exit__(None, None, None)
            except Exception:
                pass
            finally:
                self._context_manager = None
                self._span = None

    def add_score(
        self,
        name: str,
        value: float,
        comment: Optional[str] = None,
        data_type: ScoreDataType = "NUMERIC",
        config_id: Optional[str] = None,
    ):
        """
        Add a score to this trace.

        Args:
            name: Name of the score (e.g., 'quality', 'relevance', 'coherence')
            value: Numeric value (0-1 for normalized scores)
            comment: Optional explanation or context for the score
            data_type: Type of score data (NUMERIC, BOOLEAN, CATEGORICAL)
            config_id: Optional score config ID for predefined score types
        """
        if not self._low_level_client:
            return

        score_data = {
            "name": name,
            "value": value,
            "comment": comment,
            "data_type": data_type,
        }
        if config_id:
            score_data["config_id"] = config_id

        self._scores.append(score_data)

    def add_model_scores(
        self,
        model_id: str,
        quality_score: float,
        coherence_score: float,
        relevance_score: float,
        latency_ms: float,
        cost: float,
        comment: Optional[str] = None,
    ):
        """
        Add evaluation scores for a specific model response.

        Args:
            model_id: Identifier for the model (e.g., 'groq/llama3-8b')
            quality_score: Overall quality score (0-1)
            coherence_score: Text coherence score (0-1)
            relevance_score: Query relevance score (0-1)
            latency_ms: Response latency in milliseconds
            cost: Estimated cost
            comment: Optional context
        """
        prefix = model_id.replace("/", "_").replace("-", "_")

        self.add_score(
            name=f"{prefix}_quality",
            value=quality_score,
            comment=f"Quality score for {model_id}" + (f": {comment}" if comment else ""),
        )
        self.add_score(
            name=f"{prefix}_coherence",
            value=coherence_score,
            comment=f"Coherence score for {model_id}",
        )
        self.add_score(
            name=f"{prefix}_relevance",
            value=relevance_score,
            comment=f"Relevance score for {model_id}",
        )
        # Normalize latency to 0-1 (assuming max 30s = 30000ms)
        normalized_latency = min(1.0, latency_ms / 30000)
        self.add_score(
            name=f"{prefix}_latency",
            value=1.0 - normalized_latency,  # Higher is better (faster)
            comment=f"Latency score for {model_id}: {latency_ms:.0f}ms",
        )
        # Cost score (lower is better, normalize assuming max $0.10 per call)
        normalized_cost = min(1.0, cost / 0.10) if cost > 0 else 0.0
        self.add_score(
            name=f"{prefix}_cost_efficiency",
            value=1.0 - normalized_cost,  # Higher is better (cheaper)
            comment=f"Cost efficiency for {model_id}: ${cost:.6f}",
        )

    def add_judge_scores(
        self,
        model_id: str,
        accuracy_score: float,
        helpfulness_score: float,
        reasoning: str,
    ):
        """
        Add LLM-as-Judge evaluation scores.

        Args:
            model_id: Identifier for the evaluated model
            accuracy_score: Judge's accuracy assessment (0-1)
            helpfulness_score: Judge's helpfulness assessment (0-1)
            reasoning: Judge's reasoning/explanation
        """
        prefix = model_id.replace("/", "_").replace("-", "_")

        self.add_score(
            name=f"{prefix}_judge_accuracy",
            value=accuracy_score,
            comment=f"LLM Judge accuracy for {model_id}",
        )
        self.add_score(
            name=f"{prefix}_judge_helpfulness",
            value=helpfulness_score,
            comment=f"LLM Judge helpfulness for {model_id}",
        )
        # Combined judge score
        combined = (accuracy_score + helpfulness_score) / 2
        self.add_score(
            name=f"{prefix}_judge_overall",
            value=combined,
            comment=f"LLM Judge overall for {model_id}: {reasoning[:200]}",
        )

    def add_comparison_scores(
        self,
        best_overall: str,
        fastest: str,
        highest_quality: str,
        most_cost_effective: str,
        total_models: int,
    ):
        """
        Add comparison/ranking scores for the evaluation.

        Args:
            best_overall: Model ID of best overall performer
            fastest: Model ID of fastest responder
            highest_quality: Model ID with highest quality
            most_cost_effective: Model ID with best cost-effectiveness
            total_models: Total number of models evaluated
        """
        self.add_score(
            name="evaluation_model_count",
            value=float(total_models),
            comment=f"Number of models evaluated",
        )
        self.add_score(
            name="evaluation_complete",
            value=1.0,
            data_type="BOOLEAN",
            comment=f"Best: {best_overall}, Fastest: {fastest}, Quality: {highest_quality}, Cost-effective: {most_cost_effective}",
        )

    def _submit_scores(self):
        """Submit all pending scores to Langfuse."""
        if not self._low_level_client or not self._scores:
            return

        # Get trace ID - try multiple approaches
        trace_id = self._trace_id
        if not trace_id and self._span:
            # Try to get from current observation context
            try:
                if hasattr(self._span, 'trace_id'):
                    trace_id = self._span.trace_id
                elif hasattr(self._span, 'id'):
                    trace_id = self._span.id
            except Exception:
                pass

        if not trace_id:
            # Cannot submit scores without trace ID
            self._scores = []
            return

        for score in self._scores:
            try:
                self._low_level_client.score(
                    trace_id=trace_id,
                    name=score["name"],
                    value=score["value"],
                    comment=score.get("comment"),
                    data_type=score.get("data_type", "NUMERIC"),
                )
            except Exception:
                # Silently fail on individual score submission
                pass

        self._scores = []

    def add_generation(
        self,
        name: str,
        model: str,
        prompt: str,
        response: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
        provider: str,
        error: Optional[str] = None,
        metadata: Optional[dict] = None,
    ):
        """Add a generation (LLM call) to this trace."""
        if not self._client:
            return None

        try:
            # Use context manager for generation
            with self._client.start_as_current_observation(
                as_type="generation",
                name=name,
                model=model,
                input=prompt,
            ) as gen:
                # Update with output and metadata
                gen.update(
                    output=response if not error else f"Error: {error}",
                    usage_details={
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                    } if input_tokens or output_tokens else None,
                    metadata={
                        "provider": provider,
                        "latency_ms": latency_ms,
                        "error": error,
                        **(metadata or {}),
                    },
                )
                return gen
        except Exception:
            return None


def create_trace(
    name: str,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    metadata: Optional[dict] = None,
    tags: Optional[list[str]] = None,
) -> Optional[LangfuseTrace]:
    """Create a new Langfuse trace for an evaluation workflow."""
    settings = get_settings()
    if not settings.langfuse_enabled:
        return None

    trace = LangfuseTrace(
        name=name,
        user_id=user_id,
        session_id=session_id,
        metadata=metadata,
        tags=tags,
    )
    return trace.start()


def observe_llm_call(
    trace: Optional[LangfuseTrace],
    name: str,
    provider: str,
    model: str,
    prompt: str,
    response: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: float,
    error: Optional[str] = None,
    metadata: Optional[dict] = None,
):
    """Record an LLM call as a generation in Langfuse."""
    if not trace:
        return None

    return trace.add_generation(
        name=name,
        model=model,
        prompt=prompt,
        response=response,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        provider=provider,
        error=error,
        metadata=metadata,
    )


def flush_langfuse():
    """Flush any pending Langfuse events."""
    client = get_langfuse()
    if client and hasattr(client, 'flush'):
        try:
            client.flush()
        except Exception:
            pass
