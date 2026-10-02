"""Add durable APPLICATION cooldown and Submit idempotency state.

Revision ID: 0007_add_application_execution_guard
Revises: 0006_add_application_config
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0007_add_application_execution_guard"
down_revision: str | None = "0006_add_application_config"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "application_execution_cooldowns",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("execution_kind", sa.String(length=16), nullable=False),
        sa.Column("last_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "execution_kind IN ('run', 'submit')",
            name="ck_application_execution_cooldowns_kind",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "execution_kind"),
    )
    op.create_table(
        "application_submit_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("challenge_id", sa.String(length=128), nullable=False),
        sa.Column("challenge_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submission_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("result_payload", postgresql.JSONB(), nullable=True),
        sa.CheckConstraint(
            "status IN ('in_progress', 'completed')",
            name="ck_application_submit_requests_status",
        ),
        sa.ForeignKeyConstraint(["challenge_id"], ["challenges.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["challenge_version_id"], ["challenge_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("submission_id"),
        sa.UniqueConstraint(
            "user_id",
            "challenge_version_id",
            "key_hash",
            name="uq_application_submit_requests_scope_key",
        ),
    )
    op.create_index(
        "ix_application_submit_requests_user_id",
        "application_submit_requests",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_application_submit_requests_user_id",
        table_name="application_submit_requests",
    )
    op.drop_table("application_submit_requests")
    op.drop_table("application_execution_cooldowns")
