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

from agent_toolkit_cli import _pi_settings, pi_extension_install
from agent_toolkit_cli.pi_extension_lock import (
    LockEntry, add_entry, read_lock, remove_entry, write_lock,
)
from agent_toolkit_cli.pi_extension_paths import (
    Scope, library_lock_path, lock_file_path,
)

__all__ = ["install", "uninstall"]


def _global_entry(slug: str) -> LockEntry | None:
    return read_lock(library_lock_path(env={})).skills.get(slug)


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

    p = pi_extension_install.plan(
        slug=slug, scope=scope, action="uninstall", home=home, project=project
    )
    pi_extension_install.apply(p, home=home, project=project)

    if scope == "project" and project is not None:
        proj_lock_path = lock_file_path(scope="project", project=project)
        proj_lock = read_lock(proj_lock_path)
        if slug in proj_lock.skills:
            write_lock(proj_lock_path, remove_entry(proj_lock, slug))
