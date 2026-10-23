"""Data model for the TUI's pi-extension tab.

Reads the pi-extension inventory to produce PiExtensionRow records with
per-scope (global, project) cell state.

Row-universe contract (#360): this tab already implements the union semantic
— build_inventory merges both scope locks, loose extension dirs, and
settings.json packages. Canonical statement: skill_state.py docstring.
"""
from __future__ import annotations

import glob
import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from agent_toolkit_cli import _pi_settings
from agent_toolkit_cli.pi_extension_inventory import InventoryRecord, build_inventory
from agent_toolkit_cli.pi_extension_paths import library_pi_extension_path, pi_extension_dir

Origin = Literal["store-owned", "npm", "untracked", "local-package"]


@dataclass(frozen=True)
class PiCell:
    """Per-scope install state for a single Pi extension."""

    global_loaded: bool
    project_loaded: bool
    origin: Origin
    managed: bool = True
    package_spec: str | None = None
    config_path: str | None = None


@dataclass
class PiExtensionRow:
    """One row per Pi extension slug."""

    slug: str
    origin: Origin
    source: str
    global_cell: PiCell
    project_cell: PiCell
    managed: bool = True
    global_package_spec: str | None = None
    project_package_spec: str | None = None
    global_config_path: str | None = None
    project_config_path: str | None = None
    global_package_metadata: dict[str, object] | None = None
    project_package_metadata: dict[str, object] | None = None


def _row_from_record(rec: InventoryRecord) -> PiExtensionRow:
    global_cell = PiCell(
        global_loaded=rec.global_loaded,
        project_loaded=rec.project_loaded,
        origin=rec.origin,
        managed=rec.managed,
        package_spec=rec.global_package_spec,
        config_path=str(rec.global_config_path) if rec.global_config_path else None,
    )
    project_cell = PiCell(
        global_loaded=rec.global_loaded,
        project_loaded=rec.project_loaded,
        origin=rec.origin,
        managed=rec.managed,
        package_spec=rec.project_package_spec,
        config_path=str(rec.project_config_path) if rec.project_config_path else None,
    )
    return PiExtensionRow(
        slug=rec.slug,
        origin=rec.origin,
        source=rec.source,
        global_cell=global_cell,
        project_cell=project_cell,
        managed=rec.managed,
        global_package_spec=rec.global_package_spec,
        project_package_spec=rec.project_package_spec,
        global_config_path=str(rec.global_config_path) if rec.global_config_path else None,
        project_config_path=str(rec.project_config_path) if rec.project_config_path else None,
        global_package_metadata=rec.global_package_metadata,
        project_package_metadata=rec.project_package_metadata,
    )


def _local_reference_enabled(
    paths: list[Path], references: list[str], *, settings: Path, home: Path,
) -> bool:
    """Report explicit settings selection, not Pi's implicit auto-discovery."""
    enabled = False
    candidates = {path.resolve() for path in paths}
    for reference in references:
        excluded = reference.startswith(("-", "!"))
        value = reference[1:] if reference.startswith(("+", "-", "!")) else reference
        if not value:
            continue
        path = home / value[2:] if value.startswith("~/") else Path(value).expanduser()
        if not path.is_absolute():
            path = settings.parent / path
        path = Path(os.path.normpath(path))
        matches = (
            [Path(match) for match in glob.glob(str(path), recursive=True)]
            if not reference.startswith(("+", "-")) and glob.has_magic(str(path))
            else [path]
        )
        for match in matches:
            target = match.resolve()
            if any(
                candidate == target
                or (target.is_dir() and candidate.is_relative_to(target))
                for candidate in candidates
            ):
                enabled = not excluded
    return enabled


def build_pi_rows(
    *,
    home: Path | None = None,
    project: Path | None = None,
) -> list[PiExtensionRow]:
    """Build rows without treating discovery of local files as enablement.

    Packages require packages[] references; loose local files require an
    explicit extensions[] reference in the corresponding settings. Library
    connections require owned symlinks. CLI discovery and controls are unchanged.
    """
    home = home or Path.home()
    records = build_inventory(home=home, project=project)
    scopes = ["global", "project"] if project is not None else ["global"]
    references = {
        scope: _pi_settings.read_extension_paths(scope=scope, home=home, project=project)
        for scope in scopes
    } if any(record.origin == "untracked" for record in records) else {}
    rows = []
    for record in records:
        if record.origin in ("npm", "local-package"):
            record = replace(
                record, global_loaded=record.global_package_spec is not None,
                project_loaded=record.project_package_spec is not None,
            )
        elif record.origin == "store-owned":
            source = library_pi_extension_path(record.slug).resolve()
            linked = {}
            for scope in scopes:
                path = pi_extension_dir(record.slug, scope=scope, home=home, project=project)
                linked[scope] = path.is_symlink() and path.resolve() == source
            record = replace(
                record, global_loaded=linked["global"],
                project_loaded=linked.get("project", False),
            )
        else:
            paths = []
            for scope in scopes:
                base = pi_extension_dir(record.slug, scope=scope, home=home, project=project)
                for path in (base, base.with_name(base.name + ".ts"), base.with_name(base.name + ".js")):
                    if path.exists() or path.is_symlink():
                        paths.append(path)
                        if path.is_dir():
                            paths.extend(path / name for name in ("index.ts", "index.js") if (path / name).is_file())
            enabled = {
                scope: _local_reference_enabled(
                    paths, references[scope], home=home,
                    settings=_pi_settings.settings_path(scope=scope, home=home, project=project),
                )
                for scope in scopes
            }
            record = replace(
                record, global_loaded=enabled["global"],
                project_loaded=enabled.get("project", False),
            )
        rows.append(_row_from_record(record))
    return rows
