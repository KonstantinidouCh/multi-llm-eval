import httpx
from datetime import datetime
from typing import Any
import uuid
import json

from ...domain.entities import ChatMessage, EvaluationResult
from ...infrastructure.persistence import PostgresEvaluationRepository


class ChatService:
    """Service for chatbot that answers questions about evaluation history."""

    def __init__(
        self,
        evaluation_repository: PostgresEvaluationRepository,
        ollama_base_url: str,
    ):
        self.evaluation_repository = evaluation_repository
        self.ollama_base_url = ollama_base_url.rstrip('/')
        self.model = "llama3"
        # In-memory session storage (could be moved to DB for persistence)
        self._sessions: dict[str, list[ChatMessage]] = {}

    def _format_evaluation_for_context(self, eval_result: EvaluationResult) -> str:
        """Format an evaluation result for inclusion in LLM context."""
        # Handle timestamp - could be string or datetime
        try:
            if isinstance(eval_result.timestamp, datetime):
                timestamp_str = eval_result.timestamp.strftime('%Y-%m-%d %H:%M')
            else:
                timestamp_str = str(eval_result.timestamp)[:16].replace('T', ' ')
        except Exception:
            timestamp_str = str(eval_result.timestamp)

        lines = [
            f"Query: \"{eval_result.query}\"",
            f"Date: {timestamp_str}",
            "Results:"
        ]

        for resp in eval_result.responses:
            metrics = resp.metrics
            lines.append(
                f"  - {resp.provider}/{resp.model}: "
                f"latency={metrics.latency_ms:.0f}ms, "
                f"quality={metrics.quality_score:.2f}, "
                f"coherence={metrics.coherence_score:.2f}, "
                f"relevance={metrics.relevance_score:.2f}, "
                f"cost=${metrics.estimated_cost:.6f}, "
                f"tokens/s={metrics.tokens_per_second:.1f}"
            )
            if resp.error:
                lines.append(f"    (Error: {resp.error})")

        summary = eval_result.comparison_summary
        lines.extend([
            f"Summary: fastest={summary.fastest}, "
            f"highest_quality={summary.highest_quality}, "
            f"most_cost_effective={summary.most_cost_effective}, "
            f"best_overall={summary.best_overall}"
        ])

        return "\n".join(lines)

    def _build_system_prompt(self, evaluations: list[EvaluationResult]) -> str:
        """Build the system prompt with evaluation history context."""
        if not evaluations:
            context = "No evaluation history available yet."
        else:
            context_parts = []
            for i, eval_result in enumerate(evaluations, 1):
                context_parts.append(f"[Evaluation {i}]\n{self._format_evaluation_for_context(eval_result)}")
            context = "\n\n".join(context_parts)

        return f"""You are a helpful assistant that answers questions about LLM evaluation history.
You have access to the user's evaluation history data shown below.

EVALUATION HISTORY:
{context}

INSTRUCTIONS:
- Answer questions about the evaluations, comparing models, performance metrics, costs, etc.
- Be specific and reference actual data from the evaluations.
- If asked about something not in the history, say so politely.
- Keep responses concise but informative.
- When comparing models, mention specific metrics like latency, quality scores, and costs.
- You can suggest which models might be best for different use cases based on the data.
- If there's no evaluation history yet, let the user know they need to run some evaluations first.

Available metrics to discuss:
- latency_ms: Response time in milliseconds
- quality_score: Overall quality (0-1)
- coherence_score: How coherent the response is (0-1)
- relevance_score: How relevant to the query (0-1)
- estimated_cost: Cost in USD
- tokens_per_second: Generation speed"""

    async def chat(
        self,
        message: str,
        session_id: str | None = None,
    ) -> tuple[ChatMessage, str]:
        """Process a chat message and return a response."""
        # Get or create session
        if session_id is None or session_id not in self._sessions:
            session_id = str(uuid.uuid4())
            self._sessions[session_id] = []

        session_history = self._sessions[session_id]

        # Add user message to history
        user_message = ChatMessage(role="user", content=message)
        session_history.append(user_message)

        # Fetch recent evaluations for context
        evaluations = await self.evaluation_repository.get_all(limit=20)

        # Build messages for LLM
        system_prompt = self._build_system_prompt(evaluations)
        messages = [{"role": "system", "content": system_prompt}]

        # Add conversation history (last 10 messages to avoid context overflow)
        for msg in session_history[-10:]:
            messages.append({"role": msg.role, "content": msg.content})

        # Call LLM
        response_content = await self._call_llm(messages)

        # Create and store assistant message
        assistant_message = ChatMessage(role="assistant", content=response_content)
        session_history.append(assistant_message)

        return assistant_message, session_id

    async def _call_llm(self, messages: list[dict[str, str]]) -> str:
        """Call the Ollama API to generate a response."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.ollama_base_url}/api/chat",
                    headers={"Content-Type": "application/json"},
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": False,
                    },
                    timeout=120.0,
                )
                response.raise_for_status()
                data = response.json()
                return data["message"]["content"]
        except httpx.HTTPStatusError as e:
            error_detail = e.response.text[:200] if e.response.text else str(e.response.status_code)
            return f"I encountered an error while processing your request: {error_detail}"
        except httpx.ConnectError:
            return "I couldn't connect to the Ollama server. Please make sure Ollama is running."
        except Exception as e:
            return f"I encountered an error: {str(e)}"

    def get_session_history(self, session_id: str) -> list[ChatMessage]:
        """Get chat history for a session."""
        return self._sessions.get(session_id, [])

    def clear_session(self, session_id: str) -> bool:
        """Clear a chat session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False
