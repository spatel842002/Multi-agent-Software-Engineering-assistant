from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    RefreshRequest,
    TokenPairResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
@limiter.limit("10/minute")
async def register(request: Request, body: UserRegisterRequest, db: AsyncSession = Depends(get_db)) -> User:
    return await auth_service.register_user(db, body.email, body.password)


@router.post("/login", response_model=TokenPairResponse)
@limiter.limit("10/minute")
async def login(
    request: Request, body: UserLoginRequest, db: AsyncSession = Depends(get_db)
) -> TokenPairResponse:
    _, access, refresh = await auth_service.login_user(db, body.email, body.password)
    return TokenPairResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenPairResponse)
@limiter.limit("30/minute")
async def refresh(
    request: Request, body: RefreshRequest, db: AsyncSession = Depends(get_db)
) -> TokenPairResponse:
    _, access, refresh_token = await auth_service.refresh_tokens(db, body.refresh_token)
    return TokenPairResponse(access_token=access, refresh_token=refresh_token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
