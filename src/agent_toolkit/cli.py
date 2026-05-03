"""agent-toolkit Python CLI dispatcher."""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit._repo_resolution import RepoNotFoundError, resolve_toolkit_root
from agent_toolkit.commands._list_json import list_json
from agent_toolkit.commands._yaml_edit import yaml_edit
from agent_toolkit.commands.check import check
from agent_toolkit.commands.doctor import doctor
from agent_toolkit.commands.fix import fix
from agent_toolkit.commands.ingest import ingest
from agent_toolkit.commands.inventory import inventory
from agent_toolkit.commands.new import new


@click.group(
    help=(
        "agent-toolkit — metadata-aware commands for asset frontmatter and AGENTS.md.\n\n"
        "Resolves the toolkit repo via: --toolkit-repo flag > AGENT_TOOLKIT_REPO env > "
        ".agent-toolkit-source walk-up > ~/GitHub/agent-toolkit default. "
        "Subcommands' --toolkit-repo flag still works for explicit per-invocation paths."
    )
)
@click.option(
    "--toolkit-repo",
    "toolkit_repo",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Path to the agent-toolkit repo (overrides env/walk-up/default).",
)
@click.pass_context
def main(ctx: click.Context, toolkit_repo: Path | None) -> None:
    """agent-toolkit metadata commands."""
    ctx.ensure_object(dict)
    if toolkit_repo is None:
        ctx.obj["toolkit_root"] = None
        return
    try:
        ctx.obj["toolkit_root"] = resolve_toolkit_root(toolkit_repo)
    except RepoNotFoundError as exc:
        click.echo(str(exc), err=True)
        ctx.exit(2)


main.add_command(check)
main.add_command(doctor)
main.add_command(fix)
main.add_command(ingest)
main.add_command(inventory)
main.add_command(new)
main.add_command(yaml_edit)
main.add_command(list_json)


if __name__ == "__main__":
    main()
