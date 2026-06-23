"""Topic extraction and inference for knowledge tracking."""

import json
import logging
from typing import Optional

from groq import Groq

from config import settings

logger = logging.getLogger(__name__)

_client: Optional[Groq] = None


def _get_client() -> Groq:
    """Lazy-load Groq client."""
    global _client
    if _client is None:
        if not settings.groq_api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Add it to backend/.env "
                "(get a free key at https://console.groq.com)."
            )
        _client = Groq(api_key=settings.groq_api_key)
    return _client


def extract_topics_from_text(text: str) -> list[str]:
    """
    Use LLM to extract key learning topics from educational text.

    Args:
        text: The text to analyze (usually first 2000 chars of a PDF)

    Returns:
        List of topic names (e.g., ["Calculus", "Derivatives", "Integration"])
    """
    if not text or len(text.strip()) == 0:
        return []

    prompt = f"""Extract 5-10 key learning topics from this educational text.
Return ONLY a JSON list of strings, no explanation.
Example: ["Photosynthesis", "Chlorophyll", "ATP Production"]

Text:
{text[:2000]}"""

    try:
        response = _get_client().chat.completions.create(
            model=settings.groq_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=300,
        )
        content = response.choices[0].message.content or ""
        topics = json.loads(content)
        if isinstance(topics, list) and all(isinstance(t, str) for t in topics):
            return [t.strip() for t in topics if t.strip()]
    except Exception as e:
        logger.warning(f"Failed to extract topics via LLM: {e}")

    # Fallback: simple keyword extraction (if LLM fails)
    return _extract_topics_fallback(text)


def _extract_topics_fallback(text: str) -> list[str]:
    """Fallback: simple keyword extraction if LLM fails."""
    # Split by common delimiters and extract capitalized phrases
    words = text.split()
    topics = []

    for i in range(len(words)):
        word = words[i]
        # Find capitalized multi-word phrases (e.g., "Data Science")
        if word[0].isupper() and len(word) > 2:
            topic = word
            # Check if next word is also capitalized
            if i + 1 < len(words) and words[i + 1][0].isupper():
                topic = f"{word} {words[i + 1]}"
            if topic not in topics and len(topics) < 10:
                topics.append(topic)

    return topics[:10] if topics else []


def infer_topics_from_question(
    question: str,
    available_topics: list[str],
) -> list[tuple[str, float]]:
    """
    Infer which topics a question relates to by semantic similarity.

    Args:
        question: The user's question
        available_topics: List of topics the user has studied

    Returns:
        List of (topic_name, relevance_score) sorted by relevance, highest first
    """
    if not available_topics or not question:
        return []

    prompt = f"""Given this question, rank which of the available topics it relates to.
Return ONLY a JSON object mapping topic name to relevance score (0.0-1.0).
Example: {{"Calculus": 0.95, "Derivatives": 0.85}}

Question: {question}
Available topics: {', '.join(available_topics)}"""

    try:
        response = _get_client().chat.completions.create(
            model=settings.groq_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=300,
        )
        content = response.choices[0].message.content or ""
        scores = json.loads(content)

        # Convert to list of tuples, sorted by score
        result = sorted(
            [(topic, score) for topic, score in scores.items() if score > 0.3],
            key=lambda x: x[1],
            reverse=True,
        )
        return result[:5]  # Top 5 topics
    except Exception as e:
        logger.warning(f"Failed to infer topics via LLM: {e}")
        return []


def extract_or_merge_topics(
    extracted_topics: list[str],
    existing_db_topics: dict[str, int],
) -> list[int]:
    """
    Match extracted topics to existing DB topics, creating new ones if needed.

    Args:
        extracted_topics: List of topic names from LLM
        existing_db_topics: Dict of {topic_name: topic_id} from DB

    Returns:
        List of topic IDs to associate with this material
    """
    result = []

    for topic_name in extracted_topics:
        topic_name = topic_name.strip()
        if topic_name in existing_db_topics:
            result.append(existing_db_topics[topic_name])
        # Note: new topics are created by the caller, not here

    return result
