from functools import lru_cache
from typing import Optional, Any
import os

from ...config import get_settings


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
        except Exception:
            self._span = None
            self._context_manager = None

        return self

    def end(self):
        """End the trace observation by exiting the context manager."""
        if self._context_manager:
            try:
                self._context_manager.__exit__(None, None, None)
            except Exception:
                pass
            finally:
                self._context_manager = None
                self._span = None

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
