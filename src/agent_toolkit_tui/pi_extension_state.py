"""Data model for the TUI's pi-extension tab.

Reads the pi-extension inventory to produce PiExtensionRow records with
per-scope (global, project) cell state.
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


@dataclass
class PiExtensionRow:
    """One row per Pi extension slug."""

    slug: str
    origin: Origin
    source: str
    global_cell: PiCell
    project_cell: PiCell


def _row_from_record(rec: InventoryRecord) -> PiExtensionRow:
    cell = PiCell(
        global_loaded=rec.global_loaded,
        project_loaded=rec.project_loaded,
        origin=rec.origin,
    )
    return PiExtensionRow(
        slug=rec.slug,
        origin=rec.origin,
        source=rec.source,
        global_cell=cell,
        project_cell=cell,
    )


def build_pi_rows(
    *,
    home: Path | None = None,
    project: Path | None = None,
) -> list[PiExtensionRow]:
    """Build PiExtensionRow list from the live inventory."""
    records = build_inventory(home=home, project=project)
    return [_row_from_record(r) for r in records]
