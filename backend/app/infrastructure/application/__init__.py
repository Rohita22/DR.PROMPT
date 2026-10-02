"""Prototype adapters for APPLICATION challenges: starter storage, workspaces, agent, browser."""

from app.infrastructure.application.llm_coding_agent import LLMCodingAgent
from app.infrastructure.application.playwright_evaluator import PlaywrightApplicationEvaluator
from app.infrastructure.application.starter_projects import StarterProjectRepository
from app.infrastructure.application.workspace import LocalWorkspaceFactory

__all__ = [
    "LLMCodingAgent",
    "LocalWorkspaceFactory",
    "PlaywrightApplicationEvaluator",
    "StarterProjectRepository",
]
