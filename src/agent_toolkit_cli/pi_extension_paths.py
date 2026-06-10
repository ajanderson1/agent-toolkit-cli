"""Path facade for the pi-extension kind. Binds PI_EXTENSION_BINDING to the
kind-agnostic helpers in _paths_core, and owns the Pi-specific projection
dirs (~/.pi/agent/extensions and <project>/.pi/extensions). Mirrors
agent_paths.py / skill_paths.py. Pi-only: there is no per-harness fan-out."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from agent_toolkit_cli._paths_core import (
    PI_EXTENSION_BINDING,
    library_lock_path_for_asset_type,
    library_root_for_asset_type,
)

# Reuse the kind-agnostic project-store helpers verbatim.
from agent_toolkit_cli.skill_paths import (
    parent_clone_path,
    project_id,
    project_parents_root,
)

Scope = Literal["project", "global"]

# Pi discovery roots (verified against pi-coding-agent@0.77.0):
#   global:  ~/.pi/agent/extensions/<slug>
#   project: <project>/.pi/extensions/<slug>
_PI_GLOBAL_EXTENSIONS = (".pi", "agent", "extensions")
_PI_PROJECT_EXTENSIONS = (".pi", "extensions")

__all__ = [
    "Scope",
    "library_root",
    "library_pi_extension_path",
    "library_lock_path",
    "canonical_pi_extension_dir",
    "lock_file_path",
    "pi_extension_dir",
    "parent_clone_path",
    "project_id",
    "project_parents_root",
]


def library_root(env: dict[str, str] | None = None) -> Path:
    return library_root_for_asset_type(PI_EXTENSION_BINDING, env)


def library_pi_extension_path(slug: str, *, env: dict[str, str] | None = None) -> Path:
    return library_root(env) / slug


def library_lock_path(env: dict[str, str] | None = None) -> Path:
    return library_lock_path_for_asset_type(PI_EXTENSION_BINDING, env)


def canonical_pi_extension_dir(
    slug: str,
    *,
    scope: Scope,
    home: Path | None = None,
    project: Path | None = None,
) -> Path:
    """The owned store copy for a store-owned extension."""
    if scope == "global":
        return library_pi_extension_path(slug)
    if project is None:
        raise ValueError("project scope requires project")
    # Project-scope store copy lives under the per-project store root, like skills.
    from agent_toolkit_cli.skill_paths import library_root as _skill_lib_root

    return (
        _skill_lib_root().parent
        / "projects"
        / project_id(project)
        / "pi-extensions"
        / slug
    )


def lock_file_path(
    *,
    scope: Scope,
    home: Path | None = None,
    project: Path | None = None,
) -> Path:
    if scope == "global":
        return library_lock_path()
    if project is None:
        raise ValueError("project scope requires project")
    return project / PI_EXTENSION_BINDING.lock_filename


def pi_extension_dir(
    slug: str,
    *,
    scope: Scope,
    home: Path | None = None,
    project: Path | None = None,
) -> Path:
    """Where Pi discovers the extension (symlink target lives here in PR2)."""
    if scope == "global":
        if home is None:
            raise ValueError("global scope requires home")
        return home.joinpath(*_PI_GLOBAL_EXTENSIONS, slug)
    if project is None:
        raise ValueError("project scope requires project")
    return project.joinpath(*_PI_PROJECT_EXTENSIONS, slug)
