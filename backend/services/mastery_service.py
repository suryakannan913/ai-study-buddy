"""Mastery-based adaptive difficulty calculation."""

import math
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import TopicMastery


def calculate_adaptive_difficulty(
    user_id: int,
    topic_id: int,
    db: Session,
) -> tuple[str, str]:
    """
    Calculate adaptive quiz difficulty and explanation style based on mastery.

    Returns:
        (quiz_difficulty, explanation_style) where:
        - quiz_difficulty: "easy" | "medium" | "hard"
        - explanation_style: "simple" | "standard" | "deep"
    """
    mastery = db.scalar(
        select(TopicMastery)
        .where(TopicMastery.user_id == user_id)
        .where(TopicMastery.topic_id == topic_id)
    )

    if not mastery or mastery.num_attempts == 0:
        # Unknown topic: start with easy
        return "easy", "simple"

    # Calculate mastery score (0-1)
    mastery_score = (
        mastery.num_correct / mastery.num_attempts
        if mastery.num_attempts > 0
        else 0.0
    )

    # Confidence decay: recent practice = high confidence, old practice = low
    days_since_practice = (
        (datetime.utcnow() - mastery.last_practiced).days
        if mastery.last_practiced
        else 999
    )
    confidence_decay = math.exp(-days_since_practice / 30)  # Half-life: 30 days

    # Confidence combines attempt count (expertise signal) with recency
    attempt_confidence = min(1.0, mastery.num_attempts / 10)  # Saturates at 10 attempts
    confidence = attempt_confidence * confidence_decay

    # Decision logic based on mastery + confidence
    if mastery_score >= 0.85 and confidence > 0.8:
        return "hard", "deep"  # Expert: challenge them
    elif mastery_score >= 0.70 and confidence > 0.6:
        return "medium", "standard"  # Intermediate: reinforce
    elif mastery_score >= 0.50:
        return "easy", "simple"  # Novice: build foundation
    else:
        return "easy", "simple"  # Struggling: keep simple


def get_explanation_style_prompt(style: str) -> str:
    """Get the system prompt variant for the given explanation style."""
    prompts = {
        "simple": """You are a patient, beginner-friendly tutor. Your goals:
1. Explain concepts using everyday language and simple examples.
2. Break complex ideas into tiny, digestible steps.
3. Use analogies to familiar things (sports, cooking, movies, etc.).
4. Avoid jargon—if you must use a term, define it immediately.
5. After explaining, ask ONE simple follow-up question to check understanding.

Keep explanations short (2-3 sentences max per concept). Use lots of examples.
Your student is learning for the first time or struggling with this topic.""",

        "standard": """You are an expert, patient tutor helping a student learn. Your goals:
1. Explain concepts clearly and break complex topics into digestible chunks.
2. Use analogies and real-world examples where helpful.
3. Check understanding with a short follow-up question.
4. Adapt your language to the student's level.
5. Encourage curiosity and deeper thinking.

When the student asks a question:
- Give a clear, concise explanation.
- Offer an example or analogy.
- End by asking if they'd like it simpler or deeper.

If relevant study materials are provided as context, reference them naturally and
prefer them over general knowledge.""",

        "deep": """You are an expert tutor for advanced learners. Your goals:
1. Dive deep into concepts: discuss nuances, edge cases, and interconnections.
2. Assume solid foundational knowledge—skip basic definitions unless asked.
3. Challenge misconceptions and explore counterintuitive aspects.
4. Connect this topic to related fields and broader contexts.
5. Ask probing questions that push critical thinking further.

When the student asks:
- Provide sophisticated, layered explanations.
- Discuss limitations, assumptions, and open questions in the field.
- Encourage them to think like an expert in this domain.
- Ask questions that lead them to deeper insight, not just recitation.""",
    }

    return prompts.get(style, prompts["standard"])
