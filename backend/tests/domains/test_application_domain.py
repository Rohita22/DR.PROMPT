import json
from dataclasses import replace

import pytest

from app.domains.application.checks import (
    ApplicationCheckRegistry,
    ApplicationFacts,
    CheckDefinition,
    landmarks_unchanged,
)
from app.domains.application.edits import FileEdit, parse_agent_edits
from app.domains.application.errors import AgentOutputError, ApplicationConfigurationError
from app.domains.application.models import (
    ApplicationChallengeConfig,
    ApplicationLimits,
    normalize_relative_path,
)
from app.infrastructure.application.starter_projects import StarterProjectRepository
from app.infrastructure.challenges.application_fixtures import RESPONSIVE_HERO_CONFIG
from tests.fakes.application import (
    edit_output,
    layout,
    responsive_layouts,
    starter_layouts,
    starter_text,
)

PACKAGE = StarterProjectRepository().load("responsive-hero")
CHECKS = {c.id: c for c in PACKAGE.checks}


def evaluate_checks(ids, facts):
    checks = tuple(CHECKS.get(id, CheckDefinition(id, id, "Unknown")) for id in ids)
    return ApplicationCheckRegistry().evaluate(checks, facts)


ORIGINALS = {"src/index.html": "<main></main>", "src/styles.css": "body { margin: 0; }"}
LIMITS = ApplicationLimits(max_file_bytes=200, max_files=2)


def reason(raw: str) -> str:
    with pytest.raises(AgentOutputError) as raised:
        parse_agent_edits(raw, ORIGINALS, LIMITS)
    return raised.value.reason


def test_valid_edits_are_parsed_including_a_single_json_fence() -> None:
    raw = edit_output(**{"src/styles.css": "body { margin: 1px; }"})
    expected = (FileEdit("src/styles.css", "body { margin: 1px; }"),)
    assert parse_agent_edits(raw, ORIGINALS, LIMITS) == expected
    assert parse_agent_edits(f"```json\n{raw}\n```", ORIGINALS, LIMITS) == expected


@pytest.mark.parametrize(
    ("raw", "expected_reason"),
    [
        ("Sure! Here is the CSS: body { margin: 1px }", "malformed"),
        ("[]", "malformed"),
        (json.dumps({"files": [], "note": "x"}), "malformed"),
        (json.dumps({"files": "src/styles.css"}), "malformed"),
        (json.dumps({"files": [{"path": "src/styles.css"}]}), "malformed"),
        (json.dumps({"files": [{"path": "src/styles.css", "content": 3}]}), "malformed"),
        (
            json.dumps({"files": [{"path": "src/styles.css", "content": "", "mode": 7}]}),
            "malformed",
        ),
        (json.dumps({"files": []}), "no_changes"),
        (edit_output(**{"src/styles.css": ORIGINALS["src/styles.css"]}), "no_changes"),
        (edit_output(**{"../secrets.env": "x"}), "unsafe_path"),
        (edit_output(**{"src/../build.mjs": "x"}), "unsafe_path"),
        (edit_output(**{"/etc/passwd": "x"}), "unsafe_path"),
        (edit_output(**{"C:/Windows/win.ini": "x"}), "unsafe_path"),
        (edit_output(**{"src\\styles.css": "x"}), "unsafe_path"),
        (edit_output(**{"./src/styles.css": "x"}), "unsafe_path"),
        (edit_output(**{"build.mjs": "process.exit(0)"}), "forbidden_file"),
        (edit_output(**{".env": "GROQ_API_KEY=x"}), "forbidden_file"),
        (edit_output(**{"src/styles.css": "x" * 201}), "file_too_large"),
    ],
)
def test_invalid_agent_responses_are_rejected(raw: str, expected_reason: str) -> None:
    assert reason(raw) == expected_reason


def test_duplicate_paths_and_too_many_files_are_rejected() -> None:
    duplicate = json.dumps(
        {
            "files": [
                {"path": "src/styles.css", "content": "a"},
                {"path": "src/styles.css", "content": "b"},
            ]
        }
    )
    assert reason(duplicate) == "duplicate_file"
    three = json.dumps({"files": [{"path": "src/styles.css", "content": str(i)} for i in range(3)]})
    assert reason(three) == "too_many_files"


def test_relative_path_normalization_rejects_every_escape_form() -> None:
    assert normalize_relative_path("src/styles.css") == "src/styles.css"
    for unsafe in ("", " src/a", "../a", "a/../b", "/a", "a//b", "a\\b", "C:a", "a\x00b", "."):
        assert normalize_relative_path(unsafe) is None


