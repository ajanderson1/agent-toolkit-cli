"""doctor group: list assets linked at both user and project scope.

Informational only — by spec this is NOT drift; cross-scope deconfliction is
tracked separately in #69.
"""
from __future__ import annotations

from pathlib import Path

from agent_toolkit_cli._support import USER_LINKED_STATUSES
from agent_toolkit_cli.commands._list_json import _build_inventory, user_scope_covered
from agent_toolkit_cli.doctor.result import GroupResult, Status


def run(toolkit_root: Path, *, project_root: Path | None = None) -> GroupResult:
    project_root = Path(project_root) if project_root is not None else Path.cwd()
    inventory = _build_inventory(toolkit_root, project_root)

    overlaps: list[str] = []
    for asset in inventory.get("assets", []):
        slug = asset.get("slug", "?")
        for cell in asset.get("cells", []):
            if cell.get("scope") != "project":
                continue
            if cell.get("status") not in USER_LINKED_STATUSES:
                continue
            harness = cell.get("harness")
            if user_scope_covered(inventory, slug=slug, harness=harness):
                overlaps.append(f"{slug} ({asset.get('kind', '?')}, {harness})")

    if not overlaps:
        return GroupResult(
            name="user-scope-coverage",
            status=Status.OK,
            summary="No assets are linked at both user and project scope.",
            findings=[],
        )
    return GroupResult(
        name="user-scope-coverage",
        status=Status.OK,
        summary=f"{len(overlaps)} asset(s) linked at both scopes (informational).",
        findings=overlaps,
    )
