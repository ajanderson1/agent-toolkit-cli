"""Registry: get_adapter(harness) → adapter instance.

Single entry point above the package; CLI commands and the TUI runner do not
import individual adapter modules.
"""
from __future__ import annotations

from agent_toolkit.harness_adapters.base import (
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


_KNOWN_HARNESSES: tuple[str, ...] = ("claude", "codex", "opencode", "pi")


def get_adapter(harness: str):
    """Return the adapter for `harness`.

    Raises ValueError on unknown harness names.
    Returns UnimplementedAdapter for known-but-pending harnesses (currently `pi`).
    """
    if harness not in _KNOWN_HARNESSES:
        raise ValueError(f"unknown harness {harness!r}")
    if harness == "codex":
        from agent_toolkit.harness_adapters.codex import CodexAdapter
        return CodexAdapter()
    if harness == "claude":
        from agent_toolkit.harness_adapters.claude import ClaudeAdapter
        return ClaudeAdapter()
    if harness == "opencode":
        from agent_toolkit.harness_adapters.opencode import OpenCodeAdapter
        return OpenCodeAdapter()
    return UnimplementedAdapter(harness)


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
