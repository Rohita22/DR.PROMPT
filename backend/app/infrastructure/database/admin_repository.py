import uuid

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.admin.errors import (
    AdminChallengeConflictError,
    AdminChallengeNotFoundError,
    AdminChallengeStateError,
)
from app.application.admin.models import (
    AdminChallengeRecord,
    AdminChallengeSummary,
    VersionMetadata,
)
from app.application.admin.ports import AdminChallengeRepository
from app.core.exceptions import DomainError, PersistenceError
from app.domains.challenges.models import (
    Challenge,
    ChallengeTrack,
    ChallengeType,
    ChallengeVersion,
    Difficulty,
    PublicationState,
    VisibleExample,
)
from app.domains.evaluation.configuration import EvaluationConfiguration
from app.domains.evaluation.test_cases import HiddenTestCase, VisibleTestCase
from app.infrastructure.database.mappers import (
    application_config_from_data,
    application_config_to_data,
    challenge_type_from_data,
    grader_config_from_data,
    grader_config_to_data,
    model_config_from_data,
    model_config_to_data,
    scoring_config_from_data,
    scoring_config_to_data,
)
from app.infrastructure.database.models import (
    ChallengeRow,
    ChallengeVersionRow,
    HiddenTestCaseRow,
    VisibleExampleRow,
    VisibleTestCaseRow,
)


