#!/usr/bin/env python
"""Reproducible evaluation runner for the three agent workflows.

Default mode (`--provider fake`, the CI/reproducibility default) uses the
deterministic fake LLM/embedding providers against the checked-in fixture
repository, so `python evals/run_evals.py` produces the same numbers on any
machine with no network access and no external services -- it evaluates the
*retrieval and citation-grounding plumbing*, not real answer quality.

`--provider ollama` runs the same golden set against a real local Ollama
server for real answer/patch quality evidence; those numbers depend on the
model, prompt, and hardware, and are logged with that context attached (see
`docs/architecture/retrieval-evaluation-methodology.md`).

Usage:
    python evals/run_evals.py --provider fake
    python evals/run_evals.py --provider ollama
"""
from __future__ import annotations

import argparse
import asyncio
import difflib
import json
import os
import shutil
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

FIXTURE_REPO = BACKEND_ROOT / "tests" / "fixtures" / "sample_repo"
REPORT_DIR = Path(__file__).resolve().parent.parent / "docs" / "benchmarks"


def _build_fake_patch_diff() -> str:
    """Builds a real, guaranteed-`git apply`-able unified diff against the
    actual fixture file (via `difflib`, not hand-typed line numbers that
    could silently drift out of sync with the fixture), so the fake-provider
    eval's `patch_task_success` metric reflects the sandbox/apply plumbing
    rather than a fake response's own internal correctness.
    """
    original_path = FIXTURE_REPO / "calculator.py"
    original_lines = original_path.read_text().splitlines(keepends=True)
    modified_lines = []
    for line in original_lines:
        if line.strip() == "return a / b":
            indent = line[: len(line) - len(line.lstrip())]
            modified_lines.append(f'{indent}if b == 0:\n')
            modified_lines.append(f'{indent}    raise ZeroDivisionError("b must not be zero")\n')
        modified_lines.append(line)
    diff = difflib.unified_diff(
        original_lines, modified_lines, fromfile="a/calculator.py", tofile="b/calculator.py"
    )
    return "".join(diff)


def _bootstrap_env(workspace_root: Path) -> None:
    os.environ.setdefault("JWT_SECRET_KEY", "evals-only-not-a-real-secret-0123456789")
    os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{workspace_root / 'evals.sqlite3'}")
    os.environ.setdefault("WORKSPACE_ROOT", str(workspace_root))
    # A plain `file:./mlruns` URI hits MLflow 3.x's filesystem-store
    # deprecation guard when used directly (as opposed to through a real
    # `mlflow server`, which docker-compose's `mlflow` service runs and which
    # doesn't hit this); sqlite is the currently-recommended local backend.
    os.environ.setdefault("MLFLOW_TRACKING_URI", f"sqlite:///{workspace_root / 'mlflow.db'}")


