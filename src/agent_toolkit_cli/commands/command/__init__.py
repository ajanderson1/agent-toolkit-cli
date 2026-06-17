from __future__ import annotations

import click

from agent_toolkit_cli.commands.command.add_cmd import add_cmd
from agent_toolkit_cli.commands.command.doctor_cmd import doctor_cmd
from agent_toolkit_cli.commands.command.import_cmd import import_cmd
from agent_toolkit_cli.commands.command.install_cmd import install_cmd
from agent_toolkit_cli.commands.command.list_cmd import list_cmd
from agent_toolkit_cli.commands.command.push_cmd import push_cmd
from agent_toolkit_cli.commands.command.remove_cmd import remove_cmd
from agent_toolkit_cli.commands.command.reset_cmd import reset_cmd
from agent_toolkit_cli.commands.command.status_cmd import status_cmd
from agent_toolkit_cli.commands.command.uninstall_cmd import uninstall_cmd
from agent_toolkit_cli.commands.command.update_cmd import update_cmd


@click.group(name="command")
def command() -> None:
    """Manage commands via COMMAND.md folders + commands-lock.json."""


command.add_command(list_cmd)
command.add_command(list_cmd, name="ls")
command.add_command(status_cmd)
command.add_command(add_cmd)
command.add_command(install_cmd)
command.add_command(uninstall_cmd)
command.add_command(remove_cmd)
command.add_command(update_cmd)
command.add_command(push_cmd)
command.add_command(import_cmd)
command.add_command(reset_cmd)
command.add_command(doctor_cmd)
