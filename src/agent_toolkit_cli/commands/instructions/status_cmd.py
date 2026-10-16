"""`instructions status` — inventory the actual scoped pointer slots."""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli import instructions_install
from agent_toolkit_cli.instructions_adapters.symlink import canonical_usable, inspect_pointer
from agent_toolkit_cli.commands.instructions.install_cmd import _resolve_project_root


@click.command(help='Actual pointer state: ok / missing (uninstalled) / broken / conflict.')
@click.option('--scope', type=click.Choice(['project', 'global']), default='project')
@click.pass_context
def status_cmd(ctx: click.Context, scope: str) -> None:
    project = _resolve_project_root(ctx, scope)
    home = Path.home() if scope == 'global' else None
    canonical = instructions_install._resolve_canonical(scope, project)
    usable = canonical_usable(canonical)
    for harness, pointer in instructions_install.pointer_slots(scope=scope, project_root=project, home=home).items():
        state = inspect_pointer(pointer, canonical)
        label = ('ok' if usable else 'broken') if state.linked else ('conflict' if state.conflict else 'missing')
        click.echo(f'{harness:14s}  {label:8s}  {pointer}' + (f' ({state.error})' if state.error else ''))
