"""Create challenge, hidden-test, and submission persistence tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_initial_persistence"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "challenges",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("slug", sa.String(128), nullable=False),
        sa.Column("track", sa.String(32), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("current_version", sa.String(64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("slug", name="uq_challenges_slug"),
    )
    op.create_table(
        "challenge_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "challenge_id",
            sa.String(128),
            sa.ForeignKey("challenges.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("constraints", postgresql.JSONB(), nullable=False),
        sa.Column("difficulty", sa.String(32), nullable=False),
        sa.Column("prompt_token_limit", sa.Integer(), nullable=True),
        sa.Column("evaluation_config", postgresql.JSONB(), nullable=False),
        sa.Column("model_config", postgresql.JSONB(), nullable=False),
        sa.Column("scoring_config", postgresql.JSONB(), nullable=False),
        sa.Column("publication_state", sa.String(32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("challenge_id", "version", name="uq_challenge_version"),
    )
    op.create_index("ix_challenge_versions_challenge_id", "challenge_versions", ["challenge_id"])
    op.create_index(
        "ix_challenge_versions_publication_state",
        "challenge_versions",
        ["publication_state"],
    )

    op.create_table(
        "visible_examples",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "challenge_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("challenge_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("input", postgresql.JSONB(), nullable=False),
        sa.Column("expected_output", postgresql.JSONB(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.UniqueConstraint("challenge_version_id", "sort_order", name="uq_visible_examples_order"),
    )
    op.create_index(
        "ix_visible_examples_challenge_version_id",
        "visible_examples",
        ["challenge_version_id"],
    )

    _create_test_table("visible_test_cases")
    _create_test_table("hidden_test_cases")

    op.create_table(
        "submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "challenge_id",
            sa.String(128),
            sa.ForeignKey("challenges.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "challenge_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("challenge_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("passed_tests", sa.Integer(), nullable=False),
        sa.Column("total_tests", sa.Integer(), nullable=False),
        sa.Column("accuracy", sa.Float(), nullable=False),
        sa.Column("efficiency", sa.Float(), nullable=False),
        sa.Column("final_score", sa.Float(), nullable=False),
        sa.Column("stars", sa.Integer(), nullable=False),
        sa.Column("model_identifier", sa.String(255), nullable=False),
        sa.Column("model_configuration_version", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "passed_tests >= 0 AND passed_tests <= total_tests",
            name="ck_submissions_passed_tests",
        ),
        sa.CheckConstraint("total_tests > 0", name="ck_submissions_total_tests"),
        sa.CheckConstraint("prompt_tokens >= 0", name="ck_submissions_prompt_tokens"),
        sa.CheckConstraint("accuracy >= 0 AND accuracy <= 100", name="ck_submissions_accuracy"),
        sa.CheckConstraint(
            "efficiency >= 0 AND efficiency <= 100", name="ck_submissions_efficiency"
        ),
        sa.CheckConstraint(
            "final_score >= 0 AND final_score <= 100", name="ck_submissions_final_score"
        ),
        sa.CheckConstraint("stars >= 0 AND stars <= 3", name="ck_submissions_stars"),
    )
    op.create_index("ix_submissions_challenge_id", "submissions", ["challenge_id"])
    op.create_index("ix_submissions_challenge_version_id", "submissions", ["challenge_version_id"])
    op.create_index("ix_submissions_user_id", "submissions", ["user_id"])


def _create_test_table(table_name: str) -> None:
    op.create_table(
        table_name,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "challenge_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("challenge_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("test_id", sa.String(128), nullable=False),
        sa.Column("input", postgresql.JSONB(), nullable=False),
        sa.Column("expected_output", postgresql.JSONB(), nullable=False),
        sa.Column("evaluation_config", postgresql.JSONB(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.UniqueConstraint("challenge_version_id", "test_id", name=f"uq_{table_name}_test_id"),
        sa.UniqueConstraint("challenge_version_id", "sort_order", name=f"uq_{table_name}_order"),
    )
    op.create_index(f"ix_{table_name}_challenge_version_id", table_name, ["challenge_version_id"])


def downgrade() -> None:
    op.drop_table("submissions")
    op.drop_table("hidden_test_cases")
    op.drop_table("visible_test_cases")
    op.drop_table("visible_examples")
    op.drop_table("challenge_versions")
    op.drop_table("challenges")
