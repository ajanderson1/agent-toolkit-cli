# src/agent_toolkit/commands/list.py
"""list — display asset inventory with user/project install state."""
from __future__ import annotations

import os
from pathlib import Path

import click

from agent_toolkit import _ui
from agent_toolkit._allowlist import kind_to_section, read_allowlist
from agent_toolkit._repo_resolution import RepoNotFoundError, resolve_toolkit_root
from agent_toolkit.commands._link_lib import (
    KINDS_FOR_PROJECTION,
    _asset_harnesses,
    harness_target_dir,
)
from agent_toolkit.commands._list_json import ALL_HARNESSES
from agent_toolkit.walker import discover_assets

_KNOWN_KINDS = frozenset(KINDS_FOR_PROJECTION)
_KNOWN_HARNESSES = frozenset(ALL_HARNESSES)

_KIND_TITLE: dict[str, str] = {
    "skill": "SKILLS",
    "agent": "AGENTS",
    "command": "COMMANDS",
    "hook": "HOOKS",
    "plugin": "PLUGINS",
    "mcp": "MCPs",
    "pi-extension": "PI EXTENSIONS",
}


def _install_state(
    yaml_path: Path,
    kind: str,
    slug: str,
    declared_harnesses: list[str],
    harness_filter: str | None,
    scope: str,
    project_root: Path,
) -> str:
    """Return '✓' or '—' for one asset/scope combination.

    Logic mirrors bin/lib/list.sh _list_install_state:
    - If the YAML doesn't exist or slug isn't listed: '—'
    - If slug is listed: check symlink existence across harnesses
    """
    if not yaml_path.is_file():
        return "—"
    try:
        section = kind_to_section(kind)
    except ValueError:
        return "—"
    allow = read_allowlist(yaml_path)
    if slug not in (allow.get(section) or []):
        return "—"
    # Slug is in the allowlist — now check for a symlink.
    harnesses_to_check = [harness_filter] if harness_filter else declared_harnesses
    for h in harnesses_to_check:
        if not h:
            continue
        target_dir = harness_target_dir(h, kind, scope, project_root)
        if target_dir is None:
            continue
        if (target_dir / slug).is_symlink():
            return "✓"
    return "—"


@click.command("list")
@click.argument("filter1", required=False, default=None, metavar="[KIND|HARNESS]")
@click.argument("filter2", required=False, default=None, metavar="[KIND|HARNESS]")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (text or json).",
)
@click.option("--quiet", "-q", is_flag=True, default=False)
@click.option(
    "--toolkit-repo",
    "toolkit_repo",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Path to the agent-toolkit repo.",
)
@click.option(
    "--project",
    "project_flag",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Path to the consumer project (defaults to CWD).",
)
@click.option(
    "--report",
    "report",
    is_flag=True,
    default=False,
    help="Emit a grouped human-readable inventory (harness → scope → kind).",
)
@click.pass_context
def list_cmd(
    ctx: click.Context,
    filter1: str | None,
    filter2: str | None,
    fmt: str,
    quiet: bool,
    toolkit_repo: Path | None,
    project_flag: Path | None,
    report: bool,
) -> None:
    """Display the asset inventory with user/project install state."""
    if quiet:
        os.environ["AGENT_TOOLKIT_QUIET"] = "1"

    if report and fmt == "json":
        click.echo("cannot combine --report with --format=json", err=True)
        ctx.exit(2)
        return

    # Disambiguate positional filters against known kinds/harnesses.
    kind_filter: str | None = None
    harness_filter: str | None = None
    for arg in (filter1, filter2):
        if arg is None:
            continue
        if arg in _KNOWN_KINDS:
            if kind_filter is not None:
                click.echo(f"duplicate kind filter: {arg}", err=True)
                ctx.exit(2)
                return
            kind_filter = arg
        elif arg in _KNOWN_HARNESSES:
            if harness_filter is not None:
                click.echo(f"duplicate harness filter: {arg}", err=True)
                ctx.exit(2)
                return
            harness_filter = arg
        else:
            msg = (
                f"unknown filter '{arg}' — expected one of: "
                "skill agent command hook plugin mcp or claude codex opencode pi"
            )
            click.echo(msg, err=True)
            ctx.exit(2)
            return

    # Resolve toolkit_root via group context, flag, or four-step resolver.
    toolkit_root: Path | None = (ctx.obj or {}).get("toolkit_root")
    if toolkit_repo is not None:
        try:
            toolkit_root = resolve_toolkit_root(toolkit_repo)
        except RepoNotFoundError as exc:
            click.echo(str(exc), err=True)
            ctx.exit(2)
            return
    if toolkit_root is None:
        try:
            toolkit_root = resolve_toolkit_root(None)
        except RepoNotFoundError as exc:
            click.echo(str(exc), err=True)
            ctx.exit(2)
            return

    if project_flag:
        project_root = Path(project_flag).resolve()
    elif (group_proj := (ctx.obj or {}).get("project_root")) is not None:
        project_root = Path(group_proj).resolve()
    else:
        project_root = Path.cwd()

    # Report format: grouped human-readable view via the same inventory builder.
    if report:
        from agent_toolkit.commands._list_json import _build_inventory  # noqa: PLC0415
        from agent_toolkit.generators.list_report import format_report  # noqa: PLC0415

        inv = _build_inventory(
            toolkit_root, project_root, kind=kind_filter, harness=harness_filter
        )
        click.echo(format_report(inv, project_root=project_root), nl=False)
        _ui.summary("Done.")
        return

    # JSON format: delegate entirely to the existing _list-json hidden command.
    if fmt == "json":
        from agent_toolkit.commands._list_json import list_json  # noqa: PLC0415

        ctx.invoke(
            list_json,
            toolkit_root=toolkit_root,
            project_root=project_root,
            kind=kind_filter,
            harness=harness_filter,
        )
        return

    _ui.header(
        f"Asset inventory (filter: kind={kind_filter or 'any'},"
        f" harness={harness_filter or 'any'}):"
    )

    user_yaml = Path(os.environ.get("HOME", "")) / ".agent-toolkit.yaml"
    project_yaml = project_root / ".agent-toolkit.yaml"

    for kind in KINDS_FOR_PROJECTION:
        if kind_filter and kind_filter != kind:
            continue

        rows: list[str] = []
        for asset in discover_assets(toolkit_root):
            if asset.kind != kind:
                continue
            declared = _asset_harnesses(asset.path, asset.kind)
            if harness_filter and harness_filter not in declared:
                continue

            user_state = _install_state(
                user_yaml, kind, asset.slug, declared, harness_filter, "user", project_root
            )
            project_state = _install_state(
                project_yaml, kind, asset.slug, declared, harness_filter, "project", project_root
            )

            # Harness bracket: show all declared harnesses unless filtered.
            if harness_filter:
                h_display = ""
            else:
                h_display = f"[{' '.join(declared)}]"

            row = f"  {asset.slug:<20} {h_display:<30} user:{user_state} project:{project_state}"
            rows.append(row)

        if rows:
            title = _KIND_TITLE[kind]
            click.echo(f"{title} ({len(rows)})")
            for row in rows:
                click.echo(row)

    _ui.summary("Done.")
