"""Store the versioned APPLICATION challenge execution configuration.

Nullable: TEXT versions keep NULL. The value references a repository-owned starter
project; no project source is stored in the row.

Revision ID: 0006_add_application_config
Revises: 0005_add_challenge_type
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006_add_application_config"
down_revision: str | None = "0005_add_challenge_type"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "challenge_versions",
        sa.Column("application_config", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("challenge_versions", "application_config")
