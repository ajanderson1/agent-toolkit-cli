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
    library_lock_path_for_asset_type,
    library_root_for_asset_type,
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

    Thin shim over `_paths_core.library_root_for_asset_type(SKILL_BINDING, …)`.
    Honors $AGENT_TOOLKIT_SKILLS_ROOT for backward compatibility.
    """
    return library_root_for_asset_type(SKILL_BINDING, env)


def library_skill_path(slug: str, *, env: dict[str, str] | None = None) -> Path:
    """Return the canonical library path for a single skill slug."""
    return library_root(env) / slug


def library_lock_path(env: dict[str, str] | None = None) -> Path:
    """Return the path of the global skills-lock.json for v2.2+.

    Thin shim over `_paths_core.library_lock_path_for_asset_type(SKILL_BINDING, …)`.
    Lives at <library_root>.parent / "skills-lock.json" by default.
    """
    return library_lock_path_for_asset_type(SKILL_BINDING, env)


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
    """Where a monorepo parent is cloned, shared across all skills from it.

    Global scope (root=None): <library_root>/_parents/<owner>/<repo>[@<ref>]/
    so the cache is inside the AGENT_TOOLKIT_SKILLS_ROOT blast radius and
    travels with --toolkit-repo overrides.

    Project scope: pass root=project_store_root(project) (see project_parents_root)
    so the cache is <store_root>/_parents/<owner>/<repo>[@<ref>]/.
    """
    # env is only consulted when root is None (global scope).
    base = root if root is not None else library_root(env)
    leaf = repo if ref is None else f"{repo}@{ref}"
    return base / "_parents" / owner / leaf


def resolve_existing_parent_clone(
    owner: str, repo: str, *, ref: str | None, parent_url: str,
    env: dict[str, str] | None = None,
    root: Path | None = None,
) -> Path:
    """Locate an existing monorepo parent clone, tolerating the legacy
    bare-named layout (#412).

    Prefers the canonical suffixed path (`<repo>@<ref>`). Falls back to the bare
    `<repo>` path ONLY when the suffixed path is absent AND the bare dir is the
    legacy clone for THIS skill — see `skill_git.legacy_bare_clone_for`, which
    requires a matching origin remote AND that the bare clone is checked out at
    `ref` (the multi-ref safety guard, shared with doctor so the two cannot
    diverge). When neither exists, returns the suffixed path so a fresh clone
    still lands in the canonical scheme.
    """
    from agent_toolkit_cli import skill_git
    suffixed = parent_clone_path(owner, repo, ref=ref, env=env, root=root)
    if skill_git.is_git_repo(suffixed):
        return suffixed
    bare = parent_clone_path(owner, repo, ref=None, env=env, root=root)
    adopted = skill_git.legacy_bare_clone_for(
        suffixed, bare, ref=ref, parent_url=parent_url, env=env,
    )
    return adopted if adopted is not None else suffixed


def project_parents_root(project: Path) -> Path:
    """Root under which a project's monorepo `_parents/` cache lives."""
    return project_store_root(project)


def _is_hermes_profile_home(project: Path) -> bool:
    """Return whether ``project`` is a named Hermes profile home.

    Hermes treats ``~/.hermes/profiles/<name>`` as the active ``HERMES_HOME``;
    its skills therefore live directly in ``<profile>/skills`` rather than the
    generic project's ``.hermes/skills`` harness directory.
    """
    return project.parent.name == "profiles" and (project / "profile.yaml").is_file()


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
    if agent_name == "hermes-agent" and _is_hermes_profile_home(project_root):
        return project_root / "skills" / slug
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
