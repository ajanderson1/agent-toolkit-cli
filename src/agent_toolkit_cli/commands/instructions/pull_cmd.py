"""Explicit host-content deployment; pointer enablement remains separate."""
from __future__ import annotations

import difflib
import hashlib
import subprocess

import click

from agent_toolkit_cli import instructions_source as source
from agent_toolkit_cli.instructions_paths import global_canonical_agents_md


def _display(content: bytes) -> list[str]:
    text = content.decode('utf-8', errors='backslashreplace')
    # Existing user content may contain terminal escapes, unlike validated sources.
    text = ''.join(f'\\x{ord(c):02x}' if (ord(c) < 32 and c not in '\n\t') or 127 <= ord(c) <= 159 else c
                   for c in text)
    return text.splitlines(keepends=True)


def _apply(candidate: source.Candidate, *, replace: bool, dry_run: bool, yes: bool) -> None:
    before = source.current()
    canonical = global_canonical_agents_md()
    click.echo(f'Global destination: {canonical}')
    for key, value in candidate.provenance.items():
        click.echo(f'{key}: {value}')
    click.echo(f'SHA-256: {hashlib.sha256(candidate.content).hexdigest()}')
    diff = difflib.unified_diff(_display(before.content or b''), _display(candidate.content),
                                fromfile='current global AGENTS.md', tofile='selected instructions')
    click.echo(''.join(diff))
    if dry_run:
        click.echo('Preview only; no global content or harness pointers changed.')
        return
    if before.content is not None and not replace:
        raise source.DeploymentError('canonical exists; use --replace to authorize replacement (a backup is retained)')
    if not yes and not click.confirm('Deploy these global instructions? Existing harness selections are unchanged.', default=False):
        click.echo('Unchanged.')
        return
    directory = source.deploy(candidate, before)
    click.echo(f'Deployed global instructions. Deployment: {directory.name}')
    click.echo(f'Content/provenance/backup: {directory}')
    click.echo('Harness pointers unchanged. Start a fresh agent session to load the new content.')


@click.command(help='Download one committed host file into global AGENTS.md; never enables harnesses.')
@click.option('--source', 'repository', required=True, help='Git repository root: URL, owner/repo or explicit local path.')
@click.option('--host', required=True, help='Select AGENTS.<host>.md at repository root or under agents-instructions/ (lowercase).')
@click.option('--ref', default='main', show_default=True,
              help='Fetch latest main by default; override with another branch or historical ref if needed.')
@click.option('--replace', is_flag=True, help='Authorize replacing an existing regular canonical file, with backup.')
@click.option('--dry-run', is_flag=True, help='Fetch, validate and preview without changing global state.')
@click.option('--yes', is_flag=True, help='Confirm deployment without prompting; --replace is still required for existing content.')
def pull_cmd(repository: str, host: str, ref: str, replace: bool, dry_run: bool, yes: bool) -> None:
    try:
        _apply(source.fetch(repository, host, ref), replace=replace, dry_run=dry_run, yes=yes)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise click.ClickException(str(exc)) from exc


@click.command(help='Restore the previous bytes saved by a global deployment ID; keeps a new backup.')
@click.argument('deployment')
@click.option('--replace', is_flag=True, help='Authorize replacing an existing regular canonical file, with backup.')
@click.option('--dry-run', is_flag=True, help='Preview the previous content without changing global state.')
@click.option('--yes', is_flag=True, help='Confirm restoration without prompting.')
def restore_cmd(deployment: str, replace: bool, dry_run: bool, yes: bool) -> None:
    try:
        _apply(source.restore_candidate(deployment), replace=replace, dry_run=dry_run, yes=yes)
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
