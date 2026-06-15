"""`agent-toolkit-cli pi-extension <verb>` — manage Pi extensions as owned
git repos (store-owned) or tracked npm packages. PR1 ships read-only verbs
(list/status); PR2a adds add/install/uninstall/remove; PR2b adds the git
lifecycle verbs (import/update/push/reset/doctor)."""
from __future__ import annotations

import click

from agent_toolkit_cli.commands.pi_extension.add_cmd import add_cmd
from agent_toolkit_cli.commands.pi_extension.doctor_cmd import doctor_cmd
from agent_toolkit_cli.commands.pi_extension.import_cmd import import_cmd
from agent_toolkit_cli.commands.pi_extension.install_cmd import install_cmd
from agent_toolkit_cli.commands.pi_extension.list_cmd import list_cmd
from agent_toolkit_cli.commands.pi_extension.push_cmd import push_cmd
from agent_toolkit_cli.commands.pi_extension.remove_cmd import remove_cmd
from agent_toolkit_cli.commands.pi_extension.reset_cmd import reset_cmd
from agent_toolkit_cli.commands.pi_extension.status_cmd import status_cmd
from agent_toolkit_cli.commands.pi_extension.uninstall_cmd import uninstall_cmd
from agent_toolkit_cli.commands.pi_extension.update_cmd import update_cmd


@click.group(name="pi-extension")
def pi_extension() -> None:
    """Manage Pi extensions via owned git repos + pi-extensions-lock.json."""


pi_extension.add_command(list_cmd)
pi_extension.add_command(status_cmd)
pi_extension.add_command(list_cmd, name="ls")
pi_extension.add_command(add_cmd)
pi_extension.add_command(install_cmd)
pi_extension.add_command(uninstall_cmd)
pi_extension.add_command(remove_cmd)
pi_extension.add_command(update_cmd)
pi_extension.add_command(push_cmd)
pi_extension.add_command(import_cmd)
pi_extension.add_command(reset_cmd)
pi_extension.add_command(doctor_cmd)
