from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin


class PatchStatus(enum.StrEnum):
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    TEST_RUN_PASSED = "test_run_passed"
    TEST_RUN_FAILED = "test_run_failed"
    APPLIED = "applied"


class PatchProposal(UUIDPKMixin, TimestampMixin, Base):
    """A proposed code change. Nothing here is ever applied to disk or executed
    without a human approval event recorded in `approval_events` first --
    enforced in `services/patch/service.py`, not just in the UI.
    """

    __tablename__ = "patch_proposals"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True
    )
    diff_text: Mapped[str] = mapped_column(Text, nullable=False)
    target_files: Mapped[list[str]] = mapped_column(JSON, default=list)
    rationale: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[PatchStatus] = mapped_column(
        Enum(PatchStatus, native_enum=False), default=PatchStatus.PENDING_APPROVAL, index=True
    )
    test_command: Mapped[str | None] = mapped_column(String(500), nullable=True)
    test_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    approval_events: Mapped[list[ApprovalEvent]] = relationship(
        back_populates="patch_proposal", cascade="all, delete-orphan"
    )


class ApprovalDecision(enum.StrEnum):
    APPROVE = "approve"
    REJECT = "reject"


class ApprovalEvent(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "approval_events"

    patch_proposal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("patch_proposals.id", ondelete="CASCADE"), index=True
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[ApprovalDecision] = mapped_column(Enum(ApprovalDecision, native_enum=False))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    patch_proposal: Mapped[PatchProposal] = relationship(back_populates="approval_events")
