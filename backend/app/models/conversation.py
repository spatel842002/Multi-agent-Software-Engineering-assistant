from __future__ import annotations

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin


class WorkflowType(enum.StrEnum):
    REPO_QA = "repo_qa"
    BUG_INVESTIGATION = "bug_investigation"
    PATCH_PROPOSAL = "patch_proposal"


class Conversation(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "conversations"

    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True
    )
    workflow_type: Mapped[WorkflowType] = mapped_column(Enum(WorkflowType, native_enum=False), index=True)
    title: Mapped[str] = mapped_column(String(500), default="")

    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class MessageRole(enum.StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole, native_enum=False))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    citations: Mapped[list[Citation]] = relationship(back_populates="message", cascade="all, delete-orphan")


class Citation(UUIDPKMixin, Base):
    """Evidence backing an assistant answer: a real file/line span the answer drew from.

    Every assistant message produced by the retrieval-grounded workflows must
    resolve to at least one Citation whose (file_path, start_line, end_line)
    exists in the ingested repository -- this is what "groundedness" means
    and is what the MLflow citation-accuracy eval checks.
    """

    __tablename__ = "citations"

    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), index=True)
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chunks.id", ondelete="SET NULL"), nullable=True
    )
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)

    message: Mapped[Message] = relationship(back_populates="citations")
