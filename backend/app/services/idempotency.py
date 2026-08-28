"""Idempotency-Key support for side-effecting POST endpoints.

A client that retries a request after a timeout (or double-clicks a submit
button) should get back the *original* response, not trigger a second
repository ingestion job. The client opts in by sending an `Idempotency-Key`
header; without one, a request is never deduplicated (existing behavior is
unchanged for callers that don't send it).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.models.misc import IdempotencyKey


@dataclass(frozen=True)
class IdempotentReplay:
    status_code: int
    body: dict[str, object]


def _fingerprint(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def get_replay_or_reserve(
    db: AsyncSession, *, key: str, user_id: uuid.UUID, request_payload: dict[str, object]
) -> IdempotentReplay | None:
    """Returns the original response if `key` was already used for an
    identical request (a safe replay). Raises `ConflictError` if `key` was
    already used for a *different* request body -- reusing a key across
    different logical requests is a client bug, not something to silently
    paper over. Returns `None` when this is a genuinely new request, which
    the caller must follow up by calling `record_response` once it has one.
    """
    fingerprint = _fingerprint(request_payload)
    existing = await db.get(IdempotencyKey, key)
    if existing is None:
        return None

    if existing.request_fingerprint != fingerprint:
        raise ConflictError("This Idempotency-Key was already used for a different request.")

    return IdempotentReplay(status_code=existing.response_status_code, body=existing.response_body)


async def record_response(
    db: AsyncSession,
    *,
    key: str,
    user_id: uuid.UUID,
    request_payload: dict[str, object],
    status_code: int,
    body: dict[str, object],
) -> None:
    db.add(
        IdempotencyKey(
            key=key,
            user_id=user_id,
            request_fingerprint=_fingerprint(request_payload),
            response_status_code=status_code,
            response_body=body,
            created_at=datetime.now(UTC),
        )
    )
    await db.commit()
