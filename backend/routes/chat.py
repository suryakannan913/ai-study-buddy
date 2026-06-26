import json
import os
import tempfile
import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from database import get_db
from models import (
    Conversation,
    Message,
    StudyMaterial,
    User,
    Topic,
    TopicMastery,
    Quiz,
    Question,
    QuestionResponse,
)
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
from services.topic_service import extract_topics_from_text, infer_topics_from_question
from services.quiz_service import generate_questions_from_context, grade_answer
from services.mastery_service import calculate_adaptive_difficulty
from services.retrieval_service import RetrievalService

router = APIRouter(tags=["chat"])

# Auth is deferred (Phase 3 / Firebase). For now everything runs as one dev user.
DEV_USER_EMAIL = "dev@local"

# Lazy-loaded services
_embedding_service: Optional[EmbeddingService] = None
_qdrant_service: Optional[QdrantService] = None
_retrieval_service: Optional[RetrievalService] = None


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


def get_retrieval_service() -> RetrievalService:
    global _retrieval_service
    if _retrieval_service is None:
        _retrieval_service = RetrievalService()
    return _retrieval_service


def get_current_user(db: Session) -> User:
    user = db.scalar(select(User).where(User.email == DEV_USER_EMAIL))
    if user is None:
        user = User(email=DEV_USER_EMAIL)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def _retrieve_context(user_id: int, query: str, db: Session) -> str:
    """Retrieve relevant context using hybrid search (BM25 + semantic)."""
    materials = list(
        db.scalars(select(StudyMaterial).where(StudyMaterial.user_id == user_id))
    )
    if not materials:
        return ""

    try:
        # Use hybrid retrieval service
        retriever = get_retrieval_service()
        context = retriever.retrieve_context(query, materials, top_k=5)
        return context
    except Exception as e:
        # If retrieval fails, return empty context
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

    # Infer topics from question and get adaptive difficulty
    explanation_style = "standard"  # Default
    available_topics = db.scalars(
        select(Topic).where((Topic.user_id == user.id) | (Topic.user_id.is_(None)))
    )
    topic_names = [t.name for t in available_topics]

    if topic_names:
        inferred_topics = infer_topics_from_question(req.message, topic_names)
        if inferred_topics:
            # Get the top topic and calculate adaptive difficulty
            top_topic_name, _ = inferred_topics[0]
            topic = db.scalar(
                select(Topic).where(Topic.name == top_topic_name)
            )
            if topic:
                _, explanation_style = calculate_adaptive_difficulty(
                    user.id, topic.id, db
                )

    try:
        reply_text = generate_reply(
            history,
            context=context if context else None,
            explanation_style=explanation_style,
        )
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

            # Extract topics from PDF
            extracted_topics = extract_topics_from_text(text)

            # Save metadata to DB
            material = StudyMaterial(
                user_id=user.id,
                filename=file.filename,
                qdrant_collection_name=collection_name,
            )
            db.add(material)
            db.flush()

            # Link topics to material
            for topic_name in extracted_topics:
                # Check if topic exists (system-wide or user-specific)
                existing_topic = db.scalar(
                    select(Topic).where(Topic.name == topic_name).where(
                        (Topic.user_id == user.id) | (Topic.user_id.is_(None))
                    )
                )

                if existing_topic:
                    material.topics.append(existing_topic)
                else:
                    # Create new user-specific topic
                    new_topic = Topic(name=topic_name, user_id=user.id)
                    db.add(new_topic)
                    db.flush()
                    material.topics.append(new_topic)

            db.commit()
            db.refresh(material)

            topic_summary = (
                f" Extracted topics: {', '.join(extracted_topics[:5])}."
                if extracted_topics
                else ""
            )

            return UploadResponse(
                material_id=material.id,
                filename=file.filename,
                message=f"Uploaded and indexed {len(chunks)} chunks.{topic_summary}",
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


@router.get("/topics")
def list_topics(db: Session = Depends(get_db)):
    """List all topics the user has studied."""
    user = get_current_user(db)

    topics = db.scalars(
        select(Topic)
        .where((Topic.user_id == user.id) | (Topic.user_id.is_(None)))
        .order_by(Topic.name)
    )

    result = []
    for topic in topics:
        mastery = db.scalar(
            select(TopicMastery)
            .where(TopicMastery.user_id == user.id)
            .where(TopicMastery.topic_id == topic.id)
        )
        result.append(
            {
                "id": topic.id,
                "name": topic.name,
                "mastery_level": mastery.mastery_level if mastery else 0.0,
                "num_attempts": mastery.num_attempts if mastery else 0,
            }
        )

    return result


@router.post("/quizzes/generate")
def generate_quiz(
    topic_id: int,
    num_questions: int = 5,
    difficulty: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Generate a quiz on a specific topic."""
    user = get_current_user(db)

    # Validate topic belongs to user
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found.")

    # Auto-select difficulty if not provided
    if difficulty is None:
        difficulty, _ = calculate_adaptive_difficulty(user.id, topic_id, db)

    # Retrieve context from materials related to this topic
    contexts = []
    for material in topic.materials:
        try:
            query_embedding = get_embedding_service().embed_text(topic.name)
            qdrant = get_qdrant_service()
            results = qdrant.search(
                collection_name=material.qdrant_collection_name,
                query_vector=query_embedding,
                top_k=5,
            )
            contexts.extend([r["text"] for r in results])
        except Exception:
            pass

    context_text = "\n".join(contexts[:3]) if contexts else ""

    # Generate questions
    try:
        question_dicts = generate_questions_from_context(
            topic.name, context_text, num_questions, difficulty
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Quiz generation error: {e}") from e

    # Save quiz and questions to DB
    quiz = Quiz(
        user_id=user.id,
        topic_id=topic_id,
        num_questions=num_questions,
        difficulty=difficulty,
    )
    db.add(quiz)
    db.flush()

    for q_dict in question_dicts:
        question = Question(
            quiz_id=quiz.id,
            type=q_dict.get("type", "multiple_choice"),
            prompt=q_dict.get("prompt", ""),
            correct_answer=q_dict.get("correct_answer", ""),
            options=(
                json.dumps(q_dict.get("options", []))
                if q_dict.get("options")
                else None
            ),
        )
        db.add(question)

    db.commit()
    db.refresh(quiz)

    return {
        "quiz_id": quiz.id,
        "topic": topic.name,
        "num_questions": num_questions,
        "difficulty": difficulty,
        "questions": [
            {
                "id": q.id,
                "type": q.type,
                "prompt": q.prompt,
                "options": json.loads(q.options) if q.options else None,
            }
            for q in quiz.questions
        ],
    }


@router.get("/quizzes/{quiz_id}")
def get_quiz(quiz_id: int, db: Session = Depends(get_db)):
    """Get a quiz with its questions."""
    user = get_current_user(db)
    quiz = db.get(Quiz, quiz_id)

    if quiz is None or quiz.user_id != user.id:
        raise HTTPException(status_code=404, detail="Quiz not found.")

    return {
        "quiz_id": quiz.id,
        "topic": quiz.topic.name,
        "difficulty": quiz.difficulty,
        "completed": quiz.completed_at is not None,
        "questions": [
            {
                "id": q.id,
                "type": q.type,
                "prompt": q.prompt,
                "options": json.loads(q.options) if q.options else None,
            }
            for q in quiz.questions
        ],
    }


@router.post("/quizzes/{quiz_id}/submit")
def submit_answer(
    quiz_id: int,
    question_id: int,
    user_response: str,
    confidence: float = 0.5,
    db: Session = Depends(get_db),
):
    """Submit an answer to a quiz question and grade it."""
    user = get_current_user(db)

    quiz = db.get(Quiz, quiz_id)
    if quiz is None or quiz.user_id != user.id:
        raise HTTPException(status_code=404, detail="Quiz not found.")

    question = db.get(Question, question_id)
    if question is None or question.quiz_id != quiz_id:
        raise HTTPException(status_code=404, detail="Question not found.")

    # Grade the answer
    is_correct, grading_notes = grade_answer(
        question.type, user_response, question.correct_answer
    )

    # Record the response
    response = QuestionResponse(
        question_id=question_id,
        user_response=user_response,
        is_correct=is_correct,
        confidence=min(1.0, max(0.0, confidence)),
        grading_notes=grading_notes,
    )
    db.add(response)
    db.flush()

    # Update topic mastery
    mastery = db.scalar(
        select(TopicMastery)
        .where(TopicMastery.user_id == user.id)
        .where(TopicMastery.topic_id == quiz.topic_id)
    )

    if not mastery:
        mastery = TopicMastery(
            user_id=user.id,
            topic_id=quiz.topic_id,
            num_attempts=0,
            num_correct=0,
        )
        db.add(mastery)
        db.flush()

    mastery.num_attempts += 1
    if is_correct:
        mastery.num_correct += 1

    # Calculate mastery level from last 10 attempts
    recent_responses = db.scalars(
        select(QuestionResponse)
        .join(Question)
        .join(Quiz)
        .where(Quiz.user_id == user.id)
        .where(Quiz.topic_id == quiz.topic_id)
        .order_by(QuestionResponse.answered_at.desc())
        .limit(10)
    )

    recent_list = list(recent_responses)
    if recent_list:
        correct_count = sum(1 for r in recent_list if r.is_correct)
        mastery.mastery_level = correct_count / len(recent_list)
    else:
        mastery.mastery_level = 1.0 if is_correct else 0.0

    mastery.last_practiced = datetime.utcnow()
    db.commit()

    # Check if quiz is complete (all questions answered)
    answered_count = db.scalar(
        select(func.count(QuestionResponse.id))
        .select_from(QuestionResponse)
        .join(Question)
        .where(Question.quiz_id == quiz_id)
    )

    quiz_complete = answered_count == len(quiz.questions)
    if quiz_complete:
        quiz.completed_at = datetime.utcnow()
        db.commit()

    return {
        "is_correct": is_correct,
        "correct_answer": question.correct_answer,
        "explanation": grading_notes or "",
        "mastery_level": round(mastery.mastery_level, 2),
        "quiz_complete": quiz_complete,
    }


@router.get("/quizzes")
def list_quizzes(db: Session = Depends(get_db)):
    """List user's recent quizzes."""
    user = get_current_user(db)

    quizzes = db.scalars(
        select(Quiz)
        .where(Quiz.user_id == user.id)
        .order_by(Quiz.created_at.desc())
        .limit(20)
    )

    return [
        {
            "quiz_id": q.id,
            "topic": q.topic.name,
            "difficulty": q.difficulty,
            "num_questions": q.num_questions,
            "completed": q.completed_at is not None,
            "created_at": q.created_at.isoformat(),
        }
        for q in quizzes
    ]
