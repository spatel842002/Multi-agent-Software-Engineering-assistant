from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.patch import PatchProposal
from app.models.user import User
from app.schemas.patch import PatchDecisionRequest, PatchProposalResponse
from app.services.patch.service import decide_patch_proposal

router = APIRouter(prefix="/patch-proposals", tags=["patches"])


async def _get_owned_proposal(
    patch_proposal_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PatchProposal:
    proposal = await db.get(PatchProposal, patch_proposal_id)
    if proposal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patch proposal not found.")

    from app.models.repository import Repository

    repository = await db.get(Repository, proposal.repository_id)
    if repository is None or repository.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patch proposal not found.")
    return proposal


@router.get("/{patch_proposal_id}", response_model=PatchProposalResponse)
async def get_patch_proposal(proposal: PatchProposal = Depends(_get_owned_proposal)) -> PatchProposal:
    return proposal


@router.post("/{patch_proposal_id}/decision", response_model=PatchProposalResponse)
async def decide_patch(
    body: PatchDecisionRequest,
    proposal: PatchProposal = Depends(_get_owned_proposal),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PatchProposal:
    return await decide_patch_proposal(
        db,
        patch_proposal_id=proposal.id,
        actor_id=current_user.id,
        decision=body.decision,
        reason=body.reason,
    )
