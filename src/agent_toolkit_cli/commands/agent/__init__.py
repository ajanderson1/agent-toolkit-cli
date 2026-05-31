"""`agent-toolkit-cli agent <verb>` — manage agents (subagents) via owned git
repos + agents-lock.json.

Mirrors commands/pi_extension/ in structure and conventions.
Read verbs (list/status/update/push/reset/import/doctor) pass read_only=True
to scope_and_roots so they default to global outside a project.
Write verbs (install/uninstall/remove) default to the project scope when a
project lock file is present in cwd.
`agent add` is global-only by construction (no -p flag).
"""
from __future__ import annotations

import click

from agent_toolkit_cli.commands.agent.add_cmd import add_cmd
from agent_toolkit_cli.commands.agent.doctor_cmd import doctor_cmd
from agent_toolkit_cli.commands.agent.import_cmd import import_cmd
from agent_toolkit_cli.commands.agent.install_cmd import install_cmd
from agent_toolkit_cli.commands.agent.list_cmd import list_cmd
from agent_toolkit_cli.commands.agent.push_cmd import push_cmd
from agent_toolkit_cli.commands.agent.remove_cmd import remove_cmd
from agent_toolkit_cli.commands.agent.reset_cmd import reset_cmd
from agent_toolkit_cli.commands.agent.status_cmd import status_cmd
from agent_toolkit_cli.commands.agent.uninstall_cmd import uninstall_cmd
from agent_toolkit_cli.commands.agent.update_cmd import update_cmd


@click.group(name="agent")
def agent() -> None:
    """Manage agents via owned git repos + agents-lock.json."""


agent.add_command(list_cmd)
agent.add_command(list_cmd, name="ls")
agent.add_command(status_cmd)
agent.add_command(add_cmd)
agent.add_command(install_cmd)
agent.add_command(uninstall_cmd)
agent.add_command(remove_cmd)
agent.add_command(update_cmd)
agent.add_command(push_cmd)
agent.add_command(import_cmd)
agent.add_command(reset_cmd)
agent.add_command(doctor_cmd)
