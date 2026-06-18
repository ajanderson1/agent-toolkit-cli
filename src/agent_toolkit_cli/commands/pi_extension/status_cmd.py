"""`pi-extension status` — per-extension origin + loaded state."""
from __future__ import annotations

import click

from agent_toolkit_cli.commands.pi_extension._common import (
    scope_and_roots,
    scope_banner,
)
from agent_toolkit_cli.pi_extension_lock import read_lock
from agent_toolkit_cli.pi_extension_paths import lock_file_path
from agent_toolkit_cli.pi_extension_inventory import InventoryRecord, build_inventory


def _origin_label(record: InventoryRecord) -> str:
    if record.origin == "store-owned":
        return "library"
    if record.origin == "npm":
        return "npm managed" if record.managed else "npm unmanaged"
    return record.origin


@click.command("status")
@click.argument("slugs", nargs=-1)
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.pass_context
def status_cmd(
    ctx: click.Context,
    slugs: tuple[str, ...],
    global_: bool,
    project_flag: bool,
) -> None:
    """Show origin and loaded-scope for each pi extension."""
    scope, home, project_root, implicit = scope_and_roots(
        global_,
        project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
        read_only=True,
    )
    lock_path = lock_file_path(scope=scope, home=home, project=project_root)
    scope_banner(
        scope, implicit=implicit, lock_path=lock_path,
        count=len(read_lock(lock_path).skills),
    )
    records = build_inventory(home=home, project=project_root)
    if slugs:
        wanted = set(slugs)
        records = [r for r in records if r.slug in wanted]
    for r in records:
        scopes = []
        if r.global_loaded:
            scopes.append("global")
        if r.project_loaded:
            scopes.append("project")
        loaded = ",".join(scopes) if scopes else "-"
        pin = f"pinned:{r.pinned_sha[:7]}" if r.pinned_sha else ""
        click.echo(f"{r.slug}\t{_origin_label(r)}\t{loaded}\t{pin}")
