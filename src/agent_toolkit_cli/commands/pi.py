"""`agent-toolkit-cli pi …` — unified Pi extension view + manage verbs.

This module owns the `pi` Click group. Inventory landed in commit 1.
`sync` lands in commit 2; `load`/`unload` land in commit 3.
"""
from __future__ import annotations

import json
from pathlib import Path

import click

from agent_toolkit_cli._allowlist import read_allowlist
from agent_toolkit_cli._pi_inventory import PiRecord, build_pi_inventory
from agent_toolkit_cli._pi_paths import PiPaths
from agent_toolkit_cli._pi_settings import read_packages, write_packages


def _read_node_modules_dir(d: Path) -> set[str]:
    if not d.is_dir():
        return set()
    return {p.name for p in d.iterdir() if p.is_dir() or p.is_symlink()}


def _gather_inventory(home: Path, project_root: Path) -> list[PiRecord]:
    pp = PiPaths(home=home, project_root=project_root)

    user_packages = read_packages(pp.user_settings_json)
    project_packages = read_packages(pp.project_settings_json)
    user_node_modules = _read_node_modules_dir(pp.user_node_modules_dir)
    project_node_modules = _read_node_modules_dir(pp.project_node_modules_dir)

    user_allow = read_allowlist(home / ".agent-toolkit.yaml")
    project_allow = read_allowlist(project_root / ".agent-toolkit.yaml")

    user_pi_exts = list(user_allow.get("pi_extensions", []) or [])
    project_pi_exts = list(project_allow.get("pi_extensions", []) or [])
    user_pi_pkgs = list(user_allow.get("pi_packages", []) or [])
    project_pi_pkgs = list(project_allow.get("pi_packages", []) or [])

    return build_pi_inventory(
        paths=pp,
        user_packages=user_packages,
        project_packages=project_packages,
        user_node_modules=user_node_modules,
        project_node_modules=project_node_modules,
        user_allowlist_pi_extensions=user_pi_exts,
        project_allowlist_pi_extensions=project_pi_exts,
        user_allowlist_pi_packages=user_pi_pkgs,
        project_allowlist_pi_packages=project_pi_pkgs,
    )


@click.group(name="pi")
def pi() -> None:
    """Pi: unified extension inventory and load/unload across both channels."""


@pi.command(name="inventory")
@click.option(
    "--scope",
    type=click.Choice(["user", "project", "both"]),
    default="both",
    help="Restrict view to user, project, or both (default).",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["json", "text"]),
    default="text",
)
@click.pass_context
def inventory_cmd(ctx: click.Context, scope: str, fmt: str) -> None:
    """Emit one record per extension Pi could load.

    Reads first-party auto-discovery dirs + third-party `settings.json` and
    `node_modules/` + the toolkit allowlist. Read-only.
    """
    home = Path.home()
    project_root = ctx.obj.get("project_root") if ctx.obj else None
    if project_root is None:
        project_root = Path.cwd()

    records = _gather_inventory(home=home, project_root=project_root)

    # Optional scope filter — drop rows where the requested scope
    # has no loaded-or-intent presence.
    if scope == "user":
        records = [
            r
            for r in records
            if r.user_loaded or r.toolkit_intent in ("user", "both")
        ]
    elif scope == "project":
        records = [
            r
            for r in records
            if r.project_loaded or r.toolkit_intent in ("project", "both")
        ]

    if fmt == "json":
        click.echo(json.dumps([r.to_dict() for r in records], indent=2))
        return

    # text format — one row per record
    if not records:
        click.echo("(no Pi extensions found)")
        return
    click.echo(f"{'SLUG':<24} {'ORIGIN':<12} {'U':<3} {'P':<3} {'INTENT':<8} SOURCE")
    for r in records:
        click.echo(
            f"{r.slug:<24} {r.origin:<12} "
            f"{'✓' if r.user_loaded else '—':<3} "
            f"{'✓' if r.project_loaded else '—':<3} "
            f"{r.toolkit_intent:<8} {r.source}"
        )


@pi.command(name="sync")
@click.option(
    "--scope",
    type=click.Choice(["user", "project", "both"]),
    default="both",
    help="Reconcile user, project, or both allowlist files (default both).",
)
@click.pass_context
def sync_cmd(ctx: click.Context, scope: str) -> None:
    """Reconcile allowlist ``pi_packages:`` → settings.json ``packages[]``.

    Writes only. Does NOT invoke ``pi install`` (fetch step is part of
    ``pi load``). Use ``pi sync`` after manually editing the allowlist.
    Idempotent: a no-op when settings.json already matches the allowlist.
    """
    home = Path.home()
    project_root = ctx.obj.get("project_root") if ctx.obj else None
    if project_root is None:
        project_root = Path.cwd()

    scopes = ("user", "project") if scope == "both" else (scope,)
    pp = PiPaths(home=home, project_root=project_root)

    for s in scopes:
        allow_path = (
            home / ".agent-toolkit.yaml"
            if s == "user"
            else project_root / ".agent-toolkit.yaml"
        )
        allow = read_allowlist(allow_path)
        desired = list(dict.fromkeys(allow.get("pi_packages", []) or []))
        settings_path = (
            pp.user_settings_json if s == "user" else pp.project_settings_json
        )

        current = read_packages(settings_path)
        if current == desired:
            continue
        write_packages(settings_path, desired)
