"""Lockless installation truth and user-owned canonical-chain safety (#525)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli import instructions_install as ii
from agent_toolkit_cli.cli import main


def snapshot(root: Path) -> dict:
    return {
        str(p.relative_to(root)): (
            p.lstat().st_mode, p.lstat().st_mtime_ns,
            os.readlink(p) if p.is_symlink() else (p.read_bytes() if p.is_file() else None),
        )
        for p in [root, *sorted(root.rglob('*'))]
    }


def seed_chain(root: Path, hops: int, scope: str = 'project') -> tuple[Path, Path, Path]:
    project = root / 'project'
    home = root / 'home'
    project.mkdir(parents=True)
    home.mkdir()
    canonical = project / 'AGENTS.md' if scope == 'project' else home / '.agent-toolkit/AGENTS.md'
    slot = project / 'CLAUDE.md' if scope == 'project' else home / '.claude/CLAUDE.md'
    other = project / 'GEMINI.md' if scope == 'project' else home / '.gemini/GEMINI.md'
    for p in (canonical, slot, other):
        p.parent.mkdir(parents=True, exist_ok=True)
    source = root / 'user-source.md'
    source.write_text('user-owned instructions\n')
    slot.symlink_to(source)
    if hops:
        middle = root / 'middle.md'
        middle.symlink_to(slot)
        canonical.symlink_to(middle)
    else:
        canonical.symlink_to(slot)
    other.symlink_to(canonical)
    return project, home, canonical


@pytest.mark.parametrize('scope', ['project', 'global'])
@pytest.mark.parametrize('hops', [0, 1])
def test_cli_uninstall_refuses_whole_canonical_chain_batch(tmp_path, monkeypatch, scope, hops):
    project, home, canonical = seed_chain(tmp_path, hops, scope)
    monkeypatch.setenv('HOME', str(home))
    before = snapshot(tmp_path)
    result = CliRunner().invoke(main, ['--project', str(project), 'instructions', 'uninstall', '--scope', scope])
    assert result.exit_code != 0
    assert 'canonical' in result.output.lower() and 'chain' in result.output.lower()
    assert canonical.read_text() == 'user-owned instructions\n'
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize('hops', [0, 1])
def test_shared_remove_api_refuses_entire_batch(tmp_path, hops):
    project, home, canonical = seed_chain(tmp_path, hops)
    before = snapshot(tmp_path)
    with pytest.raises(ii.CanonicalChainError, match='canonical'):
        ii.apply(scope='project', project_root=project, home=None,
                 remove_harnesses=('gemini-cli', 'claude-code'))
    assert canonical.read_text() == 'user-owned instructions\n'
    assert snapshot(tmp_path) == before


def test_manual_link_inventory_ignores_malformed_legacy_files(tmp_path):
    (tmp_path / 'AGENTS.md').write_text('canonical\n')
    (tmp_path / 'CLAUDE.md').symlink_to('AGENTS.md')
    for filename in ('instructions-lock.json', 'instructions.lock'):
        (tmp_path / filename).write_bytes(b'not JSON\x00')
    before = snapshot(tmp_path)
    result = CliRunner().invoke(main, ['--project', str(tmp_path), 'instructions', 'status'])
    assert result.exit_code == 0, result.output
    assert 'claude-code' in result.output and 'ok' in result.output
    doctor = CliRunner().invoke(main, ['--project', str(tmp_path), 'instructions', 'doctor', '--no-fix'])
    assert doctor.exit_code == 0, doctor.output
    assert snapshot(tmp_path) == before


def test_selected_install_does_not_prune_manual_pointer(tmp_path):
    canonical = tmp_path / 'AGENTS.md'
    canonical.write_text('source\n')
    (tmp_path / 'CLAUDE.md').symlink_to('AGENTS.md')
    result = CliRunner().invoke(main, ['--project', str(tmp_path), 'instructions', 'install', '--harness', 'gemini-cli'])
    assert result.exit_code == 0, result.output
    assert (tmp_path / 'CLAUDE.md').is_symlink()
    assert (tmp_path / 'GEMINI.md').resolve() == canonical
    assert not (tmp_path / 'instructions-lock.json').exists()


def test_conflict_preflight_prevents_partial_install(tmp_path):
    (tmp_path / 'AGENTS.md').write_text('source\n')
    (tmp_path / 'GEMINI.md').write_text('foreign\n')
    before = snapshot(tmp_path)
    result = CliRunner().invoke(main, ['--project', str(tmp_path), 'instructions', 'install', '--harness', 'claude-code', '--harness', 'gemini-cli'])
    assert result.exit_code != 0
    assert snapshot(tmp_path) == before


def test_external_canonical_source_and_relative_chained_pointer_survive_roundtrip(tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    source = tmp_path / 'versioned-source.md'
    source.write_text('versioned content\n')
    canonical = project / 'AGENTS.md'
    canonical.symlink_to('../versioned-source.md')
    intermediate = project / 'middle.md'
    intermediate.symlink_to('AGENTS.md')
    pointer = project / 'CLAUDE.md'
    pointer.symlink_to('middle.md')
    ii.apply(scope='project', project_root=project, home=None, add_harnesses=('claude-code', 'gemini-cli'))
    assert pointer.readlink() == Path('middle.md')
    ii.uninstall(scope='project', project_root=project, home=None)
    assert not pointer.is_symlink()
    assert canonical.readlink() == Path('../versioned-source.md')
    assert intermediate.is_symlink()
    assert source.read_text() == canonical.read_text() == 'versioned content\n'


def test_canonical_directory_component_chain_is_protected(tmp_path):
    source_dir = tmp_path / 'sources'
    source_dir.mkdir()
    (source_dir / 'content.md').write_text('canonical content\n')
    (tmp_path / 'CLAUDE.md').symlink_to('sources', target_is_directory=True)
    canonical = tmp_path / 'AGENTS.md'
    canonical.symlink_to('CLAUDE.md/content.md')
    (tmp_path / 'GEMINI.md').symlink_to('AGENTS.md')
    before = snapshot(tmp_path)
    with pytest.raises(ii.CanonicalChainError):
        ii.apply(scope='project', project_root=tmp_path, home=None,
                 remove_harnesses=('gemini-cli', 'claude-code'))
    assert canonical.read_text() == 'canonical content\n'
    assert snapshot(tmp_path) == before


def test_requested_plan_does_not_create_global_directories(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', str(tmp_path))
    canonical = tmp_path / '.agent-toolkit/AGENTS.md'
    canonical.parent.mkdir()
    canonical.write_text('canonical\n')
    before = snapshot(tmp_path)
    p = ii.plan(scope='global', project_root=None, home=tmp_path, add_harnesses=('claude-code',))
    assert p.actions[0].action == 'create'
    assert snapshot(tmp_path) == before


def test_cli_scope_isolation_and_explicit_global_native_reader(tmp_path, monkeypatch):
    project = tmp_path / 'project'
    project.mkdir()
    home = tmp_path / 'home'
    home.mkdir()
    monkeypatch.setenv('HOME', str(home))
    (project / 'AGENTS.md').write_text('project\n')
    global_canonical = home / '.agent-toolkit/AGENTS.md'
    global_canonical.parent.mkdir()
    global_canonical.write_text('global\n')
    runner = CliRunner()
    for scope in ('project', 'global'):
        result = runner.invoke(main, ['--project', str(project), 'instructions', 'install', '--scope', scope, '--harness', 'claude-code'])
        assert result.exit_code == 0, result.output
    global_before = snapshot(home)
    result = runner.invoke(main, ['--project', str(project), 'instructions', 'uninstall'])
    assert result.exit_code == 0
    assert snapshot(home) == global_before
    assert not (project / 'CLAUDE.md').is_symlink()


def test_removal_rechecks_ownership_after_chain_preflight(tmp_path, monkeypatch):
    from agent_toolkit_cli.instructions_adapters import symlink
    canonical = tmp_path / 'AGENTS.md'
    canonical.write_text('canonical\n')
    pointer = tmp_path / 'CLAUDE.md'
    pointer.symlink_to(canonical)
    foreign = tmp_path / 'foreign.md'
    foreign.write_text('foreign\n')
    original = symlink.preflight_removals

    def changed(canonical, pointers):
        original(canonical, pointers)
        pointer.unlink()
        pointer.symlink_to(foreign)

    monkeypatch.setattr(symlink, 'preflight_removals', changed)
    with pytest.raises(symlink.PointerConflictError, match='changed'):
        symlink.adapter_for('claude-code').uninstall(scope='project', project_root=tmp_path, home=None, canonical=canonical)
    assert pointer.is_symlink() and pointer.resolve() == foreign
    assert canonical.read_text() == 'canonical\n'


def test_looped_global_parent_is_reported_without_traceback(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', str(tmp_path))
    parent = tmp_path / '.claude'
    parent.symlink_to('.claude', target_is_directory=True)
    before = snapshot(tmp_path)
    for verb in ('status', 'doctor'):
        args = ['instructions', verb, '--scope', 'global']
        if verb == 'doctor':
            args.append('--no-fix')
        result = CliRunner().invoke(main, args)
        assert result.exit_code == (0 if verb == 'status' else 1)
        assert 'conflict' in result.output and 'Traceback' not in result.output
    assert snapshot(tmp_path) == before
