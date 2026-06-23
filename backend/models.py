from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func, Table, Column, Integer, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class User(Base):
    """Minimal user record. Auth (Firebase) is deferred — for now we use a
    single dev user. When Firebase is added, store `firebase_uid` here instead
    of managing passwords ourselves."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    study_materials: Mapped[list["StudyMaterial"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200), default="New conversation")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.id",
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"))
    role: Mapped[str] = mapped_column(String(20))  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


class StudyMaterial(Base):
    """Uploaded PDF materials for RAG retrieval."""

    __tablename__ = "study_materials"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    filename: Mapped[str] = mapped_column(String(500))
    qdrant_collection_name: Mapped[str] = mapped_column(
        String(255), unique=True
    )  # e.g., "material_1"
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="study_materials")
    topics: Mapped[list["Topic"]] = relationship(
        secondary="study_material_topics", back_populates="materials"
    )


# Association table for StudyMaterial <-> Topic (many-to-many)
study_material_topics = Table(
    "study_material_topics",
    Base.metadata,
    Column("study_material_id", Integer, ForeignKey("study_materials.id"), primary_key=True),
    Column("topic_id", Integer, ForeignKey("topics.id"), primary_key=True),
)


class Topic(Base):
    """Learning topics extracted from or defined by the user."""

    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("topics.id"), nullable=True
    )  # For hierarchies (Math -> Calculus)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )  # null = system-defined; else user-created
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[user_id], primaryjoin="Topic.user_id == User.id"
    )
    parent: Mapped["Topic | None"] = relationship(
        "Topic",
        remote_side=[id],
        back_populates="children",
        foreign_keys=[parent_id],
    )
    children: Mapped[list["Topic"]] = relationship(
        "Topic", back_populates="parent", remote_side=[parent_id]
    )
    materials: Mapped[list["StudyMaterial"]] = relationship(
        secondary="study_material_topics", back_populates="topics"
    )
    mastery_records: Mapped[list["TopicMastery"]] = relationship(
        back_populates="topic", cascade="all, delete-orphan"
    )


class TopicMastery(Base):
    """Track a student's proficiency per topic."""

    __tablename__ = "topic_mastery"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"))
    mastery_level: Mapped[float] = mapped_column(
        Float, default=0.0
    )  # 0.0-1.0 (unknown -> mastered)
    confidence: Mapped[float] = mapped_column(
        Float, default=0.0
    )  # 0.0-1.0 (certainty of estimate)
    last_practiced: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    num_attempts: Mapped[int] = mapped_column(default=0)
    num_correct: Mapped[int] = mapped_column(default=0)
    easiness_factor: Mapped[float] = mapped_column(
        Float, default=2.5
    )  # SM-2 spaced repetition
    next_review_interval: Mapped[int] = mapped_column(default=1)  # days
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship()
    topic: Mapped["Topic"] = relationship(back_populates="mastery_records")


class Quiz(Base):
    """A quiz session for a specific topic."""

    __tablename__ = "quizzes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"))
    num_questions: Mapped[int] = mapped_column(default=5)
    difficulty: Mapped[str] = mapped_column(String(20))  # "easy", "medium", "hard"
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship()
    topic: Mapped["Topic"] = relationship()
    questions: Mapped[list["Question"]] = relationship(
        back_populates="quiz", cascade="all, delete-orphan"
    )


class Question(Base):
    """A single quiz question."""

    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("quizzes.id"))
    type: Mapped[str] = mapped_column(String(50))  # "multiple_choice", "short_answer", "true_false"
    prompt: Mapped[str] = mapped_column(Text)
    correct_answer: Mapped[str] = mapped_column(Text)
    options: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON for MC
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    quiz: Mapped["Quiz"] = relationship(back_populates="questions")
    responses: Mapped[list["QuestionResponse"]] = relationship(
        back_populates="question", cascade="all, delete-orphan"
    )


class QuestionResponse(Base):
    """A student's response to a quiz question."""

    __tablename__ = "question_responses"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    user_response: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(default=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)  # 0.0-1.0
    answered_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    grading_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    question: Mapped["Question"] = relationship(back_populates="responses")
