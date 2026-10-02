import asyncio

from app.domains.application.edits import FileEdit, parse_agent_edits
from app.domains.application.models import ApplicationLimits, SourceFile
from app.domains.application.ports import AgentTask
from app.domains.evaluation.configuration import ModelConfiguration, ReasoningEffort
from app.domains.evaluation.model_execution import LLMExecutionResult, TokenUsage
from app.infrastructure.application.llm_coding_agent import LLMCodingAgent
from tests.fakes.llm import FakeLLMProvider


def task() -> AgentTask:
    return AgentTask(
        player_prompt="Make the hero responsive.",
        files=(
            SourceFile("src/index.html", "<main></main>"),
            SourceFile("src/styles.css", "body { margin: 0; }"),
        ),
        model_config=ModelConfiguration(
            model_id="openai/gpt-oss-20b",
            temperature=0,
            max_output_tokens=8192,
            configuration_version="agent-v2",
            system_wrapper="Edit only the supplied files.",
            reasoning_effort=ReasoningEffort.LOW,
        ),
    )


def test_requests_strict_provider_neutral_edit_schema_and_maps_result() -> None:
    usage = TokenUsage(100, 50, 150)
    output = '{"files":[{"path":"src/styles.css","content":"body { margin: 1px; }"}]}'
    provider = FakeLLMProvider(LLMExecutionResult(output, "actual-model", usage))

    result = asyncio.run(LLMCodingAgent(provider).apply_instructions(task()))

    request = provider.requests[0]
    assert request.player_prompt == "Make the hero responsive."
    assert request.model_config.reasoning_effort is ReasoningEffort.LOW
    assert request.structured_output is not None
    assert request.structured_output.name == "application_file_edits"
    assert request.structured_output.strict is True
    assert request.structured_output.schema["additionalProperties"] is False
    items = request.structured_output.schema["properties"]["files"]["items"]
    assert items["properties"]["path"]["enum"] == ["src/index.html", "src/styles.css"]
    assert result.output_text == output
    assert result.usage == usage

    originals = {source.path: source.content for source in task().files}
    assert parse_agent_edits(output, originals, ApplicationLimits()) == (
        FileEdit("src/styles.css", "body { margin: 1px; }"),
    )


def test_plain_json_mode_remains_available_only_for_manual_comparison() -> None:
    provider = FakeLLMProvider(LLMExecutionResult('{"files":[]}', "fake"))

    asyncio.run(LLMCodingAgent(provider, structured_outputs=False).apply_instructions(task()))

    assert provider.requests[0].structured_output is None
