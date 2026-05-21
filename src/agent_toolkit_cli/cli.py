"""agent-toolkit-cli Python CLI dispatcher."""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import click

from agent_toolkit_cli.commands.skill import skill


try:
    _VERSION = version("agent-toolkit")
except PackageNotFoundError:
    _VERSION = "unknown"


@click.group(
    help=(
        "agent-toolkit-cli — manage skills via per-skill upstream git repos + "
        "lockfile. Run `agent-toolkit-cli skill --help` for subcommands.\n\n"
        "Pre-v2 commands (check, link, doctor, etc.) were removed in v2.3.0. "
        "The frozen v1 surface lives at the v1.0.0 tag; install it via "
        "`uv tool install --from git+https://github.com/ajanderson1/agent-toolkit-cli@v1.0.0 agent-toolkit`."
    )
)
@click.version_option(_VERSION, "--version", "-V", prog_name="agent-toolkit-cli")
@click.option(
    "--project",
    "project_root",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Path to the consumer project (default: CWD).",
)
@click.pass_context
def main(ctx: click.Context, project_root: Path | None) -> None:
    """agent-toolkit-cli."""
    ctx.ensure_object(dict)
    ctx.obj["project_root"] = Path(project_root) if project_root else None


main.add_command(skill)
# Plural alias for muscle memory (matches `npx -y skills`). See #180.
main.add_command(skill, name="skills")


if __name__ == "__main__":
    main()
