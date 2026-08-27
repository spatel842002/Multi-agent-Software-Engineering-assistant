from __future__ import annotations

import uuid

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.repository import Repository
from app.models.user import User

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials.",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _CREDENTIALS_EXCEPTION
    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_access_token(token)
        user_id = uuid.UUID(str(payload["sub"]))
    except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
        raise _CREDENTIALS_EXCEPTION from exc

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise _CREDENTIALS_EXCEPTION
    return user


async def get_owned_repository(
    repository_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Repository:
    """Owner-scoped repository lookup. Returns 404 (not 403) when the
    repository exists but belongs to someone else, so an authenticated user
    can't distinguish "not found" from "not yours" by response code -- that
    distinction would leak which repository IDs exist.
    """
    repository = await db.get(Repository, repository_id)
    if repository is None or repository.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found.")
    return repository


DbSession = AsyncSession
