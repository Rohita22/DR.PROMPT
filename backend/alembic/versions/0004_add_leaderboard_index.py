"""Add the active challenge leaderboard ranking index.

Revision ID: 0004_add_leaderboard_index
Revises: 0003_add_progression
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004_add_leaderboard_index"
down_revision: str | None = "0003_add_progression"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX ix_submissions_leaderboard_rank
        ON submissions (
            challenge_version_id,
            model_identifier,
            model_configuration_version,
            user_id,
            final_score DESC,
            accuracy DESC,
            prompt_tokens ASC,
            created_at ASC,
            id ASC
        )
        WHERE user_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_submissions_leaderboard_rank", table_name="submissions")
