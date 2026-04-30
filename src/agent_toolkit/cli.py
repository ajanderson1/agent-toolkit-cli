"""agent-toolkit Python CLI dispatcher."""
from __future__ import annotations

import click

from agent_toolkit.commands.check import check
from agent_toolkit.commands.doctor import doctor
from agent_toolkit.commands.fix import fix
from agent_toolkit.commands.ingest import ingest
from agent_toolkit.commands.inventory import inventory
from agent_toolkit.commands.new import new


@click.group()
def main() -> None:
    """agent-toolkit — manage harness-agnostic assets."""


main.add_command(check)
main.add_command(doctor)
main.add_command(fix)
main.add_command(ingest)
main.add_command(inventory)
main.add_command(new)


if __name__ == "__main__":
    main()
