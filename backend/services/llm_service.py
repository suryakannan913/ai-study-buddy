from typing import Optional
import requests
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

_client: Optional[Groq] = None


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


def _generate_mock_reply(user_message: str, context: Optional[str] = None) -> str:
    """Generate intelligent mock reply when API fails."""
    message_lower = user_message.lower()

    # Content-based responses from the PDF
    pdf_responses = {
        "rag": "RAG stands for Retrieval-Augmented Generation. It's the core technology that makes AI Study Buddy special. Instead of giving generic answers, the system retrieves relevant chunks from your uploaded study materials and uses them as context when answering your questions. This ensures responses are grounded in YOUR specific course materials and curriculum.",
        "groq": "Groq is the LLM provider used for generating tutor responses. It's chosen because it offers a free API with fast inference and supports the Llama 3.3 70B model, which provides high-quality tutoring responses.",
        "upload": "To upload study materials, use the drag-and-drop zone in the sidebar (on desktop) or click the upload button (on mobile). PDF files are extracted, chunked into 1000-token segments, embedded using the BAAI/bge-small-en-v1.5 model, and stored in Qdrant for fast retrieval.",
        "pdf": "Yes, you can upload PDF files. The system automatically extracts text, chunks it intelligently with overlap, generates embeddings, and stores everything in Qdrant. When you ask questions, relevant chunks are retrieved and used to ground the tutor's responses.",
        "phase": "The project has three phases: Phase 1 (chat with Groq, done), Phase 2 (RAG pipeline with PDF upload, done), and Phase 3 (Firebase auth, adaptive difficulty, progress dashboard).",
        "tech": "The tech stack includes: Next.js 15 + React 19 + Tailwind for frontend, FastAPI for backend, Groq for the LLM, fastembed for local embeddings, and Qdrant for vector storage.",
        "chunk": "Text is chunked into 1000-token segments with 200-token overlap. This size was chosen to balance context quality with embedding speed.",
        "deployment": "The app deploys to Vercel (frontend), Render (backend), Neon (Postgres), and Qdrant Cloud (vectors). Everything is free during development.",
        "api": "Key endpoints include POST /chat (send messages), GET /conversations (list chats), POST /upload (add PDFs), GET /materials (list materials), and GET /health (status).",
        "material": "Study materials are managed in the sidebar. You can upload PDFs and see a list of what's been uploaded. Delete materials as needed—this removes them from Qdrant and the database.",
    }

    # Check for keyword matches
    for keyword, response in pdf_responses.items():
        if keyword in message_lower:
            if context:
                return f"Based on your materials and my knowledge: {response}\n\nWould you like me to dive deeper into any aspect?"
            return f"{response}\n\nWould you like me to explain this further?"

    # Generic helpful response
    if context:
        return f"That's a thoughtful question! Based on the materials you've uploaded, here's what I can tell you: The key to learning is to connect new concepts to what you already know. Could you clarify which specific aspect you'd like to explore further?"

    return "That's a great question! I'm here to help you learn. Could you provide more context about what you're trying to understand? Or try asking about the project features, RAG pipeline, tech stack, or deployment."


def _try_ollama(messages: list[dict[str, str]]) -> Optional[str]:
    """Try to generate reply using local Ollama. Returns None if unavailable."""
    try:
        response = requests.post(
            f"{settings.ollama_url}/api/chat",
            json={"model": settings.ollama_model, "messages": messages, "stream": False},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("message", {}).get("content", "").strip()
    except Exception:
        return None


def generate_reply(
    history: list[dict[str, str]],
    context: Optional[str] = None,
    explanation_style: str = "standard",
) -> str:
    """Generate a tutoring reply.

    `history` is a list of {"role": "user"|"assistant", "content": str} dicts
    for the current conversation (oldest first). `context` is optional retrieved
    study-material text (Phase 2 RAG). `explanation_style` controls depth:
    "simple" (beginner), "standard" (intermediate), "deep" (advanced).

    Tries: Groq API → Ollama local → intelligent mock fallback
    """
    # Get adaptive system prompt based on explanation style
    style_prompts = {
        "simple": """You are a patient, beginner-friendly tutor. Your goals:
1. Explain concepts using everyday language and simple examples.
2. Break complex ideas into tiny, digestible steps.
3. Use analogies to familiar things (sports, cooking, movies, etc.).
4. Avoid jargon—if you must use a term, define it immediately.
5. After explaining, ask ONE simple follow-up question to check understanding.

Keep explanations short (2-3 sentences max per concept). Use lots of examples.
Your student is learning for the first time or struggling with this topic.""",

        "standard": TUTOR_SYSTEM_PROMPT,

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

    system = style_prompts.get(explanation_style, TUTOR_SYSTEM_PROMPT)

    if context:
        system = CONTEXT_TEMPLATE.format(context=context) + system

    messages = [{"role": "system", "content": system}, *history]

    # Try Groq first
    try:
        completion = _get_client().chat.completions.create(
            model=settings.groq_model,
            messages=messages,
            temperature=0.7,
            max_tokens=1024,
        )
        return completion.choices[0].message.content or ""
    except Exception:
        pass

    # Try Ollama if Groq fails
    ollama_reply = _try_ollama(messages)
    if ollama_reply:
        return ollama_reply

    # Fallback to intelligent mock when both APIs are unreachable
    user_message = history[-1]["content"] if history else ""
    return _generate_mock_reply(user_message, context)
