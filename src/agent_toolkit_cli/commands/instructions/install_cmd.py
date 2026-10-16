"""`instructions install` — create explicit per-harness pointers."""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli import instructions_install
from agent_toolkit_cli.instructions_adapters import SUPPORTED_HARNESSES
from agent_toolkit_cli.instructions_adapters.symlink import CELLS, PointerConflictError
from agent_toolkit_cli.instructions_matrix import instructions_matrix_rows
from agent_toolkit_cli.skill_agents import AGENTS


@click.command(help='Install per-harness pointers to AGENTS.md; no installation record is needed.')
@click.option('--scope', type=click.Choice(['project', 'global']), default='project', help='Pointer scope.')
@click.option('--harness', 'harnesses', multiple=True,
              help='Specific harness(es). Repeat for multiple. Default: all symlink-verdict harnesses.')
@click.pass_context
def install_cmd(ctx: click.Context, scope: str, harnesses: tuple[str, ...]) -> None:
    project_root = _resolve_project_root(ctx, scope)
    verdicts = {row['harness']: row['verdict'] for row in instructions_matrix_rows(scope)}
    available = {h for h in SUPPORTED_HARNESSES if CELLS[h][scope] and verdicts.get(h, '').lower().startswith('symlink')}
    targets = list(harnesses) or sorted(available)
    for h in targets:
        if h in available:
            continue
        if h in AGENTS:
            verdict = verdicts.get(h, 'native')
            raise click.ClickException(
                f'{h!r}: this harness is `{verdict}` at {scope} scope — no supported pointer needed/available. See harness-matrix.md.'
            )
        raise click.ClickException(f'{h!r}: not in the harness catalog')
    try:
        p = instructions_install.apply(
            scope=scope, project_root=project_root,
            home=Path.home() if scope == 'global' else None, add_harnesses=targets,
        )
    except (instructions_install.CanonicalMissingError, PointerConflictError, OSError, RuntimeError) as exc:
        raise click.ClickException(f'{exc}; inspect status before retrying') from exc
    for act in p.actions:
        label = 'created' if act.action == 'create' else 'ok'
        click.echo(f'{label:8s} {act.harness:14s}  {act.pointer}')


def _resolve_project_root(ctx: click.Context, scope: str) -> Path | None:
    if scope == 'global':
        return None
    obj = ctx.find_root().params.get('project_root')
    return obj if obj else Path.cwd()
