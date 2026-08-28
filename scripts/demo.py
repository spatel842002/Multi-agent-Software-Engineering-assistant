#!/usr/bin/env python
"""Reproducible demo script: exercises the full real user journey against a
running instance (register -> ingest a real repository -> ask a grounded
question -> propose a patch -> reject it) over plain HTTP, no browser
required. This is the scriptable equivalent of `frontend/e2e/smoke.spec.ts`;
use that instead if you want browser screenshots.

Usage:
    docker compose up -d --build
    docker compose exec ollama ollama pull qwen2.5-coder:1.5b
    docker compose exec ollama ollama pull nomic-embed-text
    python scripts/demo.py [--base-url http://localhost:8000] [--repo-url https://github.com/octocat/Hello-World.git]
"""
from __future__ import annotations

import argparse
import sys
import time
import uuid

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000/api/v1")
    parser.add_argument("--repo-url", default="https://github.com/octocat/Hello-World.git")
    parser.add_argument("--repo-name", default="demo-repo")
    parser.add_argument("--question", default="What is this repository for?")
    parser.add_argument("--poll-timeout-seconds", type=int, default=60)
    args = parser.parse_args()

    client = httpx.Client(base_url=args.base_url, timeout=180.0)
    email = f"demo-{uuid.uuid4().hex[:12]}@example.com"
    password = "correct-horse-battery-staple"

    print(f"[1/6] Registering {email}...")
    r = client.post("/auth/register", json={"email": email, "password": password})
    r.raise_for_status()

    print("[2/6] Logging in...")
    r = client.post("/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    token = r.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"

    print(f"[3/6] Ingesting {args.repo_url}...")
    r = client.post("/repositories", json={"name": args.repo_name, "source_url": args.repo_url})
    r.raise_for_status()
    repo = r.json()
    repo_id = repo["id"]

    print("      Waiting for ingestion to reach a terminal status...")
    deadline = time.monotonic() + args.poll_timeout_seconds
    while time.monotonic() < deadline:
        r = client.get(f"/repositories/{repo_id}")
        r.raise_for_status()
        repo = r.json()
        if repo["status"] in ("ready", "failed"):
            break
        time.sleep(2)
    else:
        print("      Timed out waiting for ingestion.", file=sys.stderr)
        sys.exit(1)

    if repo["status"] != "ready":
        print(f"      Ingestion failed: {repo['status_detail']}", file=sys.stderr)
        sys.exit(1)
    print(f"      Ready: {repo['file_count']} files, {repo['chunk_count']} chunks.")

    print(f"[4/6] Asking: {args.question!r} (this calls a real local LLM -- can take a while)...")
    r = client.post(f"/repositories/{repo_id}/qa", json={"question": args.question})
    r.raise_for_status()
    answer = r.json()
    print(f"      Answer ({answer['latency_ms']}ms): {answer['answer'][:300]}")
    print(f"      Citations: {answer['citations']}")

    print("[5/6] Proposing a patch (real local LLM call)...")
    r = client.post(
        f"/repositories/{repo_id}/patch-proposals",
        json={"task_description": "Add one short sentence to the README explaining this is a demo repository."},
    )
    r.raise_for_status()
    proposal = r.json()
    patch_id = proposal["patch_proposal_id"]
    print(f"      Patch proposal {patch_id} created (pending approval, nothing applied yet).")

    print("[6/6] Rejecting the proposal (a safe, side-effect-free decision for this demo)...")
    r = client.post(f"/patch-proposals/{patch_id}/decision", json={"decision": "reject", "reason": "demo script"})
    r.raise_for_status()
    print(f"      Final status: {r.json()['status']}")

    print("\nDemo complete. Nothing was applied to any real filesystem outside the sandbox.")


if __name__ == "__main__":
    main()
