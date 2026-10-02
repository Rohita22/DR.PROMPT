"""Add the challenge family/type to challenge versions.

Existing versions are backfilled as TEXT by the server default.

Revision ID: 0005_add_challenge_type
Revises: 0004_add_leaderboard_index
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_add_challenge_type"
down_revision: str | None = "0004_add_leaderboard_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "challenge_versions",
        sa.Column(
            "challenge_type",
            sa.String(length=32),
            nullable=False,
            server_default="text",
        ),
    )
    op.create_check_constraint(
        "ck_challenge_versions_challenge_type",
        "challenge_versions",
        "challenge_type IN ('text', 'application', 'image')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_challenge_versions_challenge_type",
        "challenge_versions",
        type_="check",
    )
    op.drop_column("challenge_versions", "challenge_type")
