"""agent-toolkit-cli Python CLI dispatcher."""
from __future__ import annotations

import click

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
def main() -> None:
    """agent-toolkit-cli."""


main.add_command(skill)


if __name__ == "__main__":
    main()
