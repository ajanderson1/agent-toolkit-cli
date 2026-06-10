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

from agent_toolkit_cli.instructions_adapters import SUPPORTED_HARNESSES
from agent_toolkit_cli.skill_agents import AGENTS

# The harnesses of interest that must always be covered (standard column or
# own column) on every asset type they support.
MAIN_HARNESSES: tuple[str, ...] = (
    "claude-code", "gemini-cli", "codex", "opencode", "pi", "cursor",
)


def skills_nonstandard_main() -> tuple[str, ...]:
    """Main harnesses that need their own skills column (not standard-covered)."""
    return tuple(n for n in MAIN_HARNESSES if not AGENTS[n].is_standard)


def instructions_nonstandard_main() -> tuple[str, ...]:
    """Main harnesses that need their own instructions column (symlink verdict)."""
    return tuple(h for h in MAIN_HARNESSES if h in SUPPORTED_HARNESSES)


def agents_nonstandard_main(scope: str) -> tuple[str, ...]:
    """Main harnesses that need their own agents column at `scope`:
    support the agent asset type (mechanism != 'none') and are not covered
    by the standard .claude/agents slot (#361)."""
    from agent_toolkit_cli.agent_adapters.standard import agents_standard_covered

    covered = agents_standard_covered(scope)
    return tuple(
        h for h in MAIN_HARNESSES
        if AGENTS[h].subagent_mechanism != "none" and h not in covered
    )
