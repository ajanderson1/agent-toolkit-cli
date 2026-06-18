from __future__ import annotations

from agent_toolkit_cli.command_adapters.gemini import GeminiCommandAdapter
from agent_toolkit_cli.command_adapters.markdown import MarkdownCommandAdapter

SUPPORTED_HARNESSES = ("claude-code", "pi", "codex", "gemini-cli")
DEFAULT_HARNESSES = ("claude-code", "pi", "gemini-cli")


def get_adapter(name: str):
    if name == "gemini-cli":
        return GeminiCommandAdapter()
    if name in {"claude-code", "pi", "codex"}:
        return MarkdownCommandAdapter(name)
    raise ValueError(f"unsupported command harness: {name}")
