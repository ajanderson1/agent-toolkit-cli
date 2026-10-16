"""Real TUI alias-chain safety and dependent-pointer removal/retry regressions."""
from __future__ import annotations

import pytest
from textual.widgets import Static

from agent_toolkit_cli.instructions_adapters.symlink import Adapter
from agent_toolkit_tui.app import TUIApp
from agent_toolkit_tui.widgets.instruction_grid import InstructionGrid
from tests.test_cli.test_instructions_lockless import snapshot
from tests.test_cli.test_instructions_pointer_identity import seed_dependent_pointers, seed_native_alias


@pytest.mark.parametrize('scope', ['project', 'global'])
@pytest.mark.parametrize('alias_kind', ['case', 'unicode'])
@pytest.mark.asyncio
async def test_tui_refuses_native_alias_chain_removal_before_entire_batch(tmp_path, monkeypatch, scope, alias_kind):
    project, home, canonical, pointer, other = seed_native_alias(tmp_path, scope, alias_kind)
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.chdir(project)
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_asset_type('instruction')
        app.action_scope(scope)
        grid = app.query_one('#instruction-grid', InstructionGrid)
        pending = {(scope, h, 'AGENTS.md'): 'unlink' for h in ('claude-code', 'gemini-cli')}
        grid.restore_pending(pending)
        before = snapshot(tmp_path)
        app.action_apply()
        await pilot.pause()
        assert 'chain' in str(app.query_one('#footer-pending', Static).render())
        assert grid.pending_entries() == pending
        assert canonical.read_text() == 'keep user source\n'
        assert snapshot(tmp_path) == before


@pytest.mark.parametrize('scope', ['project', 'global'])
@pytest.mark.parametrize('fail_once', [False, True])
@pytest.mark.asyncio
async def test_tui_removes_dependent_pointers_and_retries_only_unfinished_node(tmp_path, monkeypatch, scope, fail_once):
    project, home, canonical, pointers = seed_dependent_pointers(tmp_path, scope)
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.chdir(project)
    original = Adapter.uninstall
    failing = fail_once

    def injected(self, **kwargs):
        if self.harness == 'claude-code' and failing:
            raise OSError('injected removal failure')
        return original(self, **kwargs)

    monkeypatch.setattr(Adapter, 'uninstall', injected)
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_asset_type('instruction')
        app.action_scope(scope)
        grid = app.query_one('#instruction-grid', InstructionGrid)
        grid.restore_pending({(scope, h, 'AGENTS.md'): 'unlink' for h, _ in pointers})
        app.action_apply()
        await pilot.pause()
        if fail_once:
            assert not pointers[1][1].is_symlink(), 'dependent must be removed before referent'
            assert grid.pending_entries() == {(scope, 'claude-code', 'AGENTS.md'): 'unlink'}
            failing = False
            app.action_apply()
            await pilot.pause()
        assert all(not p.is_symlink() for _, p in pointers)
        assert not grid.pending_entries()
        assert canonical.read_text() == 'canonical source\n'
        app.action_apply()
        assert not grid.pending_entries()
