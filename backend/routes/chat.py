import os
import tempfile
import time
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from models import Conversation, Message, StudyMaterial, User
from schemas import (
    ChatRequest,
    ChatResponse,
    ConversationOut,
    MessageOut,
    StudyMaterialOut,
    UploadResponse,
)
from services.embedding_service import EmbeddingService
from services.llm_service import generate_reply
from services.pdf_service import chunk_text, extract_text_from_pdf
from services.qdrant_service import QdrantService

router = APIRouter(tags=["chat"])

# Auth is deferred (Phase 3 / Firebase). For now everything runs as one dev user.
DEV_USER_EMAIL = "dev@local"

# Lazy-loaded services
_embedding_service: EmbeddingService | None = None
_qdrant_service: QdrantService | None = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


def get_qdrant_service() -> QdrantService:
    global _qdrant_service
    if _qdrant_service is None:
        _qdrant_service = QdrantService()
    return _qdrant_service


def get_current_user(db: Session) -> User:
    user = db.scalar(select(User).where(User.email == DEV_USER_EMAIL))
    if user is None:
        user = User(email=DEV_USER_EMAIL)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def _retrieve_context(user_id: int, query: str, db: Session) -> str:
    """Retrieve relevant context from user's study materials."""
    materials = db.scalars(
        select(StudyMaterial).where(StudyMaterial.user_id == user_id)
    )
    if not materials:
        return ""

    try:
        query_embedding = get_embedding_service().embed_text(query)
        qdrant = get_qdrant_service()
        contexts = []

        for material in materials:
            try:
                results = qdrant.search(
                    collection_name=material.qdrant_collection_name,
                    query_vector=query_embedding,
                    top_k=3,
                )
                contexts.extend([r["text"] for r in results])
            except Exception:
                # Collection may not exist or be inaccessible
                pass

        return "\n".join(contexts[:5])  # top 5 results
    except Exception:
        # If embedding service fails (e.g., model download), return empty context
        return ""


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    user = get_current_user(db)

    if req.conversation_id is not None:
        conversation = db.get(Conversation, req.conversation_id)
        if conversation is None or conversation.user_id != user.id:
            raise HTTPException(status_code=404, detail="Conversation not found.")
    else:
        title = req.message.strip()[:60]
        conversation = Conversation(user_id=user.id, title=title)
        db.add(conversation)
        db.flush()

    db.add(Message(conversation_id=conversation.id, role="user", content=req.message))
    db.flush()

    history = [
        {"role": m.role, "content": m.content} for m in conversation.messages
    ]

    context = _retrieve_context(user.id, req.message, db)

    try:
        reply_text = generate_reply(history, context=context if context else None)
    except Exception as exc:  # surface a clean error to the client
        raise HTTPException(status_code=502, detail=f"LLM error: {exc}") from exc

    assistant_msg = Message(
        conversation_id=conversation.id, role="assistant", content=reply_text
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    return ChatResponse(
        response=reply_text,
        conversation_id=conversation.id,
        message_id=assistant_msg.id,
    )


@router.post("/upload", response_model=UploadResponse)
async def upload_material(
    file: UploadFile = File(...), db: Session = Depends(get_db)
) -> UploadResponse:
    """Upload and process a PDF for RAG."""
    if not file.filename or not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF.")

    user = get_current_user(db)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        try:
            content = await file.read()
            tmp.write(content)
            tmp.flush()

            # Extract and chunk
            text = extract_text_from_pdf(tmp.name)
            chunks = chunk_text(text)

            if not chunks:
                raise HTTPException(
                    status_code=400, detail="Could not extract text from PDF."
                )

            # Embed chunks
            try:
                embeddings = get_embedding_service().embed_texts(chunks)
            except Exception as e:
                raise HTTPException(
                    status_code=502, detail=f"Embedding service error: {e}"
                ) from e

            # Create Qdrant collection with unique name (user_id + filename + timestamp)
            timestamp = int(time.time() * 1000)  # milliseconds for uniqueness
            collection_name = f"m{user.id}_{int(timestamp)}"
            try:
                qdrant = get_qdrant_service()
                qdrant.create_collection(collection_name)

                # Upsert vectors
                points = [
                    {
                        "id": i,
                        "vector": emb,
                        "payload": {"text": chunk},
                    }
                    for i, (chunk, emb) in enumerate(zip(chunks, embeddings))
                ]
                qdrant.upsert_vectors(collection_name, points)
            except Exception as e:
                raise HTTPException(
                    status_code=502, detail=f"Vector DB error: {e}"
                ) from e

            # Save metadata to DB
            material = StudyMaterial(
                user_id=user.id,
                filename=file.filename,
                qdrant_collection_name=collection_name,
            )
            db.add(material)
            db.commit()
            db.refresh(material)

            return UploadResponse(
                material_id=material.id,
                filename=file.filename,
                message=f"Uploaded and indexed {len(chunks)} chunks.",
            )
        finally:
            os.unlink(tmp.name)


@router.get("/materials", response_model=list[StudyMaterialOut])
def list_materials(db: Session = Depends(get_db)) -> list[StudyMaterial]:
    """List user's uploaded study materials."""
    user = get_current_user(db)
    return list(
        db.scalars(
            select(StudyMaterial)
            .where(StudyMaterial.user_id == user.id)
            .order_by(StudyMaterial.created_at.desc())
        )
    )


@router.delete("/materials/{material_id}")
def delete_material(material_id: int, db: Session = Depends(get_db)):
    """Delete a study material and its Qdrant collection."""
    user = get_current_user(db)
    material = db.get(StudyMaterial, material_id)

    if material is None or material.user_id != user.id:
        raise HTTPException(status_code=404, detail="Material not found.")

    try:
        qdrant_service.delete_collection(material.qdrant_collection_name)
    except Exception:
        pass  # Collection may already be deleted

    db.delete(material)
    db.commit()

    return {"message": "Material deleted."}


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(db: Session = Depends(get_db)) -> list[Conversation]:
    user = get_current_user(db)
    return list(
        db.scalars(
            select(Conversation)
            .where(Conversation.user_id == user.id)
            .order_by(Conversation.updated_at.desc())
        )
    )


@router.get("/conversations/{conversation_id}", response_model=list[MessageOut])
def get_conversation(
    conversation_id: int, db: Session = Depends(get_db)
) -> list[Message]:
    user = get_current_user(db)
    conversation = db.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return list(conversation.messages)
