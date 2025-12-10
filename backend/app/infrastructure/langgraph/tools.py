from langchain_core.tools import tool
from typing import Optional
import re


@tool
def analyze_response_sentiment(response: str) -> str:
    """Analyze the sentiment and tone of an LLM response"""
    # Simple heuristic-based analysis
    positive_words = ["great", "excellent", "helpful", "clear", "accurate", "comprehensive"]
    negative_words = ["wrong", "incorrect", "confusing", "unclear", "error", "mistake"]
    
    response_lower = response.lower()
    positive_count = sum(1 for word in positive_words if word in response_lower)
    negative_count = sum(1 for word in negative_words if word in response_lower)
    
    if positive_count > negative_count:
        sentiment = "positive"
    elif negative_count > positive_count:
        sentiment = "negative"
    else:
        sentiment = "neutral"
    
    return f"Sentiment: {sentiment} (positive indicators: {positive_count}, negative indicators: {negative_count})"


@tool
def detect_code_blocks(response: str) -> str:
    """Detect and count code blocks in a response"""
    code_pattern = r"```[\s\S]*?```"
    inline_code_pattern = r"`[^`]+`"
    
    code_blocks = re.findall(code_pattern, response)
    inline_codes = re.findall(inline_code_pattern, response)
    
    return f"Found {len(code_blocks)} code blocks and {len(inline_codes)} inline code snippets"


@tool
def estimate_reading_time(response: str) -> str:
    """Estimate reading time for a response"""
    words = len(response.split())
    # Average reading speed: 200-250 words per minute
    minutes = words / 225
    
    if minutes < 1:
        return f"Reading time: ~{int(minutes * 60)} seconds ({words} words)"
    return f"Reading time: ~{minutes:.1f} minutes ({words} words)"


@tool
def check_response_structure(response: str) -> str:
    """Check if response has good structure (headers, lists, etc.)"""
    has_headers = bool(re.search(r'^#{1,6}\s', response, re.MULTILINE))
    has_bullet_lists = bool(re.search(r'^[\-\*]\s', response, re.MULTILINE))
    has_numbered_lists = bool(re.search(r'^\d+\.\s', response, re.MULTILINE))
    paragraphs = len([p for p in response.split('\n\n') if p.strip()])
    
    structure_score = sum([has_headers, has_bullet_lists, has_numbered_lists, paragraphs > 1])
    
    return f"Structure score: {structure_score}/4 (headers: {has_headers}, bullets: {has_bullet_lists}, numbered: {has_numbered_lists}, paragraphs: {paragraphs})"


@tool
def find_key_topics(query: str, response: str) -> str:
    """Extract key topics mentioned in query and check if response addresses them"""
    # Simple keyword extraction
    query_words = set(query.lower().split())
    stop_words = {"the", "a", "an", "is", "are", "was", "were", "what", "how", "why", "when", "where", "which", "who"}
    query_keywords = query_words - stop_words
    
    response_lower = response.lower()
    addressed = [kw for kw in query_keywords if kw in response_lower]
    missed = [kw for kw in query_keywords if kw not in response_lower]
    
    coverage = len(addressed) / len(query_keywords) * 100 if query_keywords else 100
    
    return f"Topic coverage: {coverage:.0f}% - Addressed: {addressed[:5]}, Potentially missed: {missed[:3]}"


# Export all tools
evaluation_tools = [
    analyze_response_sentiment,
    detect_code_blocks,
    estimate_reading_time,
    check_response_structure,
    find_key_topics,
]