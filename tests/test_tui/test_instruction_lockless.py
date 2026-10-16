"""Real Instructions inventory/save behavior, canonical-chain safety and rendered evidence."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from rich.text import Text
from textual.widgets import DataTable, Static

from agent_toolkit_cli import instructions_install as ii
from agent_toolkit_cli.instructions_adapters.symlink import Adapter, _pointer_path
from agent_toolkit_tui.app import TUIApp
from agent_toolkit_tui.instruction_state import build_instruction_rows
from agent_toolkit_tui.widgets.instruction_grid import InstructionGrid
from tests.test_cli.test_instructions_lockless import seed_chain, snapshot

ARTIFACTS = Path(__file__).resolve().parents[2] / 'assets/verification/525'


@pytest.mark.parametrize('scope', ['project', 'global'])
@pytest.mark.parametrize('hops', [0, 1])
@pytest.mark.asyncio
async def test_tui_refuses_whole_canonical_chain_removal_batch(tmp_path, monkeypatch, scope, hops):
    project, home, canonical = seed_chain(tmp_path, hops, scope)
    monkeypatch.chdir(project)
    monkeypatch.setenv('HOME', str(home))
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app._scope = scope
        app.action_asset_type('instruction')
        app._refresh_instruction_view()
        grid = app.query_one('#instruction-grid', InstructionGrid)
        pending = {(scope, h, 'AGENTS.md'): 'unlink' for h in ('gemini-cli', 'claude-code')}
        grid.restore_pending(pending)
        before = snapshot(tmp_path)
        app._apply_instruction_pending()
        await pilot.pause()
        assert 'chain' in str(app.query_one('#footer-pending', Static).render())
        assert grid.pending_entries() == pending
        assert canonical.read_text() == 'user-owned instructions\n'
        assert snapshot(tmp_path) == before


@pytest.fixture
def roots(tmp_path, monkeypatch):
    project = tmp_path / 'project'
    home = tmp_path / 'home'
    project.mkdir()
    home.mkdir()
    monkeypatch.chdir(project)
    monkeypatch.setenv('HOME', str(home))
    (project / 'AGENTS.md').write_text('project\n')
    global_canonical = home / '.agent-toolkit/AGENTS.md'
    global_canonical.parent.mkdir()
    global_canonical.write_text('global\n')
    return project, home


@pytest.mark.parametrize('scope', ['project', 'global'])
@pytest.mark.asyncio
async def test_save_link_unlink_preserves_other_scope_and_legacy_files(roots, scope):
    project, home = roots
    (project / 'instructions-lock.json').write_text('invalid legacy state')
    (home / '.agent-toolkit/instructions-lock.json').write_text('also invalid')
    other_scope = 'global' if scope == 'project' else 'project'
    ii.apply(scope=other_scope, project_root=project, home=home, add_harnesses=('claude-code',))
    other = _pointer_path('claude-code', other_scope, project, home)
    other_target = other.readlink()
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app._scope = scope
        app.action_asset_type('instruction')
        app._refresh_instruction_view()
        grid = app.query_one('#instruction-grid', InstructionGrid)
        for op in ('link', 'unlink'):
            grid.restore_pending({(scope, 'claude-code', 'AGENTS.md'): op})
            app._apply_instruction_pending()
            await pilot.pause()
            pointer = _pointer_path('claude-code', scope, project, home)
            assert pointer.is_symlink() == (op == 'link')
            assert not grid.pending_entries()
            assert other.readlink() == other_target
        assert (project / 'instructions-lock.json').read_text() == 'invalid legacy state'
        assert (home / '.agent-toolkit/instructions-lock.json').read_text() == 'also invalid'


@pytest.mark.asyncio
async def test_partial_failure_keeps_only_unsatisfied_intent_then_retries(roots, monkeypatch):
    project, home = roots
    original = Adapter.install

    def fail_gemini(self, **kwargs):
        if self.harness == 'gemini-cli':
            raise OSError('injected disk failure')
        original(self, **kwargs)

    monkeypatch.setattr(Adapter, 'install', fail_gemini)
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app._scope = 'project'
        app.action_asset_type('instruction')
        app._refresh_instruction_view()
        grid = app.query_one('#instruction-grid', InstructionGrid)
        grid.restore_pending({('project', h, 'AGENTS.md'): 'link' for h in ('claude-code', 'gemini-cli')})
        app._apply_instruction_pending()
        await pilot.pause()
        assert (project / 'CLAUDE.md').is_symlink()
        assert not (project / 'GEMINI.md').exists()
        assert grid.pending_entries() == {('project', 'gemini-cli', 'AGENTS.md'): 'link'}
        assert 'apply failed' in str(app.query_one('#footer-pending', Static).render())
        monkeypatch.setattr(Adapter, 'install', original)
        app._apply_instruction_pending()
        await pilot.pause()
        assert (project / 'GEMINI.md').is_symlink()
        assert not grid.pending_entries()


@pytest.mark.asyncio
async def test_alias_save_refreshes_both_cells_and_refuses_opposing_intents(roots):
    project, home = roots
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app._scope = 'project'
        app.action_asset_type('instruction')
        app._refresh_instruction_view()
        grid = app.query_one('#instruction-grid', InstructionGrid)
        grid.restore_pending({('project', h, 'AGENTS.md'): 'link' for h in ('augment', 'claude-code')})
        app._apply_instruction_pending()
        assert (project / 'CLAUDE.md').is_symlink()
        assert not grid.pending_entries()
        rows = build_instruction_rows(scope='project', project=project, home=home, selection=('augment', 'claude-code'))
        assert all(rows[0].cells[(h, 'project')].linked for h in ('augment', 'claude-code'))
        before = snapshot(project)
        grid.restore_pending({('project', 'augment', 'AGENTS.md'): 'link', ('project', 'claude-code', 'AGENTS.md'): 'unlink'})
        app._apply_instruction_pending()
        assert snapshot(project) == before
        assert 'opposing' in str(app.query_one('#footer-pending', Static).render())


@pytest.mark.parametrize('occupant', ['absent', 'broken', 'foreign', 'regular', 'loop'])
def test_inventory_is_read_only_and_row_universe_is_local(roots, occupant):
    project, home = roots
    (project / 'AGENTS.md').unlink()
    pointer = project / 'CLAUDE.md'
    if occupant == 'regular':
        pointer.write_text('mine')
    elif occupant != 'absent':
        target = {'broken': 'AGENTS.md', 'foreign': 'elsewhere', 'loop': 'CLAUDE.md'}[occupant]
        pointer.symlink_to(target)
    ii.apply(scope='global', project_root=None, home=home, add_harnesses=('claude-code',))
    before = snapshot(home.parent)
    rows = build_instruction_rows(scope='project', project=project, home=home)
    assert bool(rows) == (occupant != 'absent')
    if rows:
        cell = rows[0].cells[('claude-code', 'project')]
        assert cell.linked == (occupant == 'broken')
        assert cell.conflict == (occupant in {'regular', 'foreign', 'loop'})
        assert rows[0].cells[('claude-code', 'global')].linked
        assert not rows[0].canonical_exists
    assert snapshot(home.parent) == before


@pytest.mark.parametrize('scope', ['project', 'global'])
@pytest.mark.parametrize('broken', [False, True])
@pytest.mark.asyncio
async def test_rendered_lockless_instruction_evidence(roots, scope, broken):
    project, home = roots
    ii.apply(scope='global', project_root=None, home=home, add_harnesses=('claude-code',))
    if scope == 'project':
        ii.apply(scope=scope, project_root=project, home=None, add_harnesses=('claude-code',))
    pointer = _pointer_path('gemini-cli', scope, project, home)
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text('foreign user file\n')
    if broken:
        ii._resolve_canonical(scope, project).unlink()
    app = TUIApp()
    async with app.run_test(size=(180, 30)) as pilot:
        await pilot.pause()
        app.action_asset_type('instruction')
        app.action_scope(scope)
        app._refresh_instruction_view()
        await pilot.pause()
        grid = app.query_one('#instruction-grid', InstructionGrid)
        table = grid.query_one('#instruction-table', DataTable)
        assert grid.display and table.row_count == 1
        values = table.get_row_at(0)
        visible = [v.plain if isinstance(v, Text) else str(v) for v in values]
        assert visible[0] == 'AGENTS.md' and 'green' in visible[2]
        assert ('red' in visible[1]) == broken
        columns = [str(c.label) for c in table.columns.values()]
        gemini_column = next(i for i, label in enumerate(columns) if label.startswith('Gemini'))
        assert 'red' in visible[gemini_column] and '!' in visible[gemini_column]
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        suffix = f'{scope}-broken' if broken else scope
        (ARTIFACTS / f'instructions-{suffix}.svg').write_text(app.export_screenshot())
        (ARTIFACTS / f'instructions-{suffix}.json').write_text(json.dumps({'columns': columns, 'row': visible}, indent=2))


@pytest.mark.parametrize('conflict', [False, True])
@pytest.mark.asyncio
async def test_all_kind_save_integrates_hidden_lockless_instructions_with_real_command(roots, conflict):
    from agent_toolkit_cli import command_paths
    from agent_toolkit_cli.command_adapters import get_adapter
    from agent_toolkit_cli.command_lock import LockEntry, LockFile, write_lock
    from agent_toolkit_tui.widgets.command_grid import CommandGrid

    project, home = roots
    source = command_paths.library_root() / 'test-command'
    source.mkdir(parents=True)
    (source / 'COMMAND.md').write_text('test prompt\n')
    write_lock(command_paths.library_lock_path(), LockFile(version=1, skills={
        'test-command': LockEntry(source='o/r', source_type='github', ref='main', command_path='COMMAND.md'),
    }))
    if conflict:
        (project / 'CLAUDE.md').write_text('user file\n')
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        instructions = app.query_one('#instruction-grid', InstructionGrid)
        commands = app.query_one('#command-grid', CommandGrid)
        instruction_pending = {(scope, 'claude-code', 'AGENTS.md'): 'link' for scope in ('global', 'project')}
        instructions.restore_pending(instruction_pending)
        commands.restore_pending({(scope, 'standard', 'test-command'): 'link' for scope in ('global', 'project')})
        app.action_asset_type('mcp')
        app.action_scope('global')
        app.action_apply()
        await pilot.pause()
        assert not commands.pending_entries()
        for scope in ('global', 'project'):
            assert get_adapter('standard').destination('test-command', scope=scope, home=home,
                                                       project=project if scope == 'project' else None).is_file()
        footer = str(app.query_one('#footer-pending', Static).render())
        assert '(2 global, 2 project)' in footer
        if conflict:
            assert 'apply failed' in footer
            assert (project / 'CLAUDE.md').read_text() == 'user file\n'
            assert instructions.pending_entries() == instruction_pending
            assert not (home / '.claude/CLAUDE.md').exists()
            (project / 'CLAUDE.md').unlink()
            app.action_apply()
            await pilot.pause()
        else:
            assert 'applied: 4 ok, 0 failed' in footer
        assert not instructions.pending_entries()
        assert (project / 'CLAUDE.md').read_text() == 'project\n'
        assert (home / '.claude/CLAUDE.md').read_text() == 'global\n'
        assert not list(project.rglob('instructions-lock.json'))
        assert not list(home.rglob('instructions-lock.json'))