class PostgresAdminChallengeRepository(AdminChallengeRepository):
    """Admin-only persistence adapter for drafts and immutable published versions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self) -> tuple[AdminChallengeSummary, ...]:
        try:
            async with self._session.begin():
                rows = (
                    await self._session.scalars(
                        select(ChallengeRow).order_by(
                            ChallengeRow.track, ChallengeRow.sort_order, ChallengeRow.slug
                        )
                    )
                ).all()
                summaries: list[AdminChallengeSummary] = []
                for row in rows:
                    record = await self._load_record(row)
                    if record is None:
                        continue
                    summaries.append(
                        AdminChallengeSummary(
                            challenge_type=record.version.challenge_type,
                            slug=row.slug,
                            title=record.version.title,
                            track=ChallengeTrack(row.track),
                            difficulty=record.version.difficulty,
                            order=row.sort_order,
                            version=record.version.version_id,
                            current_version=row.current_version,
                            publication_state=record.version.publication_state,
                            visible_test_count=len(record.version.application_config.visible_checks)
                            if record.version.application_config
                            else len(record.version.visible_test_cases),
                            hidden_test_count=len(record.version.application_config.hidden_checks)
                            if record.version.application_config
                            else len(record.hidden_test_cases),
                            created_at=row.created_at,
                            updated_at=row.updated_at,
                        )
                    )
                return tuple(summaries)
        except (DomainError, SQLAlchemyError, ValueError):
            raise PersistenceError("Database operation failed.") from None

    async def get_by_slug(self, slug: str) -> AdminChallengeRecord | None:
        try:
            async with self._session.begin():
                row = await self._session.scalar(
                    select(ChallengeRow).where(ChallengeRow.slug == slug)
                )
                return await self._load_record(row)
        except (DomainError, SQLAlchemyError, ValueError):
            raise PersistenceError("Database operation failed.") from None

    async def create(self, record: AdminChallengeRecord) -> None:
        try:
            async with self._session.begin():
                await self._ensure_order_available(record)
                self._session.add(
                    ChallengeRow(
                        id=record.challenge.id,
                        slug=record.challenge.slug,
                        track=record.challenge.track.value,
                        sort_order=record.challenge.order,
                        current_version=record.challenge.current_version_id,
                    )
                )
                await self._session.flush()
                await self._insert_version(record)
        except AdminChallengeConflictError:
            raise
        except IntegrityError:
            raise AdminChallengeConflictError(
                "Challenge slug, version, or test identifiers conflict with existing data."
            ) from None
        except (DomainError, SQLAlchemyError, ValueError):
            raise PersistenceError("Database operation failed.") from None

    async def update_draft(self, record: AdminChallengeRecord) -> None:
        try:
            async with self._session.begin():
                await self._ensure_order_available(record)
                challenge_row = await self._session.scalar(
                    select(ChallengeRow)
                    .where(ChallengeRow.id == record.challenge.id)
                    .with_for_update()
                )
                version_row = await self._session.scalar(
                    select(ChallengeVersionRow)
                    .where(
                        ChallengeVersionRow.challenge_id == record.challenge.id,
                        ChallengeVersionRow.version == record.version.version_id,
                    )
                    .with_for_update()
                )
                if challenge_row is None or version_row is None:
                    raise AdminChallengeNotFoundError("Challenge draft was not found.")
                if version_row.publication_state != PublicationState.DRAFT.value:
                    raise AdminChallengeStateError("Only draft versions may be edited.")
                if version_row.challenge_type != record.version.challenge_type.value:
                    raise AdminChallengeStateError("Challenge type cannot change after creation.")
                challenge_row.track = record.challenge.track.value
                challenge_row.sort_order = record.challenge.order
                challenge_row.updated_at = func.now()
                self._update_version_row(version_row, record.version)
                await self._replace_children(version_row.id, record)
        except (AdminChallengeNotFoundError, AdminChallengeConflictError, AdminChallengeStateError):
            raise
        except IntegrityError:
            raise AdminChallengeConflictError(
                "Challenge version or test identifiers conflict with existing data."
            ) from None
        except (DomainError, SQLAlchemyError, ValueError):
            raise PersistenceError("Database operation failed.") from None

    async def create_version(self, record: AdminChallengeRecord) -> None:
        try:
            async with self._session.begin():
                challenge = await self._session.scalar(
                    select(ChallengeRow).where(ChallengeRow.id == record.challenge.id)
                )
                if challenge is None:
                    raise AdminChallengeNotFoundError("Challenge was not found.")
                await self._insert_version(record)
                challenge.updated_at = func.now()
        except (AdminChallengeNotFoundError, AdminChallengeConflictError):
            raise
        except IntegrityError:
            raise AdminChallengeConflictError("This challenge version already exists.") from None
        except (DomainError, SQLAlchemyError, ValueError):
            raise PersistenceError("Database operation failed.") from None

    async def publish(self, slug: str, version: str) -> AdminChallengeRecord:
        try:
            async with self._session.begin():
                challenge = await self._session.scalar(
                    select(ChallengeRow).where(ChallengeRow.slug == slug).with_for_update()
                )
                if challenge is None:
                    raise AdminChallengeNotFoundError(f"Challenge '{slug}' was not found.")
                target = await self._session.scalar(
                    select(ChallengeVersionRow)
                    .where(
                        ChallengeVersionRow.challenge_id == challenge.id,
                        ChallengeVersionRow.version == version,
                    )
                    .with_for_update()
                )
                if target is None:
                    raise AdminChallengeNotFoundError("Challenge version was not found.")
                if target.publication_state != PublicationState.DRAFT.value:
                    raise AdminChallengeStateError("Only a draft version can be published.")
                visible_count = await self._session.scalar(
                    select(func.count())
                    .select_from(VisibleTestCaseRow)
                    .where(VisibleTestCaseRow.challenge_version_id == target.id)
                )
                hidden_count = await self._session.scalar(
                    select(func.count())
                    .select_from(HiddenTestCaseRow)
                    .where(HiddenTestCaseRow.challenge_version_id == target.id)
                )
                if target.challenge_type == ChallengeType.APPLICATION.value:
                    application_config_from_data(target.application_config)
                    if target.application_config is None:
                        raise AdminChallengeStateError("Application configuration is required.")
                elif target.challenge_type != ChallengeType.TEXT.value:
                    raise AdminChallengeStateError("Unsupported challenge type.")
                elif not visible_count or not hidden_count:
                    raise AdminChallengeStateError(
                        "Publishing requires at least one visible and one hidden test case."
                    )
                await self._session.execute(
                    update(ChallengeVersionRow)
                    .where(
                        ChallengeVersionRow.challenge_id == challenge.id,
                        ChallengeVersionRow.publication_state == PublicationState.PUBLISHED.value,
                    )
                    .values(publication_state=PublicationState.RETIRED.value)
                )
                target.publication_state = PublicationState.PUBLISHED.value
                challenge.current_version = target.version
                challenge.updated_at = func.now()
                await self._session.flush()
                result = await self._load_record(challenge, preferred_version=target.version)
                if result is None:
                    raise PersistenceError("Published challenge could not be reloaded.")
                return result
        except (AdminChallengeNotFoundError, AdminChallengeStateError, PersistenceError):
            raise
        except (DomainError, SQLAlchemyError, ValueError):
            raise PersistenceError("Database operation failed.") from None

    async def unpublish(self, slug: str) -> AdminChallengeRecord:
        try:
            async with self._session.begin():
                challenge = await self._session.scalar(
                    select(ChallengeRow).where(ChallengeRow.slug == slug).with_for_update()
                )
                if challenge is None:
                    raise AdminChallengeNotFoundError(f"Challenge '{slug}' was not found.")
                if challenge.current_version is None:
                    raise AdminChallengeStateError("Challenge is not currently published.")
                current = challenge.current_version
                await self._session.execute(
                    update(ChallengeVersionRow)
                    .where(
                        ChallengeVersionRow.challenge_id == challenge.id,
                        ChallengeVersionRow.version == current,
                        ChallengeVersionRow.publication_state == PublicationState.PUBLISHED.value,
                    )
                    .values(publication_state=PublicationState.RETIRED.value)
                )
                challenge.current_version = None
                challenge.updated_at = func.now()
                await self._session.flush()
                result = await self._load_record(challenge, preferred_version=current)
                if result is None:
                    raise PersistenceError("Unpublished challenge could not be reloaded.")
                return result
        except (AdminChallengeNotFoundError, AdminChallengeStateError, PersistenceError):
            raise
        except (DomainError, SQLAlchemyError, ValueError):
            raise PersistenceError("Database operation failed.") from None

    async def _ensure_order_available(self, record: AdminChallengeRecord) -> None:
        conflict = await self._session.scalar(
            select(ChallengeRow.id).where(
                ChallengeRow.track == record.challenge.track.value,
                ChallengeRow.sort_order == record.challenge.order,
                ChallengeRow.id != record.challenge.id,
            )
        )
        if conflict is not None:
            raise AdminChallengeConflictError(
                f"Order {record.challenge.order} is already used in the "
                f"{record.challenge.track.value.upper()} track."
            )

    async def _load_record(
        self,
        challenge: ChallengeRow | None,
        *,
        preferred_version: str | None = None,
    ) -> AdminChallengeRecord | None:
        if challenge is None:
            return None
        versions = list(
            (
                await self._session.scalars(
                    select(ChallengeVersionRow)
                    .where(ChallengeVersionRow.challenge_id == challenge.id)
                    .order_by(
                        ChallengeVersionRow.created_at.desc(),
                        ChallengeVersionRow.version.desc(),
                    )
                )
            ).all()
        )
        if not versions:
            return None
        version = next(
            (item for item in versions if item.version == preferred_version),
            None,
        )
        if version is None:
            version = next(
                (
                    item
                    for item in versions
                    if item.publication_state == PublicationState.DRAFT.value
                ),
                None,
            )
        if version is None and challenge.current_version is not None:
            version = next(
                (item for item in versions if item.version == challenge.current_version),
                None,
            )
        version = version or versions[0]
        examples = list(
            (
                await self._session.scalars(
                    select(VisibleExampleRow)
                    .where(VisibleExampleRow.challenge_version_id == version.id)
                    .order_by(VisibleExampleRow.sort_order)
                )
            ).all()
        )
        visible = list(
            (
                await self._session.scalars(
                    select(VisibleTestCaseRow)
                    .where(VisibleTestCaseRow.challenge_version_id == version.id)
                    .order_by(VisibleTestCaseRow.sort_order)
                )
            ).all()
        )
        hidden = list(
            (
                await self._session.scalars(
                    select(HiddenTestCaseRow)
                    .where(HiddenTestCaseRow.challenge_version_id == version.id)
                    .order_by(HiddenTestCaseRow.sort_order)
                )
            ).all()
        )
        version_domain = ChallengeVersion(
            version_id=version.version,
            challenge_id=challenge.id,
            title=version.title,
            description=version.description,
            objective=version.objective,
            constraints=tuple(version.constraints),
            difficulty=Difficulty(version.difficulty),
            visible_examples=tuple(
                VisibleExample(item.input, item.expected_output, item.explanation)
                for item in examples
            ),
            visible_test_cases=tuple(
                VisibleTestCase(
                    item.test_id,
                    item.input,
                    item.expected_output,
                    grader_config_from_data(item.evaluation_config),
                )
                for item in visible
            ),
            prompt_token_limit=version.prompt_token_limit,
            evaluation_config=EvaluationConfiguration(
                grader_config_from_data(version.evaluation_config["default_grader"])
            ),
            scoring_config=scoring_config_from_data(version.scoring_config),
            model_config=model_config_from_data(version.model_config),
            publication_state=PublicationState(version.publication_state),
            challenge_type=challenge_type_from_data(version.challenge_type),
            application_config=application_config_from_data(version.application_config),
        )
        return AdminChallengeRecord(
            challenge=Challenge(
                id=challenge.id,
                slug=challenge.slug,
                track=ChallengeTrack(challenge.track),
                order=challenge.sort_order,
                current_version_id=challenge.current_version,
            ),
            version=version_domain,
            hidden_test_cases=tuple(
                HiddenTestCase(
                    item.test_id,
                    item.input,
                    item.expected_output,
                    grader_config_from_data(item.evaluation_config),
                )
                for item in hidden
            ),
            versions=tuple(
                VersionMetadata(
                    item.version,
                    PublicationState(item.publication_state),
                    item.created_at,
                )
                for item in reversed(versions)
            ),
            created_at=challenge.created_at,
            updated_at=challenge.updated_at,
        )

    async def _insert_version(self, record: AdminChallengeRecord) -> None:
        version = record.version
        row = ChallengeVersionRow(
            id=uuid.uuid4(),
            challenge_id=record.challenge.id,
            version=version.version_id,
            title=version.title,
            description=version.description,
            objective=version.objective,
            constraints=list(version.constraints),
            difficulty=version.difficulty.value,
            prompt_token_limit=version.prompt_token_limit,
            evaluation_config={
                "default_grader": grader_config_to_data(version.evaluation_config.default_grader)
            },
            model_config=model_config_to_data(version.model_config),
            scoring_config=scoring_config_to_data(version.scoring_config),
            publication_state=version.publication_state.value,
            challenge_type=version.challenge_type.value,
            application_config=application_config_to_data(version.application_config),
        )
        self._session.add(row)
        await self._session.flush()
        await self._add_children(row.id, record)

    @staticmethod
    def _update_version_row(row: ChallengeVersionRow, version: ChallengeVersion) -> None:
        row.application_config = application_config_to_data(version.application_config)
        row.title = version.title
        row.description = version.description
        row.objective = version.objective
        row.constraints = list(version.constraints)
        row.difficulty = version.difficulty.value
        row.prompt_token_limit = version.prompt_token_limit
        row.evaluation_config = {
            "default_grader": grader_config_to_data(version.evaluation_config.default_grader)
        }
        row.model_config = model_config_to_data(version.model_config)
        row.scoring_config = scoring_config_to_data(version.scoring_config)

    async def _replace_children(
        self, version_row_id: uuid.UUID, record: AdminChallengeRecord
    ) -> None:
        for row_type in (VisibleExampleRow, VisibleTestCaseRow, HiddenTestCaseRow):
            await self._session.execute(
                delete(row_type).where(row_type.challenge_version_id == version_row_id)
            )
        await self._add_children(version_row_id, record)

    async def _add_children(self, version_row_id: uuid.UUID, record: AdminChallengeRecord) -> None:
        self._session.add_all(
            VisibleExampleRow(
                id=uuid.uuid4(),
                challenge_version_id=version_row_id,
                input=item.input,
                expected_output=item.expected_output,
                explanation=item.explanation,
                sort_order=index,
            )
            for index, item in enumerate(record.version.visible_examples, start=1)
        )
        self._session.add_all(
            VisibleTestCaseRow(
                id=uuid.uuid4(),
                challenge_version_id=version_row_id,
                test_id=item.id,
                input=item.input,
                expected_output=item.expected_output,
                evaluation_config=grader_config_to_data(item.grader_config),
                sort_order=index,
            )
            for index, item in enumerate(record.version.visible_test_cases, start=1)
        )
        self._session.add_all(
            HiddenTestCaseRow(
                id=uuid.uuid4(),
                challenge_version_id=version_row_id,
                test_id=item.id,
                input=item.input,
                expected_output=item.expected_output,
                evaluation_config=grader_config_to_data(item.grader_config),
                sort_order=index,
            )
            for index, item in enumerate(record.hidden_test_cases, start=1)
        )
