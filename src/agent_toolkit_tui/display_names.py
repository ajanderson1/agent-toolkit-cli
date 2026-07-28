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
    "paperclip": "Paperclip",
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


def _standard_covered_count(asset_type: str, scope: str) -> int | None:
    """Live covered-harness count for ``asset_type`` at ``scope``.

    ``None`` means this asset type has no standard slot here (#478 R4/R5),
    which is a real answer — not an error. An unknown asset type raises
    ``KeyError`` so a new asset type cannot be silently treated as slot-less.

    Imports are function-local and resolved at call time on purpose: counts
    must track their SSOT, never an import-time snapshot (#478 R1).
    """
    if asset_type not in _ASSET_TYPE_SINGULAR:
        raise KeyError(f"unknown asset type: {asset_type!r}")

    if asset_type == "skill":
        from agent_toolkit_cli.skill_agents import get_standard_agents

        return len(get_standard_agents())

    if asset_type == "agent":
        from agent_toolkit_cli.agent_adapters.standard import agents_standard_covered

        return len(agents_standard_covered(scope))

    if asset_type == "instruction":
        from agent_toolkit_cli.instructions_matrix import instructions_matrix_rows

        return sum(1 for row in instructions_matrix_rows() if row["verdict"] == "native")

    if asset_type == "mcp":
        from agent_toolkit_cli.mcp_standard import mcp_standard_covered

        try:
            return len(mcp_standard_covered(scope))
        except KeyError:
            # Deliberate: STANDARD_MCP_READERS has only a ``project`` key. The
            # standard MCP projection IS the project .mcp.json, so there is no
            # global slot to count (#478 R4, composition.py:58-71).
            return None

    # command: no standard projection exists yet (#482).
    # pi-extension: single-harness asset type; nothing converges (#478 R5).
    return None


def standard_column_header(asset_type: str, scope: str) -> str | None:
    """Return ``Standard (N)`` or ``None`` when no standard slot exists.

    Single owner of the standard-column header rule (#478 R1). Every grid
    calls this instead of re-deriving a count behind its own special case.
    """
    count = _standard_covered_count(asset_type, scope)
    if count is None:
        return None
    return standard_label(count)


def pi_extension_origin_label(origin: str) -> str:
    return _PI_EXTENSION_ORIGINS.get(origin, origin)
