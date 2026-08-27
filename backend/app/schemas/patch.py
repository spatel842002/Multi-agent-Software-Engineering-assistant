from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.patch import ApprovalDecision, PatchStatus


class PatchDecisionRequest(BaseModel):
    decision: ApprovalDecision
    reason: str | None = Field(default=None, max_length=2000)


class PatchProposalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    repository_id: uuid.UUID
    conversation_id: uuid.UUID
    diff_text: str
    target_files: list[str]
    rationale: str
    status: PatchStatus
    test_command: str | None
    test_output: str | None
    decided_by: uuid.UUID | None
    decided_at: datetime | None
    created_at: datetime
