"""Directory entries remain independent even when they hardlink a symlink node."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli import instructions_install as ii
from agent_toolkit_cli.cli import main
from agent_toolkit_cli.instructions_adapters import symlink
from tests.test_cli.test_instructions_lockless import snapshot
from tests.test_cli.test_instructions_pointer_identity import seed_dependent_pointers


@pytest.fixture(params=['project', 'global'])
def hardlinked_slots(tmp_path, monkeypatch, request):
    home, project = tmp_path / 'home', tmp_path / 'project'
    home.mkdir()
    project.mkdir()
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.chdir(project)
    scope = request.param
    canonical = ii._resolve_canonical(scope, project)
    canonical.parent.mkdir(parents=True, exist_ok=True)
    canonical.write_text('canonical\n')
    first = symlink._pointer_path('claude-code', scope, project, home)
    second = symlink._pointer_path('gemini-cli', scope, project, home)
    for pointer in (first, second):
        pointer.parent.mkdir(parents=True, exist_ok=True)
    first.symlink_to(canonical)
    try:
        os.link(first, second, follow_symlinks=False)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f'filesystem cannot hardlink symlinks: {exc}')
    assert first.is_symlink() and second.is_symlink()
    assert first.lstat().st_ino == second.lstat().st_ino
    return scope, home, project, canonical, first, second


@pytest.mark.parametrize('surface', ['api', 'cli'])
def test_remove_all_distinct_hardlinked_entries(hardlinked_slots, surface):
    scope, home, project, canonical, first, second = hardlinked_slots
    if surface == 'api':
        result = ii.apply(scope=scope, home=home, project_root=project,
                          remove_harnesses=('claude-code', 'gemini-cli'))
        assert len(result.actions) == 2
    else:
        result = CliRunner().invoke(main, ['--project', str(project), 'instructions', 'uninstall', '--scope', scope])
        assert result.exit_code == 0, result.output
    assert not first.is_symlink() and not second.is_symlink()
    assert canonical.read_text() == 'canonical\n'


def test_opposing_intents_on_distinct_hardlinked_entries(hardlinked_slots):
    scope, home, project, canonical, first, second = hardlinked_slots
    before = symlink.link_snapshot(first)
    ii.apply(scope=scope, project_root=project, home=home,
             add_harnesses=('claude-code',), remove_harnesses=('gemini-cli',))
    assert symlink.link_snapshot(first) == before
    assert not second.is_symlink()
    assert canonical.read_text() == 'canonical\n'


@pytest.mark.parametrize('opposing', [False, True])
@pytest.mark.parametrize('case_alias', [False, True])
def test_actual_shared_entry_alias_coalesces_or_refuses(hardlinked_slots, opposing, case_alias):
    scope, home, project, canonical, first, second = hardlinked_slots
    if scope == 'global':
        augment = symlink._pointer_path('augment', scope, project, home)
        tabnine = symlink._pointer_path('tabnine-cli', scope, project, home)
        target = augment.parent.with_name('.RULES') if case_alias else augment.parent
        if not target.exists():
            pytest.skip('filesystem does not alias directory case')
        tabnine.parent.mkdir(parents=True, exist_ok=True)
        tabnine.parent.rmdir()
        tabnine.parent.symlink_to(target, target_is_directory=True)
        added, removed, shared = ('augment',), ('tabnine-cli',), augment
    else:
        added, removed, shared = ('augment',), ('claude-code',), first
    before = snapshot(home.parent)
    kwargs = dict(scope=scope, project_root=project, home=home)
    if opposing:
        with pytest.raises(symlink.PointerConflictError, match='opposing'):
            ii.apply(**kwargs, add_harnesses=added, remove_harnesses=removed)
        assert snapshot(home.parent) == before
    else:
        result = ii.apply(**kwargs, remove_harnesses=(*added, *removed))
        assert len(result.actions) == 1
        assert not shared.is_symlink()
        if scope == 'project':
            assert second.is_symlink()
    assert canonical.read_text() == 'canonical\n'


@pytest.mark.parametrize('alias_target', [False, True])
def test_hardlinked_entries_have_independent_real_dependencies(hardlinked_slots, alias_target):
    scope, home, project, canonical, first, second = hardlinked_slots
    dependent = symlink._pointer_path('iflow-cli', scope, project, home)
    dependent.parent.mkdir(parents=True, exist_ok=True)
    target = first.with_name('claude.md') if alias_target else first
    if not target.is_symlink():
        pytest.skip('filesystem does not alias leaf case')
    dependent.symlink_to(target)
    plan = ii.apply(scope=scope, project_root=project, home=home,
                    remove_harnesses=('claude-code', 'gemini-cli', 'iflow-cli'))
    removed = [a.harness for a in plan.actions]
    assert removed.index('iflow-cli') < removed.index('claude-code')
    assert len(removed) == 3
    assert all(not p.is_symlink() for p in (first, second, dependent))
    assert canonical.read_text() == 'canonical\n'


def test_relative_hardlinked_entries_both_remove(hardlinked_slots):
    scope, home, project, canonical, first, second = hardlinked_slots
    first.unlink()
    second.unlink()
    first.symlink_to(os.path.relpath(canonical, first.parent))
    os.link(first, second, follow_symlinks=False)
    ii.apply(scope=scope, project_root=project, home=home,
             remove_harnesses=('claude-code', 'gemini-cli'))
    assert not first.is_symlink() and not second.is_symlink()
    assert canonical.read_text() == 'canonical\n'


def test_conservative_source_node_guard_still_refuses_hardlinked_sibling(hardlinked_slots):
    scope, home, project, canonical, first, second = hardlinked_slots
    source = home.parent / 'user-source.md'
    source.write_text('source\n')
    first.unlink()
    second.unlink()
    first.symlink_to(source)
    os.link(first, second, follow_symlinks=False)
    canonical.unlink()
    canonical.symlink_to(first)
    independent = symlink._pointer_path('iflow-cli', scope, project, home)
    independent.parent.mkdir(parents=True, exist_ok=True)
    independent.symlink_to(canonical)
    before = snapshot(home.parent)
    with pytest.raises(symlink.CanonicalChainError, match='canonical'):
        ii.apply(scope=scope, project_root=project, home=home,
                 remove_harnesses=('gemini-cli', 'iflow-cli'))
    assert snapshot(home.parent) == before
    assert canonical.read_text() == 'source\n'


def test_entry_spelling_exact_wins_and_ambiguous_alias_fails_closed(tmp_path, monkeypatch):
    """Portable lookup emulation, not proof of native case-sensitive hardlinks."""
    first = tmp_path / 'CLAUDE.md'
    second = tmp_path / 'claude.md'
    alternate = tmp_path / 'Claude.md'
    first.symlink_to('AGENTS.md')
    info = first.lstat()
    node = info.st_dev, info.st_ino
    original_lstat = Path.lstat
    original_iterdir = Path.iterdir

    def emulated_lstat(path, *args, **kwargs):
        if path in (first, second, alternate):
            return info
        return original_lstat(path, *args, **kwargs)

    def emulated_iterdir(path):
        return iter((first, second)) if path == tmp_path else original_iterdir(path)

    monkeypatch.setattr(Path, 'lstat', emulated_lstat)
    monkeypatch.setattr(Path, 'iterdir', emulated_iterdir)
    assert symlink.pointer_slot(first, node=node) != symlink.pointer_slot(second, node=node)
    with pytest.raises(symlink.PointerConflictError, match='cannot identify directory entry'):
        symlink.pointer_slot(alternate, node=node)


def seed_stored_lowercase_chain(root, scope, lowercase_dependent=False):
    project, home, canonical, pointers = seed_dependent_pointers(root, scope)
    actuals = []
    for index, (_, documented) in enumerate(pointers):
        if index == 0 or lowercase_dependent:
            target = documented.readlink()
            documented.unlink()
            actual = documented.with_name(documented.name.lower())
            actual.symlink_to(target)
            if not documented.is_symlink():
                pytest.skip('filesystem does not alias lowercase stored leaf')
            assert symlink.link_snapshot(actual) == symlink.link_snapshot(documented)
        else:
            actual = documented
        actuals.append(actual)
    return project, home, canonical, actuals


@pytest.mark.parametrize('scope', ['project', 'global'])
@pytest.mark.parametrize('surface', ['api', 'cli'])
@pytest.mark.parametrize('lowercase_dependent', [False, True])
def test_stored_lowercase_chain_removes_dependents_first(tmp_path, monkeypatch, scope, surface, lowercase_dependent):
    project, home, canonical, actuals = seed_stored_lowercase_chain(tmp_path, scope, lowercase_dependent)
    monkeypatch.setenv('HOME', str(home))
    if surface == 'api':
        for requested in [('claude-code', 'gemini-cli'), ('gemini-cli', 'claude-code')]:
            plan = ii.plan(scope=scope, project_root=project, home=home, remove_harnesses=requested)
            assert [a.harness for a in plan.actions] == ['gemini-cli', 'claude-code']
        ii.apply(scope=scope, project_root=project, home=home, remove_harnesses=requested)
    else:
        result = CliRunner().invoke(main, ['--project', str(project), 'instructions', 'uninstall', '--scope', scope])
        assert result.exit_code == 0, result.output
    assert all(not pointer.is_symlink() for pointer in actuals)
    assert canonical.read_text() == 'canonical source\n'


def test_missing_parent_planning_is_read_only(tmp_path, monkeypatch):
    home = tmp_path / 'home'
    home.mkdir()
    monkeypatch.setenv('HOME', str(home))
    canonical = home / '.agent-toolkit/AGENTS.md'
    canonical.parent.mkdir()
    canonical.write_text('canonical\n')
    before = snapshot(tmp_path)
    result = ii.plan(scope='global', project_root=None, home=home,
                     add_harnesses=('augment', 'claude-code', 'pi'))
    assert len(result.actions) == 3
    assert snapshot(tmp_path) == before
