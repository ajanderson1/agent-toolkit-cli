# src/agent_toolkit_cli/commands/diff.py
"""diff — preview what `link` would change. Alias for `link --dry-run`."""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli.commands.link import link


@click.command("diff")
@click.argument("scope", type=click.Choice(["user", "project"]))
@click.argument("harness")
@click.option(
    "--toolkit-repo",
    "toolkit_repo",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
)
@click.option(
    "--project",
    "project_flag",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
)
@click.option("--quiet", "-q", is_flag=True, default=False)
@click.pass_context
def diff(
    ctx: click.Context,
    scope: str,
    harness: str,
    toolkit_repo: Path | None,
    project_flag: Path | None,
    quiet: bool,
) -> None:
    """Preview what `link` would change (alias for `link --dry-run`)."""
    ctx.invoke(
        link,
        scope=scope,
        harness=harness,
        target=None,
        all_flag=False,
        plan_flag=None,
        assume_yes=False,
        dry_run=True,
        quiet=quiet,
        toolkit_repo=toolkit_repo,
        project_flag=project_flag,
    )
