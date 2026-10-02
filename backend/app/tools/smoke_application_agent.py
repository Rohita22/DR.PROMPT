"""Opt-in real-provider smoke matrix for the Responsive Hero coding agent.

This command never persists submissions or XP. It prints only bounded operational
measurements and safe project-owned failure categories.
"""

import argparse
import asyncio
import os
import time
from dataclasses import dataclass
from pathlib import Path

from app.core.config.settings import Settings
from app.domains.application.edits import parse_agent_edits
from app.domains.application.models import SourceFile
from app.domains.application.ports import AgentTask
from app.domains.evaluation.model_execution import LLMExecutionRequest, LLMExecutionResult
from app.domains.evaluation.ports import LLMProvider
from app.domains.execution.application import ApplicationChallengeExecutor
from app.domains.execution.models import (
    AgentStatus,
    BuildArtifact,
    ChallengeExecutionRequest,
    ChangedFilesArtifact,
    ScreenshotArtifact,
)
from app.infrastructure.application import (
    LLMCodingAgent,
    LocalWorkspaceFactory,
    PlaywrightApplicationEvaluator,
    StarterProjectRepository,
)
from app.infrastructure.challenges.application_fixtures import (
    RESPONSIVE_HERO_CHALLENGE,
    RESPONSIVE_HERO_CONFIG,
)
from app.infrastructure.llm.factory import create_llm_provider

_PROMPTS = {
    "explicit": (
        "Create a responsive hero. On desktop, use two columns with the heading, copy, and "
        "visible CTA on the left and the illustration on the right. On mobile, stack into "
        "one readable column with no horizontal overflow. Preserve the header, navigation, "
        "features, footer, existing data-role attributes, and all unrelated behavior."
    ),
    "concise": (
        "Make the hero a responsive two-column layout on desktop, stacking on mobile. "
        "Keep the rest of the page unchanged."
    ),
    "underspecified": "Improve the hero layout and make it responsive.",
    "awkward": (
        "Please fix hero so big screens text left picture right, but phones one column and "
        "no sideways scroll; CTA should stay visible, don't mess with header/footer or other "
        "page parts."
    ),
}


class RecordingProvider:
    def __init__(self, inner: LLMProvider) -> None:
        self._inner = inner
        self.last_result: LLMExecutionResult | None = None

    async def generate(self, request: LLMExecutionRequest) -> LLMExecutionResult:
        result = await self._inner.generate(request)
        self.last_result = result
        return result


@dataclass(frozen=True, slots=True)
class SmokeOutcome:
    name: str
    provider_succeeded: bool
    latency_seconds: float
    structured_parsed: bool
    files_returned: int
    validation_passed: bool
    build_status: str
    visible_score: float | None
    screenshot_count: int
    input_tokens: int | None
    output_tokens: int | None
    failure_category: str | None

    def render(self) -> str:
        def value(item: object | None) -> str:
            return "n/a" if item is None else str(item)

        return " ".join(
            (
                f"prompt={self.name}",
                f"provider={'ok' if self.provider_succeeded else 'failed'}",
                f"latency_s={self.latency_seconds:.2f}",
                f"structured_parsed={'yes' if self.structured_parsed else 'no'}",
                f"files={self.files_returned}",
                f"validation={'pass' if self.validation_passed else 'fail'}",
                f"build={self.build_status}",
                f"visible_score={value(self.visible_score)}",
                f"screenshots={self.screenshot_count}",
                f"input_tokens={value(self.input_tokens)}",
                f"output_tokens={value(self.output_tokens)}",
                f"failure={value(self.failure_category)}",
            )
        )


def _failure_category(error: Exception) -> str:
    return str(getattr(error, "code", type(error).__name__))


def _usage(provider: RecordingProvider) -> tuple[int | None, int | None]:
    usage = provider.last_result.usage if provider.last_result is not None else None
    return (
        usage.input_tokens if usage is not None else None,
        usage.output_tokens if usage is not None else None,
    )


async def _direct_smoke(
    name: str,
    prompt: str,
    provider: RecordingProvider,
    *,
    structured_outputs: bool,
) -> SmokeOutcome:
    config = RESPONSIVE_HERO_CONFIG
    starter = StarterProjectRepository().starter_dir(config.starter_project)
    originals = {
        path: (starter / Path(path)).read_text(encoding="utf-8") for path in config.editable_files
    }
    task = AgentTask(
        player_prompt=prompt,
        files=tuple(SourceFile(path, content) for path, content in originals.items()),
        model_config=RESPONSIVE_HERO_CHALLENGE.version.model_config,
    )
    started = time.perf_counter()
    try:
        result = await LLMCodingAgent(
            provider, structured_outputs=structured_outputs
        ).apply_instructions(task)
        edits = parse_agent_edits(result.output_text, originals, config.limits)
        input_tokens, output_tokens = _usage(provider)
        return SmokeOutcome(
            name,
            True,
            time.perf_counter() - started,
            structured_outputs,
            len(edits),
            True,
            "not_run",
            None,
            0,
            input_tokens,
            output_tokens,
            None,
        )
    except Exception as error:
        input_tokens, output_tokens = _usage(provider)
        return SmokeOutcome(
            name,
            provider.last_result is not None,
            time.perf_counter() - started,
            False,
            0,
            False,
            "not_run",
            None,
            0,
            input_tokens,
            output_tokens,
            _failure_category(error),
        )


