"""Fresh-review regressions: symlink-node aliases and dependent pointer removal."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli import instructions_install as ii
from agent_toolkit_cli.cli import main
from agent_toolkit_cli.instructions_adapters import symlink
from tests.test_cli.test_instructions_lockless import snapshot


def seed_native_alias(root: Path, scope: str, alias_kind: str):
    base = root / 'cafe\u0301'
    project = base / 'project'
    home = base / 'home'
    project.mkdir(parents=True)
    home.mkdir()
    canonical = project / 'AGENTS.md' if scope == 'project' else home / '.agent-toolkit/AGENTS.md'
    pointer = symlink._pointer_path('claude-code', scope, project, home)
    other = symlink._pointer_path('gemini-cli', scope, project, home)
    for p in (canonical, pointer, other):
        p.parent.mkdir(parents=True, exist_ok=True)
    source = base / 'user-source.md'
    source.write_text('keep user source\n')
    pointer.symlink_to(source)
    if alias_kind == 'case':
        alias = pointer.with_name('claude.md')
    else:
        alias = Path(str(pointer).replace('cafe\u0301', 'caf\u00e9'))
    try:
        actual_stat, alias_stat = pointer.lstat(), alias.lstat()
    except FileNotFoundError:
        pytest.skip(f'filesystem does not alias {alias_kind} spelling; portable identity emulation covers guard')
    if (actual_stat.st_dev, actual_stat.st_ino) != (alias_stat.st_dev, alias_stat.st_ino):
        pytest.skip(f'filesystem gives {alias_kind} spelling a distinct node')
    canonical.symlink_to(alias)
    other.symlink_to(canonical)
    assert canonical.read_text() == 'keep user source\n'
    return project, home, canonical, pointer, other


@pytest.mark.parametrize('scope', ['project', 'global'])
@pytest.mark.parametrize('alias_kind', ['case', 'unicode'])
def test_cli_preserves_native_alias_canonical_chain(tmp_path, monkeypatch, scope, alias_kind):
    project, home, canonical, pointer, other = seed_native_alias(tmp_path, scope, alias_kind)
    monkeypatch.setenv('HOME', str(home))
    before = snapshot(tmp_path)
    result = CliRunner().invoke(main, ['--project', str(project), 'instructions', 'uninstall', '--scope', scope])
    assert result.exit_code != 0, result.output
    assert 'canonical' in result.output and 'chain' in result.output
    assert canonical.read_text() == 'keep user source\n'
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize('alias_name', ['claude.md', 'alias-caf\u00e9.md', 'alias-cafe\u0301.md'])
@pytest.mark.parametrize('directory_component', [False, True])
def test_guard_uses_symlink_node_identity_with_portable_alias_emulation(tmp_path, monkeypatch, alias_name, directory_component):
    """Emulate alternate lstat/readlink spellings, not native filesystem normalization."""
    pointer = tmp_path / 'CLAUDE.md'
    source = tmp_path / 'source.md'
    if directory_component:
        source.mkdir()
        (source / 'content.md').write_text('source\n')
    else:
        source.write_text('source\n')
    pointer.symlink_to(source)
    alias = tmp_path / alias_name
    canonical = tmp_path / 'AGENTS.md'
    canonical.symlink_to(alias / 'content.md' if directory_component else alias)
    safe = tmp_path / 'GEMINI.md'
    safe.symlink_to(canonical)
    lstat = Path.lstat
    readlink = os.readlink

    def alias_lstat(path, *args, **kwargs):
        return lstat(pointer if path == alias else path, *args, **kwargs)

    def alias_readlink(path, *args, **kwargs):
        return readlink(pointer if Path(path) == alias else path, *args, **kwargs)

    monkeypatch.setattr(Path, 'lstat', alias_lstat)
    monkeypatch.setattr(os, 'readlink', alias_readlink)
    with pytest.raises(symlink.CanonicalChainError, match='canonical'):
        symlink.preflight_removals(canonical, [safe, pointer])
    assert pointer.is_symlink() and safe.is_symlink()
    assert (source / 'content.md' if directory_component else source).read_text() == 'source\n'


def seed_dependent_pointers(root: Path, scope: str, depth: int = 2):
    project = root / 'project'
    home = root / 'home'
    project.mkdir(parents=True)
    home.mkdir()
    canonical = project / 'AGENTS.md' if scope == 'project' else home / '.agent-toolkit/AGENTS.md'
    canonical.parent.mkdir(parents=True, exist_ok=True)
    canonical.write_text('canonical source\n')
    pointers = []
    target = canonical
    for harness in ('claude-code', 'gemini-cli', 'iflow-cli')[:depth]:
        pointer = symlink._pointer_path(harness, scope, project, home)
        pointer.parent.mkdir(parents=True, exist_ok=True)
        pointer.symlink_to(target)
        pointers.append((harness, pointer))
        target = pointer
    return project, home, canonical, pointers


@pytest.mark.parametrize('scope', ['project', 'global'])
@pytest.mark.parametrize('depth', [2, 3])
def test_cli_removes_all_owned_dependent_pointers_and_retry_is_noop(tmp_path, monkeypatch, scope, depth):
    project, home, canonical, pointers = seed_dependent_pointers(tmp_path, scope, depth)
    monkeypatch.setenv('HOME', str(home))
    args = ['--project', str(project), 'instructions', 'uninstall', '--scope', scope]
    for attempt in range(2):
        result = CliRunner().invoke(main, args)
        assert result.exit_code == 0, result.output
        assert all(not p.is_symlink() for _, p in pointers), (attempt, result.output)
        assert canonical.read_text() == 'canonical source\n'


@pytest.mark.parametrize('scope', ['project', 'global'])
@pytest.mark.parametrize('alias_kind', ['case', 'unicode'])
def test_native_alias_directory_component_is_protected(tmp_path, monkeypatch, scope, alias_kind):
    project, home, canonical, pointer, other = seed_native_alias(tmp_path, scope, alias_kind)
    monkeypatch.setenv('HOME', str(home))
    alias = canonical.readlink()
    source_dir = tmp_path / 'source-directory'
    source_dir.mkdir()
    (source_dir / 'content.md').write_text('source content\n')
    pointer.unlink()
    pointer.symlink_to(source_dir, target_is_directory=True)
    canonical.unlink()
    canonical.symlink_to(alias / 'content.md')
    before = snapshot(tmp_path)
    with pytest.raises(symlink.CanonicalChainError, match='canonical'):
        ii.apply(scope=scope, project_root=project, home=home,
                 remove_harnesses=('gemini-cli', 'claude-code'))
    assert canonical.read_text() == 'source content\n'
    assert snapshot(tmp_path) == before


def test_prevalidated_removal_rejects_replaced_link_with_same_terminal_target(tmp_path, monkeypatch):
    canonical = tmp_path / 'AGENTS.md'
    canonical.write_text('canonical source\n')
    pointer = tmp_path / 'CLAUDE.md'
    pointer.symlink_to('AGENTS.md')
    plan = ii.plan(scope='project', project_root=tmp_path, home=None, remove_harnesses=('claude-code',))
    pointer.unlink()
    pointer.symlink_to('./AGENTS.md')
    before = snapshot(tmp_path)
    monkeypatch.setattr(ii, 'plan', lambda **kwargs: plan)
    with pytest.raises(symlink.PointerConflictError, match='changed'):
        ii.apply(scope='project', project_root=tmp_path, home=None, remove_harnesses=('claude-code',))
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize('scope', ['project', 'global'])
@pytest.mark.parametrize('requested', [('claude-code', 'gemini-cli'), ('gemini-cli', 'claude-code'), ('augment', 'gemini-cli')])
def test_requested_order_and_shared_slot_alias_do_not_strand_dependents(tmp_path, monkeypatch, scope, requested):
    project, home, canonical, pointers = seed_dependent_pointers(tmp_path, scope)
    monkeypatch.setenv('HOME', str(home))
    if scope == 'global' and 'augment' in requested:
        pytest.skip('Augment and Claude share only their project slot, not global slots')
    ii.apply(scope=scope, project_root=project, home=home, remove_harnesses=requested)
    assert all(not pointer.is_symlink() for _, pointer in pointers)
    assert canonical.read_text() == 'canonical source\n'


@pytest.mark.parametrize('scope', ['project', 'global'])
def test_subset_preserves_unrequested_dependent_node_even_when_it_becomes_dangling(tmp_path, monkeypatch, scope):
    project, home, canonical, pointers = seed_dependent_pointers(tmp_path, scope)
    monkeypatch.setenv('HOME', str(home))
    dependent = pointers[1][1]
    before = dependent.lstat(), dependent.readlink()
    ii.apply(scope=scope, project_root=project, home=home, remove_harnesses=('claude-code',))
    assert not pointers[0][1].is_symlink()
    assert (dependent.lstat(), dependent.readlink()) == before
    assert dependent.is_symlink() and not dependent.is_file()
    assert canonical.read_text() == 'canonical source\n'
