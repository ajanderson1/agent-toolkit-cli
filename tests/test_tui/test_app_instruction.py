"""Tests for instruction kind wiring in app.py.

Covers:
1. Sidebar OptionList includes "Instruction" before "skill" (ordering check).
2. Selecting instruction option shows #instruction-grid, hides others.
3. Existing kinds still render (regression guard).
4. Apply routing: instructions_install.apply called with pending scope.
5. PointerConflictError path: footer shows error, notify severity=error.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from textual.widgets import DataTable, OptionList, Static

from agent_toolkit_tui.widgets.agent_grid import AgentGrid
from agent_toolkit_tui.widgets.instruction_grid import InstructionGrid
from agent_toolkit_tui.widgets.pi_grid import PiGrid
from agent_toolkit_tui.widgets.skill_grid import SkillGrid


@pytest.mark.asyncio
async def test_kind_sidebar_includes_instruction_before_skill():
    """Instruction must appear in the sidebar and before Skill (ordering check)."""
    from agent_toolkit_tui.app import TUIApp

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        ol = app.query_one("#kinds-list", OptionList)
        prompts = [str(ol.get_option_at_index(i).prompt) for i in range(ol.option_count)]
        assert "Instruction" in prompts, f"Expected 'Instruction' in {prompts}"
        assert "skill" in prompts, f"Expected 'skill' in {prompts}"
        instr_idx = prompts.index("Instruction")
        skill_idx = prompts.index("skill")
        assert instr_idx < skill_idx, (
            f"Instruction (idx={instr_idx}) must appear before skill (idx={skill_idx})"
        )


@pytest.mark.asyncio
async def test_kind_sidebar_has_four_kinds():
    """The sidebar OptionList must include all four kinds: instruction, skill, pi-extension, agent."""
    from agent_toolkit_tui.app import TUIApp

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        ol = app.query_one("#kinds-list", OptionList)
        prompts = [str(ol.get_option_at_index(i).prompt) for i in range(ol.option_count)]
        assert "Instruction" in prompts
        assert "skill" in prompts
        assert "pi-extension" in prompts
        assert "agent" in prompts


@pytest.mark.asyncio
async def test_switch_to_instruction_shows_instruction_grid():
    """Switching to instruction kind makes InstructionGrid visible, others hidden."""
    from agent_toolkit_tui.app import TUIApp

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_kind("instruction")
        await pilot.pause()
        instr_grid = app.query_one("#instruction-grid", InstructionGrid)
        skill_grid = app.query_one("#skill-grid", SkillGrid)
        pi_grid = app.query_one("#pi-grid", PiGrid)
        agent_grid = app.query_one("#agent-grid", AgentGrid)
        assert instr_grid.display is True
        assert skill_grid.display is False
        assert pi_grid.display is False
        assert agent_grid.display is False


@pytest.mark.asyncio
async def test_switch_to_instruction_then_back_to_skill():
    """Can round-trip skill → instruction → skill."""
    from agent_toolkit_tui.app import TUIApp

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_kind("instruction")
        await pilot.pause()
        app.action_kind("skill")
        await pilot.pause()
        instr_grid = app.query_one("#instruction-grid", InstructionGrid)
        skill_grid = app.query_one("#skill-grid", SkillGrid)
        assert skill_grid.display is True
        assert instr_grid.display is False


@pytest.mark.asyncio
async def test_existing_kinds_still_render():
    """Regression: skill, pi-extension, and agent grids are still present."""
    from agent_toolkit_tui.app import TUIApp

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.query_one("#skill-grid", SkillGrid)
        app.query_one("#pi-grid", PiGrid)
        app.query_one("#agent-grid", AgentGrid)


@pytest.mark.asyncio
async def test_ctrl_s_routes_to_instruction_apply_when_active(monkeypatch):
    """ctrl+s dispatches to _apply_instruction_pending when instruction kind is active."""
    from agent_toolkit_tui.app import TUIApp

    called: list[str] = []

    def fake_apply_instruction(self) -> None:  # noqa: ANN001
        called.append("instruction")

    def fake_apply_skill(self) -> None:  # noqa: ANN001
        called.append("skill")

    monkeypatch.setattr(TUIApp, "_apply_instruction_pending", fake_apply_instruction)
    monkeypatch.setattr(TUIApp, "_apply_skill_pending", fake_apply_skill)

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app._active_kind = "instruction"
        await pilot.press("ctrl+s")
        await pilot.pause()

    assert "instruction" in called
    assert "skill" not in called


@pytest.mark.asyncio
async def test_apply_instruction_calls_instructions_install_apply(monkeypatch):
    """Apply a 'link' pending instruction calls instructions_install.apply()."""
    from agent_toolkit_tui.app import TUIApp
    import agent_toolkit_cli.instructions_install as _ii
    from agent_toolkit_tui.instruction_state import InstructionCell, InstructionRow

    apply_calls: list[Any] = []

    def fake_apply(*, scope, project_root, home):
        apply_calls.append({"scope": scope, "project_root": project_root, "home": home})
        from unittest.mock import MagicMock
        plan = MagicMock()
        plan.actions = []
        return plan

    monkeypatch.setattr(_ii, "apply", fake_apply)
    monkeypatch.setattr(
        "agent_toolkit_tui.app.build_instruction_rows",
        lambda **kw: [],
    )

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app._active_kind = "instruction"
        grid = app.query_one("#instruction-grid", InstructionGrid)
        grid.set_rows([
            InstructionRow(
                slug="AGENTS.md",
                scope="global",
                general_linked=True,
                cells={"claude-code": InstructionCell(applicable=True, linked=False)},
            )
        ])
        grid.restore_pending({("global", "claude-code", "AGENTS.md"): "link"})
        await pilot.pause()

        app._apply_instruction_pending()
        footer = str(app.query_one("#footer-pending", Static).render())

    assert "applied:" in footer
    assert len(apply_calls) >= 1
    assert apply_calls[0]["scope"] == "global"
    # Global scope must pass home (not None).
    assert apply_calls[0]["home"] is not None


@pytest.mark.asyncio
async def test_apply_pointer_conflict_error_surfaces_notify_and_footer(monkeypatch):
    """PointerConflictError from instructions_install.apply must surface via notify + footer."""
    from agent_toolkit_tui.app import TUIApp
    import agent_toolkit_cli.instructions_install as _ii
    from agent_toolkit_cli.instructions_adapters.symlink import PointerConflictError
    from agent_toolkit_tui.instruction_state import InstructionCell, InstructionRow

    notify_calls: list[Any] = []

    def fake_apply_conflict(*, scope, project_root, home):
        raise PointerConflictError("CLAUDE.md is a real file at /fake/CLAUDE.md; refused.")

    monkeypatch.setattr(_ii, "apply", fake_apply_conflict)
    monkeypatch.setattr(
        "agent_toolkit_tui.app.build_instruction_rows",
        lambda **kw: [],
    )

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        orig_notify = app.notify

        def spy_notify(*a, **k):
            notify_calls.append(k)
            return orig_notify(*a, **k)

        monkeypatch.setattr(app, "notify", spy_notify)
        app._active_kind = "instruction"
        grid = app.query_one("#instruction-grid", InstructionGrid)
        grid.set_rows([
            InstructionRow(
                slug="AGENTS.md",
                scope="global",
                general_linked=True,
                cells={"claude-code": InstructionCell(applicable=True, linked=False)},
            )
        ])
        grid.restore_pending({("global", "claude-code", "AGENTS.md"): "link"})
        await pilot.pause()

        app._apply_instruction_pending()
        footer = str(app.query_one("#footer-pending", Static).render())

    assert "apply failed" in footer, f"Expected 'apply failed' in footer: {footer!r}"
    assert notify_calls, "expected notify to be called with error"
    assert notify_calls[-1].get("severity") == "error"
