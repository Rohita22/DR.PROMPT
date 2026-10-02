import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ChallengeRow(Base):
    __tablename__ = "challenges"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    track: Mapped[str] = mapped_column(String(32), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    current_version: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ChallengeVersionRow(Base):
    __tablename__ = "challenge_versions"
    __table_args__ = (
        UniqueConstraint("challenge_id", "version", name="uq_challenge_version"),
        CheckConstraint(
            "challenge_type IN ('text', 'application', 'image')",
            name="ck_challenge_versions_challenge_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    challenge_id: Mapped[str] = mapped_column(
        ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    constraints: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt_token_limit: Mapped[int | None] = mapped_column(Integer)
    evaluation_config: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    model_config: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    scoring_config: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    publication_state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    challenge_type: Mapped[str] = mapped_column(String(32), nullable=False, server_default="text")
    application_config: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class VisibleExampleRow(Base):
    __tablename__ = "visible_examples"
    __table_args__ = (
        UniqueConstraint(
            "challenge_version_id",
            "sort_order",
            name="uq_visible_examples_order",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    challenge_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("challenge_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    input: Mapped[object] = mapped_column(JSONB, nullable=False)
    expected_output: Mapped[object] = mapped_column(JSONB, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)


class VisibleTestCaseRow(Base):
    __tablename__ = "visible_test_cases"
    __table_args__ = (
        UniqueConstraint("challenge_version_id", "test_id", name="uq_visible_test_cases_test_id"),
        UniqueConstraint("challenge_version_id", "sort_order", name="uq_visible_test_cases_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    challenge_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("challenge_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    test_id: Mapped[str] = mapped_column(String(128), nullable=False)
    input: Mapped[object] = mapped_column(JSONB, nullable=False)
    expected_output: Mapped[object] = mapped_column(JSONB, nullable=False)
    evaluation_config: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)


class HiddenTestCaseRow(Base):
    __tablename__ = "hidden_test_cases"
    __table_args__ = (
        UniqueConstraint("challenge_version_id", "test_id", name="uq_hidden_test_cases_test_id"),
        UniqueConstraint("challenge_version_id", "sort_order", name="uq_hidden_test_cases_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    challenge_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("challenge_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    test_id: Mapped[str] = mapped_column(String(128), nullable=False)
    input: Mapped[object] = mapped_column(JSONB, nullable=False)
    expected_output: Mapped[object] = mapped_column(JSONB, nullable=False)
    evaluation_config: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)


class UserRow(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint(
            "auth_provider",
            "auth_provider_user_id",
            name="uq_users_external_identity",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    auth_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    auth_provider_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SubmissionRow(Base):
    __tablename__ = "submissions"
    __table_args__ = (
        CheckConstraint(
            "passed_tests >= 0 AND passed_tests <= total_tests",
            name="ck_submissions_passed_tests",
        ),
        CheckConstraint("total_tests > 0", name="ck_submissions_total_tests"),
        CheckConstraint("prompt_tokens >= 0", name="ck_submissions_prompt_tokens"),
        CheckConstraint(
            "accuracy >= 0 AND accuracy <= 100",
            name="ck_submissions_accuracy",
        ),
        CheckConstraint(
            "efficiency >= 0 AND efficiency <= 100",
            name="ck_submissions_efficiency",
        ),
        CheckConstraint(
            "final_score >= 0 AND final_score <= 100",
            name="ck_submissions_final_score",
        ),
        CheckConstraint("stars >= 0 AND stars <= 3", name="ck_submissions_stars"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    challenge_id: Mapped[str] = mapped_column(
        ForeignKey("challenges.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    challenge_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("challenge_versions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "users.id",
            name="fk_submissions_user_id_users",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    passed_tests: Mapped[int] = mapped_column(Integer, nullable=False)
    total_tests: Mapped[int] = mapped_column(Integer, nullable=False)
    accuracy: Mapped[float] = mapped_column(Float, nullable=False)
    efficiency: Mapped[float] = mapped_column(Float, nullable=False)
    final_score: Mapped[float] = mapped_column(Float, nullable=False)
    stars: Mapped[int] = mapped_column(Integer, nullable=False)
    model_identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    model_configuration_version: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


Index(
    "ix_submissions_leaderboard_rank",
    SubmissionRow.challenge_version_id,
    SubmissionRow.model_identifier,
    SubmissionRow.model_configuration_version,
    SubmissionRow.user_id,
    SubmissionRow.final_score.desc(),
    SubmissionRow.accuracy.desc(),
    SubmissionRow.prompt_tokens.asc(),
    SubmissionRow.created_at.asc(),
    SubmissionRow.id.asc(),
    postgresql_where=SubmissionRow.user_id.is_not(None),
)


class ApplicationExecutionCooldownRow(Base):
    __tablename__ = "application_execution_cooldowns"
    __table_args__ = (
        CheckConstraint(
            "execution_kind IN ('run', 'submit')",
            name="ck_application_execution_cooldowns_kind",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    execution_kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    last_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ApplicationSubmitRequestRow(Base):
    __tablename__ = "application_submit_requests"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "challenge_version_id",
            "key_hash",
            name="uq_application_submit_requests_scope_key",
        ),
        CheckConstraint(
            "status IN ('in_progress', 'completed')",
            name="ck_application_submit_requests_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    challenge_id: Mapped[str] = mapped_column(
        ForeignKey("challenges.id", ondelete="RESTRICT"), nullable=False
    )
    challenge_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("challenge_versions.id", ondelete="RESTRICT"), nullable=False
    )
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submission_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("submissions.id", ondelete="RESTRICT"), unique=True
    )
    result_payload: Mapped[dict[str, object] | None] = mapped_column(JSONB)


class UserProgressRow(Base):
    __tablename__ = "user_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "challenge_id", name="uq_user_progress_user_challenge"),
        CheckConstraint("best_score >= 0 AND best_score <= 100", name="ck_progress_best_score"),
        CheckConstraint("best_stars >= 0 AND best_stars <= 3", name="ck_progress_best_stars"),
        CheckConstraint("attempts > 0", name="ck_progress_attempts"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    challenge_id: Mapped[str] = mapped_column(
        ForeignKey("challenges.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    best_submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("submissions.id", ondelete="RESTRICT"), nullable=False
    )
    best_score: Mapped[float] = mapped_column(Float, nullable=False)
    best_stars: Mapped[int] = mapped_column(Integer, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class XPTransactionRow(Base):
    __tablename__ = "xp_transactions"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "challenge_id",
            "reason",
            name="uq_xp_milestone_user_challenge_reason",
        ),
        CheckConstraint("amount > 0", name="ck_xp_transactions_amount"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    challenge_id: Mapped[str] = mapped_column(
        ForeignKey("challenges.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("submissions.id", ondelete="RESTRICT"), nullable=False
    )
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
