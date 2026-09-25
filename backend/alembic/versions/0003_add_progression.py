"""Add XP ledger and per-user challenge progress.

Revision ID: 0003_add_progression
Revises: 0002_add_authenticated_users
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003_add_progression"
down_revision: str | None = "0002_add_authenticated_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_progress",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("challenge_id", sa.String(length=128), nullable=False),
        sa.Column("best_submission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("best_score", sa.Float(), nullable=False),
        sa.Column("best_stars", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("best_score >= 0 AND best_score <= 100", name="ck_progress_best_score"),
        sa.CheckConstraint("best_stars >= 0 AND best_stars <= 3", name="ck_progress_best_stars"),
        sa.CheckConstraint("attempts > 0", name="ck_progress_attempts"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["challenge_id"], ["challenges.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["best_submission_id"], ["submissions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "challenge_id", name="uq_user_progress_user_challenge"),
    )
    op.create_index("ix_user_progress_user_id", "user_progress", ["user_id"])
    op.create_index("ix_user_progress_challenge_id", "user_progress", ["challenge_id"])

    op.create_table(
        "xp_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("challenge_id", sa.String(length=128), nullable=False),
        sa.Column("submission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_xp_transactions_amount"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["challenge_id"], ["challenges.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "challenge_id",
            "reason",
            name="uq_xp_milestone_user_challenge_reason",
        ),
    )
    op.create_index("ix_xp_transactions_user_id", "xp_transactions", ["user_id"])
    op.create_index("ix_xp_transactions_challenge_id", "xp_transactions", ["challenge_id"])


def downgrade() -> None:
    op.drop_index("ix_xp_transactions_challenge_id", table_name="xp_transactions")
    op.drop_index("ix_xp_transactions_user_id", table_name="xp_transactions")
    op.drop_table("xp_transactions")
    op.drop_index("ix_user_progress_challenge_id", table_name="user_progress")
    op.drop_index("ix_user_progress_user_id", table_name="user_progress")
    op.drop_table("user_progress")
