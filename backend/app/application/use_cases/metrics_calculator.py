import re
from typing import Optional
import numpy as np


class MetricsCalculator:
    """Calculate quality metrics for LLM responses"""

    def calculate_coherence(self, text: str) -> float:
        """
        Calculate coherence score based on:
        - Sentence structure
        - Transition words
        - Logical flow indicators
        """
        if not text or len(text.strip()) < 10:
            return 0.0

        sentences = self._split_sentences(text)
        if len(sentences) == 0:
            return 0.0

        # Check for transition words
        transition_words = [
            "however", "therefore", "furthermore", "moreover", "additionally",
            "consequently", "nevertheless", "meanwhile", "subsequently", "thus",
            "hence", "accordingly", "first", "second", "finally", "in conclusion"
        ]

        transition_count = sum(
            1 for word in transition_words
            if word.lower() in text.lower()
        )

        # Sentence length consistency
        sentence_lengths = [len(s.split()) for s in sentences]
        if len(sentence_lengths) > 1:
            length_variance = np.std(sentence_lengths) / (np.mean(sentence_lengths) + 1)
            consistency_score = max(0, 1 - length_variance / 5)
        else:
            consistency_score = 0.5

        # Combine scores
        transition_score = min(1.0, transition_count / max(1, len(sentences) / 3))
        coherence = (consistency_score * 0.5 + transition_score * 0.3 + 0.2)

        return min(1.0, max(0.0, coherence))

    def calculate_relevance(self, query: str, response: str) -> float:
        """
        Calculate relevance score based on:
        - Keyword overlap
        - Query term coverage
        - Response addressing the question
        """
        if not query or not response:
            return 0.0

        query_words = set(self._extract_keywords(query.lower()))
        response_words = set(self._extract_keywords(response.lower()))

        if not query_words:
            return 0.5

        # Calculate overlap
        overlap = query_words.intersection(response_words)
        overlap_ratio = len(overlap) / len(query_words)

        # Check if response addresses question type
        question_indicators = {
            "what": ["is", "are", "means", "refers"],
            "how": ["by", "through", "using", "steps"],
            "why": ["because", "reason", "due to", "since"],
            "when": ["time", "date", "period", "during"],
            "where": ["location", "place", "in", "at"],
        }

        question_type_score = 0.5
        for q_type, indicators in question_indicators.items():
            if q_type in query.lower():
                if any(ind in response.lower() for ind in indicators):
                    question_type_score = 0.8
                    break

        # Combine scores
        relevance = overlap_ratio * 0.6 + question_type_score * 0.4

        return min(1.0, max(0.0, relevance))

    def calculate_quality(
        self,
        text: str,
        query: str,
        coherence: Optional[float] = None,
        relevance: Optional[float] = None
    ) -> float:
        """
        Calculate overall quality score combining multiple factors
        """
        if not text or len(text.strip()) < 10:
            return 0.0

        if coherence is None:
            coherence = self.calculate_coherence(text)
        if relevance is None:
            relevance = self.calculate_relevance(query, text)

        # Length appropriateness (penalize very short or very long)
        word_count = len(text.split())
        if word_count < 20:
            length_score = word_count / 20
        elif word_count > 1000:
            length_score = max(0.5, 1 - (word_count - 1000) / 2000)
        else:
            length_score = 1.0

        # Completeness (check for incomplete sentences)
        completeness = 1.0
        if text.rstrip()[-1] not in ".!?\"'":
            completeness = 0.8

        # Combine all scores
        quality = (
            coherence * 0.3 +
            relevance * 0.4 +
            length_score * 0.15 +
            completeness * 0.15
        )

        return min(1.0, max(0.0, quality))

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences"""
        sentences = re.split(r'[.!?]+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract meaningful keywords from text"""
        # Remove common stopwords
        stopwords = {
            "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "must", "shall", "can", "need", "dare",
            "ought", "used", "to", "of", "in", "for", "on", "with", "at", "by",
            "from", "as", "into", "through", "during", "before", "after", "above",
            "below", "between", "under", "again", "further", "then", "once", "here",
            "there", "when", "where", "why", "how", "all", "each", "few", "more",
            "most", "other", "some", "such", "no", "nor", "not", "only", "own",
            "same", "so", "than", "too", "very", "just", "and", "but", "if", "or",
            "because", "until", "while", "this", "that", "these", "those", "i",
            "me", "my", "we", "our", "you", "your", "he", "him", "his", "she",
            "her", "it", "its", "they", "them", "their", "what", "which", "who"
        }

        words = re.findall(r'\b[a-z]+\b', text.lower())
        return [w for w in words if w not in stopwords and len(w) > 2]
