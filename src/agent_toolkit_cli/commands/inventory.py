"""`agent-toolkit inventory` — man-page-style asset library."""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli._repo_resolution import RepoNotFoundError, resolve_toolkit_root
from agent_toolkit_cli._support import ALL_HARNESSES
from agent_toolkit_cli.inventory import render_asset_card, render_inventory

_KINDS = ("skill", "agent", "command", "hook", "mcp", "plugin", "pi-extension")


@click.command(name="inventory")
@click.argument("target", required=False)
@click.option(
    "--toolkit-repo",
    "toolkit_root",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Path to the agent-toolkit repo (defaults to group --toolkit-repo / env / walk-up / ~/GitHub/agent-toolkit).",
)
@click.option("--harness", type=click.Choice(list(ALL_HARNESSES)))
@click.option("--origin", type=click.Choice(["first-party", "third-party"]))
@click.option("--lifecycle", type=click.Choice(["experimental", "stable", "deprecated"]))
@click.option("--format", "fmt", type=click.Choice(["md", "json"]), default="md")
@click.pass_context
def inventory(
    ctx: click.Context,
    target: str | None,
    toolkit_root: Path | None,
    harness: str | None,
    origin: str | None,
    lifecycle: str | None,
    fmt: str,
) -> None:
    """List assets, filter by kind, or zoom into a single asset by slug.

    Library-scoped: this is a read-only view of the SSOT's asset catalog. For
    install state per scope (user/project), use the bash `list` command.

    Argument-shape dispatch:
      - no TARGET           → full inventory (with optional filter flags)
      - TARGET ∈ kinds      → filter to that kind. Kind names take precedence
                              over slug names; if you have an asset whose slug
                              equals a kind name (e.g. a skill literally named
                              "skill"), use the kind filter and look for it in
                              the rendered group.
      - TARGET (otherwise)  → render the man-page card for that slug. Errors
                              non-zero if no asset has that slug.
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
    if target is None:
        click.echo(render_inventory(root, fmt=fmt, harness=harness, origin=origin, lifecycle=lifecycle))
        return
    if target in _KINDS:
        click.echo(render_inventory(root, fmt=fmt, kind=target, harness=harness, origin=origin, lifecycle=lifecycle))
        return
    try:
        click.echo(render_asset_card(root, slug=target))
    except KeyError:
        raise click.ClickException(f"unknown asset slug or kind: {target!r}")
