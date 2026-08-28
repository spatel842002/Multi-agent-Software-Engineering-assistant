#!/usr/bin/env bash
# Drops every table by rolling every migration back, then re-applies them.
# Idempotent: safe to run repeatedly. Only ever touches the schema, never
# host files -- run against a database you're fine wiping (local dev only).
set -euo pipefail

cd "$(dirname "$0")/../backend"

if command -v docker >/dev/null && [ -n "$(docker compose ps -q backend 2>/dev/null)" ]; then
    echo "Resetting via the running backend container..."
    docker compose exec backend alembic downgrade base
    docker compose exec backend alembic upgrade head
else
    echo "Resetting via local alembic (activate the backend venv first if this fails)..."
    alembic downgrade base
    alembic upgrade head
fi

echo "Done. Schema reset to head with no data."
