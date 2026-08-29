"""Initial schema — users, problems, test_cases, contests, contest_participants, contest_problems, submissions, submission_results.

Revision ID: 0001_initial
Revises:
Create Date: 2025-01-01 00:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_admin", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("rating", sa.Integer, nullable=False, server_default="1500"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # --- problems ---
    op.create_table(
        "problems",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("slug", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("statement_md", sa.Text, nullable=False),
        sa.Column(
            "difficulty",
            sa.Enum("easy", "medium", "hard", name="difficulty", native_enum=False, length=16),
            nullable=False,
            server_default="easy",
        ),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.String(32)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("time_limit_ms", sa.Integer, nullable=False, server_default="2000"),
        sa.Column("memory_limit_kb", sa.Integer, nullable=False, server_default="262144"),
        sa.Column(
            "boilerplate_code",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "function_signature", sa.String(255), nullable=False, server_default=""
        ),
        sa.Column(
            "solution_visibility",
            sa.Enum("public", "private", name="solution_visibility", native_enum=False, length=16),
            nullable=False,
            server_default="private",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # --- test_cases ---
    op.create_table(
        "test_cases",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "problem_id",
            sa.Integer,
            sa.ForeignKey("problems.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("input", sa.Text, nullable=False),
        sa.Column("expected_output", sa.Text, nullable=False),
        sa.Column("is_sample", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("is_public", sa.Boolean, nullable=False, server_default=sa.text("true")),
    )

    # --- contests ---
    op.create_table(
        "contests",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(2000), nullable=False, server_default=""),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # --- contest_participants ---
    op.create_table(
        "contest_participants",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "contest_id",
            sa.Integer,
            sa.ForeignKey("contests.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("total_points", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("contest_id", "user_id", name="uq_contest_user"),
    )

    # --- contest_problems ---
    op.create_table(
        "contest_problems",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "contest_id",
            sa.Integer,
            sa.ForeignKey("contests.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "problem_id",
            sa.Integer,
            sa.ForeignKey("problems.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
        sa.Column("score", sa.Integer, nullable=False, server_default="100"),
        sa.UniqueConstraint("contest_id", "problem_id", name="uq_contest_problem"),
    )

    # --- submissions ---
    op.create_table(
        "submissions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "problem_id",
            sa.Integer,
            sa.ForeignKey("problems.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "contest_id",
            sa.Integer,
            sa.ForeignKey("contests.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("language", sa.String(32), nullable=False),
        sa.Column("code", sa.Text, nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "running",
                "accepted",
                "wrong_answer",
                "tle",
                "mle",
                "runtime_error",
                "compile_error",
                "internal_error",
                name="submission_status",
                native_enum=False,
                length=32,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("runtime_ms", sa.Integer, nullable=True),
        sa.Column("memory_kb", sa.Integer, nullable=True),
        sa.Column("score", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_submissions_created_at", "submissions", ["created_at"])

    # --- submission_results ---
    op.create_table(
        "submission_results",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "submission_id",
            sa.Integer,
            sa.ForeignKey("submissions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "testcase_id",
            sa.Integer,
            sa.ForeignKey("test_cases.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "running",
                "accepted",
                "wrong_answer",
                "tle",
                "mle",
                "runtime_error",
                "compile_error",
                "internal_error",
                name="submission_result_status",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("runtime_ms", sa.Integer, nullable=True),
        sa.Column("memory_kb", sa.Integer, nullable=True),
        sa.Column("stdout", sa.Text, nullable=False, server_default=""),
        sa.Column("stderr", sa.Text, nullable=False, server_default=""),
        sa.Column("compile_output", sa.Text, nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_table("submission_results")
    op.drop_table("submissions")
    op.drop_table("contest_problems")
    op.drop_table("contest_participants")
    op.drop_table("contests")
    op.drop_table("test_cases")
    op.drop_table("problems")
    op.drop_table("users")
