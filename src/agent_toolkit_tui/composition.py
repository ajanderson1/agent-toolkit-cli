"""Per-kind column composition for the Standard / Non-standard groups (#351).

Derived from the catalog/SSOT at call time — never hardcoded — so adding a
compliant harness upstream changes the grids without touching grid code.
Kinds without a standard concept (agents, pi-extensions) have no entry here.
"""
from __future__ import annotations

from agent_toolkit_cli.instructions_adapters import SUPPORTED_HARNESSES
from agent_toolkit_cli.skill_agents import AGENTS

# Pseudo-column key for the collapsed long-tail set; never a catalog name.
LONGTAIL_KEY = "longtail"

BIG_FIVE: tuple[str, ...] = ("claude-code", "pi", "codex", "gemini-cli", "opencode")

_SYNTHETIC = frozenset({"standard", "standard-skill", "standard-agent"})


def skills_nonstandard_big_five() -> tuple[str, ...]:
    return tuple(n for n in BIG_FIVE if not AGENTS[n].is_standard)


def skills_longtail() -> tuple[str, ...]:
    return tuple(sorted(
        n for n, c in AGENTS.items()
        if not c.is_standard and n not in BIG_FIVE and n not in _SYNTHETIC
    ))


def instructions_nonstandard_big_five() -> tuple[str, ...]:
    return tuple(h for h in BIG_FIVE if h in SUPPORTED_HARNESSES)


def instructions_longtail() -> tuple[str, ...]:
    return tuple(sorted(
        h for h in SUPPORTED_HARNESSES if h not in BIG_FIVE
    ))
