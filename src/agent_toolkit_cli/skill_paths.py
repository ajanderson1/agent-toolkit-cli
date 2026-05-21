"""Pure path-computation helpers for the skill lock-file model.

Canonical layout mirrors vercel-labs/skills:
  global:  ~/.agents/skills/<slug>/   +  ~/.agents/.skill-lock.json
  project: <proj>/.agents/skills/<slug>/  +  <proj>/skills-lock.json

Per-agent projections live under the location described by AGENTS[name],
either `cfg.global_skills_dir / slug` (global scope) or `<project> /
cfg.skills_dir / slug` (project scope). See skill_agents.py.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from agent_toolkit_cli.skill_agents import AGENTS, UnknownAgentError

Scope = Literal["project", "global"]


def _root(scope: Scope, home: Path | None, project: Path | None) -> Path:
    if scope == "global":
        if home is None:
            raise ValueError("global scope requires home")
        return home
    if project is None:
        raise ValueError("project scope requires project")
    return project


def canonical_skill_dir(
    slug: str, *, scope: Scope, home: Path | None, project: Path | None,
) -> Path:
    return _root(scope, home, project) / ".agents" / "skills" / slug


def lock_file_path(
    *, scope: Scope, home: Path | None, project: Path | None,
) -> Path:
    root = _root(scope, home, project)
    if scope == "global":
        return root / ".agents" / ".skill-lock.json"
    return root / "skills-lock.json"


def agent_projection_dir(
    agent_name: str, slug: str, *,
    scope: Scope, home: Path | None, project: Path | None,
) -> Path:
    """Where the per-agent skill projection lives, given agent + scope."""
    if agent_name not in AGENTS:
        raise UnknownAgentError(agent_name)
    cfg = AGENTS[agent_name]
    if scope == "global":
        # global_skills_dir is absolute; ignore home (resolved at import time).
        return cfg.global_skills_dir / slug
    project_root = _root(scope, home, project)
    return project_root / cfg.skills_dir / slug


# Backwards-compatible aliases for the v2.0.0 5-harness shortcut. These
# resolve to the same agent_projection_dir() and use skills.sh's canonical
# agent names internally.
_SHORTCUT_TO_AGENT = {
    "claude":   "claude-code",
    "codex":    "codex",
    "opencode": "opencode",
    "gemini":   "gemini-cli",
    "pi":       "pi",
}

SUPPORTED_HARNESSES: tuple[str, ...] = tuple(_SHORTCUT_TO_AGENT.keys())


def harness_projection_dir(
    harness: str, slug: str, *,
    scope: Scope, home: Path | None, project: Path | None,
) -> Path:
    """Legacy 5-harness shortcut → agent_projection_dir(). Used by older code
    paths and tests; new code should call agent_projection_dir() directly."""
    if harness not in _SHORTCUT_TO_AGENT:
        raise ValueError(f"unknown harness: {harness}")
    return agent_projection_dir(
        _SHORTCUT_TO_AGENT[harness], slug,
        scope=scope, home=home, project=project,
    )
