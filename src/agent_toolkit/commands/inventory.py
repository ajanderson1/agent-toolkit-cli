"""`agent-toolkit inventory` — man-page-style asset library."""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit.inventory import render_asset_card, render_inventory

_KINDS = ("skill", "agent", "command", "hook", "mcp", "plugin")


@click.command(name="inventory")
@click.argument("target", required=False)
@click.option("--repo-root", default=".", type=click.Path(exists=True, file_okay=False))
@click.option("--harness", type=click.Choice(["claude", "codex", "opencode", "pi"]))
@click.option("--origin", type=click.Choice(["first-party", "third-party"]))
@click.option("--lifecycle", type=click.Choice(["experimental", "stable", "deprecated"]))
@click.option("--format", "fmt", type=click.Choice(["md", "plain", "json"]), default="md")
def inventory(
    target: str | None,
    repo_root: str,
    harness: str | None,
    origin: str | None,
    lifecycle: str | None,
    fmt: str,
) -> None:
    """List assets, filter by kind, or zoom into a single asset by slug."""
    root = Path(repo_root).resolve()
    if target is None:
        click.echo(render_inventory(root, fmt=fmt, harness=harness, origin=origin, lifecycle=lifecycle))
        return
    if target in _KINDS:
        click.echo(render_inventory(root, fmt=fmt, kind=target, harness=harness, origin=origin, lifecycle=lifecycle))
        return
    try:
        click.echo(render_asset_card(root, slug=target))
    except KeyError:
        raise click.UsageError(f"unknown asset slug or kind: {target!r}")
