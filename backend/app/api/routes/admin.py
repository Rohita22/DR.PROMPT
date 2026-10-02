from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import (
    get_admin_challenge_use_case,
    get_application_packages_use_case,
    get_create_challenge_use_case,
    get_create_challenge_version_use_case,
    get_list_admin_challenges_use_case,
    get_package_health,
    get_publish_challenge_use_case,
    get_starter_project_repository,
    get_test_challenge_use_case,
    get_unpublish_challenge_use_case,
    get_update_challenge_draft_use_case,
    require_admin_authorization,
)
from app.api.schemas.admin import (
    AdminChallengeDetailResponse,
    AdminChallengeListItemResponse,
    AdminChallengeListResponse,
    ApplicationPackageResponse,
    PublishChallengeRequest,
    TestChallengeRequest,
    TestChallengeResponse,
    UpsertChallengeRequest,
    UpsertChallengeResponse,
)
from app.application.admin import (
    CreateChallengeUseCase,
    CreateChallengeVersionUseCase,
    GetAdminChallengeUseCase,
    ListAdminChallengesUseCase,
    PublishChallengeUseCase,
    TestChallengeUseCase,
    UnpublishChallengeUseCase,
    UpdateChallengeDraftUseCase,
)
from app.application.admin.models import CreateChallengeCommand, UpdateChallengeDraftCommand
from app.application.admin.package_health import ApplicationPackageHealth
from app.application.admin.use_cases import ListApplicationPackagesUseCase
from app.domains.application.ports import StarterPreviewReader
from app.domains.challenges.errors import ChallengeNotFoundError

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin_authorization)],
)


@router.get("/challenges", response_model=AdminChallengeListResponse)
async def list_challenges(
    use_case: Annotated[
        ListAdminChallengesUseCase,
        Depends(get_list_admin_challenges_use_case),
    ],
) -> AdminChallengeListResponse:
    items = await use_case.execute()
    return AdminChallengeListResponse(
        challenges=[AdminChallengeListItemResponse.from_summary(item) for item in items]
    )


@router.get("/challenges/{slug}", response_model=AdminChallengeDetailResponse)
async def get_challenge(
    slug: str,
    use_case: Annotated[GetAdminChallengeUseCase, Depends(get_admin_challenge_use_case)],
) -> AdminChallengeDetailResponse:
    return AdminChallengeDetailResponse.from_record(await use_case.execute(slug))


@router.post(
    "/challenges",
    response_model=UpsertChallengeResponse,
    status_code=status.HTTP_200_OK,
)
async def create_challenge(
    request: UpsertChallengeRequest,
    use_case: Annotated[CreateChallengeUseCase, Depends(get_create_challenge_use_case)],
) -> UpsertChallengeResponse:
    result = await use_case.execute(
        CreateChallengeCommand(
            definition=request.to_spec(),
            publish=request.publication_state == "published",
        )
    )
    return UpsertChallengeResponse.from_result(result)


@router.put("/challenges/{slug}", response_model=UpsertChallengeResponse)
async def update_challenge(
    slug: str,
    request: UpsertChallengeRequest,
    use_case: Annotated[
        UpdateChallengeDraftUseCase,
        Depends(get_update_challenge_draft_use_case),
    ],
) -> UpsertChallengeResponse:
    result = await use_case.execute(
        UpdateChallengeDraftCommand(challenge_slug=slug, definition=request.to_spec())
    )
    return UpsertChallengeResponse.from_result(result)


@router.post("/challenges/{slug}/versions", response_model=UpsertChallengeResponse)
async def create_challenge_version(
    slug: str,
    use_case: Annotated[
        CreateChallengeVersionUseCase,
        Depends(get_create_challenge_version_use_case),
    ],
) -> UpsertChallengeResponse:
    return UpsertChallengeResponse.from_result(await use_case.execute(slug))


@router.post("/challenges/{slug}/test", response_model=TestChallengeResponse)
async def test_challenge(
    slug: str,
    request: TestChallengeRequest,
    use_case: Annotated[TestChallengeUseCase, Depends(get_test_challenge_use_case)],
) -> TestChallengeResponse:
    return TestChallengeResponse.from_result(await use_case.execute(slug, request.prompt))


@router.post("/challenges/{slug}/publish", response_model=UpsertChallengeResponse)
async def publish_challenge(
    slug: str,
    request: PublishChallengeRequest,
    use_case: Annotated[
        PublishChallengeUseCase,
        Depends(get_publish_challenge_use_case),
    ],
) -> UpsertChallengeResponse:
    return UpsertChallengeResponse.from_result(await use_case.execute(slug, request.version))


@router.post("/challenges/{slug}/unpublish", response_model=UpsertChallengeResponse)
async def unpublish_challenge(
    slug: str,
    use_case: Annotated[
        UnpublishChallengeUseCase,
        Depends(get_unpublish_challenge_use_case),
    ],
) -> UpsertChallengeResponse:
    return UpsertChallengeResponse.from_result(await use_case.execute(slug))


@router.get("/application-packages", response_model=list[ApplicationPackageResponse])
async def application_packages(
    use_case: Annotated[ListApplicationPackagesUseCase, Depends(get_application_packages_use_case)],
):
    return [ApplicationPackageResponse.from_package(p) for p in use_case.execute()]


@router.get("/application-packages/{package_id}/preview/{viewport}.png")
async def package_preview(
    package_id: str,
    viewport: str,
    packages: Annotated[StarterPreviewReader, Depends(get_starter_project_repository)],
):
    png = packages.preview_png(package_id, viewport)
    if png is None:
        raise ChallengeNotFoundError("Package preview was not found.")
    return Response(png, media_type="image/png")


@router.post("/application-packages/{package_id}/health")
async def package_health(
    package_id: str, use_case: Annotated[ApplicationPackageHealth, Depends(get_package_health)]
):
    return await use_case.execute(package_id)
