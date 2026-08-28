from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_owned_repository
from app.db.session import get_db
from app.models.repository import Repository, RepositoryStatus
from app.models.user import User
from app.schemas.repository import RepositoryCreateRequest, RepositoryResponse
from app.services.idempotency import get_replay_or_reserve, record_response
from app.workers.tasks import run_ingestion_task

router = APIRouter(prefix="/repositories", tags=["repositories"])


@router.post("", response_model=RepositoryResponse, status_code=202)
async def create_repository(
    body: RepositoryCreateRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Repository | dict[str, object]:
    request_payload = body.model_dump()

    if idempotency_key:
        replay = await get_replay_or_reserve(
            db, key=idempotency_key, user_id=current_user.id, request_payload=request_payload
        )
        if replay is not None:
            # A retried request (client timeout, double-click) -- return the
            # original response instead of enqueueing a second ingestion job.
            return replay.body

    repository = Repository(
        owner_id=current_user.id,
        name=body.name,
        source_url=body.source_url,
        status=RepositoryStatus.PENDING,
    )
    db.add(repository)
    await db.commit()
    await db.refresh(repository)

    run_ingestion_task.delay(str(repository.id))

    if idempotency_key:
        body_json = json.loads(RepositoryResponse.model_validate(repository).model_dump_json())
        await record_response(
            db,
            key=idempotency_key,
            user_id=current_user.id,
            request_payload=request_payload,
            status_code=202,
            body=body_json,
        )

    return repository


@router.get("", response_model=list[RepositoryResponse])
async def list_repositories(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[Repository]:
    result = await db.execute(
        select(Repository)
        .where(Repository.owner_id == current_user.id)
        .order_by(Repository.created_at.desc())
    )
    return list(result.scalars())


@router.get("/{repository_id}", response_model=RepositoryResponse)
async def get_repository(repository: Repository = Depends(get_owned_repository)) -> Repository:
    return repository
