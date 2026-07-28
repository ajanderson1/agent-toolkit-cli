from __future__ import annotations

from agent_toolkit_cli.command_adapters.gemini import GeminiCommandAdapter
from agent_toolkit_cli.command_adapters.markdown import MarkdownCommandAdapter
from agent_toolkit_cli.command_adapters.standard import StandardCommandAdapter

# Concrete harness catalog only — virtual slots never land here.
SUPPORTED_HARNESSES = ("claude-code", "pi", "codex", "gemini-cli")
# Installable targets include the virtual standard slot.
INSTALLABLE_HARNESSES = ("standard", *SUPPORTED_HARNESSES)
DEFAULT_HARNESSES = ("standard", "pi", "gemini-cli")


def get_adapter(name: str):
    if name == "standard":
        return StandardCommandAdapter()
    if name == "gemini-cli":
        return GeminiCommandAdapter()
    if name in {"claude-code", "pi", "codex"}:
        return MarkdownCommandAdapter(name)
    raise ValueError(f"unsupported command harness: {name}")
