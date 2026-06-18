"""Data model for the TUI's pi-extension tab.

Reads the pi-extension inventory to produce PiExtensionRow records with
per-scope (global, project) cell state.

Row-universe contract (#360): this tab already implements the union semantic
— build_inventory merges both scope locks, loose extension dirs, and
settings.json packages. Canonical statement: skill_state.py docstring.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from agent_toolkit_cli.pi_extension_inventory import InventoryRecord, build_inventory

Origin = Literal["store-owned", "npm", "untracked"]


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
    )


def build_pi_rows(
    *,
    home: Path | None = None,
    project: Path | None = None,
) -> list[PiExtensionRow]:
    """Build PiExtensionRow list from the live inventory."""
    records = build_inventory(home=home, project=project)
    return [_row_from_record(r) for r in records]
