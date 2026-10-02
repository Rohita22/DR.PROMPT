from app.domains.application.ports import AgentResult, AgentTask
from app.domains.evaluation.model_execution import (
    LLMExecutionRequest,
    StructuredOutputSpecification,
)
from app.domains.evaluation.ports import LLMProvider

_RESPONSE_CONTRACT = (
    'Respond with only a JSON object: {"files": [{"path": "<one of editable_files>", '
    '"content": "<complete new file content>"}]}. Include only files you change. '
    "No prose, no diffs, no other paths."
)


def _edit_response_spec(task: AgentTask) -> StructuredOutputSpecification:
    return StructuredOutputSpecification(
        name="application_file_edits",
        schema={
            "type": "object",
            "properties": {
                "files": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": len(task.files),
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "enum": [source.path for source in task.files],
                            },
                            "content": {"type": "string"},
                        },
                        "required": ["path", "content"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["files"],
            "additionalProperties": False,
        },
        strict=True,
    )


class LLMCodingAgent:
    """Single-shot coding agent over the existing provider-neutral LLMProvider port.

    The model sees the challenge's system wrapper, the player's prompt unchanged, and the
    current editable files. It has no shell, no filesystem access, and no tools: its only
    capability is proposing whole-file replacements, which are validated before any write.
    """

    def __init__(self, llm_provider: LLMProvider, *, structured_outputs: bool = True) -> None:
        self._llm_provider = llm_provider
        self._structured_outputs = structured_outputs

    async def apply_instructions(self, task: AgentTask) -> AgentResult:
        execution = await self._llm_provider.generate(
            LLMExecutionRequest(
                player_prompt=task.player_prompt,
                test_input={
                    "editable_files": [
                        {"path": source.path, "content": source.content} for source in task.files
                    ],
                    "response_format": _RESPONSE_CONTRACT,
                },
                model_config=task.model_config,
                structured_output=(_edit_response_spec(task) if self._structured_outputs else None),
            )
        )
        return AgentResult(output_text=execution.output_text, usage=execution.usage)
