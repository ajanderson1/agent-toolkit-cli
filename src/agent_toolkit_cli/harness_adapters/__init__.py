"""Registry: get_adapter(harness) → adapter instance.

Single entry point above the package; CLI commands and the TUI runner do not
import individual adapter modules.
"""
from __future__ import annotations

from agent_toolkit_cli._support import ALL_HARNESSES as _KNOWN_HARNESSES
from agent_toolkit_cli.harness_adapters.base import (
    CannotInstall,
    ConfigFileAdapter,
    ConfigFileFolderAdapter,
    HookEntry,
    McpEntry,
    PluginFolderAdapter,
    Scope,
    UnimplementedAdapter,
    WriteAction,
)


def get_adapter(harness: str, kind: str = "mcp"):
    """Return the adapter for `(harness, kind)`.

    Raises ValueError on unknown harness. Returns UnimplementedAdapter for
    known-but-pending pairs (currently `pi`).

    The `kind` parameter exists because some harnesses have different
    adapters for different asset kinds (e.g. codex has a config_file
    adapter for mcp and a config_file+folder adapter for hook). Defaults
    to "mcp" for backward compatibility with existing call sites.
    """
    if harness not in _KNOWN_HARNESSES:
        raise ValueError(f"unknown harness {harness!r}")
    if harness == "codex" and kind == "hook":
        from agent_toolkit_cli.harness_adapters.codex_hook import CodexHookAdapter
        return CodexHookAdapter()
    if harness == "codex" and kind == "mcp":
        from agent_toolkit_cli.harness_adapters.codex import CodexAdapter
        return CodexAdapter()
    if harness == "claude" and kind == "mcp":
        from agent_toolkit_cli.harness_adapters.claude import ClaudeAdapter
        return ClaudeAdapter()
    if harness == "opencode" and kind == "mcp":
        from agent_toolkit_cli.harness_adapters.opencode import OpenCodeAdapter
        return OpenCodeAdapter()
    if harness == "gemini" and kind == "mcp":
        from agent_toolkit_cli.harness_adapters.gemini import GeminiAdapter
        return GeminiAdapter()
    return UnimplementedAdapter(harness, kind=kind)


__all__ = [
    "get_adapter",
    "CannotInstall",
    "ConfigFileAdapter",
    "ConfigFileFolderAdapter",
    "HookEntry",
    "McpEntry",
    "PluginFolderAdapter",
    "Scope",
    "UnimplementedAdapter",
    "WriteAction",
]