async def _visible_smoke(
    name: str,
    prompt: str,
    provider: RecordingProvider,
    settings: Settings,
    *,
    structured_outputs: bool,
) -> SmokeOutcome:
    executor = ApplicationChallengeExecutor(
        LLMCodingAgent(provider, structured_outputs=structured_outputs),
        LocalWorkspaceFactory(StarterProjectRepository()),
        PlaywrightApplicationEvaluator(settings.application_browser_channel),
        StarterProjectRepository(),
    )
    started = time.perf_counter()
    try:
        result = await executor.execute_visible(
            ChallengeExecutionRequest(RESPONSIVE_HERO_CHALLENGE, prompt)
        )
        changed = next(
            artifact for artifact in result.artifacts if isinstance(artifact, ChangedFilesArtifact)
        )
        build = next(
            artifact for artifact in result.artifacts if isinstance(artifact, BuildArtifact)
        )
        screenshots = tuple(
            artifact for artifact in result.artifacts if isinstance(artifact, ScreenshotArtifact)
        )
        valid_screenshots = sum(item.png.startswith(b"\x89PNG\r\n\x1a\n") for item in screenshots)
        input_tokens, output_tokens = _usage(provider)
        validation_passed = changed.agent_status is AgentStatus.APPLIED
        return SmokeOutcome(
            name,
            True,
            time.perf_counter() - started,
            structured_outputs,
            len(changed.files),
            validation_passed,
            build.status.value,
            round(result.evaluation_score, 2),
            valid_screenshots,
            input_tokens,
            output_tokens,
            None if validation_passed else "agent_edit_rejected",
        )
    except Exception as error:
        input_tokens, output_tokens = _usage(provider)
        return SmokeOutcome(
            name,
            provider.last_result is not None,
            time.perf_counter() - started,
            False,
            0,
            False,
            "not_run",
            None,
            0,
            input_tokens,
            output_tokens,
            _failure_category(error),
        )


async def _run(args: argparse.Namespace) -> int:
    if os.environ.get("RUN_REAL_GROQ_TESTS") != "1":
        print("Refusing live calls: set RUN_REAL_GROQ_TESTS=1 to opt in.")
        return 2

    settings = Settings()
    if settings.groq_api_key is None or not settings.groq_api_key.get_secret_value().strip():
        print("Real provider validation was not executed because GROQ_API_KEY was unavailable.")
        return 2

    selected = args.prompt or list(_PROMPTS)
    visible = set(args.run_visible)
    structured_outputs = not args.plain_json
    print(
        "Responsive Hero real-provider smoke "
        f"mode={'strict_json_schema' if structured_outputs else 'plain_json'} "
        f"model={RESPONSIVE_HERO_CHALLENGE.version.model_config.model_id} "
        f"reasoning={RESPONSIVE_HERO_CHALLENGE.version.model_config.reasoning_effort.value} "
        f"max_output_tokens={RESPONSIVE_HERO_CHALLENGE.version.model_config.max_output_tokens}"
    )

    failed = False
    for name in selected:
        provider = RecordingProvider(create_llm_provider(settings))
        if name in visible:
            outcome = await _visible_smoke(
                name,
                _PROMPTS[name],
                provider,
                settings,
                structured_outputs=structured_outputs,
            )
        else:
            outcome = await _direct_smoke(
                name,
                _PROMPTS[name],
                provider,
                structured_outputs=structured_outputs,
            )
        print(outcome.render())
        failed |= not outcome.provider_succeeded or not outcome.validation_passed
    return 1 if failed else 0


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prompt",
        action="append",
        choices=tuple(_PROMPTS),
        help="Prompt case to run; repeat as needed. Defaults to all four.",
    )
    parser.add_argument(
        "--run-visible",
        action="append",
        default=[],
        choices=tuple(_PROMPTS),
        help="Run this case through workspace, build, browser checks, and screenshots.",
    )
    parser.add_argument(
        "--plain-json",
        action="store_true",
        help="Development comparison only: disable strict provider Structured Outputs.",
    )
    return parser.parse_args()


def main() -> None:
    raise SystemExit(asyncio.run(_run(_arguments())))


if __name__ == "__main__":
    main()
