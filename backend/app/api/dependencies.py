from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.auth import ResolveAuthenticatedUserUseCase
from app.application.challenges import (
    ChallengeAccessService,
    GetChallengeDetailUseCase,
    ListChallengesUseCase,
)
from app.application.challenges.run_challenge import RunChallengeUseCase
from app.application.challenges.submit_challenge import SubmitChallengeUseCase
from app.application.progression import GetUserProgressUseCase
from app.core.config.settings import Settings, get_settings
from app.core.exceptions import AuthenticationError
from app.domains.auth import AccessTokenVerifier, ApplicationUser, UserRepository
from app.domains.challenges.ports import ChallengeReader
from app.domains.evaluation.engine import EvaluationEngine
from app.domains.evaluation.ports import HiddenTestSuiteReader, LLMProvider
from app.domains.progression import UserProgressReader
from app.domains.scoring.ports import PromptTokenCounter
from app.domains.scoring.service import ScoringService
from app.domains.submissions import SubmissionRepository
from app.infrastructure.auth import create_access_token_verifier
from app.infrastructure.database import (
    PostgresChallengeRepository,
    PostgresHiddenTestSuiteRepository,
    PostgresSubmissionRepository,
    PostgresUserProgressRepository,
    PostgresUserRepository,
    create_session_factory,
)
from app.infrastructure.llm import create_llm_provider
from app.infrastructure.tokenization import GptOssPromptTokenCounter

_bearer_scheme = HTTPBearer(auto_error=False)


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


def get_user_repository(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> UserRepository:
    return PostgresUserRepository(session)


def get_user_progress_reader(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> UserProgressReader:
    return PostgresUserProgressRepository(session)


def get_user_progress_use_case(
    reader: Annotated[UserProgressReader, Depends(get_user_progress_reader)],
) -> GetUserProgressUseCase:
    return GetUserProgressUseCase(reader)


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


def get_run_challenge_use_case(
    challenge_reader: Annotated[ChallengeReader, Depends(get_challenge_reader)],
    llm_provider: Annotated[LLMProvider, Depends(get_llm_provider)],
    evaluation_engine: Annotated[EvaluationEngine, Depends(get_evaluation_engine)],
    access_service: Annotated[ChallengeAccessService, Depends(get_challenge_access_service)],
) -> RunChallengeUseCase:
    return RunChallengeUseCase(
        challenge_reader=challenge_reader,
        llm_provider=llm_provider,
        evaluation_engine=evaluation_engine,
        access_service=access_service,
    )


def get_submit_challenge_use_case(
    challenge_reader: Annotated[ChallengeReader, Depends(get_challenge_reader)],
    hidden_test_suite_reader: Annotated[
        HiddenTestSuiteReader,
        Depends(get_hidden_test_suite_reader),
    ],
    llm_provider: Annotated[LLMProvider, Depends(get_llm_provider)],
    evaluation_engine: Annotated[EvaluationEngine, Depends(get_evaluation_engine)],
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
) -> SubmitChallengeUseCase:
    return SubmitChallengeUseCase(
        challenge_reader=challenge_reader,
        hidden_test_suite_reader=hidden_test_suite_reader,
        llm_provider=llm_provider,
        evaluation_engine=evaluation_engine,
        prompt_token_counter=prompt_token_counter,
        scoring_service=scoring_service,
        submission_repository=submission_repository,
        access_service=access_service,
    )
