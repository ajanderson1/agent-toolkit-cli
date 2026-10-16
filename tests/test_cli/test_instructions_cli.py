"""CLI behavior through real disposable filesystem pointers and opt-in doctor fixes."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from agent_toolkit_cli import instructions_install as ii
from agent_toolkit_cli.instructions_adapters.symlink import CELLS, _pointer_path
from tests.test_cli.test_instructions_lockless import snapshot


@pytest.fixture(params=['project', 'global'])
def scoped(tmp_path, monkeypatch, request):
    home = tmp_path / 'home'
    project = tmp_path / 'project'
    home.mkdir()
    project.mkdir()
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.chdir(project)
    scope = request.param
    canonical = ii._resolve_canonical(scope, project)
    canonical.parent.mkdir(parents=True, exist_ok=True)
    canonical.write_text('canonical\n')
    return scope, project, home, canonical


def invoke(scoped, verb, *args, input=None):
    scope, project, home, canonical = scoped
    return CliRunner().invoke(main, ['--project', str(project), 'instructions', verb, '--scope', scope, *args], input=input)


def test_instructions_group_registered():
    result = CliRunner().invoke(main, ['instructions', '--help'])
    assert result.exit_code == 0
    assert all(verb in result.output for verb in ('install', 'uninstall', 'list', 'status', 'doctor'))


def test_default_install_roundtrip(scoped):
    scope, project, home, canonical = scoped
    assert invoke(scoped, 'install').exit_code == 0
    for harness, cell in CELLS.items():
        if cell[scope]:
            assert _pointer_path(harness, scope, project, home).resolve() == canonical
    assert invoke(scoped, 'status').exit_code == 0
    assert invoke(scoped, 'doctor', '--no-fix').exit_code == 0
    assert invoke(scoped, 'uninstall').exit_code == 0
    assert canonical.read_text() == 'canonical\n'
    assert not list(home.parent.rglob('instructions-lock.json'))


@pytest.mark.parametrize('harness', ['codex', 'opencode', 'pi'])
def test_scope_aware_native_readers(scoped, harness):
    scope, project, home, canonical = scoped
    result = invoke(scoped, 'install', '--harness', harness)
    if scope == 'project':
        assert result.exit_code != 0 and 'native' in result.output
        assert not canonical.is_symlink()
    else:
        assert result.exit_code == 0, result.output
        assert _pointer_path(harness, scope, project, home).is_symlink()


def test_missing_canonical_install_refusal_and_empty_doctor(scoped):
    scope, project, home, canonical = scoped
    canonical.unlink()
    before = snapshot(home.parent)
    result = invoke(scoped, 'install', '--harness', 'claude-code')
    assert result.exit_code != 0 and 'AGENTS.md' in result.output
    assert invoke(scoped, 'doctor', '--no-fix').exit_code == 0
    assert snapshot(home.parent) == before


@pytest.mark.parametrize('occupant', ['regular', 'foreign', 'dangling', 'loop', 'directory'])
def test_conflicts_preserved_by_all_non_adopting_verbs(scoped, occupant):
    scope, project, home, canonical = scoped
    pointer = _pointer_path('claude-code', scope, project, home)
    pointer.parent.mkdir(parents=True, exist_ok=True)
    foreign = home.parent / 'foreign.md'
    if occupant == 'regular':
        pointer.write_text('my instructions\n')
    elif occupant == 'directory':
        pointer.mkdir()
    else:
        if occupant == 'foreign':
            foreign.write_text('foreign\n')
        pointer.symlink_to(pointer if occupant == 'loop' else foreign)
    before = snapshot(home.parent)
    assert invoke(scoped, 'install', '--harness', 'claude-code').exit_code != 0
    status = invoke(scoped, 'status')
    assert status.exit_code == 0 and 'conflict' in status.output
    doctor = invoke(scoped, 'doctor', '--no-fix')
    assert doctor.exit_code == 1
    # Resolution errors fail loudly; ordinary foreign occupants are simply retained.
    result = invoke(scoped, 'uninstall')
    assert result.exit_code != 0 if occupant == 'loop' else result.exit_code == 0
    assert snapshot(home.parent) == before


def test_owned_dangling_pointer_is_visible_and_removable(scoped):
    scope, project, home, canonical = scoped
    pointer = _pointer_path('claude-code', scope, project, home)
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.symlink_to(canonical)
    canonical.unlink()
    status = invoke(scoped, 'status')
    assert status.exit_code == 0 and 'broken' in status.output
    doctor = invoke(scoped, 'doctor', '--no-fix')
    assert doctor.exit_code == 1 and 'canonical' in doctor.output
    assert invoke(scoped, 'uninstall').exit_code == 0
    assert not pointer.is_symlink()


@pytest.mark.parametrize('mode', ['absent', 'empty', 'populated'])
def test_explicit_adoption_preserves_content(scoped, mode):
    scope, project, home, canonical = scoped
    if mode == 'absent':
        canonical.unlink()
    elif mode == 'empty':
        canonical.write_text('')
    pointer = _pointer_path('claude-code', scope, project, home)
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text('authored\n')
    result = invoke(scoped, 'doctor', input='y\n')
    assert result.exit_code == 0, result.output
    assert pointer.is_symlink()
    if mode == 'populated':
        assert canonical.read_text() == 'canonical\n'
        assert pointer.with_name(pointer.name + '.pre-adopt.bak').read_text() == 'authored\n'
    else:
        assert canonical.read_text() == 'authored\n'
    assert not list(home.parent.rglob('instructions-lock.json'))


@pytest.mark.parametrize('mode', ['absent', 'empty', 'populated'])
@pytest.mark.parametrize('fail_after_link', [False, True])
def test_adoption_failure_restores_original_source_and_canonical(scoped, monkeypatch, mode, fail_after_link):
    scope, project, home, canonical = scoped
    if mode == 'absent':
        canonical.unlink()
    elif mode == 'empty':
        canonical.write_text('')
    pointer = _pointer_path('claude-code', scope, project, home)
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text('authored\n')
    before = {p.name: p.read_bytes() for p in [canonical, pointer] if p.exists()}
    original = ii.apply

    def fail(**kwargs):
        if fail_after_link:
            original(**kwargs)
        raise OSError('injected install failure')

    monkeypatch.setattr(ii, 'apply', fail)
    result = invoke(scoped, 'doctor', input='y\n')
    assert result.exit_code == 1 and 'injected' in result.output
    assert not pointer.is_symlink()
    assert {p.name: p.read_bytes() for p in [canonical, pointer] if p.exists()} == before
    assert not pointer.with_name(pointer.name + '.pre-adopt.bak').exists()


@pytest.mark.parametrize('answer', ['N\n', 'q\n', ''])
def test_adoption_declined_or_noninteractive_is_read_only(scoped, answer):
    scope, project, home, canonical = scoped
    pointer = _pointer_path('claude-code', scope, project, home)
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text('unmanaged\n')
    before = snapshot(home.parent)
    result = invoke(scoped, 'doctor', input=answer)
    assert result.exit_code == 1
    assert snapshot(home.parent) == before


@pytest.mark.parametrize('dangling', [False, True])
def test_existing_backup_never_clobbered(scoped, dangling):
    scope, project, home, canonical = scoped
    pointer = _pointer_path('claude-code', scope, project, home)
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text('unmanaged\n')
    backup = pointer.with_name(pointer.name + '.pre-adopt.bak')
    if dangling:
        backup.symlink_to('missing')
    else:
        backup.write_text('previous backup\n')
    before = snapshot(home.parent)
    result = invoke(scoped, 'doctor', input='y\n')
    assert result.exit_code == 1 and 'already exists' in result.output
    assert snapshot(home.parent) == before


@pytest.mark.parametrize('harness', ['augment', 'gemini-cli'])
def test_global_adoption_uses_its_actual_slot(tmp_path, monkeypatch, harness):
    monkeypatch.setenv('HOME', str(tmp_path))
    canonical = tmp_path / '.agent-toolkit/AGENTS.md'
    canonical.parent.mkdir()
    canonical.write_text('canonical\n')
    pointer = _pointer_path(harness, 'global', None, tmp_path)
    pointer.parent.mkdir(parents=True)
    pointer.write_text('authored\n')
    result = CliRunner().invoke(main, ['instructions', 'doctor', '--scope', 'global'], input='y\n')
    assert result.exit_code == 0, result.output
    assert pointer.resolve() == canonical
    assert not (tmp_path / '.claude/CLAUDE.md').exists()


@pytest.mark.parametrize('kind', ['direct', 'indirect', 'dangling'])
def test_stale_global_conventions_pointer_is_report_only(tmp_path, monkeypatch, kind):
    monkeypatch.setenv('HOME', str(tmp_path))
    stale = tmp_path / '.conventions/CONVENTIONS.md'
    stale.parent.mkdir()
    if kind != 'dangling':
        stale.write_text('legacy\n')
    pointer = tmp_path / '.pi/agent/AGENTS.md'
    pointer.parent.mkdir(parents=True)
    if kind == 'indirect':
        middle = tmp_path / 'middle.md'
        middle.symlink_to(stale)
        pointer.symlink_to(middle)
    else:
        pointer.symlink_to(stale)
    before = snapshot(tmp_path)
    result = CliRunner().invoke(main, ['instructions', 'doctor', '--scope', 'global'], input='y\n')
    assert result.exit_code == 1 and 'stale conventions' in result.output
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize('scope', ['project', 'global'])
def test_list_reports_matrix_without_installing(scope):
    result = CliRunner().invoke(main, ['instructions', 'list', '--scope', scope, '--format', 'json'])
    assert result.exit_code == 0
    rows = {r['harness']: r for r in json.loads(result.output)}
    assert rows['pi']['verdict'].lower().startswith('native' if scope == 'project' else 'symlink')
