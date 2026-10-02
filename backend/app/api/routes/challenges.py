from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response

from app.api.dependencies import (
    get_application_sandbox,
    get_challenge_detail_use_case,
    get_challenge_leaderboard_use_case,
    get_current_user,
    get_list_challenges_use_case,
    get_optional_current_user,
    get_run_challenge_use_case,
    get_starter_preview_use_case,
    get_submit_challenge_use_case,
)
from app.api.schemas.challenges import (
    ApplicationRunResponse,
    ApplicationSubmitResponse,
    ChallengeDetailResponse,
    ChallengeLeaderboardResponse,
    ChallengeListItemResponse,
    ChallengeListResponse,
    RunChallengeRequest,
    RunChallengeResponse,
    SubmitChallengeRequest,
    SubmitChallengeResponse,
)
from app.application.challenges import (
    GetChallengeDetailUseCase,
    GetStarterPreviewUseCase,
    ListChallengesUseCase,
)
from app.application.challenges.models import (
    ApplicationRunResult,
    ApplicationSubmitResult,
    RunChallengeCommand,
    SubmitChallengeCommand,
)
from app.application.challenges.run_challenge import RunChallengeUseCase
from app.application.challenges.submit_challenge import SubmitChallengeUseCase
from app.application.leaderboard import GetChallengeLeaderboardUseCase
from app.domains.application.sandbox import ApplicationSandbox
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


@router.get(
    "/{challenge_slug}/leaderboard",
    response_model=ChallengeLeaderboardResponse,
)
async def get_challenge_leaderboard(
    challenge_slug: str,
    current_user: Annotated[ApplicationUser | None, Depends(get_optional_current_user)],
    use_case: Annotated[
        GetChallengeLeaderboardUseCase,
        Depends(get_challenge_leaderboard_use_case),
    ],
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ChallengeLeaderboardResponse:
    result = await use_case.execute(
        challenge_slug,
        limit=limit,
        offset=offset,
        current_user_id=current_user.id if current_user is not None else None,
    )
    return ChallengeLeaderboardResponse.from_application_result(result)


@router.get(
    "/{challenge_slug}/starter-preview/{viewport}.png",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
)
async def get_starter_preview(
    challenge_slug: str,
    viewport: str,
    use_case: Annotated[GetStarterPreviewUseCase, Depends(get_starter_preview_use_case)],
) -> Response:
    png = await use_case.execute(challenge_slug, viewport)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/{challenge_slug}", response_model=ChallengeDetailResponse)
async def get_challenge_detail(
    challenge_slug: str,
    current_user: Annotated[ApplicationUser | None, Depends(get_optional_current_user)],
    use_case: Annotated[GetChallengeDetailUseCase, Depends(get_challenge_detail_use_case)],
    sandbox: Annotated[ApplicationSandbox, Depends(get_application_sandbox)],
) -> ChallengeDetailResponse:
    playable, access = await use_case.execute(
        challenge_slug,
        current_user.id if current_user is not None else None,
    )
    response = ChallengeDetailResponse.from_domain(playable, access)
    if response.application and response.application.execution_mode == "sandboxed_executable":
        response.application.available = (await sandbox.capability()).available
    return response


@router.post(
    "/{challenge_slug}/run",
    response_model=RunChallengeResponse | ApplicationRunResponse,
)
async def run_challenge(
    challenge_slug: str,
    request: RunChallengeRequest,
    current_user: Annotated[ApplicationUser | None, Depends(get_optional_current_user)],
    use_case: Annotated[RunChallengeUseCase, Depends(get_run_challenge_use_case)],
) -> RunChallengeResponse | ApplicationRunResponse:
    result = await use_case.execute(
        RunChallengeCommand(
            challenge_slug=challenge_slug,
            player_prompt=request.prompt,
            owner_user_id=current_user.id if current_user is not None else None,
        )
    )
    if isinstance(result, ApplicationRunResult):
        return ApplicationRunResponse.from_application_result(result)
    return RunChallengeResponse.from_application_result(result)


@router.post(
    "/{challenge_slug}/submit",
    response_model=SubmitChallengeResponse | ApplicationSubmitResponse,
)
async def submit_challenge(
    challenge_slug: str,
    request: SubmitChallengeRequest,
    current_user: Annotated[ApplicationUser, Depends(get_current_user)],
    use_case: Annotated[
        SubmitChallengeUseCase,
        Depends(get_submit_challenge_use_case),
    ],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> SubmitChallengeResponse | ApplicationSubmitResponse:
    result = await use_case.execute(
        SubmitChallengeCommand(
            challenge_slug=challenge_slug,
            player_prompt=request.prompt,
            owner_user_id=current_user.id,
            idempotency_key=idempotency_key,
        )
    )
    if isinstance(result, ApplicationSubmitResult):
        return ApplicationSubmitResponse.from_application_result(result)
    return SubmitChallengeResponse.from_application_result(result)
