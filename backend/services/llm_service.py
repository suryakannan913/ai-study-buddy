from groq import Groq

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

_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        if not settings.groq_api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Add it to backend/.env "
                "(get a free key at https://console.groq.com)."
            )
        _client = Groq(api_key=settings.groq_api_key)
    return _client


def generate_reply(
    history: list[dict[str, str]],
    context: str | None = None,
) -> str:
    """Generate a tutoring reply.

    `history` is a list of {"role": "user"|"assistant", "content": str} dicts
    for the current conversation (oldest first). `context` is optional retrieved
    study-material text (Phase 2 RAG).
    """
    system = TUTOR_SYSTEM_PROMPT
    if context:
        system = CONTEXT_TEMPLATE.format(context=context) + system

    messages = [{"role": "system", "content": system}, *history]

    completion = _get_client().chat.completions.create(
        model=settings.groq_model,
        messages=messages,
        temperature=0.7,
        max_tokens=1024,
    )
    return completion.choices[0].message.content or ""