async def _run(provider_name: str) -> tuple[dict, Path]:
    from golden_dataset import BUG_INVESTIGATION_GOLDEN_SET, PATCH_GOLDEN_SET, QA_GOLDEN_SET
    from metrics import (
        PatchEvalItemResult,
        QAEvalItemResult,
        citation_accuracy,
        groundedness,
        latency,
        patch_task_success,
        qa_task_success,
        retrieval_quality,
    )

    workspace_root = Path(tempfile.mkdtemp(prefix="masea-evals-"))
    _bootstrap_env(workspace_root)

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    import app.models  # noqa: F401 - populate Base.metadata
    from app.db.base import Base
    from app.models.repository import Repository, RepositoryStatus
    from app.models.user import User
    from app.services.agents.workflows import run_bug_investigation, run_patch_proposal, run_repo_qa
    from app.services.ingestion.service import index_repository_files
    from app.services.patch.sandbox import run_patch_in_sandbox
    from app.services.retrieval.hybrid import hybrid_retrieve

    if provider_name == "ollama":
        from app.services.llm.providers import OllamaChatProvider
        from app.services.retrieval.embeddings import OllamaEmbeddingProvider

        embedder = OllamaEmbeddingProvider()
        chat_provider = OllamaChatProvider()
        patch_chat_provider = chat_provider
    else:
        from app.services.llm.providers import FakeChatProvider
        from app.services.retrieval.embeddings import FakeEmbeddingProvider

        embedder = FakeEmbeddingProvider(dimensions=64)

        def _grounded_fake_responder(messages) -> str:  # noqa: ANN001
            return "This is a deterministic fake answer for evaluation plumbing.\nCitations: [1]"

        chat_provider = FakeChatProvider(responder=_grounded_fake_responder)

        def _patch_fake_responder(messages) -> str:  # noqa: ANN001
            return f"```diff\n{_build_fake_patch_diff()}```\n\nTest command: echo ok\n\nCitations: [1]"

        patch_chat_provider = FakeChatProvider(responder=_patch_fake_responder)

    from app.services.retrieval.vector_store import InMemoryVectorStore

    vector_store = InMemoryVectorStore()

    db_engine = create_async_engine(
        f"sqlite+aiosqlite:///{workspace_root / 'evals.sqlite3'}", connect_args={"check_same_thread": False}
    )
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(bind=db_engine, expire_on_commit=False)

    async with session_factory() as db:
        user = User(email="evals@example.com", hashed_password="x")
        db.add(user)
        await db.flush()

        repo = Repository(
            owner_id=user.id,
            name="sample-repo",
            source_url="https://example.com/sample-repo.git",
            status=RepositoryStatus.INDEXING,
        )
        db.add(repo)
        await db.commit()
        await db.refresh(repo)

        # The sandbox applies diffs against a real on-disk clone; copy the
        # fixture repo into the workspace so it has one, matching what a real
        # ingested repository looks like on disk.
        local_repo_path = workspace_root / "sample-repo"
        shutil.copytree(FIXTURE_REPO, local_repo_path)
        repo.local_path = str(local_repo_path)

        await index_repository_files(
            db, repository=repo, root_path=local_repo_path, embedder=embedder, vector_store=vector_store
        )
        repo.status = RepositoryStatus.READY
        await db.commit()

        qa_results: list[QAEvalItemResult] = []
        for item in QA_GOLDEN_SET:
            hits = await hybrid_retrieve(
                db, repository_id=repo.id, query=item.question, embedder=embedder, vector_store=vector_store
            )
            retrieved_files = [h.chunk.file_path for h in hits]

            start = time.perf_counter()
            result = await run_repo_qa(
                db,
                owner_id=user.id,
                repository_id=repo.id,
                question=item.question,
                embedder=embedder,
                vector_store=vector_store,
                chat_provider=chat_provider,
            )
            elapsed_ms = int((time.perf_counter() - start) * 1000)

            qa_results.append(
                QAEvalItemResult(
                    question=item.question,
                    expected_file=item.expected_file,
                    retrieved_files=retrieved_files,
                    answer=result.answer,
                    cited_files=[c.file_path for c in result.citations],
                    latency_ms=elapsed_ms,
                    all_citations_resolved=all(c.chunk_id is not None for c in result.citations),
                )
            )

        for bitem in BUG_INVESTIGATION_GOLDEN_SET:
            hits = await hybrid_retrieve(
                db, repository_id=repo.id, query=bitem.question, embedder=embedder, vector_store=vector_store
            )
            retrieved_files = [h.chunk.file_path for h in hits]

            start = time.perf_counter()
            result = await run_bug_investigation(
                db,
                owner_id=user.id,
                repository_id=repo.id,
                bug_description=bitem.question,
                embedder=embedder,
                vector_store=vector_store,
                chat_provider=chat_provider,
            )
            elapsed_ms = int((time.perf_counter() - start) * 1000)

            qa_results.append(
                QAEvalItemResult(
                    question=bitem.question,
                    expected_file=bitem.expected_file,
                    retrieved_files=retrieved_files,
                    answer=result.answer,
                    cited_files=[c.file_path for c in result.citations],
                    latency_ms=elapsed_ms,
                    all_citations_resolved=all(c.chunk_id is not None for c in result.citations),
                )
            )

        patch_results: list[PatchEvalItemResult] = []
        for pitem in PATCH_GOLDEN_SET:
            start = time.perf_counter()
            presult = await run_patch_proposal(
                db,
                owner_id=user.id,
                repository_id=repo.id,
                task_description=pitem.task_description,
                embedder=embedder,
                vector_store=vector_store,
                chat_provider=patch_chat_provider,
            )
            elapsed_ms = int((time.perf_counter() - start) * 1000)

            from sqlalchemy import select

            from app.models.patch import PatchProposal

            proposal = (
                await db.execute(select(PatchProposal).where(PatchProposal.id == presult.patch_proposal_id))
            ).scalar_one()

            sandbox_result = run_patch_in_sandbox(
                source_repo_path=local_repo_path, diff_text=proposal.diff_text, test_command=None
            )

            patch_results.append(
                PatchEvalItemResult(
                    task_description=pitem.task_description,
                    expected_file=pitem.expected_file,
                    target_files=proposal.target_files,
                    diff_applies_cleanly=sandbox_result.apply_succeeded,
                    latency_ms=elapsed_ms,
                )
            )

    await db_engine.dispose()
    # `workspace_root` (including the sqlite MLflow store) is cleaned up by
    # the caller in `main()`, *after* `_log_to_mlflow` has run against it.

    report = {
        "provider": provider_name,
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset_size": {"qa": len(qa_results), "patch": len(patch_results)},
        "retrieval_quality": retrieval_quality(qa_results),
        "groundedness": groundedness(qa_results),
        "citation_accuracy": citation_accuracy(qa_results),
        "qa_latency": latency(qa_results),
        "patch_latency": latency(patch_results),
        "qa_task_success": qa_task_success(qa_results),
        "patch_task_success": patch_task_success(patch_results),
        "items": {
            "qa": [
                {
                    "question": r.question,
                    "expected_file": r.expected_file,
                    "retrieved_files": r.retrieved_files,
                    "cited_files": r.cited_files,
                    "latency_ms": r.latency_ms,
                }
                for r in qa_results
            ],
            "patch": [
                {
                    "task_description": r.task_description,
                    "expected_file": r.expected_file,
                    "target_files": r.target_files,
                    "diff_applies_cleanly": r.diff_applies_cleanly,
                    "latency_ms": r.latency_ms,
                }
                for r in patch_results
            ],
        },
    }
    return report, workspace_root


