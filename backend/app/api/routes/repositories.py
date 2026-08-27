from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_owned_repository
from app.db.session import get_db
from app.models.repository import Repository, RepositoryStatus
from app.models.user import User
from app.schemas.repository import RepositoryCreateRequest, RepositoryResponse
from app.workers.tasks import run_ingestion_task

router = APIRouter(prefix="/repositories", tags=["repositories"])


@router.post("", response_model=RepositoryResponse, status_code=202)
async def create_repository(
    body: RepositoryCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Repository:
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
