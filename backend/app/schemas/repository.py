from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.repository import RepositoryStatus


class RepositoryCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    source_url: str = Field(min_length=1)


class RepositoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    source_url: str
    status: RepositoryStatus
    status_detail: str | None
    commit_sha: str | None
    file_count: int
    symbol_count: int
    chunk_count: int
    created_at: datetime
    updated_at: datetime
