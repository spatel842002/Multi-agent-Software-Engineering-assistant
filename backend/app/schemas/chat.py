from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class BugInvestigationRequest(BaseModel):
    bug_description: str = Field(min_length=1, max_length=4000)


class PatchProposalRequest(BaseModel):
    task_description: str = Field(min_length=1, max_length=4000)


class CitationResponse(BaseModel):
    file_path: str
    start_line: int
    end_line: int


class WorkflowResponse(BaseModel):
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    answer: str
    citations: list[CitationResponse]
    prompt_version: str
    latency_ms: int
    patch_proposal_id: uuid.UUID | None = None
