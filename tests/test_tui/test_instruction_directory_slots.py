"""Real TUI completion for independent entries sharing a symlink node."""
from __future__ import annotations

import pytest

from agent_toolkit_cli.instructions_adapters.symlink import link_snapshot, _pointer_path
from tests.test_cli.test_instructions_lockless import snapshot
from agent_toolkit_tui.app import TUIApp
from agent_toolkit_tui.widgets.instruction_grid import InstructionGrid
from tests.test_cli.test_instructions_directory_slots import hardlinked_slots, seed_stored_lowercase_chain


@pytest.mark.parametrize('opposing', [False, True])
@pytest.mark.asyncio
async def test_tui_distinct_hardlinked_slot_intents_complete(hardlinked_slots, opposing):
    scope, home, project, canonical, first, second = hardlinked_slots
    before = link_snapshot(first)
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one('#instruction-grid', InstructionGrid)
        grid.restore_pending({
            (scope, 'claude-code', 'AGENTS.md'): 'link' if opposing else 'unlink',
            (scope, 'gemini-cli', 'AGENTS.md'): 'unlink',
        })
        result = app._apply_instruction_pending()
        assert (result.ok, result.failed) == (2, 0)
        assert not grid.pending_entries()
        assert not second.is_symlink()
        if opposing:
            assert link_snapshot(first) == before
        else:
            assert not first.is_symlink()
        assert canonical.read_text() == 'canonical\n'


@pytest.mark.parametrize('scope', ['project', 'global'])
@pytest.mark.parametrize('lowercase_dependent', [False, True])
@pytest.mark.asyncio
async def test_tui_stored_lowercase_chain_completes(tmp_path, monkeypatch, scope, lowercase_dependent):
    project, home, canonical, actuals = seed_stored_lowercase_chain(tmp_path, scope, lowercase_dependent)
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.chdir(project)
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one('#instruction-grid', InstructionGrid)
        grid.restore_pending({(scope, harness, 'AGENTS.md'): 'unlink'
                              for harness in ('claude-code', 'gemini-cli')})
        result = app._apply_instruction_pending()
        assert (result.ok, result.failed) == (2, 0)
        assert not grid.pending_entries()
        assert all(not pointer.is_symlink() for pointer in actuals)
        assert canonical.read_text() == 'canonical source\n'


@pytest.mark.parametrize('opposing', [False, True])
@pytest.mark.asyncio
async def test_tui_actual_shared_slot_alias_intents(hardlinked_slots, opposing):
    scope, home, project, canonical, first, second = hardlinked_slots
    if scope == 'global':
        augment = _pointer_path('augment', scope, project, home)
        tabnine = _pointer_path('tabnine-cli', scope, project, home)
        tabnine.parent.mkdir(parents=True, exist_ok=True)
        tabnine.parent.rmdir()
        tabnine.parent.symlink_to(augment.parent, target_is_directory=True)
        remove_harness, shared = 'tabnine-cli', augment
        failed_intent = (scope, 'augment', 'AGENTS.md')
    else:
        remove_harness, shared = 'claude-code', first
        failed_intent = (scope, remove_harness, 'AGENTS.md')
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one('#instruction-grid', InstructionGrid)
        pending = {
            (scope, 'augment', 'AGENTS.md'): 'link' if opposing else 'unlink',
            (scope, remove_harness, 'AGENTS.md'): 'unlink',
        }
        grid.restore_pending(pending)
        before = snapshot(home.parent)
        result = app._apply_instruction_pending()
        if opposing:
            assert (result.ok, result.failed) == (1, 1)
            assert any('opposing' in error for error in result.errors)
            assert grid.pending_entries() == {failed_intent: 'link' if scope == 'global' else 'unlink'}
            assert snapshot(home.parent) == before
        else:
            assert (result.ok, result.failed) == (2, 0)
            assert not grid.pending_entries()
            assert not shared.is_symlink()
            if scope == 'project':
                assert second.is_symlink()
        assert canonical.read_text() == 'canonical\n'