def _log_to_mlflow(report: dict) -> None:
    import mlflow

    mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
    mlflow.set_experiment("masea-evals")
    with mlflow.start_run(run_name=f"evals-{report['provider']}"):
        mlflow.log_param("provider", report["provider"])
        mlflow.log_param("dataset_size_qa", report["dataset_size"]["qa"])
        mlflow.log_param("dataset_size_patch", report["dataset_size"]["patch"])
        for group in ("retrieval_quality", "groundedness", "citation_accuracy", "qa_task_success", "patch_task_success"):
            for k, v in report[group].items():
                if k != "n":
                    mlflow.log_metric(f"{group}.{k}", v)
        for k, v in report["qa_latency"].items():
            if k != "n":
                mlflow.log_metric(f"qa_latency.{k}", v)
        for k, v in report["patch_latency"].items():
            if k != "n":
                mlflow.log_metric(f"patch_latency.{k}", v)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["fake", "ollama"], default="fake")
    parser.add_argument("--skip-mlflow", action="store_true", help="Skip logging to MLflow (report file only).")
    args = parser.parse_args()

    report, workspace_root = asyncio.run(_run(args.provider))

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / f"eval_report_{args.provider}.json"
    report_path.write_text(json.dumps(report, indent=2))

    print(f"\n=== MASEA eval report ({args.provider}) ===")
    print(f"Retrieval quality (hit@k):   {report['retrieval_quality']}")
    print(f"Groundedness:                {report['groundedness']}")
    print(f"Citation accuracy:           {report['citation_accuracy']}")
    print(f"QA latency:                  {report['qa_latency']}")
    print(f"Patch latency:               {report['patch_latency']}")
    print(f"QA task success (proxy):     {report['qa_task_success']}")
    print(f"Patch task success (apply):  {report['patch_task_success']}")
    print(f"Report written to: {report_path}")

    if not args.skip_mlflow:
        try:
            _log_to_mlflow(report)
            print("Logged to MLflow.")
        except Exception as exc:  # noqa: BLE001 - MLflow logging must never fail the eval run itself
            print(f"(MLflow logging skipped: {exc})")

    shutil.rmtree(workspace_root, ignore_errors=True)


if __name__ == "__main__":
    main()
