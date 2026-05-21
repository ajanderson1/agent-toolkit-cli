"""Pure path-computation helpers for the skill lock-file model.

v2.2 model — library vs install:

  Global scope canonical lives in the library at $AGENT_TOOLKIT_SKILLS_ROOT
  (default ~/.agent-toolkit/skills/<slug>/).  Each library entry is a real git
  working tree.  Agents reach a library skill via a symlink created by
  `skill install`.  The global lock is at <library_root>.parent/skills-lock.json.

  Project scope retains skills.sh's model: its own per-project canonical at
  <project>/.agents/skills/<slug>/ (independent git clone).  Project lock at
  <project>/skills-lock.json.

  canonical_skill_dir(slug, scope='global') now delegates to library_skill_path.
  canonical_skill_dir(slug, scope='project') is unchanged.
  The `home` parameter is accepted but IGNORED at global scope (legacy callers).
"""
from __future__ import annotations

import os
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
    slug: str,
    *,
    scope: Scope,
    home: Path | None = None,
    project: Path | None = None,
) -> Path:
    """Return the canonical on-disk path for a skill at the given scope.

    Global scope: delegates to library_skill_path(slug). The `home` parameter
    is accepted for backward compatibility but ignored — the library root is
    always determined by $AGENT_TOOLKIT_SKILLS_ROOT.

    Project scope: <project>/.agents/skills/<slug>/ (unchanged from v2.1).
    """
    if scope == "global":
        return library_skill_path(slug)
    if project is None:
        raise ValueError("project scope requires project")
    return project / ".agents" / "skills" / slug


def lock_file_path(
    *,
    scope: Scope,
    home: Path | None = None,
    project: Path | None = None,
) -> Path:
    """Return the lock file path for the given scope.

    Global scope: delegates to library_lock_path(). The `home` parameter is
    accepted for backward compatibility but ignored.

    Project scope: <project>/skills-lock.json (unchanged from v2.1).
    """
    if scope == "global":
        return library_lock_path()
    if project is None:
        raise ValueError("project scope requires project")
    return project / "skills-lock.json"


def library_root(env: dict[str, str] | None = None) -> Path:
    """Return the root of the global skill library.

    Respects $AGENT_TOOLKIT_SKILLS_ROOT when set to a non-empty, non-whitespace
    string.  Falls back to ~/.agent-toolkit/skills/.

    The `env` parameter exists so callers can inject a fake environment in
    tests without monkeypatching os.environ.
    """
    resolved = (env if env is not None else os.environ).get(
        "AGENT_TOOLKIT_SKILLS_ROOT", ""
    ).strip()
    if resolved:
        return Path(resolved)
    return Path.home() / ".agent-toolkit" / "skills"


def library_skill_path(slug: str, *, env: dict[str, str] | None = None) -> Path:
    """Return the canonical library path for a single skill slug."""
    return library_root(env) / slug


def parent_clone_path(
    owner: str, repo: str, *, ref: str | None,
    env: dict[str, str] | None = None,
) -> Path:
    """Where a monorepo parent is cloned, shared across all skills from it.

    Lives at <library_root>/_parents/<owner>/<repo>[@<ref>]/ so the cache is
    inside the AGENT_TOOLKIT_SKILLS_ROOT blast radius and travels with
    --toolkit-repo overrides.
    """
    leaf = repo if ref is None else f"{repo}@{ref}"
    return library_root(env) / "_parents" / owner / leaf


def library_lock_path(env: dict[str, str] | None = None) -> Path:
    """Return the path of the global skills-lock.json for v2.2+.

    Lives at <library_root>.parent / "skills-lock.json", i.e.
    ~/.agent-toolkit/skills-lock.json by default.

    DO NOT confuse with lock_file_path(), which returns the skills.sh-compatible
    path (~/.agents/.skill-lock.json).  That function is unchanged until Phase 2-6.
    """
    return library_root(env).parent / "skills-lock.json"


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
