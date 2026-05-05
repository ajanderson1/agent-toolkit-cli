"""Registry: get_adapter(harness) → adapter instance.

Single entry point above the package; CLI commands and the TUI runner do not
import individual adapter modules.
"""
from __future__ import annotations

from agent_toolkit.harness_adapters.base import (
    CannotInstall,
    ConfigFileAdapter,
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
    Returns UnimplementedAdapter for known-but-pending harnesses.
    """
    if harness not in _KNOWN_HARNESSES:
        raise ValueError(f"unknown harness {harness!r}")
    if harness == "codex":
        # Lazy import so the dependency on tomlkit (and any future codex deps)
        # only loads when the codex adapter is actually requested.
        from agent_toolkit.harness_adapters.codex import CodexAdapter
        return CodexAdapter()
    return UnimplementedAdapter(harness)


__all__ = [
    "get_adapter",
    "McpEntry",
    "WriteAction",
    "CannotInstall",
    "Scope",
    "PluginFolderAdapter",
    "ConfigFileAdapter",
    "UnimplementedAdapter",
]
