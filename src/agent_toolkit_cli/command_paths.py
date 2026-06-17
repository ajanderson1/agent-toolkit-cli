"""Command-flavoured path facade over `_paths_core.py`."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from agent_toolkit_cli._paths_core import COMMAND_BINDING, library_lock_path_for_asset_type, library_root_for_asset_type
from agent_toolkit_cli.skill_paths import parent_clone_path, project_id, project_store_root as _skill_project_store_root

Scope = Literal["project", "global"]


def library_root(env: dict[str, str] | None = None) -> Path:
    return library_root_for_asset_type(COMMAND_BINDING, env)


def library_command_path(slug: str, *, env: dict[str, str] | None = None) -> Path:
    return library_root(env) / slug


def command_parent_clone_path(owner: str, repo: str, *, ref: str | None, env: dict[str, str] | None = None, root: Path | None = None) -> Path:
    return parent_clone_path(owner, repo, ref=ref, env=env, root=root or library_root(env))


def library_lock_path(env: dict[str, str] | None = None) -> Path:
    return library_lock_path_for_asset_type(COMMAND_BINDING, env)


def project_store_root(project: Path, *, env: dict[str, str] | None = None) -> Path:
    return library_root(env).parent / "projects" / project_id(project) / "commands"


def project_parents_root(project: Path) -> Path:
    return project_store_root(project)


def canonical_command_dir(slug: str, *, scope: Scope, home: Path | None = None, project: Path | None = None) -> Path:
    if scope == "global":
        return library_command_path(slug)
    if project is None:
        raise ValueError("project scope requires project")
    return project_store_root(project) / slug


def lock_file_path(*, scope: Scope, home: Path | None = None, project: Path | None = None) -> Path:
    if scope == "global":
        return library_lock_path()
    if project is None:
        raise ValueError("project scope requires project")
    return project / COMMAND_BINDING.lock_filename
