"""
Langfuse Evals - Automated quality assessment using Langfuse evaluators.

This module provides integration with Langfuse's evaluation system for:
- Running predefined evaluators on LLM responses
- Creating custom evaluation criteria
- Batch evaluation of historical traces
"""

from typing import Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum

from .langfuse_client import get_langfuse_low_level, get_langfuse
from ...config import get_settings


class EvalType(str, Enum):
    """Types of evaluations supported."""
    RELEVANCE = "relevance"
    COHERENCE = "coherence"
    FACTUALITY = "factuality"
    HELPFULNESS = "helpfulness"
    TOXICITY = "toxicity"
    CUSTOM = "custom"


@dataclass
class EvalResult:
    """Result from an evaluation."""
    name: str
    score: float
    reasoning: Optional[str] = None
    passed: Optional[bool] = None
    metadata: Optional[dict] = None


class LangfuseEvaluator:
    """
    Evaluator class for running Langfuse evaluations.

    Supports both heuristic evaluations and LLM-based evaluations.
    """

    def __init__(self):
        self._client = get_langfuse_low_level()
        self._settings = get_settings()

    def evaluate_relevance(
        self,
        query: str,
        response: str,
        threshold: float = 0.5,
    ) -> EvalResult:
        """
        Evaluate how relevant the response is to the query.

        Uses keyword overlap and semantic similarity heuristics.
        """
        if not query or not response:
            return EvalResult(
                name="relevance",
                score=0.0,
                reasoning="Empty query or response",
                passed=False,
            )

        # Extract keywords (simple implementation)
        query_words = set(self._extract_keywords(query.lower()))
        response_words = set(self._extract_keywords(response.lower()))

        if not query_words:
            return EvalResult(
                name="relevance",
                score=0.5,
                reasoning="No keywords found in query",
                passed=True,
            )

        # Calculate overlap
        overlap = query_words.intersection(response_words)
        overlap_ratio = len(overlap) / len(query_words)

        # Boost for addressing question type
        question_boost = self._check_question_type(query, response)

        score = min(1.0, overlap_ratio * 0.7 + question_boost * 0.3)

        return EvalResult(
            name="relevance",
            score=score,
            reasoning=f"Keyword overlap: {len(overlap)}/{len(query_words)}, Question type addressed: {question_boost > 0}",
            passed=score >= threshold,
            metadata={"overlap_words": list(overlap)[:10]},
        )

    def evaluate_coherence(
        self,
        response: str,
        threshold: float = 0.5,
    ) -> EvalResult:
        """
        Evaluate the coherence and logical flow of a response.
        """
        if not response or len(response.strip()) < 10:
            return EvalResult(
                name="coherence",
                score=0.0,
                reasoning="Response too short",
                passed=False,
            )

        sentences = self._split_sentences(response)
        if not sentences:
            return EvalResult(
                name="coherence",
                score=0.0,
                reasoning="No sentences found",
                passed=False,
            )

        # Check for transition words
        transition_words = [
            "however", "therefore", "furthermore", "moreover", "additionally",
            "consequently", "nevertheless", "thus", "hence", "first", "second",
            "finally", "in conclusion", "for example", "specifically"
        ]

        transition_count = sum(
            1 for word in transition_words
            if word.lower() in response.lower()
        )

        # Sentence length consistency
        sentence_lengths = [len(s.split()) for s in sentences]
        avg_length = sum(sentence_lengths) / len(sentence_lengths)
        variance = sum((l - avg_length) ** 2 for l in sentence_lengths) / len(sentence_lengths)
        consistency_score = max(0, 1 - (variance ** 0.5) / (avg_length + 1) / 2)

        # Completeness check
        completeness = 1.0 if response.rstrip()[-1] in ".!?\"'" else 0.8

        transition_score = min(1.0, transition_count / max(1, len(sentences) / 3))
        score = consistency_score * 0.4 + transition_score * 0.3 + completeness * 0.3

        return EvalResult(
            name="coherence",
            score=min(1.0, max(0.0, score)),
            reasoning=f"Sentences: {len(sentences)}, Transitions: {transition_count}, Consistency: {consistency_score:.2f}",
            passed=score >= threshold,
            metadata={
                "sentence_count": len(sentences),
                "transition_count": transition_count,
                "avg_sentence_length": avg_length,
            },
        )

    def evaluate_helpfulness(
        self,
        query: str,
        response: str,
        threshold: float = 0.5,
    ) -> EvalResult:
        """
        Evaluate how helpful and actionable the response is.
        """
        if not response:
            return EvalResult(
                name="helpfulness",
                score=0.0,
                reasoning="Empty response",
                passed=False,
            )

        score = 0.0
        reasons = []

        # Length check - not too short, not too long
        word_count = len(response.split())
        if word_count < 20:
            length_score = word_count / 20
            reasons.append(f"Too short ({word_count} words)")
        elif word_count > 1000:
            length_score = max(0.5, 1 - (word_count - 1000) / 2000)
            reasons.append(f"Very long ({word_count} words)")
        else:
            length_score = 1.0
            reasons.append(f"Good length ({word_count} words)")

        # Check for actionable content
        actionable_indicators = [
            "you can", "you should", "try", "here's how", "steps:",
            "first", "then", "finally", "example:", "for instance"
        ]
        actionable_count = sum(
            1 for indicator in actionable_indicators
            if indicator.lower() in response.lower()
        )
        actionable_score = min(1.0, actionable_count / 3)
        if actionable_count > 0:
            reasons.append(f"Actionable ({actionable_count} indicators)")

        # Check for structure (lists, headings)
        has_list = any(c in response for c in ["-", "•", "1.", "2."])
        structure_score = 0.8 if has_list else 0.5
        if has_list:
            reasons.append("Has structured content")

        score = length_score * 0.3 + actionable_score * 0.4 + structure_score * 0.3

        return EvalResult(
            name="helpfulness",
            score=min(1.0, max(0.0, score)),
            reasoning="; ".join(reasons),
            passed=score >= threshold,
            metadata={
                "word_count": word_count,
                "actionable_indicators": actionable_count,
                "has_structure": has_list,
            },
        )

    def evaluate_toxicity(
        self,
        response: str,
        threshold: float = 0.1,
    ) -> EvalResult:
        """
        Check for potentially toxic or inappropriate content.

        Returns score where LOWER is better (less toxic).
        """
        if not response:
            return EvalResult(
                name="toxicity",
                score=0.0,
                reasoning="Empty response",
                passed=True,
            )

        # Simple keyword-based toxicity check
        # In production, you'd use a proper toxicity classifier
        toxic_patterns = [
            "hate", "kill", "stupid", "idiot", "dumb",
            "offensive language", "discriminatory"
        ]

        response_lower = response.lower()
        matches = [p for p in toxic_patterns if p in response_lower]

        if matches:
            score = min(1.0, len(matches) * 0.2)
            return EvalResult(
                name="toxicity",
                score=score,
                reasoning=f"Potential issues detected: {len(matches)} patterns",
                passed=score <= threshold,
                metadata={"patterns_found": len(matches)},
            )

        return EvalResult(
            name="toxicity",
            score=0.0,
            reasoning="No toxic patterns detected",
            passed=True,
        )

    def run_all_evaluations(
        self,
        query: str,
        response: str,
        thresholds: Optional[dict] = None,
    ) -> list[EvalResult]:
        """
        Run all available evaluations on a query-response pair.

        Args:
            query: The input query
            response: The LLM response
            thresholds: Optional dict of threshold values per evaluation

        Returns:
            List of EvalResult objects
        """
        thresholds = thresholds or {}

        results = [
            self.evaluate_relevance(
                query, response,
                threshold=thresholds.get("relevance", 0.5)
            ),
            self.evaluate_coherence(
                response,
                threshold=thresholds.get("coherence", 0.5)
            ),
            self.evaluate_helpfulness(
                query, response,
                threshold=thresholds.get("helpfulness", 0.5)
            ),
            self.evaluate_toxicity(
                response,
                threshold=thresholds.get("toxicity", 0.1)
            ),
        ]

        return results

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract meaningful keywords from text."""
        import re

        stopwords = {
            "a", "an", "the", "is", "are", "was", "were", "be", "been",
            "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "must", "to", "of", "in",
            "for", "on", "with", "at", "by", "from", "as", "into", "through",
            "and", "but", "or", "if", "this", "that", "what", "which", "who",
            "how", "when", "where", "why", "i", "you", "he", "she", "it",
            "we", "they", "my", "your", "his", "her", "its", "our", "their"
        }

        words = re.findall(r'\b[a-z]+\b', text.lower())
        return [w for w in words if w not in stopwords and len(w) > 2]

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        import re
        sentences = re.split(r'[.!?]+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _check_question_type(self, query: str, response: str) -> float:
        """Check if response addresses the question type appropriately."""
        question_indicators = {
            "what": ["is", "are", "means", "definition", "refers"],
            "how": ["by", "through", "using", "steps", "process", "method"],
            "why": ["because", "reason", "due to", "since", "cause"],
            "when": ["time", "date", "period", "during", "after", "before"],
            "where": ["location", "place", "in", "at", "region"],
            "which": ["option", "choice", "select", "prefer"],
            "can": ["yes", "no", "able", "possible", "cannot"],
        }

        query_lower = query.lower()
        response_lower = response.lower()

        for q_type, indicators in question_indicators.items():
            if q_type in query_lower:
                if any(ind in response_lower for ind in indicators):
                    return 1.0
                return 0.3  # Question type found but not addressed

        return 0.5  # No specific question type


def create_evaluator() -> Optional[LangfuseEvaluator]:
    """Create a Langfuse evaluator instance if Langfuse is enabled."""
    settings = get_settings()
    if not settings.langfuse_enabled:
        return None
    return LangfuseEvaluator()


def run_evals_on_response(
    query: str,
    response: str,
    model_id: str,
    trace: Optional[Any] = None,
) -> list[EvalResult]:
    """
    Convenience function to run all evaluations on a response and optionally
    record the results in Langfuse.

    Args:
        query: The input query
        response: The LLM response text
        model_id: Identifier for the model (e.g., 'groq/llama3-8b')
        trace: Optional LangfuseTrace to record scores to

    Returns:
        List of EvalResult objects
    """
    evaluator = create_evaluator()
    if not evaluator:
        return []

    results = evaluator.run_all_evaluations(query, response)

    # Record to Langfuse trace if provided
    if trace and hasattr(trace, 'add_score'):
        prefix = model_id.replace("/", "_").replace("-", "_")
        for result in results:
            trace.add_score(
                name=f"{prefix}_eval_{result.name}",
                value=result.score,
                comment=result.reasoning,
            )
            # Also record pass/fail as boolean
            if result.passed is not None:
                trace.add_score(
                    name=f"{prefix}_eval_{result.name}_passed",
                    value=1.0 if result.passed else 0.0,
                    data_type="BOOLEAN",
                    comment=f"Threshold check for {result.name}",
                )

    return results
