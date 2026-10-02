import secrets
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.admin import (
    AdminChallengeRepository,
    CreateChallengeUseCase,
    CreateChallengeVersionUseCase,
    GetAdminChallengeUseCase,
    ListAdminChallengesUseCase,
    PublishChallengeUseCase,
    TestChallengeUseCase,
    UnpublishChallengeUseCase,
    UpdateChallengeDraftUseCase,
)
from app.application.auth import ResolveAuthenticatedUserUseCase
from app.application.challenges import (
    ChallengeAccessService,
    GetChallengeDetailUseCase,
    GetStarterPreviewUseCase,
    ListChallengesUseCase,
)
from app.application.challenges.execution_guard import (
    ApplicationExecutionService,
    ApplicationSubmissionRepository,
)
from app.application.challenges.run_challenge import RunChallengeUseCase
from app.application.challenges.submit_challenge import SubmitChallengeUseCase
from app.application.leaderboard import GetChallengeLeaderboardUseCase
from app.application.profile import GetCurrentUserProfileUseCase
from app.application.progression import GetUserProgressUseCase
from app.core.config.settings import Settings, get_settings
from app.core.exceptions import AuthenticationError
from app.domains.auth import AccessTokenVerifier, ApplicationUser, UserRepository
from app.domains.challenges import ChallengeType
from app.domains.challenges.ports import ChallengeReader
from app.domains.evaluation.engine import EvaluationEngine
from app.domains.evaluation.ports import HiddenTestSuiteReader, LLMProvider
from app.domains.execution import ChallengeExecutorResolver, TextChallengeExecutor
from app.domains.execution.application import ApplicationChallengeExecutor
from app.domains.leaderboard import LeaderboardReader
from app.domains.profile import ProfileReader
from app.domains.progression import UserProgressReader
from app.domains.scoring.ports import PromptTokenCounter
from app.domains.scoring.service import ScoringService
from app.domains.submissions import SubmissionRepository
from app.infrastructure.application import (
    LLMCodingAgent,
    LocalWorkspaceFactory,
    PlaywrightApplicationEvaluator,
    StarterProjectRepository,
)
from app.infrastructure.application.sandbox import configured_sandbox
from app.infrastructure.auth import create_access_token_verifier
from app.infrastructure.database import (
    PostgresAdminChallengeRepository,
    PostgresChallengeRepository,
    PostgresHiddenTestSuiteRepository,
    PostgresLeaderboardRepository,
    PostgresProfileRepository,
    PostgresSubmissionRepository,
    PostgresUserProgressRepository,
    PostgresUserRepository,
    create_database_engine,
    create_session_factory,
)
from app.infrastructure.database.application_execution import (
    PostgresApplicationExecutionCoordinator,
)
from app.infrastructure.llm import create_llm_provider
from app.infrastructure.tokenization import GptOssPromptTokenCounter

_bearer_scheme = HTTPBearer(auto_error=False)


def require_admin_authorization(
    settings: Annotated[Settings, Depends(get_settings)],
    x_admin_key: Annotated[str | None, Header(alias="X-Admin-Key")] = None,
) -> None:
    """Transport authorization boundary; admin use cases remain auth-mechanism agnostic."""
    configured = settings.admin_api_key
    if configured is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin API is not configured on this server.",
        )
    expected = configured.get_secret_value()
    supplied = x_admin_key or ""
    if not secrets.compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Admin-Key header.",
        )


