"""`agent-toolkit fix` — regenerate auto-generated regions and reconcile MCP drift."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import click

from agent_toolkit_cli._repo_resolution import RepoNotFoundError, resolve_toolkit_root
from agent_toolkit_cli._ui import header, summary
from agent_toolkit_cli.generators.component_table import render_component_table
from agent_toolkit_cli.generators.markers import inject_region
from agent_toolkit_cli.generators.submodule_table import render_submodule_table
from agent_toolkit_cli.schema import Validator
from agent_toolkit_cli.walker import discover_assets

_REGION_GENERATORS = ("component-table", "submodule-table")


@click.command(short_help="Regenerate AGENTS.md auto-regions.")
@click.option(
    "--toolkit-repo",
    "toolkit_root",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Path to the agent-toolkit repo (defaults to group --toolkit-repo / env / walk-up / ~/GitHub/agent-toolkit).",
)
@click.option(
    "--only",
    "only",
    default=None,
    type=click.Choice(_REGION_GENERATORS),
    help="Regenerate only this region; default regenerates all.",
)
@click.option(
    "--to-stdout",
    is_flag=True,
    help="Print the rebuilt AGENTS.md to stdout without modifying the file.",
)
@click.option(
    "--harness",
    type=click.Choice(["claude", "codex", "opencode", "pi"]),
    default="codex",
    help="Harness for MCP reconcile (default: codex).",
)
@click.option(
    "--scope",
    type=click.Choice(["user", "project"]),
    default="user",
    help="Scope for MCP reconcile (default: user).",
)
@click.option(
    "--mcps-only",
    "mcps_only",
    is_flag=True,
    default=False,
    help="Skip AGENTS.md region regen; reconcile MCPs only.",
)
@click.pass_context
def fix(
    ctx: click.Context,
    toolkit_root: Path | None,
    only: str | None,
    to_stdout: bool,
    harness: str,
    scope: str,
    mcps_only: bool,
) -> None:
    """Regenerate the BEGIN/END marker-bounded regions inside AGENTS.md
    (component-table and submodule-table) and/or reconcile MCP drift to
    canonical form. With --to-stdout, prints the AGENTS.md result without
    touching the file (MCP reconcile is skipped in that mode).
    """
    if toolkit_root is None:
        toolkit_root = (ctx.obj or {}).get("toolkit_root")
    if toolkit_root is None:
        try:
            toolkit_root = resolve_toolkit_root(explicit=None)
        except RepoNotFoundError as exc:
            raise click.ClickException(str(exc))
    else:
        toolkit_root = Path(toolkit_root).resolve()
    root = toolkit_root

    if not mcps_only:
        # Existing AGENTS.md regen path (preserved verbatim from original impl).
        header("Regenerating AGENTS.md auto-regions...")
        targets = (only,) if only in _REGION_GENERATORS else _REGION_GENERATORS
        agents_path = root / "AGENTS.md"
        text = agents_path.read_text()
        for region in targets:
            body = _render(region, root)
            text = inject_region(text, region=region, body=body)
        if to_stdout:
            click.echo(text, nl=False)
            summary(f"Rendered AGENTS.md to stdout ({len(targets)} regions, file unchanged).")
        else:
            agents_path.write_text(text)
            summary(f"Updated AGENTS.md ({len(targets)} regions).")

    # MCP reconcile pass: skip in --to-stdout mode (it's region-only).
    if not to_stdout:
        _reconcile_mcps(root, harness=harness, scope=scope, project_root=Path.cwd())


def _render(region: str, root: Path) -> str:
    if region == "component-table":
        validator = Validator(toolkit_root=root)
        assets = discover_assets(root)
        metadata: dict[tuple[str, str], dict] = {}
        for asset in assets:
            data = validator._load_metadata(asset)  # noqa: SLF001
            if data is not None:
                metadata[(asset.kind, asset.slug)] = data
        return render_component_table(assets, metadata)
    if region == "submodule-table":
        return render_submodule_table(root)
    raise ValueError(f"unknown region: {region}")


def _reconcile_mcps(
    toolkit_root: Path,
    *,
    harness: str,
    scope: str,
    project_root: Path,
) -> None:
    """For each allow-listed MCP, run apply_link to bring on-disk to canonical.

    Skips silently with a loud message if the harness has no adapter.
    Diff-first: when nothing to write, mtime is preserved.
    """
    from agent_toolkit_cli._allowlist import read_allowlist
    from agent_toolkit_cli.commands._mcp_dispatch import (
        _build_mcp_entries,
        apply_link,
    )
    from agent_toolkit_cli.harness_adapters import get_adapter
    from agent_toolkit_cli.harness_adapters.base import (
        CannotInstall,
        UnimplementedAdapter,
    )

    if scope == "user":
        allowlist_path = Path(os.environ.get("HOME", "")) / ".agent-toolkit.yaml"
    else:
        allowlist_path = project_root / ".agent-toolkit.yaml"
    if not allowlist_path.is_file():
        return
    allowed = read_allowlist(allowlist_path).get("mcps") or []
    if not allowed:
        return

    adapter = get_adapter(harness)
    if isinstance(adapter, UnimplementedAdapter):
        click.echo(adapter.skip_message())
        return

    entries = _build_mcp_entries(toolkit_root, allowed)
    if not entries:
        return

    # Diff-first: preserve mtime when nothing changed.
    actions = adapter.diff(
        scope, project_root, entries, previously_allowed=set(allowed)
    )
    nontrivial = [a for a in actions if a.op != "unchanged"]
    if not nontrivial:
        return

    try:
        apply_link(
            adapter,
            scope=scope,
            project_root=project_root,
            entries=entries,
            dry_run=False,
            stdout=sys.stdout,
            previously_allowed=set(allowed),
        )
    except CannotInstall as exc:
        click.echo(f"warning: {exc}", err=True)
