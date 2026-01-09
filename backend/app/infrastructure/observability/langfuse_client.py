from typing import Optional, Any, Literal
import os
import logging
import uuid

from ...config import get_settings

logger = logging.getLogger(__name__)


# Score type definitions
ScoreDataType = Literal["NUMERIC", "BOOLEAN", "CATEGORICAL"]

# Global client instance (lazy initialized)
_langfuse_client: Optional[Any] = None
_langfuse_initialized: bool = False


def _ensure_langfuse_env():
    """Configure Langfuse environment variables from settings if not already set."""
    settings = get_settings()
    if settings.langfuse_enabled:
        # Only set if not already set (allows env override)
        if "LANGFUSE_SECRET_KEY" not in os.environ or not os.environ["LANGFUSE_SECRET_KEY"]:
            os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key
        if "LANGFUSE_PUBLIC_KEY" not in os.environ or not os.environ["LANGFUSE_PUBLIC_KEY"]:
            os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
        if "LANGFUSE_HOST" not in os.environ or not os.environ["LANGFUSE_HOST"]:
            os.environ["LANGFUSE_HOST"] = settings.langfuse_host
        if "LANGFUSE_TRACING_ENVIRONMENT" not in os.environ:
            os.environ["LANGFUSE_TRACING_ENVIRONMENT"] = settings.langfuse_tracing_environment


def get_langfuse_client() -> Optional[Any]:
    """Get the Langfuse client for SDK v3 operations."""
    global _langfuse_client, _langfuse_initialized

    # Return cached client if already initialized
    if _langfuse_initialized:
        return _langfuse_client

    settings = get_settings()
    if not settings.langfuse_enabled:
        logger.info("Langfuse is disabled in settings")
        _langfuse_initialized = True
        return None

    # Ensure environment variables are set
    _ensure_langfuse_env()

    try:
        from langfuse import get_client
        _langfuse_client = get_client()
        _langfuse_initialized = True
        logger.info(f"Langfuse client initialized successfully (host: {settings.langfuse_host})")
        return _langfuse_client
    except Exception as e:
        logger.error(f"Failed to initialize Langfuse client: {e}")
        _langfuse_initialized = True
        return None


# Keep for backward compatibility
def get_langfuse_low_level() -> Optional[Any]:
    """Get the Langfuse client (alias for get_langfuse_client)."""
    return get_langfuse_client()


