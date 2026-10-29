"""`agent-toolkit-cli instructions ...` command group."""
from __future__ import annotations

import click

from .doctor_cmd import doctor_cmd
from .install_cmd import install_cmd
from .list_cmd import list_cmd
from .pull_cmd import pull_cmd, restore_cmd
from .status_cmd import status_cmd
from .uninstall_cmd import uninstall_cmd


@click.group(help="Deploy global instruction content and manage harness-aware pointers to canonical AGENTS.md.")
def instructions() -> None:
    """Root for the instructions-asset-type verb group."""


instructions.add_command(install_cmd, name="install")
instructions.add_command(uninstall_cmd, name="uninstall")
instructions.add_command(list_cmd, name="list")
instructions.add_command(status_cmd, name="status")
instructions.add_command(doctor_cmd, name="doctor")
instructions.add_command(pull_cmd, name="pull")
instructions.add_command(restore_cmd, name="restore")
