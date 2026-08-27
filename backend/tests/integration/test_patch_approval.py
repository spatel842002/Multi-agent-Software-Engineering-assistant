from __future__ import annotations

import pytest

from app.core.exceptions import ConflictError
from app.models.patch import ApprovalDecision, PatchProposal, PatchStatus
from app.models.repository import Repository, RepositoryStatus
from app.models.user import User
from app.services.patch.service import decide_patch_proposal

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def approver(db_session):
    user = User(email="approver@example.com", hashed_password="x")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def repository_with_local_clone(db_session, approver, tmp_path):
    repo_dir = tmp_path / "clone"
    repo_dir.mkdir()
    (repo_dir / "greet.py").write_text('print("hello")\n')

    repo = Repository(
        owner_id=approver.id,
        name="greet-repo",
        source_url="https://example.com/greet.git",
        status=RepositoryStatus.READY,
        local_path=str(repo_dir),
    )
    db_session.add(repo)
    await db_session.commit()
    await db_session.refresh(repo)
    return repo


@pytest.fixture
async def pending_proposal(db_session, repository_with_local_clone):
    from app.models.conversation import Conversation, WorkflowType

    conversation = Conversation(
        owner_id=repository_with_local_clone.owner_id,
        repository_id=repository_with_local_clone.id,
        workflow_type=WorkflowType.PATCH_PROPOSAL,
    )
    db_session.add(conversation)
    await db_session.flush()

    diff = '--- a/greet.py\n+++ b/greet.py\n@@ -1 +1 @@\n-print("hello")\n+print("hello world")\n'
    proposal = PatchProposal(
        conversation_id=conversation.id,
        repository_id=repository_with_local_clone.id,
        diff_text=diff,
        target_files=["greet.py"],
        test_command='python -c "print(1)"',
    )
    db_session.add(proposal)
    await db_session.commit()
    await db_session.refresh(proposal)
    return proposal


async def test_approve_applies_and_tests_in_sandbox(
    db_session, approver, pending_proposal, monkeypatch, tmp_path
):
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path / "workspace"))
    from app.core.config import get_settings

    get_settings.cache_clear()

    result = await decide_patch_proposal(
        db_session,
        patch_proposal_id=pending_proposal.id,
        actor_id=approver.id,
        decision=ApprovalDecision.APPROVE,
    )

    assert result.status == PatchStatus.TEST_RUN_PASSED
    assert result.decided_by == approver.id

    get_settings.cache_clear()


async def test_reject_never_touches_the_filesystem(db_session, approver, pending_proposal):
    result = await decide_patch_proposal(
        db_session,
        patch_proposal_id=pending_proposal.id,
        actor_id=approver.id,
        decision=ApprovalDecision.REJECT,
        reason="Not the right fix.",
    )
    assert result.status == PatchStatus.REJECTED


async def test_deciding_an_already_decided_proposal_conflicts(db_session, approver, pending_proposal):
    await decide_patch_proposal(
        db_session,
        patch_proposal_id=pending_proposal.id,
        actor_id=approver.id,
        decision=ApprovalDecision.REJECT,
    )
    with pytest.raises(ConflictError):
        await decide_patch_proposal(
            db_session,
            patch_proposal_id=pending_proposal.id,
            actor_id=approver.id,
            decision=ApprovalDecision.APPROVE,
        )
