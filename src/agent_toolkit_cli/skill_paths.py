"""Skill-flavoured facade over `_paths_core.py`.

v2.2 model — library vs install:

  Global scope canonical lives in the library at $AGENT_TOOLKIT_SKILLS_ROOT
  (default ~/.agent-toolkit/skills/<slug>/).  Each library entry is a real git
  working tree.  Agents reach a library skill via a symlink created by
  `skill install`.  The global lock is at <library_root>.parent/skills-lock.json.

  Project scope: its own per-project canonical at an external store outside
  the project tree (see project_store_root).  Project lock at
  <project>/skills-lock.json.

  canonical_skill_dir(slug, scope='global') now delegates to library_skill_path.
  canonical_skill_dir(slug, scope='project') is unchanged.
  The `home` parameter is accepted but IGNORED at global scope (legacy callers).

Public symbols (`canonical_skill_dir`, `lock_file_path`, `library_root`,
`library_skill_path`, `library_lock_path`, `project_id`,
`project_store_root`, `project_parents_root`, `parent_clone_path`,
`agent_projection_dir`, `harness_projection_dir`, `SUPPORTED_HARNESSES`,
`Scope`) are preserved verbatim — implementations delegate to
`_paths_core` where the binding-driven helpers live.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

from agent_toolkit_cli._paths_core import (
    SKILL_BINDING,
    library_lock_path_for_kind,
    library_root_for_kind,
)
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


def library_root(env: dict[str, str] | None = None) -> Path:
    """Return the root of the global skill library.

    Thin shim over `_paths_core.library_root_for_kind(SKILL_BINDING, …)`.
    Honors $AGENT_TOOLKIT_SKILLS_ROOT for backward compatibility.
    """
    return library_root_for_kind(SKILL_BINDING, env)


def library_skill_path(slug: str, *, env: dict[str, str] | None = None) -> Path:
    """Return the canonical library path for a single skill slug."""
    return library_root(env) / slug


def library_lock_path(env: dict[str, str] | None = None) -> Path:
    """Return the path of the global skills-lock.json for v2.2+.

    Thin shim over `_paths_core.library_lock_path_for_kind(SKILL_BINDING, …)`.
    Lives at <library_root>.parent / "skills-lock.json" by default.
    """
    return library_lock_path_for_kind(SKILL_BINDING, env)


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

    Project scope: <store_root>/<slug> (external store; see project_store_root).
    """
    if scope == "global":
        return library_skill_path(slug)
    if project is None:
        raise ValueError("project scope requires project")
    return project_store_root(project) / slug


def lock_file_path(
    *,
    scope: Scope,
    home: Path | None = None,
    project: Path | None = None,
) -> Path:
    """Return the lock file path for the given scope.

    Global scope: delegates to library_lock_path(). The `home` parameter is
    accepted for backward compatibility but ignored.

    Project scope: <project>/<binding.lock_filename> — uses the binding so
    PR2's agent lock at project scope lands at <project>/agents-lock.json
    automatically.
    """
    if scope == "global":
        return library_lock_path()
    if project is None:
        raise ValueError("project scope requires project")
    return project / SKILL_BINDING.lock_filename


def project_id(project: Path) -> str:
    """Stable, collision-free directory name for a project's skill store.

    Sanitized absolute path + 6-hex-char sha256 suffix. The sanitized prefix
    keeps doctor output and on-disk inspection human-readable; the hash suffix
    guarantees uniqueness even if two distinct paths sanitize to the same
    string. Taken over project.resolve() so symlinked/relative invocations of
    the same project map to one id.
    """
    real = project.resolve()
    abs_str = str(real)
    sanitized = "".join(
        c if (c.isalnum() or c in "._-") else "-" for c in abs_str
    ).strip("-")
    digest = hashlib.sha256(abs_str.encode()).hexdigest()[:6]
    return f"{sanitized}-{digest}"


def project_store_root(project: Path, *, env: dict[str, str] | None = None) -> Path:
    """Per-project skill store: <library_root>.parent/projects/<id>/skills.

    Holds project canonical skill dirs AND the project's _parents/ cache.
    Lives under ~/.agent-toolkit (library_root().parent) by default, OUTSIDE
    the project tree, so removing a skill never touches project files.
    Honors $AGENT_TOOLKIT_SKILLS_ROOT via library_root(env).
    """
    return library_root(env).parent / "projects" / project_id(project) / "skills"


def parent_clone_path(
    owner: str, repo: str, *, ref: str | None,
    env: dict[str, str] | None = None,
    root: Path | None = None,
) -> Path:
    """Where a monorepo parent is cloned, shared across all skills from it."""
    base = root if root is not None else library_root(env)
    leaf = repo if ref is None else f"{repo}@{ref}"
    return base / "_parents" / owner / leaf


def project_parents_root(project: Path) -> Path:
    """Root under which a project's monorepo `_parents/` cache lives."""
    return project_store_root(project)


def agent_projection_dir(
    agent_name: str, slug: str, *,
    scope: Scope, home: Path | None, project: Path | None,
) -> Path:
    """Where the per-agent skill projection lives, given agent + scope."""
    if agent_name not in AGENTS:
        raise UnknownAgentError(agent_name)
    cfg = AGENTS[agent_name]
    if scope == "global":
        return cfg.global_skills_dir / slug
    project_root = _root(scope, home, project)
    return project_root / cfg.skills_dir / slug


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
    """Legacy 5-harness shortcut → agent_projection_dir()."""
    if harness not in _SHORTCUT_TO_AGENT:
        raise ValueError(f"unknown harness: {harness}")
    return agent_projection_dir(
        _SHORTCUT_TO_AGENT[harness], slug,
        scope=scope, home=home, project=project,
    )
