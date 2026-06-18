"""Toggle a pi-extension projection on/off — the single source of truth
shared by the CLI (`pi-extension install`/`uninstall`) and the TUI
(`_apply_pi_pending`). Lifted out of the Click commands so the two surfaces
cannot diverge (#333).

npm rows  -> packages[] in settings.json (add verbatim / remove by identity).
store-owned -> one symlink per scope via pi_extension_install (lock-after-
projection). Global uninstall drops the symlink but KEEPS the global library
lock entry — deleting the library copy is the `remove` verb's job, not
`uninstall`'s (PR #306 two-verb contract)."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from agent_toolkit_cli import _pi_settings, pi_extension_install
from agent_toolkit_cli.pi_extension_lock import (
    LockEntry, add_entry, read_lock, remove_entry, write_lock,
)
from agent_toolkit_cli.pi_extension_paths import (
    Scope, library_lock_path, lock_file_path,
)

__all__ = ["install", "uninstall"]



from typing import Literal

def unmanaged_npm_advice(
    slug: str,
    *,
    scope: Scope,
    home: Path | None,
    project: Path | None,
    action: Literal["remove", "uninstall"],
) -> str | None:
    path = _pi_settings.settings_path(scope=scope, home=home, project=project)
    if not path.exists():
        return None
    for spec in _pi_settings.read_packages(scope=scope, home=home, project=project):
        if spec.startswith("npm:") and _pi_settings.npm_identity(spec) == _pi_settings.npm_identity(slug):
            if action == "remove":
                return (
                    f"{slug} is not managed by agent-toolkit.\n"
                    f"Found unmanaged npm package in {path}.\n"
                    "agent-toolkit-cli will not remove packages it did not add.\n"
                    f"To remove it manually, remove \"{spec}\" from packages[]."
                )
            return (
                f"{slug} is an unmanaged npm package in Pi settings.\n"
                "agent-toolkit-cli will not remove packages it did not add.\n"
                f"To remove it manually, edit {path} and remove \"{spec}\" from packages[]."
            )
    return None

def _global_entry(slug: str) -> LockEntry | None:
    return read_lock(library_lock_path(env={})).skills.get(slug)


def _store_owned_global_loaded(slug: str, *, home: Path | None) -> bool:
    p = pi_extension_install.plan(
        slug=slug, scope="global", action="install", home=home, project=None
    )
    return not p.create


def _globally_loaded(slug: str, entry: LockEntry, *, home: Path | None) -> bool:
    if entry.source_type == "npm":
        return _pi_settings.has_package_identity(
            entry.source, scope="global", home=home, project=None
        )
    return _store_owned_global_loaded(slug, home=home)


def _reject_project_install_if_global_loaded(
    *, slug: str, entry: LockEntry, scope: Scope, home: Path | None
) -> None:
    if scope != "project":
        return
    if not _globally_loaded(slug, entry, home=home):
        return
    raise pi_extension_install.InstallError(
        f"{slug}: already installed at global scope; "
        f"uninstall globally before installing at project scope"
    )


def install(
    *,
    slug: str,
    scope: Scope,
    home: Path | None = None,
    project: Path | None = None,
) -> None:
    """Project `slug` into `scope`. Raises InstallError / PiSettingsError."""
    entry = _global_entry(slug)
    if entry is None:
        raise pi_extension_install.InstallError(
            f"{slug}: not in the global library; run `pi-extension add` first"
        )

    _reject_project_install_if_global_loaded(
        slug=slug, entry=entry, scope=scope, home=home
    )

    if entry.source_type == "npm":
        _pi_settings.add_package(entry.source, scope=scope, home=home, project=project)
        return

    p = pi_extension_install.plan(
        slug=slug, scope=scope, action="install", home=home, project=project
    )
    pi_extension_install.apply(p, home=home, project=project)

    if scope == "project" and project is not None:
        proj_lock_path = lock_file_path(scope="project", project=project)
        proj_lock = read_lock(proj_lock_path)
        if slug not in proj_lock.skills:
            write_lock(proj_lock_path, add_entry(proj_lock, slug, LockEntry(
                source=entry.source, source_type=entry.source_type,
                ref=entry.ref, pi_extension_path=entry.pi_extension_path,
            )))


def uninstall(
    *,
    slug: str,
    scope: Scope,
    home: Path | None = None,
    project: Path | None = None,
) -> None:
    """Drop `slug`'s projection from `scope`. Raises InstallError / PiSettingsError.

    npm: remove matching packages[] entries by identity (catches drift).
    store-owned: unlink the projection. Global keeps the library lock entry;
    project scope prunes the project lock."""
    entry = _global_entry(slug)

    if entry is not None and entry.source_type == "npm":
        _pi_settings.remove_package_by_identity(
            entry.source, scope=scope, home=home, project=project
        )
        return

    if entry is None:
        advice = unmanaged_npm_advice(
            slug, scope=scope, home=home, project=project, action="uninstall"
        )
        if advice:
            raise pi_extension_install.InstallError(advice)

    p = pi_extension_install.plan(
        slug=slug, scope=scope, action="uninstall", home=home, project=project
    )
    pi_extension_install.apply(p, home=home, project=project)

    if scope == "project" and project is not None:
        proj_lock_path = lock_file_path(scope="project", project=project)
        proj_lock = read_lock(proj_lock_path)
        if slug in proj_lock.skills:
            write_lock(proj_lock_path, remove_entry(proj_lock, slug))
