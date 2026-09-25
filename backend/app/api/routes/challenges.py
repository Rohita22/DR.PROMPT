from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import (
    get_challenge_detail_use_case,
    get_current_user,
    get_list_challenges_use_case,
    get_optional_current_user,
    get_run_challenge_use_case,
    get_submit_challenge_use_case,
)
from app.api.schemas.challenges import (
    ChallengeDetailResponse,
    ChallengeListItemResponse,
    ChallengeListResponse,
    RunChallengeRequest,
    RunChallengeResponse,
    SubmitChallengeRequest,
    SubmitChallengeResponse,
)
from app.application.challenges import GetChallengeDetailUseCase, ListChallengesUseCase
from app.application.challenges.models import RunChallengeCommand, SubmitChallengeCommand
from app.application.challenges.run_challenge import RunChallengeUseCase
from app.application.challenges.submit_challenge import SubmitChallengeUseCase
from app.domains.auth import ApplicationUser

router = APIRouter(tags=["challenges"])


@router.get("", response_model=ChallengeListResponse)
async def list_challenges(
    current_user: Annotated[ApplicationUser | None, Depends(get_optional_current_user)],
    use_case: Annotated[ListChallengesUseCase, Depends(get_list_challenges_use_case)],
) -> ChallengeListResponse:
    items = await use_case.execute(current_user.id if current_user is not None else None)
    return ChallengeListResponse(
        challenges=[ChallengeListItemResponse.from_access(item) for item in items]
    )


@router.get("/{challenge_slug}", response_model=ChallengeDetailResponse)
async def get_challenge_detail(
    challenge_slug: str,
    current_user: Annotated[ApplicationUser | None, Depends(get_optional_current_user)],
    use_case: Annotated[GetChallengeDetailUseCase, Depends(get_challenge_detail_use_case)],
) -> ChallengeDetailResponse:
    playable, access = await use_case.execute(
        challenge_slug,
        current_user.id if current_user is not None else None,
    )
    return ChallengeDetailResponse.from_domain(playable, access)


@router.post("/{challenge_slug}/run", response_model=RunChallengeResponse)
async def run_challenge(
    challenge_slug: str,
    request: RunChallengeRequest,
    current_user: Annotated[ApplicationUser | None, Depends(get_optional_current_user)],
    use_case: Annotated[RunChallengeUseCase, Depends(get_run_challenge_use_case)],
) -> RunChallengeResponse:
    result = await use_case.execute(
        RunChallengeCommand(
            challenge_slug=challenge_slug,
            player_prompt=request.prompt,
            owner_user_id=current_user.id if current_user is not None else None,
        )
    )
    return RunChallengeResponse.from_application_result(result)


@router.post("/{challenge_slug}/submit", response_model=SubmitChallengeResponse)
async def submit_challenge(
    challenge_slug: str,
    request: SubmitChallengeRequest,
    current_user: Annotated[ApplicationUser, Depends(get_current_user)],
    use_case: Annotated[
        SubmitChallengeUseCase,
        Depends(get_submit_challenge_use_case),
    ],
) -> SubmitChallengeResponse:
    result = await use_case.execute(
        SubmitChallengeCommand(
            challenge_slug=challenge_slug,
            player_prompt=request.prompt,
            owner_user_id=current_user.id,
        )
    )
    return SubmitChallengeResponse.from_application_result(result)
