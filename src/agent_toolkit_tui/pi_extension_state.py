"""Data model for the TUI's pi-extension tab.

Reads the pi-extension inventory to produce PiExtensionRow records with
per-scope (global, project) cell state.

Row-universe contract (#360): this tab already implements the union semantic
— build_inventory merges both scope locks, loose extension dirs, and
settings.json packages. Canonical statement: skill_state.py docstring.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from agent_toolkit_cli.pi_local_extensions import LocalExtensionState, read_local_extension_states
from agent_toolkit_cli.pi_npm import NpmState
from agent_toolkit_tui.catalog_state import CatalogFields, merge_catalog_rows
from agent_toolkit_cli.pi_extension_inventory import InventoryRecord, build_inventory
from agent_toolkit_cli.pi_extension_paths import library_pi_extension_path, pi_extension_dir

Origin = Literal["store-owned", "npm", "untracked", "local-package", "catalog"]


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
class PiExtensionRow(CatalogFields):
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
    local_state: LocalExtensionState | None = None
    npm_state: NpmState | None = None


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
        npm_state=rec.npm_state,
    )


def build_pi_rows(
    *,
    home: Path | None = None,
    project: Path | None = None,
    catalog_snapshot=None,
) -> list[PiExtensionRow]:
    """Separate native local selection from package settings and library links."""
    home = home or Path.home()
    records = build_inventory(home=home, project=project)
    scopes = ["global", "project"] if project is not None else ["global"]
    local_states = read_local_extension_states(home=home, project=project) if any(record.origin == "untracked" for record in records) else {}
    rows = []
    for record in records:
        if record.origin == "local-package":
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
        elif record.origin == "untracked":
            state = local_states.get(record.slug, LocalExtensionState())
            record = replace(record, global_loaded=state.global_enabled, project_loaded=state.project_enabled)
        row = _row_from_record(record)
        if record.origin == "untracked":
            row.local_state = local_states.get(record.slug, LocalExtensionState())
        rows.append(row)
    return merge_catalog_rows("pi-extension", rows, catalog_snapshot,
        scope="project" if project else "global", home=home, project=project)
