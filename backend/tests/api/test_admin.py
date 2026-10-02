import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_list_admin_challenges_use_case
from app.api.schemas.admin import TestCaseInput as AdminTestCaseInput
from app.core.config.settings import get_settings
from app.main import app


class EmptyListUseCase:
    async def execute(self):
        return ()


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_admin_api_rejects_missing_and_incorrect_keys() -> None:
    app.dependency_overrides[get_settings] = lambda: type(
        "SettingsStub",
        (),
        {"admin_api_key": type("Secret", (), {"get_secret_value": lambda self: "correct"})()},
    )()
    client = TestClient(app)
    assert client.get("/api/v1/admin/challenges").status_code == 401
    assert (
        client.get("/api/v1/admin/challenges", headers={"X-Admin-Key": "incorrect"}).status_code
        == 401
    )


def test_admin_list_accepts_valid_key_without_returning_secret() -> None:
    app.dependency_overrides[get_settings] = lambda: type(
        "SettingsStub",
        (),
        {"admin_api_key": type("Secret", (), {"get_secret_value": lambda self: "correct"})()},
    )()
    app.dependency_overrides[get_list_admin_challenges_use_case] = lambda: EmptyListUseCase()
    response = TestClient(app).get("/api/v1/admin/challenges", headers={"X-Admin-Key": "correct"})
    assert response.status_code == 200
    assert response.json() == {"challenges": []}
    assert "correct" not in response.text


@pytest.mark.parametrize(
    ("grader", "expected_type"),
    [
        ({"type": "exact_match"}, "exact_match"),
        ({"type": "case_insensitive_exact_match"}, "case_insensitive_exact_match"),
        ({"type": "allowed_label", "allowed_labels": ["YES", "NO"]}, "allowed_label"),
        ({"type": "json_schema", "schema": {"type": "object"}}, "json_schema"),
        ({"type": "field_comparison", "fields": ["category"]}, "field_comparison"),
        ({"type": "array_comparison", "order_matters": False}, "array_comparison"),
    ],
)
def test_admin_schema_supports_every_deterministic_grader(grader, expected_type) -> None:
    parsed = AdminTestCaseInput.model_validate(
        {"id": "test-1", "input": "input", "expected_output": "output", "grader": grader}
    )
    assert parsed.grader.type == expected_type
