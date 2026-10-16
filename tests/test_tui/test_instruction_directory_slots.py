"""Real TUI completion for independent entries sharing a symlink node."""
from __future__ import annotations

import pytest

from agent_toolkit_cli.instructions_adapters.symlink import link_snapshot
from tests.test_cli.test_instructions_lockless import snapshot
from agent_toolkit_tui.app import TUIApp
from agent_toolkit_tui.widgets.instruction_grid import InstructionGrid
from tests.test_cli.test_instructions_directory_slots import hardlinked_slots


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


@pytest.mark.parametrize('opposing', [False, True])
@pytest.mark.asyncio
async def test_tui_actual_shared_slot_alias_intents(hardlinked_slots, opposing):
    scope, home, project, canonical, first, second = hardlinked_slots
    if scope == 'global':
        (home / '.augment').symlink_to(first.parent, target_is_directory=True)
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one('#instruction-grid', InstructionGrid)
        pending = {
            (scope, 'augment', 'AGENTS.md'): 'link' if opposing else 'unlink',
            (scope, 'claude-code', 'AGENTS.md'): 'unlink',
        }
        grid.restore_pending(pending)
        before = snapshot(home.parent)
        result = app._apply_instruction_pending()
        if opposing:
            assert (result.ok, result.failed) == (1, 1)
            assert any('opposing' in error for error in result.errors)
            assert grid.pending_entries() == {(scope, 'claude-code', 'AGENTS.md'): 'unlink'}
            assert snapshot(home.parent) == before
        else:
            assert (result.ok, result.failed) == (2, 0)
            assert not grid.pending_entries()
            assert not first.is_symlink()
            assert second.is_symlink()
        assert canonical.read_text() == 'canonical\n'