def test_application_config_rejects_unsafe_or_inconsistent_definitions() -> None:
    for changes in (
        {"editable_files": ("../outside.css",)},
        {"page_source": "../other.html"},
        {"build_command": ()},
        {"hidden_checks": ()},
        {"starter_project": "../responsive_hero"},
        {"build_output": "/tmp/index.html"},
    ):
        with pytest.raises(ApplicationConfigurationError):
            replace(RESPONSIVE_HERO_CONFIG, **changes)
    assert isinstance(RESPONSIVE_HERO_CONFIG, ApplicationChallengeConfig)


def facts(layouts, **overrides) -> ApplicationFacts:
    values = {
        "build_succeeded": True,
        "protected_files_unchanged": True,
        "starter_html": "<header>Header</header><footer>Footer</footer>",
        "result_html": "<header>Header</header><footer>Footer</footer>",
        "layouts": layouts,
    }
    values.update(overrides)
    return ApplicationFacts(**values)


def passed(check_ids, value: ApplicationFacts) -> list[bool]:
    return [outcome.passed for outcome in evaluate_checks(check_ids, value)]


def test_responsive_result_passes_every_visible_and_hidden_check() -> None:
    value = facts(responsive_layouts())
    assert all(passed(RESPONSIVE_HERO_CONFIG.visible_checks, value))
    assert all(passed(RESPONSIVE_HERO_CONFIG.hidden_checks, value))


def test_unchanged_starter_fails_the_layout_requirements() -> None:
    value = facts(starter_layouts())
    outcomes = {o.check_id: o for o in evaluate_checks(tuple(CHECKS), value)}
    assert not outcomes["desktop_two_column"].passed
    assert not outcomes["wide_two_column"].passed
    assert not outcomes["mobile_no_overflow"].passed
    assert not outcomes["small_no_overflow"].passed
    assert outcomes["desktop_two_column"].message is not None
    assert passed(RESPONSIVE_HERO_CONFIG.hidden_checks, value).count(True) == 5


def test_reversed_columns_hidden_cta_and_missing_hero_fail() -> None:
    layouts = responsive_layouts()
    desktop = layouts["desktop"]
    c, v, cta = '[data-role="hero-content"]', '[data-role="hero-visual"]', '[data-role="hero-cta"]'
    layouts["desktop"] = replace(
        desktop, elements={**desktop.elements, c: desktop.elements[v], v: desktop.elements[c]}
    )
    assert passed(("desktop_two_column",), facts(layouts)) == [False]
    layouts = responsive_layouts()
    desktop = layouts["desktop"]
    button = desktop.elements[cta][0]
    layouts["desktop"] = replace(
        desktop,
        elements={**desktop.elements, cta: (replace(button, box=replace(button.box, y=900)),)},
    )
    assert passed(("cta_visible",), facts(layouts)) == [False]
    layouts = responsive_layouts()
    mobile = layouts["mobile"]
    layouts["mobile"] = replace(mobile, elements={**mobile.elements, c: (), cta: ()})
    assert passed(("mobile_stacked", "cta_interactive"), facts(layouts)) == [False, False]


def test_build_failure_fails_build_and_layout_checks_deterministically() -> None:
    value = facts({}, build_succeeded=False)
    outcomes = evaluate_checks(RESPONSIVE_HERO_CONFIG.visible_checks, value)
    assert [o.passed for o in outcomes] == [False, False, False, False]
    assert outcomes[1].message == "Not measured because the page did not build."


def test_semantic_landmark_and_protected_checks() -> None:
    layouts = responsive_layouts()
    layouts["desktop"] = replace(
        layouts["desktop"], elements={**layouts["desktop"].elements, "h1": ()}
    )
    assert passed(("semantic_structure",), facts(layouts)) == [False]
    assert passed(
        ("landmarks_unchanged",),
        facts(layouts, result_html="<header>Changed</header><footer>Footer</footer>"),
    ) == [False]
    assert passed(
        ("protected_files_unchanged",), facts(layouts, protected_files_unchanged=False)
    ) == [False]


def test_unknown_checks_fail_explicitly() -> None:
    with pytest.raises(ApplicationConfigurationError):
        evaluate_checks(("does_not_exist",), facts(responsive_layouts()))


def test_landmark_comparison_ignores_whitespace_but_not_content() -> None:
    html = starter_text("src/index.html")
    assert landmarks_unchanged(html, html.replace("\n    ", "\n"))
    assert landmarks_unchanged(html, html.replace("hero-content", "hero-copy"))
    assert not landmarks_unchanged(html, html.replace("Pricing", "Plans"))
    assert not landmarks_unchanged(
        html, html.replace("<footer", "<div").replace("</footer>", "</div>")
    )


def test_synthetic_layout_helper_is_consistent() -> None:
    assert (
        layout(1280, 800, two_column=True).elements['[data-role="hero-content"]'][0].box.right
        <= layout(1280, 800, two_column=True).elements['[data-role="hero-visual"]'][0].box.x
    )