class LangfuseTrace:
    """A wrapper for Langfuse trace functionality using SDK v3."""

    def __init__(self, name: str, user_id: Optional[str] = None,
                 session_id: Optional[str] = None, metadata: Optional[dict] = None,
                 tags: Optional[list[str]] = None):
        self.name = name
        self.user_id = user_id
        self.session_id = session_id
        self.metadata = metadata or {}
        self.tags = tags or []
        self._client = get_langfuse_client()
        self._context_manager = None
        self._propagate_context = None
        self._span = None
        self._trace_id: Optional[str] = None
        self._scores: list[dict] = []  # Store scores for batch submission

    def start(self):
        """Start the trace using SDK v3 context manager."""
        if not self._client:
            logger.warning("Langfuse client not available, trace will not be recorded")
            return self

        try:
            # Generate a trace ID for this evaluation
            self._trace_id = uuid.uuid4().hex[:32]

            # Use start_as_current_observation to create a span that acts as the trace root
            self._context_manager = self._client.start_as_current_observation(
                as_type="span",
                name=self.name,
                input=self.metadata,
                metadata={"tags": self.tags} if self.tags else None,
            )
            self._span = self._context_manager.__enter__()

            # Propagate user_id and session_id using SDK v3 propagate_attributes
            if self.user_id or self.session_id:
                try:
                    from langfuse import propagate_attributes
                    attrs = {}
                    if self.user_id:
                        attrs["user_id"] = self.user_id
                    if self.session_id:
                        attrs["session_id"] = self.session_id
                    self._propagate_context = propagate_attributes(**attrs)
                    self._propagate_context.__enter__()
                except Exception as e:
                    logger.warning(f"Failed to propagate attributes: {e}")

            # Try to get the actual trace_id from the span
            if self._span:
                # Log available attributes for debugging
                span_attrs = [attr for attr in dir(self._span) if not attr.startswith('_')]
                logger.debug(f"Span attributes: {span_attrs}")

                if hasattr(self._span, 'trace_id'):
                    self._trace_id = self._span.trace_id
                    logger.debug(f"Got trace_id from span.trace_id: {self._trace_id}")
                elif hasattr(self._span, 'id'):
                    self._trace_id = self._span.id
                    logger.debug(f"Got trace_id from span.id: {self._trace_id}")

                # Also try to get trace_id from context
                if not self._trace_id:
                    try:
                        from langfuse import get_current_trace_id
                        self._trace_id = get_current_trace_id()
                        logger.debug(f"Got trace_id from get_current_trace_id: {self._trace_id}")
                    except ImportError:
                        pass

            logger.info(f"Started Langfuse trace {self._trace_id} (name={self.name}, session_id={self.session_id})")
        except Exception as e:
            logger.error(f"Failed to start Langfuse trace: {e}", exc_info=True)
            self._span = None
            self._context_manager = None

        return self

    def update(self, input: Optional[Any] = None, output: Optional[Any] = None, metadata: Optional[dict] = None):
        """Update the trace span with input, output, or metadata."""
        if not self._span:
            return

        try:
            update_kwargs = {}
            if input is not None:
                update_kwargs["input"] = input
            if output is not None:
                update_kwargs["output"] = output
            if metadata is not None:
                update_kwargs["metadata"] = {**self.metadata, **metadata}

            if update_kwargs and hasattr(self._span, 'update'):
                self._span.update(**update_kwargs)
        except Exception as e:
            logger.error(f"Failed to update trace: {e}")

    def end(self, output: Optional[Any] = None):
        """End the trace and submit all pending scores."""
        logger.info(f"Ending Langfuse trace {self._trace_id}")

        # Update output if provided
        if output is not None:
            self.update(output=output)

        # Submit any pending scores before ending
        self._submit_scores()

        # Exit propagate context first (inner context)
        if self._propagate_context:
            try:
                self._propagate_context.__exit__(None, None, None)
            except Exception:
                pass
            finally:
                self._propagate_context = None

        # Exit main observation context
        if self._context_manager:
            try:
                self._context_manager.__exit__(None, None, None)
            except Exception:
                pass
            finally:
                self._context_manager = None
                self._span = None

        # Flush to ensure all data is sent
        if self._client:
            try:
                self._client.flush()
                logger.info(f"Flushed Langfuse client for trace {self._trace_id}")
            except Exception as e:
                logger.error(f"Failed to flush Langfuse client: {e}")

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
        if not self._client:
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
        """Submit all pending scores to Langfuse using SDK v3."""
        if not self._client or not self._scores:
            logger.debug(f"Skipping score submission: client={bool(self._client)}, scores={len(self._scores)}")
            return

        logger.info(f"Submitting {len(self._scores)} scores (trace_id={self._trace_id}, span={bool(self._span)})")
        submitted = 0

        for score in self._scores:
            try:
                # Method 1: Try using span.score_trace() if span is available (SDK v3 preferred)
                if self._span and hasattr(self._span, 'score_trace'):
                    self._span.score_trace(
                        name=score["name"],
                        value=score["value"],
                        comment=score.get("comment"),
                        data_type=score.get("data_type", "NUMERIC"),
                    )
                    submitted += 1
                    logger.debug(f"Submitted score '{score['name']}' via span.score_trace()")
                # Method 2: Try create_score with trace_id
                elif self._trace_id:
                    self._client.create_score(
                        trace_id=self._trace_id,
                        name=score["name"],
                        value=score["value"],
                        comment=score.get("comment"),
                        data_type=score.get("data_type", "NUMERIC"),
                    )
                    submitted += 1
                    logger.debug(f"Submitted score '{score['name']}' via create_score()")
                # Method 3: Try score_current_trace
                else:
                    try:
                        from langfuse import score_current_trace
                        score_current_trace(
                            name=score["name"],
                            value=score["value"],
                            comment=score.get("comment"),
                            data_type=score.get("data_type", "NUMERIC"),
                        )
                        submitted += 1
                        logger.debug(f"Submitted score '{score['name']}' via score_current_trace()")
                    except ImportError:
                        logger.warning(f"Cannot submit score '{score['name']}': no trace_id and score_current_trace not available")
            except Exception as e:
                logger.error(f"Failed to submit score '{score['name']}': {e}", exc_info=True)

        logger.info(f"Successfully submitted {submitted}/{len(self._scores)} scores")
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
        """Add a generation (LLM call) to this trace using SDK v3."""
        if not self._client:
            logger.warning(f"Cannot add generation {name}: no client available")
            return None

        try:
            # Use context manager to create a generation within the current trace context
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
                    level="ERROR" if error else "DEFAULT",
                )
            logger.info(f"Added generation '{name}' (model={model}) to trace {self._trace_id}")
            return gen
        except Exception as e:
            logger.error(f"Failed to add generation {name}: {e}", exc_info=True)
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
        logger.debug("Langfuse is disabled, not creating trace")
        return None

    logger.info(f"Creating trace: name={name}, user_id={user_id}, session_id={session_id}")
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
    # Flush low-level client (used for traces, generations, scores)
    low_level_client = get_langfuse_low_level()
    if low_level_client:
        try:
            low_level_client.flush()
        except Exception as e:
            logger.error(f"Failed to flush Langfuse: {e}")
