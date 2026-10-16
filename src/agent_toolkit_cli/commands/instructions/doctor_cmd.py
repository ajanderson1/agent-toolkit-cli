"""`instructions doctor` — diagnose actual pointers; explicitly opt into file adoption."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import os
from pathlib import Path
import stat

import click

from agent_toolkit_cli import instructions_install
from agent_toolkit_cli.commands.instructions.install_cmd import _resolve_project_root
from agent_toolkit_cli.instructions_adapters.symlink import (
    _pointer_path, canonical_usable, inspect_pointer,
)


@dataclass
class FixAction:
    shell_preview: str
    apply: Callable[[], None]


@dataclass
class Finding:
    message: str
    fix_action: FixAction | None = None


def _adopt_harness_for(pointer: Path, harness: str, *, scope: str,
                       project_root: Path | None, home: Path | None) -> str:
    if pointer == _pointer_path('claude-code', scope, project_root, home):
        return 'claude-code'
    return harness


def _unmanaged_finding(*, pointer: Path, harness: str, canonical: Path,
                       scope: str, project_root: Path | None, home: Path | None) -> Finding:
    message = f'unmanaged: real file at {pointer}'
    if not pointer.is_file() or canonical.is_symlink() or (canonical.exists() and not canonical.is_file()):
        return Finding(message + '; source/destination is not an adoptable regular file')
    harness = _adopt_harness_for(pointer, harness, scope=scope, project_root=project_root, home=home)
    populated = canonical.exists() and canonical.stat().st_size > 0
    backup = pointer.with_name(pointer.name + '.pre-adopt.bak')
    original_stat = pointer.lstat()

    def adopt() -> None:
        if pointer.is_symlink() or not pointer.is_file() or pointer.lstat() != original_stat:
            raise click.ClickException(f'{pointer} changed — re-run doctor')
        if canonical.is_symlink() or (canonical.exists() and not canonical.is_file()):
            raise click.ClickException(f'{canonical} is not an adoptable regular file')
        now_populated = canonical.exists() and canonical.stat().st_size > 0
        if now_populated != populated:
            raise click.ClickException(f'{canonical} changed — re-run doctor')
        if backup.exists() or backup.is_symlink():
            raise click.ClickException(f'{backup} already exists — refusing to overwrite a previous backup')
        empty_stat = canonical.stat() if canonical.exists() and not populated else None
        destination = backup if populated else canonical
        destination.parent.mkdir(parents=True, exist_ok=True)
        pointer.rename(destination)
        try:
            instructions_install.apply(scope=scope, project_root=project_root, home=home, add_harnesses=(harness,))
        except Exception:
            # Remove only the exact link this adoption could have created.
            if pointer.is_symlink() and os.readlink(pointer) == str(canonical.absolute()):
                pointer.unlink()
            if pointer.exists() or pointer.is_symlink():
                raise click.ClickException(f'adoption failed; original preserved at {destination}, slot changed externally')
            destination.rename(pointer)
            if empty_stat is not None:
                with canonical.open('xb'):
                    pass
                canonical.chmod(stat.S_IMODE(empty_stat.st_mode))
                os.utime(canonical, ns=(empty_stat.st_atime_ns, empty_stat.st_mtime_ns))
            raise

    preview = (f'mv {pointer.name} {backup.name} && ' if populated else f'mv {pointer.name} AGENTS.md && ')
    preview += f'instructions install --scope {scope} --harness {harness}'
    detail = f'; AGENTS.md already has content — back up to {backup.name}; reconcile manually' if populated else '; adopt as AGENTS.md'
    return Finding(message + detail, FixAction(preview, adopt))


@click.command(help='Find broken or conflicting pointers; correct manual links need no registration.')
@click.option('--scope', type=click.Choice(['project', 'global']), default='project')
@click.option('--no-fix', is_flag=True, help='Report only; do not prompt or mutate.')
@click.pass_context
def doctor_cmd(ctx: click.Context, scope: str, no_fix: bool) -> None:
    project = _resolve_project_root(ctx, scope)
    home = Path.home() if scope == 'global' else None
    canonical = instructions_install._resolve_canonical(scope, project)
    usable = canonical_usable(canonical)
    findings = []
    seen = set()
    for harness, pointer in instructions_install.pointer_slots(scope=scope, project_root=project, home=home).items():
        try:
            physical = pointer.parent.resolve() / pointer.name
        except (OSError, RuntimeError):
            physical = pointer.absolute()
        if physical in seen:
            continue
        seen.add(physical)
        state = inspect_pointer(pointer, canonical)
        if state.error:
            findings.append(Finding(f'conflict: cannot inspect {pointer}: {state.error}'))
        elif state.linked:
            if not usable:
                findings.append(Finding(f'broken orphan: canonical AGENTS.md missing or unreadable at {canonical}; pointer {pointer}'))
        elif state.conflict:
            if pointer.is_symlink():
                stale = False
                try:
                    stale = scope == 'global' and pointer.resolve() == (home / '.conventions/CONVENTIONS.md').resolve()
                except (OSError, RuntimeError):
                    pass
                label = 'unmanaged stale conventions pointer' if stale else 'conflict: foreign/unresolvable symlink'
                findings.append(Finding(f'{label}: {harness} at {pointer}; {state.error}'))
            else:
                findings.append(_unmanaged_finding(pointer=pointer, harness=harness, canonical=canonical,
                                                   scope=scope, project_root=project, home=home))
    if not findings:
        click.echo('clean — no findings at this scope')
        return
    fixed = skipped = 0
    quit_loop = False
    for finding in findings:
        click.echo('\n' + finding.message)
        if finding.fix_action is None or no_fix or quit_loop:
            skipped += 1
            if finding.fix_action is None:
                click.echo('  (report-only — no automatic fix)')
            continue
        click.echo(f'  fix:    {finding.fix_action.shell_preview}')
        try:
            answer = click.prompt('  apply?', default='N', show_default=False,
                                  type=click.Choice(['y', 'N', 'q'], case_sensitive=False)).lower()
        except (click.Abort, EOFError, OSError):
            click.echo('\n  (no input available — stopping; nothing applied)')
            answer = 'q'
        if answer == 'y':
            try:
                finding.fix_action.apply()
                click.echo('  adopted.')
                fixed += 1
            except Exception as exc:
                click.echo(f'  adopt failed: {exc}')
                skipped += 1
        else:
            quit_loop = answer == 'q'
            skipped += 1
    click.echo(f'\nsummary: {len(findings)} findings, {fixed} fixed, {skipped} skipped')
    if skipped:
        ctx.exit(1)
