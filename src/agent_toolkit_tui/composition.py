"""Per-asset-type column composition for the Standard / Non-standard groups (#351).

Derived from the catalog/SSOT at call time — never hardcoded — so adding a
compliant harness upstream changes the grids without touching grid code.
Asset types without a standard concept (pi-extensions) have no entry here;
agents gained one with the .claude/agents slot (#361).

The TUI renders ONLY the standard column plus the non-covered main harnesses;
the long tail of harnesses is managed via the CLI (post-demo AJ decision,
#351 — the collapsible long-tail column set was removed). The coverage
invariant — every MAIN_HARNESSES member is either standard-covered or has its
own rendered column, for every asset type it supports — is guarded by
tests/test_tui/test_composition.py.
"""
from __future__ import annotations

from agent_toolkit_cli.agent_adapters.standard import agents_standard_covered
from agent_toolkit_cli.command_adapters import DEFAULT_HARNESSES
from agent_toolkit_cli.instructions_adapters import SUPPORTED_HARNESSES
from agent_toolkit_cli.skill_agents import AGENTS

# The fresh-install default main harnesses.
DEFAULT_MAIN_HARNESSES: tuple[str, ...] = (
    "claude-code", "gemini-cli", "codex", "opencode", "pi", "cursor",
    "hermes-agent", "paperclip",
)

# All real catalog harnesses eligible for main-harness selection.
MAIN_HARNESS_CANDIDATES: tuple[str, ...] = tuple(
    ag.name for ag in AGENTS.values() if ag.show_in_standard_list
)

MAIN_HARNESSES = DEFAULT_MAIN_HARNESSES


def effective_main_harnesses(
    selection: tuple[str, ...] | None = None,
) -> tuple[str, ...]:
    """Return the selected MAIN_HARNESSES in canonical render order.

    A selection is only a filter against MAIN_HARNESS_CANDIDATES, and ``None``
    preserves the fresh-install default.
    """
    chosen = DEFAULT_MAIN_HARNESSES if selection is None else selection
    return tuple(
        harness for harness in MAIN_HARNESS_CANDIDATES if harness in chosen
    )


def skills_nonstandard_main(
    selection: tuple[str, ...] | None = None,
) -> tuple[str, ...]:
    """Selected main harnesses needing their own skills column."""
    chosen = effective_main_harnesses(selection)
    return tuple(
        harness
        for harness in chosen
        if harness in AGENTS and not AGENTS[harness].is_standard
    )


def instructions_nonstandard_main(
    selection: tuple[str, ...] | None = None,
) -> tuple[str, ...]:
    """Selected main harnesses needing an instructions pointer column."""
    chosen = effective_main_harnesses(selection)
    return tuple(
        harness
        for harness in chosen
        if harness in SUPPORTED_HARNESSES
    )


def agents_nonstandard_main(
    scope: str,
    selection: tuple[str, ...] | None = None,
) -> tuple[str, ...]:
    """Selected main harnesses needing their own agents column at ``scope``."""
    chosen = effective_main_harnesses(selection)
    covered = agents_standard_covered(scope)
    return tuple(
        harness
        for harness in chosen
        if harness in AGENTS
        and AGENTS[harness].subagent_mechanism != "none"
        and harness not in covered
    )


# The four real MCP harnesses (commands/mcp/_common.py _HARNESSES), in
# canonical render order. Distinct from MAIN_HARNESSES: MCP has no gemini-cli
# or cursor adapter, so the MCP grid derives its columns from this set, not
# MAIN_HARNESSES.
_MCP_HARNESSES: tuple[str, ...] = ("claude-code", "codex", "opencode", "pi")


def mcp_nonstandard_main(
    scope: str,
    selection: tuple[str, ...] | None = None,
) -> tuple[str, ...]:
    """Selected MCP harnesses needing their own column at ``scope``.

    Scope asymmetry (load-bearing): STANDARD_MCP_READERS has ONLY a 'project'
    key, so mcp_standard_covered('global') raises KeyError. At global scope the
    covered set is empty and all selected MCP harnesses render their own column.
    """
    from agent_toolkit_cli.mcp_standard import mcp_standard_covered

    chosen = effective_main_harnesses(selection)
    try:
        covered = mcp_standard_covered(scope)
    except KeyError:
        covered = frozenset()
    return tuple(
        harness
        for harness in _MCP_HARNESSES
        if harness not in covered and harness in chosen
    )


def commands_main(
    selection: tuple[str, ...] | None = None,
) -> tuple[str, ...]:
    """Selected command columns, filtered from command SUPPORTED_HARNESSES."""
    from agent_toolkit_cli.command_adapters import (
        SUPPORTED_HARNESSES as COMMAND_SUPPORTED_HARNESSES,
    )

    chosen = effective_main_harnesses(selection)
    return tuple(
        harness for harness in chosen if harness in COMMAND_SUPPORTED_HARNESSES
    )
