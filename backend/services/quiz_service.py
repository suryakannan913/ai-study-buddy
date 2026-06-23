"""Quiz generation and grading service."""

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


def generate_questions_from_context(
    topic_name: str,
    context: str,
    num_questions: int = 5,
    difficulty: str = "medium",
) -> list[dict]:
    """
    Generate quiz questions using LLM.

    Args:
        topic_name: The topic being quizzed
        context: Relevant text from study materials
        num_questions: How many questions to generate
        difficulty: "easy", "medium", or "hard"

    Returns:
        List of question dicts with: type, prompt, correct_answer, options (for MC)
    """
    if not context or len(context.strip()) == 0:
        return _generate_fallback_questions(topic_name, num_questions, difficulty)

    difficulty_instructions = {
        "easy": "Generate EASY questions suitable for beginners. Provide clear, straightforward questions.",
        "medium": "Generate MEDIUM difficulty questions. Mix of definition and application.",
        "hard": "Generate HARD questions requiring deep understanding and critical thinking.",
    }

    prompt = f"""Generate {num_questions} quiz questions about "{topic_name}" at {difficulty.lower()} level.
{difficulty_instructions.get(difficulty, '')}

Context from study materials:
{context[:1500]}

Return ONLY a JSON array with this structure (no explanation):
[
  {{
    "type": "multiple_choice",
    "prompt": "Question text here?",
    "correct_answer": "A",
    "options": ["A. Option 1", "B. Option 2", "C. Option 3", "D. Option 4"]
  }},
  {{
    "type": "true_false",
    "prompt": "Is this statement true?",
    "correct_answer": "true"
  }},
  {{
    "type": "short_answer",
    "prompt": "Explain this concept in a few words.",
    "correct_answer": "The expected answer or key concepts"
  }}
]

Ensure:
- Mix of MC, true/false, and short answer
- Questions are grounded in the provided context
- Difficulty level is consistent
- Correct answers are clear and unambiguous"""

    try:
        response = _get_client().chat.completions.create(
            model=settings.groq_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=2000,
        )
        content = response.choices[0].message.content or ""
        questions = json.loads(content)

        if isinstance(questions, list) and len(questions) > 0:
            return questions[:num_questions]
    except Exception as e:
        logger.warning(f"Failed to generate questions via LLM: {e}")

    return _generate_fallback_questions(topic_name, num_questions, difficulty)


def _generate_fallback_questions(
    topic_name: str, num_questions: int, difficulty: str
) -> list[dict]:
    """Fallback questions when LLM fails."""
    return [
        {
            "type": "multiple_choice",
            "prompt": f"What is {topic_name}?",
            "correct_answer": "A",
            "options": [
                "A. A core concept in this topic",
                "B. An unrelated concept",
                "C. A misconception",
                "D. None of the above",
            ],
        },
        {
            "type": "true_false",
            "prompt": f"{topic_name} is an important topic to understand.",
            "correct_answer": "true",
        },
        {
            "type": "short_answer",
            "prompt": f"Briefly explain {topic_name}.",
            "correct_answer": f"A clear, concise explanation of {topic_name}",
        },
    ][:num_questions]


def grade_answer(
    question_type: str, user_response: str, correct_answer: str
) -> tuple[bool, Optional[str]]:
    """
    Grade a student's answer.

    Args:
        question_type: "multiple_choice", "true_false", or "short_answer"
        user_response: The student's answer
        correct_answer: The expected answer

    Returns:
        (is_correct: bool, grading_notes: Optional[str])
    """
    if question_type == "multiple_choice":
        user_clean = user_response.strip().upper()
        expected_clean = correct_answer.strip().upper()
        is_correct = user_clean == expected_clean
        return is_correct, None

    elif question_type == "true_false":
        user_clean = user_response.strip().lower()
        expected_clean = correct_answer.strip().lower()
        is_correct = user_clean in expected_clean or expected_clean in user_clean
        return is_correct, None

    elif question_type == "short_answer":
        # Use LLM to grade short answers
        return _grade_short_answer_llm(user_response, correct_answer)

    return False, "Unknown question type"


def _grade_short_answer_llm(user_response: str, correct_answer: str) -> tuple[bool, str]:
    """Use LLM to grade short-answer questions."""
    prompt = f"""Grade this student's answer to the question.

Expected answer/key concepts: {correct_answer}
Student's answer: {user_response}

Respond with ONLY a JSON object:
{{"correct": true/false, "notes": "brief explanation"}}

Consider the answer correct if it captures the main concepts, even if worded differently."""

    try:
        response = _get_client().chat.completions.create(
            model=settings.groq_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,  # Deterministic
            max_tokens=100,
        )
        content = response.choices[0].message.content or ""
        result = json.loads(content)
        return bool(result.get("correct", False)), result.get("notes", "")
    except Exception as e:
        logger.warning(f"Failed to grade short answer: {e}")
        # Fallback: simple substring match
        is_correct = any(
            keyword.lower() in user_response.lower()
            for keyword in correct_answer.split()[:3]  # Match first 3 keywords
        )
        return is_correct, None
