"""add_mode_to_submissions.

Revision ID: 0002
Revises: 0001
Create Date: 2025-01-01 00:00:00.000000

"""
from __future__ import annotations

revision: str = "0002"
down_revision: str = "0001"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Add mode column: 'test' (sample-only) or 'submit' (all cases)."""
    from alembic import op

    op.execute(
        "ALTER TABLE submissions ADD COLUMN mode VARCHAR(16) NOT NULL DEFAULT 'submit'"
    )


def downgrade() -> None:
    """Remove mode column."""
    from alembic import op

    op.execute("ALTER TABLE submissions DROP COLUMN IF EXISTS mode")
