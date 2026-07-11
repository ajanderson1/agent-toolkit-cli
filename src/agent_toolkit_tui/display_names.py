"""User-facing display names for the Textual TUI.

This module is intentionally TUI-only: persisted lock keys, adapter names, CLI
arguments, and catalog identifiers stay unchanged.
"""
from __future__ import annotations

_ASSET_TYPE_SINGULAR: dict[str, str] = {
    "instruction": "Instruction",
    "skill": "Skill",
    "command": "Command",
    "pi-extension": "Pi Extension",
    "agent": "Agent",
    "mcp": "MCP",
}

_ASSET_TYPE_PLURAL: dict[str, str] = {
    "instruction": "Instructions",
    "skill": "Skills",
    "command": "Commands",
    "pi-extension": "Pi Extensions",
    "agent": "Agents",
    "mcp": "MCPs",
}

_HARNESS_LABELS: dict[str, str] = {
    "claude-code": "Claude",
    "gemini-cli": "Gemini",
    "codex": "Codex",
    "opencode": "OpenCode",
    "pi": "Pi",
    "cursor": "Cursor",
    "hermes-agent": "Hermes",
}

_PI_EXTENSION_ORIGINS: dict[str, str] = {
    "store-owned": "library",
    "npm": "npm",
    "untracked": "untracked",
}


def _titleize_key(value: str) -> str:
    return " ".join(part.capitalize() for part in value.replace("_", "-").split("-") if part)


def asset_type_label(asset_type: str, *, plural: bool = False) -> str:
    labels = _ASSET_TYPE_PLURAL if plural else _ASSET_TYPE_SINGULAR
    return labels.get(asset_type, _titleize_key(asset_type))


def harness_label(harness: str) -> str:
    return _HARNESS_LABELS.get(harness, _titleize_key(harness))


def standard_label(count: int) -> str:
    return f"Standard ({count})"


def pi_extension_origin_label(origin: str) -> str:
    return _PI_EXTENSION_ORIGINS.get(origin, origin)
