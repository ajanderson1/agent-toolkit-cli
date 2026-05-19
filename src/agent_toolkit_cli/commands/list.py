# src/agent_toolkit_cli/commands/list.py
"""list — display asset inventory with user/project install state."""
from __future__ import annotations

import os
from pathlib import Path

import click

from agent_toolkit_cli import _ui
from agent_toolkit_cli._repo_resolution import RepoNotFoundError, resolve_toolkit_root
from agent_toolkit_cli._support import USER_LINKED_STATUSES
from agent_toolkit_cli.commands._link_lib import KINDS_FOR_PROJECTION
from agent_toolkit_cli.commands._list_json import ALL_HARNESSES, _build_inventory

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

_USER_SCOPE_GLYPH = "🌐"


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
                "skill agent command hook plugin mcp or "
                + " ".join(ALL_HARNESSES)
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
        from agent_toolkit_cli.generators.list_report import format_report  # noqa: PLC0415

        inv = _build_inventory(
            toolkit_root, project_root, kind=kind_filter, harness=harness_filter
        )
        click.echo(format_report(inv, project_root=project_root), nl=False)
        _ui.summary("Done.")
        return

    # JSON format: delegate entirely to the existing _list-json hidden command.
    if fmt == "json":
        from agent_toolkit_cli.commands._list_json import list_json  # noqa: PLC0415

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

    inv = _build_inventory(
        toolkit_root, project_root, kind=kind_filter, harness=harness_filter
    )

    def _scope_glyph(cells: list[dict], scope: str) -> str:  # type: ignore[type-arg]
        """Return '✓' iff any cell at this scope is in a linked state, else '—'.

        For text mode we collapse all harnesses/aliases for the scope into
        one glyph — the bracket already discloses which harnesses declared it.
        """
        for c in cells:
            if c.get("scope") != scope:
                continue
            if c.get("status") in USER_LINKED_STATUSES:
                return "✓"
        return "—"

    # Group inventory assets by kind to preserve the previous "KIND (N)" headers.
    by_kind: dict[str, list[dict]] = {}  # type: ignore[type-arg]
    for asset in inv.get("assets", []):
        by_kind.setdefault(asset["kind"], []).append(asset)

    for kind in KINDS_FOR_PROJECTION:
        if kind_filter and kind_filter != kind:
            continue
        assets_for_kind = by_kind.get(kind, [])
        rows: list[str] = []
        for asset in assets_for_kind:
            declared = asset.get("declared_harnesses") or []
            # When a harness filter is active, _build_inventory has already
            # narrowed cells to that harness; declared_harnesses is unfiltered
            # (it's the on-disk frontmatter) so respect the filter here for
            # the bracket display as well.
            if harness_filter and harness_filter not in declared:
                continue

            cells = asset.get("cells", [])
            user_state = _scope_glyph(cells, "user")
            project_state = _scope_glyph(cells, "project")

            if harness_filter:
                h_display = ""
            else:
                h_display = f"[{' '.join(declared)}]"

            project_suffix = (
                f" {_USER_SCOPE_GLYPH}"
                if user_state == "✓" and project_state == "✓"
                else ""
            )
            row = (
                f"  {asset['slug']:<20} {h_display:<30} "
                f"user:{user_state} project:{project_state}{project_suffix}"
            )
            rows.append(row)

        if rows:
            title = _KIND_TITLE[kind]
            click.echo(f"{title} ({len(rows)})")
            for row in rows:
                click.echo(row)

    _ui.summary("Done.")
