"""Strict validation of the coding agent's structured file-replacement protocol.

Accepted response (optionally wrapped in one ```json fence and nothing else):

    {"files": [{"path": "src/styles.css", "content": "<complete new file>"}]}

Nothing else is ever turned into a filesystem change.
"""

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass

from app.domains.application.errors import AgentOutputError
from app.domains.application.models import ApplicationLimits, normalize_relative_path

_FENCE = re.compile(r"^```(?:json)?\s*\n(.*)\n```$", re.DOTALL)


@dataclass(frozen=True, slots=True)
class FileEdit:
    path: str
    content: str


def parse_agent_edits(
    raw_output: str,
    originals: Mapping[str, str],
    limits: ApplicationLimits,
) -> tuple[FileEdit, ...]:
    """Return validated edits to allowlisted files, or raise AgentOutputError."""
    text = raw_output.strip()
    fenced = _FENCE.fullmatch(text)
    if fenced is not None:
        text = fenced.group(1).strip()
    try:
        payload = json.loads(text)
    except (ValueError, RecursionError):
        raise AgentOutputError(
            "malformed", "The coding agent did not return the required JSON edit format."
        ) from None

    if not isinstance(payload, dict) or set(payload) != {"files"}:
        raise AgentOutputError("malformed", "The edit response must contain only a files list.")
    items = payload["files"]
    if not isinstance(items, list):
        raise AgentOutputError("malformed", "The edit response files value must be a list.")
    if not items:
        raise AgentOutputError("no_changes", "The coding agent did not propose any file edits.")
    if len(items) > limits.max_files:
        raise AgentOutputError("too_many_files", "The coding agent edited too many files.")

    edits: list[FileEdit] = []
    seen: set[str] = set()
    for item in items:
        if (
            not isinstance(item, dict)
            or set(item) != {"path", "content"}
            or not isinstance(item["path"], str)
            or not isinstance(item["content"], str)
        ):
            raise AgentOutputError("malformed", "Each edit needs exactly a path and content.")
        path = normalize_relative_path(item["path"])
        if path is None or path != item["path"]:
            raise AgentOutputError("unsafe_path", "The coding agent returned an unsafe path.")
        if path not in originals:
            raise AgentOutputError(
                "forbidden_file", f"The coding agent tried to edit a protected file: {path}."
            )
        if path in seen:
            raise AgentOutputError("duplicate_file", f"The coding agent edited {path} twice.")
        if len(item["content"].encode("utf-8")) > limits.max_file_bytes:
            raise AgentOutputError("file_too_large", f"The proposed {path} is too large.")
        seen.add(path)
        edits.append(FileEdit(path=path, content=item["content"]))

    if all(originals[edit.path] == edit.content for edit in edits):
        raise AgentOutputError("no_changes", "The coding agent returned files without changes.")
    return tuple(edits)
