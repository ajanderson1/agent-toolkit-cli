"""`bundle` command group — install/validate a toolkit-native bundle manifest."""
from __future__ import annotations

import click

from agent_toolkit_cli.commands.bundle import install_cmd as _install_mod
from agent_toolkit_cli.commands.bundle import validate_cmd as _validate_mod


@click.group(help="Install assets declared together in a bundle manifest.")
def bundle() -> None:
    """Bundle = a stateless shortcut that fans out to per-kind installers."""


bundle.add_command(_install_mod.install_cmd, name="install")
bundle.add_command(_validate_mod.validate_cmd, name="validate")