async def get_database_session(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncIterator[AsyncSession]:
    factory = create_session_factory(settings)
    async with factory() as session:
        yield session


def get_challenge_reader(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> ChallengeReader:
    return PostgresChallengeRepository(session)


def get_admin_challenge_repository(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> AdminChallengeRepository:
    return PostgresAdminChallengeRepository(session)


def get_list_admin_challenges_use_case(
    repository: Annotated[AdminChallengeRepository, Depends(get_admin_challenge_repository)],
) -> ListAdminChallengesUseCase:
    return ListAdminChallengesUseCase(repository)


def get_admin_challenge_use_case(
    repository: Annotated[AdminChallengeRepository, Depends(get_admin_challenge_repository)],
) -> GetAdminChallengeUseCase:
    return GetAdminChallengeUseCase(repository)


def get_create_challenge_use_case(
    repository: Annotated[AdminChallengeRepository, Depends(get_admin_challenge_repository)],
) -> CreateChallengeUseCase:
    return CreateChallengeUseCase(repository, StarterProjectRepository())


def get_update_challenge_draft_use_case(
    repository: Annotated[AdminChallengeRepository, Depends(get_admin_challenge_repository)],
) -> UpdateChallengeDraftUseCase:
    return UpdateChallengeDraftUseCase(repository, StarterProjectRepository())


def get_create_challenge_version_use_case(
    repository: Annotated[AdminChallengeRepository, Depends(get_admin_challenge_repository)],
) -> CreateChallengeVersionUseCase:
    return CreateChallengeVersionUseCase(repository)


def get_publish_challenge_use_case(
    repository: Annotated[AdminChallengeRepository, Depends(get_admin_challenge_repository)],
) -> PublishChallengeUseCase:
    return PublishChallengeUseCase(repository, StarterProjectRepository())


def get_unpublish_challenge_use_case(
    repository: Annotated[AdminChallengeRepository, Depends(get_admin_challenge_repository)],
) -> UnpublishChallengeUseCase:
    return UnpublishChallengeUseCase(repository)


def get_evaluation_engine() -> EvaluationEngine:
    return EvaluationEngine.with_builtin_graders()


def get_hidden_test_suite_reader(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> HiddenTestSuiteReader:
    return PostgresHiddenTestSuiteRepository(session)


def get_submission_repository(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> SubmissionRepository:
    return PostgresSubmissionRepository(session)


def get_application_execution_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ApplicationExecutionService:
    return ApplicationExecutionService(
        PostgresApplicationExecutionCoordinator(create_database_engine(settings)),
        run_cooldown_seconds=settings.application_run_cooldown_seconds,
        submit_cooldown_seconds=settings.application_submit_cooldown_seconds,
        stale_after_seconds=settings.application_execution_lock_timeout_seconds,
    )


def get_application_submission_repository(
    repository: Annotated[SubmissionRepository, Depends(get_submission_repository)],
) -> ApplicationSubmissionRepository:
    return repository  # type: ignore[return-value]


def get_user_repository(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> UserRepository:
    return PostgresUserRepository(session)


def get_user_progress_reader(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> UserProgressReader:
    return PostgresUserProgressRepository(session)


def get_profile_reader(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> ProfileReader:
    return PostgresProfileRepository(session)


def get_leaderboard_reader(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> LeaderboardReader:
    return PostgresLeaderboardRepository(session)


def get_challenge_leaderboard_use_case(
    challenge_reader: Annotated[ChallengeReader, Depends(get_challenge_reader)],
    leaderboard_reader: Annotated[LeaderboardReader, Depends(get_leaderboard_reader)],
) -> GetChallengeLeaderboardUseCase:
    return GetChallengeLeaderboardUseCase(challenge_reader, leaderboard_reader)


def get_user_progress_use_case(
    reader: Annotated[UserProgressReader, Depends(get_user_progress_reader)],
) -> GetUserProgressUseCase:
    return GetUserProgressUseCase(reader)


def get_current_user_profile_use_case(
    reader: Annotated[ProfileReader, Depends(get_profile_reader)],
) -> GetCurrentUserProfileUseCase:
    return GetCurrentUserProfileUseCase(reader)


def get_access_token_verifier(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AccessTokenVerifier:
    return create_access_token_verifier(settings)


def get_resolve_authenticated_user_use_case(
    verifier: Annotated[AccessTokenVerifier, Depends(get_access_token_verifier)],
    user_repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> ResolveAuthenticatedUserUseCase:
    return ResolveAuthenticatedUserUseCase(verifier, user_repository)


def require_bearer_access_token(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(_bearer_scheme),
    ],
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError()
    return credentials.credentials


async def get_current_user(
    access_token: Annotated[str, Depends(require_bearer_access_token)],
    use_case: Annotated[
        ResolveAuthenticatedUserUseCase,
        Depends(get_resolve_authenticated_user_use_case),
    ],
) -> ApplicationUser:
    return await use_case.execute(access_token)


async def get_optional_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(_bearer_scheme),
    ],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ApplicationUser | None:
    if credentials is None:
        return None
    if credentials.scheme.lower() != "bearer":
        raise AuthenticationError()
    factory = create_session_factory(settings)
    async with factory() as session:
        use_case = ResolveAuthenticatedUserUseCase(
            create_access_token_verifier(settings),
            PostgresUserRepository(session),
        )
        return await use_case.execute(credentials.credentials)


def get_prompt_token_counter() -> PromptTokenCounter:
    return GptOssPromptTokenCounter()


def get_scoring_service() -> ScoringService:
    return ScoringService()


def get_challenge_access_service(
    challenge_reader: Annotated[ChallengeReader, Depends(get_challenge_reader)],
    progress_reader: Annotated[UserProgressReader, Depends(get_user_progress_reader)],
) -> ChallengeAccessService:
    return ChallengeAccessService(challenge_reader, progress_reader)


def get_list_challenges_use_case(
    access_service: Annotated[ChallengeAccessService, Depends(get_challenge_access_service)],
) -> ListChallengesUseCase:
    return ListChallengesUseCase(access_service)


def get_challenge_detail_use_case(
    challenge_reader: Annotated[ChallengeReader, Depends(get_challenge_reader)],
    access_service: Annotated[ChallengeAccessService, Depends(get_challenge_access_service)],
) -> GetChallengeDetailUseCase:
    return GetChallengeDetailUseCase(challenge_reader, access_service)


def get_llm_provider(settings: Annotated[Settings, Depends(get_settings)]) -> LLMProvider:
    return create_llm_provider(settings)


def get_test_challenge_use_case(
    settings: Annotated[Settings, Depends(get_settings)],
    repository: Annotated[AdminChallengeRepository, Depends(get_admin_challenge_repository)],
    llm_provider: Annotated[LLMProvider, Depends(get_llm_provider)],
    evaluation_engine: Annotated[EvaluationEngine, Depends(get_evaluation_engine)],
    prompt_token_counter: Annotated[PromptTokenCounter, Depends(get_prompt_token_counter)],
    scoring_service: Annotated[ScoringService, Depends(get_scoring_service)],
) -> TestChallengeUseCase:
    return TestChallengeUseCase(
        repository,
        llm_provider,
        evaluation_engine,
        prompt_token_counter,
        scoring_service,
        ApplicationChallengeExecutor(
            LLMCodingAgent(llm_provider),
            LocalWorkspaceFactory(StarterProjectRepository()),
            PlaywrightApplicationEvaluator(settings.application_browser_channel),
            StarterProjectRepository(),
            configured_sandbox(settings),
        ),
    )


def get_starter_project_repository() -> StarterProjectRepository:
    return StarterProjectRepository()


def get_starter_preview_use_case(
    challenge_reader: Annotated[ChallengeReader, Depends(get_challenge_reader)],
    starters: Annotated[StarterProjectRepository, Depends(get_starter_project_repository)],
) -> GetStarterPreviewUseCase:
    return GetStarterPreviewUseCase(challenge_reader, starters)


def get_challenge_executor_resolver(
    settings: Annotated[Settings, Depends(get_settings)],
    llm_provider: Annotated[LLMProvider, Depends(get_llm_provider)],
    evaluation_engine: Annotated[EvaluationEngine, Depends(get_evaluation_engine)],
    hidden_test_suite_reader: Annotated[
        HiddenTestSuiteReader,
        Depends(get_hidden_test_suite_reader),
    ],
    starters: Annotated[StarterProjectRepository, Depends(get_starter_project_repository)],
) -> ChallengeExecutorResolver:
    # TEXT and the APPLICATION prototype are executable; IMAGE fails explicitly on resolve.
    return ChallengeExecutorResolver(
        {
            ChallengeType.TEXT: TextChallengeExecutor(
                llm_provider,
                evaluation_engine,
                hidden_test_suite_reader,
            ),
            ChallengeType.APPLICATION: ApplicationChallengeExecutor(
                LLMCodingAgent(llm_provider),
                LocalWorkspaceFactory(starters),
                PlaywrightApplicationEvaluator(settings.application_browser_channel),
                StarterProjectRepository(),
                configured_sandbox(settings),
            ),
        }
    )


def get_run_challenge_use_case(
    challenge_reader: Annotated[ChallengeReader, Depends(get_challenge_reader)],
    executor_resolver: Annotated[
        ChallengeExecutorResolver,
        Depends(get_challenge_executor_resolver),
    ],
    access_service: Annotated[ChallengeAccessService, Depends(get_challenge_access_service)],
    application_execution_service: Annotated[
        ApplicationExecutionService,
        Depends(get_application_execution_service),
    ],
) -> RunChallengeUseCase:
    return RunChallengeUseCase(
        challenge_reader=challenge_reader,
        executor_resolver=executor_resolver,
        access_service=access_service,
        application_execution_service=application_execution_service,
    )


def get_submit_challenge_use_case(
    challenge_reader: Annotated[ChallengeReader, Depends(get_challenge_reader)],
    executor_resolver: Annotated[
        ChallengeExecutorResolver,
        Depends(get_challenge_executor_resolver),
    ],
    prompt_token_counter: Annotated[
        PromptTokenCounter,
        Depends(get_prompt_token_counter),
    ],
    scoring_service: Annotated[ScoringService, Depends(get_scoring_service)],
    submission_repository: Annotated[
        SubmissionRepository,
        Depends(get_submission_repository),
    ],
    access_service: Annotated[ChallengeAccessService, Depends(get_challenge_access_service)],
    application_execution_service: Annotated[
        ApplicationExecutionService,
        Depends(get_application_execution_service),
    ],
    application_submission_repository: Annotated[
        ApplicationSubmissionRepository,
        Depends(get_application_submission_repository),
    ],
) -> SubmitChallengeUseCase:
    return SubmitChallengeUseCase(
        challenge_reader=challenge_reader,
        executor_resolver=executor_resolver,
        prompt_token_counter=prompt_token_counter,
        scoring_service=scoring_service,
        submission_repository=submission_repository,
        access_service=access_service,
        application_execution_service=application_execution_service,
        application_submission_repository=application_submission_repository,
    )


def get_application_packages_use_case():
    from app.application.admin.use_cases import ListApplicationPackagesUseCase

    return ListApplicationPackagesUseCase(StarterProjectRepository())


def get_application_sandbox(settings: Annotated[Settings, Depends(get_settings)]):
    return configured_sandbox(settings)


def get_package_health(settings: Annotated[Settings, Depends(get_settings)]):
    from app.application.admin.package_health import ApplicationPackageHealth

    packages = StarterProjectRepository()
    return ApplicationPackageHealth(
        packages,
        LocalWorkspaceFactory(packages),
        configured_sandbox(settings),
        PlaywrightApplicationEvaluator(settings.application_browser_channel),
    )
