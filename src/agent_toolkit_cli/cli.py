"""agent-toolkit-cli Python CLI dispatcher."""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli._repo_resolution import RepoNotFoundError, resolve_toolkit_root
from agent_toolkit_cli.commands.skill import skill


@click.group(
    help=(
        "agent-toolkit-cli — manage skills via per-skill upstream git repos + "
        "lockfile. Run `agent-toolkit-cli skill --help` for subcommands.\n\n"
        "Pre-v2 commands (check, link, doctor, etc.) were removed in v2.3.0. "
        "The frozen v1 surface lives at the v1.0.0 tag; install it via "
        "`uv tool install --from git+https://github.com/ajanderson1/agent-toolkit-cli@v1.0.0 agent-toolkit`."
    )
)
@click.option(
    "--toolkit-repo",
    "toolkit_repo",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Path to the agent-toolkit repo (overrides env/walk-up/default).",
)
@click.option(
    "--project",
    "project_root",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Path to the consumer project (default: CWD).",
)
@click.pass_context
def main(ctx: click.Context, toolkit_repo: Path | None, project_root: Path | None) -> None:
    """agent-toolkit-cli."""
    ctx.ensure_object(dict)
    ctx.obj["project_root"] = Path(project_root) if project_root else None
    if toolkit_repo is None:
        ctx.obj["toolkit_root"] = None
        return
    try:
        ctx.obj["toolkit_root"] = resolve_toolkit_root(toolkit_repo)
    except RepoNotFoundError as exc:
        click.echo(str(exc), err=True)
        ctx.exit(2)


main.add_command(skill)


if __name__ == "__main__":
    main()
