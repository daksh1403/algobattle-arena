"""add_slug_to_contests.

Revision ID: 0003
Revises: 0002
Create Date: 2025-01-02 00:00:00.000000

"""
from __future__ import annotations

import re

from alembic import op

revision: str = "0003"
down_revision: str = "0002"
branch_labels: str | None = None
depends_on: str | None = None


def _slugify(name: str) -> str:
    """Convert a contest name to a URL-safe slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug


def upgrade() -> None:
    """Add unique slug column to contests, auto-populated from name."""
    op.add_column(
        "contests",
        # nullable first, then backfill slugs, then set NOT NULL
        op.Column("slug", op.TEXT(), nullable=True),
    )

    # Backfill slug for existing rows
    conn = op.get_bind()
    result = conn.execute(
        op.get_context().session.query  # type: ignore[attr-defined]
    )
    # Use raw SQL backfill for SQLite compatibility
    op.execute("""
        UPDATE contests
        SET slug = LOWER(
            REPLACE(
                REPLACE(
                    REPLACE(TRIM(name), ' ', '-'),
                    CHAR(10), '-'
                ),
                CHAR(9), '-'
            )
        )
        WHERE slug IS NULL
    """)
    op.alter_column("contests", "slug", nullable=False)


def downgrade() -> None:
    """Remove slug column from contests."""
    op.drop_column("contests", "slug")
