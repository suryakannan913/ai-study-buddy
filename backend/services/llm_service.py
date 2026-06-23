import os
import httpx

from config import settings

TUTOR_SYSTEM_PROMPT = """You are an expert, patient tutor helping a student learn. Your goals:
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
prefer them over general knowledge."""

CONTEXT_TEMPLATE = """The following passages are from the student's uploaded study materials. \
Use them as the primary reference when relevant:

{context}

---
"""


def _get_api_key() -> str:
    """Get API key from environment (Together AI or Groq)."""
    # Check for Together AI first
    if os.getenv("TOGETHER_API_KEY"):
        return os.getenv("TOGETHER_API_KEY")
    # Fall back to Groq
    if settings.groq_api_key:
        return settings.groq_api_key
    raise RuntimeError(
        "No API key set. Add TOGETHER_API_KEY or GROQ_API_KEY to backend/.env"
    )


def _generate_mock_reply(user_message: str, context: str | None = None) -> str:
    """Generate a mock reply for local testing without API access."""
    responses = {
        "array": "Arrays are collections of elements stored in contiguous memory. They provide O(1) access time but O(n) insertion/deletion. Great for fast lookups!",
        "linked list": "Linked lists store elements in nodes with pointers to the next. They're O(n) for access but O(1) for insertion/deletion at known positions.",
        "hash": "Hash tables use hash functions to map keys to values, providing O(1) average time for operations. Perfect for fast lookups!",
        "tree": "Trees are hierarchical structures. Binary trees have at most 2 children. Useful for organizing hierarchical data.",
        "graph": "Graphs consist of vertices and edges. They can be directed/undirected and weighted/unweighted. Great for modeling networks.",
    }

    message_lower = user_message.lower()
    for keyword, response in responses.items():
        if keyword in message_lower:
            if context:
                return f"Based on your materials: {response}\n\nWould you like me to explain this deeper?"
            return f"{response}\n\nWould you like me to explain this in more detail?"

    return "That's a great question! Could you provide more context about what aspect you'd like to explore? I'm here to help you learn! 🎓"


def _call_together_ai(messages: list[dict], model: str = "meta-llama/Llama-2-7b-chat-hf") -> str:
    """Call Together AI API (OpenAI-compatible)."""
    api_key = os.getenv("TOGETHER_API_KEY")
    if not api_key:
        raise RuntimeError("TOGETHER_API_KEY not set")

    url = "https://api.together.xyz/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 1024,
    }

    response = httpx.post(url, json=payload, headers=headers, timeout=30.0)
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


def generate_reply(
    history: list[dict[str, str]],
    context: str | None = None,
) -> str:
    """Generate a tutoring reply using Together AI Llama or Groq.

    `history` is a list of {"role": "user"|"assistant", "content": str} dicts
    for the current conversation (oldest first). `context` is optional retrieved
    study-material text (Phase 2 RAG).
    """
    system = TUTOR_SYSTEM_PROMPT
    if context:
        system = CONTEXT_TEMPLATE.format(context=context) + system

    messages = [{"role": "system", "content": system}, *history]

    try:
        # Try Together AI first
        if os.getenv("TOGETHER_API_KEY"):
            return _call_together_ai(messages)

        # Fall back to Groq
        from groq import Groq
        client = Groq(api_key=settings.groq_api_key)
        completion = client.chat.completions.create(
            model=settings.groq_model,
            messages=messages,
            temperature=0.7,
            max_tokens=1024,
        )
        return completion.choices[0].message.content or ""
    except Exception:
        # Fallback to mock responses for local dev without API access
        user_message = history[-1]["content"] if history else ""
        return _generate_mock_reply(user_message, context)
