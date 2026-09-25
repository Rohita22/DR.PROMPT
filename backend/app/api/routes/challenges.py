from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_run_challenge_use_case
from app.api.schemas.challenges import RunChallengeRequest, RunChallengeResponse
from app.application.challenges.models import RunChallengeCommand
from app.application.challenges.run_challenge import RunChallengeUseCase

router = APIRouter(tags=["challenges"])


@router.post("/{challenge_slug}/run", response_model=RunChallengeResponse)
async def run_challenge(
    challenge_slug: str,
    request: RunChallengeRequest,
    use_case: Annotated[RunChallengeUseCase, Depends(get_run_challenge_use_case)],
) -> RunChallengeResponse:
    result = await use_case.execute(
        RunChallengeCommand(
            challenge_slug=challenge_slug,
            player_prompt=request.prompt,
        )
    )
    return RunChallengeResponse.from_application_result(result)
