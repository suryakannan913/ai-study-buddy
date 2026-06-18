from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from models import Conversation, Message, User
from schemas import ChatRequest, ChatResponse, ConversationOut, MessageOut
from services.llm_service import generate_reply

router = APIRouter(tags=["chat"])

# Auth is deferred (Phase 3 / Firebase). For now everything runs as one dev user.
DEV_USER_EMAIL = "dev@local"


def get_current_user(db: Session) -> User:
    user = db.scalar(select(User).where(User.email == DEV_USER_EMAIL))
    if user is None:
        user = User(email=DEV_USER_EMAIL)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


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

    try:
        reply_text = generate_reply(history)
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
