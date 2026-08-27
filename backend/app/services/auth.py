"""Registration, login, and refresh-token rotation.

Refresh-token reuse detection: a refresh token is single-use. Rotating it
marks the old row `revoked_at` and links `replaced_by_id` to the new row. If
a caller ever presents a token whose row is already revoked, that means the
token was reused (e.g. stolen and used after the legitimate client already
rotated it) -- in that case, the entire chain from that token forward is
revoked and the request is rejected, forcing re-authentication.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models.user import RefreshToken, User


async def register_user(db: AsyncSession, email: str, password: str) -> User:
    existing = await db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise ConflictError("An account with this email already exists.")
    user = User(email=email, hashed_password=hash_password(password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _issue_token_pair(
    db: AsyncSession, user: User, replaces: RefreshToken | None = None
) -> tuple[str, str]:
    access_token = create_access_token(user.id)
    opaque_refresh, refresh_hash, expires_at = generate_refresh_token()
    row = RefreshToken(
        user_id=user.id,
        token_hash=refresh_hash,
        expires_at=expires_at,
        created_at=datetime.now(UTC),
    )
    db.add(row)
    await db.flush()
    if replaces is not None:
        replaces.revoked_at = datetime.now(UTC)
        replaces.replaced_by_id = row.id
    await db.commit()
    return access_token, opaque_refresh


async def login_user(db: AsyncSession, email: str, password: str) -> tuple[User, str, str]:
    user = await db.scalar(select(User).where(User.email == email))
    if user is None or not user.is_active or not verify_password(password, user.hashed_password):
        raise UnauthorizedError("Invalid email or password.")
    access_token, refresh_token = await _issue_token_pair(db, user)
    return user, access_token, refresh_token


async def _revoke_chain_from(db: AsyncSession, token: RefreshToken) -> None:
    now = datetime.now(UTC)
    current: RefreshToken | None = token
    seen: set[uuid.UUID] = set()
    while current is not None and current.id not in seen:
        seen.add(current.id)
        current.revoked_at = current.revoked_at or now
        if current.replaced_by_id is None:
            break
        current = await db.get(RefreshToken, current.replaced_by_id)
    await db.commit()


async def refresh_tokens(db: AsyncSession, opaque_refresh_token: str) -> tuple[User, str, str]:
    token_hash = hash_refresh_token(opaque_refresh_token)
    row = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if row is None:
        raise UnauthorizedError("Invalid refresh token.")

    now = datetime.now(UTC)
    if row.expires_at.replace(tzinfo=UTC) < now:
        raise UnauthorizedError("Refresh token expired.")

    if row.revoked_at is not None:
        # Reuse of an already-rotated token: treat as compromise, kill the chain.
        await _revoke_chain_from(db, row)
        raise UnauthorizedError(
            "Refresh token has already been used. All sessions in this chain were revoked."
        )

    user = await db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("Account is inactive.")

    access_token, new_refresh = await _issue_token_pair(db, user, replaces=row)
    return user, access_token, new_refresh
