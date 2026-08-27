from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin


class IdempotencyKey(Base):
    """Records the outcome of a request made with an `Idempotency-Key` header so
    a retried request (client timeout, double-click, at-least-once delivery)
    replays the original response instead of re-executing a side effect such
    as creating a second repository ingestion job.
    """

    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EvalRun(UUIDPKMixin, TimestampMixin, Base):
    """A pointer row into MLflow for an evaluation run triggered from the API
    or CI, so eval history can be queried without hitting the MLflow server.
    """

    __tablename__ = "eval_runs"

    run_type: Mapped[str] = mapped_column(String(64), nullable=False)
    mlflow_run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    repository_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("repositories.id", ondelete="SET NULL"), nullable=True
    )
    metrics: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
