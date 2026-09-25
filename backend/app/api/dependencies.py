from typing import Annotated

from fastapi import Depends

from app.application.challenges.run_challenge import RunChallengeUseCase
from app.core.config.settings import Settings, get_settings
from app.domains.challenges.ports import ChallengeReader
from app.domains.evaluation.engine import EvaluationEngine
from app.domains.evaluation.ports import LLMProvider
from app.infrastructure.challenges import InMemoryChallengeRepository
from app.infrastructure.llm import create_llm_provider


def get_challenge_reader() -> ChallengeReader:
    return InMemoryChallengeRepository()


def get_evaluation_engine() -> EvaluationEngine:
    return EvaluationEngine.with_builtin_graders()


def get_llm_provider(settings: Annotated[Settings, Depends(get_settings)]) -> LLMProvider:
    return create_llm_provider(settings)


def get_run_challenge_use_case(
    challenge_reader: Annotated[ChallengeReader, Depends(get_challenge_reader)],
    llm_provider: Annotated[LLMProvider, Depends(get_llm_provider)],
    evaluation_engine: Annotated[EvaluationEngine, Depends(get_evaluation_engine)],
) -> RunChallengeUseCase:
    return RunChallengeUseCase(
        challenge_reader=challenge_reader,
        llm_provider=llm_provider,
        evaluation_engine=evaluation_engine,
    )
