"""Agent-flavoured facade over `_paths_core.py`.

v3.0.0 PR2 — mirrors `skill_paths.py` for the agent (subagent) asset type.

v3.0.0 model — library vs install:

  Global scope canonical lives in the library at
  ~/.agent-toolkit/agents/<slug>/. Each library entry is a real git
  working tree. Harnesses reach a library agent via a file/symlink/registry
  entry created by `agent install`. The global lock is at
  ~/.agent-toolkit/agents-lock.json.

  Project scope: its own per-project canonical at an external store outside
  the project tree (shared with skills — see project_store_root). Project
  lock at <project>/agents-lock.json.

Public symbols (`canonical_agent_dir`, `lock_file_path`, `library_root`,
`library_agent_path`, `library_lock_path`, `project_id`,
`project_store_root`, `project_parents_root`, `parent_clone_path`,
`agent_projection_dir`, `harness_projection_dir`, `SUPPORTED_HARNESSES`,
`Scope`) are preserved verbatim — implementations delegate to
`_paths_core` where the binding-driven helpers live.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from agent_toolkit_cli._paths_core import (
    AGENT_BINDING,
    library_lock_path_for_asset_type,
    library_root_for_asset_type,
)
# Shared helpers (independent of asset type) re-exported from skill_paths.
# Re-exporting (rather than hoisting into _paths_core) is deliberate: it
# avoids touching PR1's frozen public surface mid-cycle. Hoist to an asset-type-
# agnostic module once both facades have shipped and stabilised (PR3+).
from agent_toolkit_cli.skill_paths import (
    SUPPORTED_HARNESSES,
    agent_projection_dir,
    harness_projection_dir,
    parent_clone_path,
    project_id,
    project_parents_root,
    project_store_root,
)

Scope = Literal["project", "global"]


# Machine-checked re-export contract. ruff/pyflakes treat __all__ membership
# as use, so the re-exports above stay even without internal callers.
__all__ = [
    "AGENT_BINDING",
    "Scope",
    "SUPPORTED_HARNESSES",
    "agent_projection_dir",
    "canonical_agent_dir",
    "harness_projection_dir",
    "library_agent_path",
    "library_lock_path",
    "library_root",
    "lock_file_path",
    "parent_clone_path",
    "project_id",
    "project_parents_root",
    "project_store_root",
]


def library_root(env: dict[str, str] | None = None) -> Path:
    """Return the root of the global agent library.

    Thin shim over `_paths_core.library_root_for_asset_type(AGENT_BINDING, …)`.
    Does NOT honor $AGENT_TOOLKIT_SKILLS_ROOT (that env var is skill-only).
    """
    return library_root_for_asset_type(AGENT_BINDING, env)


def library_agent_path(slug: str, *, env: dict[str, str] | None = None) -> Path:
    """Return the canonical library path for a single agent slug."""
    return library_root(env) / slug


def library_lock_path(env: dict[str, str] | None = None) -> Path:
    """Return the path of the global agents-lock.json."""
    return library_lock_path_for_asset_type(AGENT_BINDING, env)


def canonical_agent_dir(
    slug: str,
    *,
    scope: Scope,
    home: Path | None = None,
    project: Path | None = None,
) -> Path:
    """Return the canonical on-disk path for an agent at the given scope.

    Global scope: delegates to library_agent_path(slug). `home` accepted
    for backward compatibility but ignored — library root is always
    determined by AGENT_BINDING.

    Project scope: <store_root>/<slug> (external store — shared with
    skills via the same project_store_root).
    """
    if scope == "global":
        return library_agent_path(slug)
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

    Global scope: delegates to library_lock_path(). `home` accepted for
    backward compatibility but ignored.

    Project scope: <project>/<AGENT_BINDING.lock_filename> — uses the
    binding so the per-project lock lands at <project>/agents-lock.json.
    """
    if scope == "global":
        return library_lock_path()
    if project is None:
        raise ValueError("project scope requires project")
    return project / AGENT_BINDING.lock_filename
