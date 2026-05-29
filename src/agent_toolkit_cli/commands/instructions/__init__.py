"""`agent-toolkit-cli instructions ...` command group."""
from __future__ import annotations

import click

from .doctor_cmd import doctor_cmd
from .install_cmd import install_cmd
from .list_cmd import list_cmd
from .status_cmd import status_cmd
from .uninstall_cmd import uninstall_cmd


@click.group(help="Manage harness-aware pointers to a canonical AGENTS.md.")
def instructions() -> None:
    """Root for the instructions-kind verb group."""


instructions.add_command(install_cmd, name="install")
instructions.add_command(uninstall_cmd, name="uninstall")
instructions.add_command(list_cmd, name="list")
instructions.add_command(status_cmd, name="status")
instructions.add_command(doctor_cmd, name="doctor")
