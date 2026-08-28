"""chunk fulltext index

Adds a generated, always-in-sync `content_tsv` tsvector column on `chunks`
plus a GIN index over it, backing the Postgres branch of
`app.services.retrieval.lexical.lexical_search`. Postgres-only (GENERATED
... STORED tsvector columns and GIN indexes are not portable); the SQLite
test path never runs Alembic migrations at all -- it uses `Base.metadata.create_all`
against a throwaway file, so it's unaffected by this being Postgres-specific.

Revision ID: 21b381a63167
Revises: 0a1d2da24712
Create Date: 2026-08-27 16:21:57.035977
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "21b381a63167"
down_revision: str | None = "0a1d2da24712"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE chunks
        ADD COLUMN content_tsv tsvector
        GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
        """
    )
    op.execute("CREATE INDEX ix_chunks_content_tsv ON chunks USING GIN (content_tsv)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_content_tsv")
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS content_tsv")
