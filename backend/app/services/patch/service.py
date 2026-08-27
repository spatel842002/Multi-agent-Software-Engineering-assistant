"""The only code path that can move a `PatchProposal` past
`PENDING_APPROVAL`. Every call requires an authenticated actor and records an
`ApprovalEvent`; on approval, the diff is applied and tested in an isolated
sandbox copy (`sandbox.py`) -- never against the canonical ingested clone.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.core.telemetry import PATCH_APPROVAL_DECISIONS
from app.models.patch import ApprovalDecision, ApprovalEvent, PatchProposal, PatchStatus
from app.models.repository import Repository
from app.services.patch.sandbox import run_patch_in_sandbox


async def decide_patch_proposal(
    db: AsyncSession,
    *,
    patch_proposal_id: uuid.UUID,
    actor_id: uuid.UUID,
    decision: ApprovalDecision,
    reason: str | None = None,
) -> PatchProposal:
    proposal = await db.get(PatchProposal, patch_proposal_id)
    if proposal is None:
        raise NotFoundError("Patch proposal not found.")
    if proposal.status != PatchStatus.PENDING_APPROVAL:
        raise ConflictError(f"Patch proposal is '{proposal.status.value}', not awaiting approval.")

    db.add(ApprovalEvent(patch_proposal_id=proposal.id, actor_id=actor_id, decision=decision, reason=reason))
    PATCH_APPROVAL_DECISIONS.labels(decision=decision.value).inc()

    if decision == ApprovalDecision.REJECT:
        proposal.status = PatchStatus.REJECTED
        proposal.decided_by = actor_id
        await db.commit()
        await db.refresh(proposal)
        return proposal

    proposal.status = PatchStatus.APPROVED
    proposal.decided_by = actor_id
    await db.flush()

    repository = await db.get(Repository, proposal.repository_id)
    if repository is None or not repository.local_path:
        raise ValidationAppError("Repository has no local clone to apply this patch against.")

    result = run_patch_in_sandbox(
        source_repo_path=Path(repository.local_path),
        diff_text=proposal.diff_text,
        test_command=proposal.test_command,
    )

    if not result.apply_succeeded:
        proposal.status = PatchStatus.TEST_RUN_FAILED
        proposal.test_output = f"git apply failed:\n{result.apply_output}"
    elif not result.test_ran:
        # Applied cleanly but no test command was proposed to validate it.
        proposal.status = PatchStatus.APPLIED
        proposal.test_output = result.apply_output
    elif result.test_succeeded:
        proposal.status = PatchStatus.TEST_RUN_PASSED
        proposal.test_output = result.test_output
    else:
        proposal.status = PatchStatus.TEST_RUN_FAILED
        proposal.test_output = result.test_output

    await db.commit()
    await db.refresh(proposal)
    return proposal
