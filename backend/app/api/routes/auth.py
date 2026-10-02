from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import (
    get_current_user,
    get_current_user_profile_use_case,
    get_user_progress_use_case,
)
from app.api.schemas.auth import MeProfileResponse, MeProgressResponse, MeResponse
from app.application.profile import GetCurrentUserProfileUseCase
from app.application.progression import GetUserProgressUseCase
from app.domains.auth import ApplicationUser

router = APIRouter(tags=["authentication"])


@router.get("/me", response_model=MeResponse)
async def get_me(
    current_user: Annotated[ApplicationUser, Depends(get_current_user)],
) -> MeResponse:
    return MeResponse.from_user(current_user)


@router.get("/me/progress", response_model=MeProgressResponse)
async def get_me_progress(
    current_user: Annotated[ApplicationUser, Depends(get_current_user)],
    use_case: Annotated[GetUserProgressUseCase, Depends(get_user_progress_use_case)],
) -> MeProgressResponse:
    result = await use_case.execute(current_user.id)
    return MeProgressResponse.from_application_result(result)


@router.get("/me/profile", response_model=MeProfileResponse)
async def get_me_profile(
    current_user: Annotated[ApplicationUser, Depends(get_current_user)],
    use_case: Annotated[
        GetCurrentUserProfileUseCase,
        Depends(get_current_user_profile_use_case),
    ],
) -> MeProfileResponse:
    result = await use_case.execute(current_user)
    return MeProfileResponse.from_application_result(result)
