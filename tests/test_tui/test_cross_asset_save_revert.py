"""Unit tests verifying that save, revert, diff, and tab-switching work correctly
when changes span multiple asset types.
"""

from __future__ import annotations

import pytest
from textual.widgets import Static

from agent_toolkit_tui.app import ApplyResult, TUIApp
from agent_toolkit_tui.instruction_state import InstructionRow
from agent_toolkit_tui.skill_state import SkillRow
from agent_toolkit_tui.widgets.command_grid import CommandGrid
from agent_toolkit_tui.widgets.instruction_grid import InstructionGrid
from agent_toolkit_tui.widgets.pi_grid import PiGrid
from agent_toolkit_tui.widgets.skill_grid import SkillGrid


@pytest.mark.asyncio
async def test_pending_survives_asset_type_tab_switching() -> None:
    """Queued changes on one asset type must not be discarded when switching tabs."""
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()

        # Start on skill tab and queue a pending edit
        app.action_asset_type("skill")
        await pilot.pause()
        skill_grid = app.query_one("#skill-grid", SkillGrid)
        skill_grid.set_rows(
            [
                SkillRow(
                    slug="myskill",
                    source="o/r",
                    ref="main",
                    state="library",
                    cells={},
                )
            ]
        )
        skill_grid.restore_pending({("project", "claude", "myskill"): "link"})
        app._refresh_pending_label()
        await pilot.pause()

        assert ("project", "claude", "myskill") in skill_grid.pending_entries()
        assert "Pending: 1" in str(app.query_one("#footer-pending", Static).render())

        # Switch to instruction tab and queue another pending edit
        app.action_asset_type("instruction")
        await pilot.pause()
        instruction_grid = app.query_one("#instruction-grid", InstructionGrid)
        instruction_grid.set_rows(
            [
                InstructionRow(
                    slug="AGENTS.md",
                    source="AGENTS.md",
                    canonical_exists=True,
                    cells={},
                )
            ]
        )
        instruction_grid.restore_pending({("global", "cursor", "AGENTS.md"): "link"})
        app._refresh_pending_label()
        await pilot.pause()

        # Both edits should be counted in footer
        footer = str(app.query_one("#footer-pending", Static).render())
        assert "Pending: 2" in footer
        assert "1 global, 1 project" in footer

        # Switch back to skill tab: skill pending must still be preserved
        app.action_asset_type("skill")
        await pilot.pause()

        assert ("project", "claude", "myskill") in skill_grid.pending_entries()
        assert ("global", "cursor", "AGENTS.md") in instruction_grid.pending_entries()
        footer = str(app.query_one("#footer-pending", Static).render())
        assert "Pending: 2" in footer


@pytest.mark.asyncio
async def test_action_revert_clears_all_asset_types_and_is_scope_tagged() -> None:
    """ctrl+z clears pending across ALL asset types and reports total with scope tags."""
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        pi_grid = app.query_one("#pi-grid", PiGrid)
        cmd_grid = app.query_one("#command-grid", CommandGrid)

        pi_grid._pending[("global", "my-pi")] = "link"
        cmd_grid._pending[("project", "standard", "my-cmd")] = "unlink"
        app._refresh_pending_label()
        await pilot.pause()

        assert len(app._get_all_pending_edits()) == 2

        app.action_revert()
        await pilot.pause()

        assert pi_grid.pending_entries() == {}
        assert cmd_grid.pending_entries() == {}
        assert len(app._get_all_pending_edits()) == 0

        label = str(app.query_one("#footer-pending", Static).render())
        assert "reverted: 2 pending cleared (1 global, 1 project)" in label


@pytest.mark.asyncio
async def test_action_diff_reports_across_multiple_asset_types() -> None:
    """ctrl+d diffs pending across all asset types, including scope tags."""
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        pi_grid = app.query_one("#pi-grid", PiGrid)
        cmd_grid = app.query_one("#command-grid", CommandGrid)

        pi_grid._pending[("global", "my-pi")] = "link"
        cmd_grid._pending[("project", "standard", "my-cmd")] = "unlink"

        app.action_diff()
        label = str(app.query_one("#footer-pending", Static).render())
        assert "diff: 1 would-link, 1 would-unlink (1 global, 1 project)" in label


@pytest.mark.asyncio
async def test_action_apply_applies_across_multiple_asset_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ctrl+s applies all pending asset types and aggregates footer counts."""
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        skill_grid = app.query_one("#skill-grid", SkillGrid)
        cmd_grid = app.query_one("#command-grid", CommandGrid)

        skill_grid._pending[("project", "claude", "myskill")] = "link"
        cmd_grid._pending[("global", "standard", "mycmd")] = "unlink"

        called: list[str] = []

        def fake_apply_skill(self_app: TUIApp) -> ApplyResult:
            called.append("skill")
            skill_grid.clear_pending()
            return ApplyResult(
                ok=1, failed=0, errors=[], keys=[("project", "claude", "myskill")]
            )

        def fake_apply_command(self_app: TUIApp) -> ApplyResult:
            called.append("command")
            cmd_grid.clear_pending()
            return ApplyResult(
                ok=1, failed=0, errors=[], keys=[("global", "standard", "mycmd")]
            )

        monkeypatch.setattr(TUIApp, "_apply_skill_pending", fake_apply_skill)
        monkeypatch.setattr(TUIApp, "_apply_command_pending", fake_apply_command)

        # We are on pi-extension tab (neither skill nor command is active)
        app.action_asset_type("pi-extension")
        await pilot.pause()

        app.action_apply()
        await pilot.pause()

        assert "skill" in called
        assert "command" in called
        assert skill_grid.pending_entries() == {}
        assert cmd_grid.pending_entries() == {}

        footer = str(app.query_one("#footer-pending", Static).render())
        assert "applied: 2 ok, 0 failed (1 global, 1 project)" in footer


@pytest.mark.asyncio
async def test_action_apply_aggregates_errors_across_asset_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When some asset types fail, errors are aggregated and failed pending remains."""
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        skill_grid = app.query_one("#skill-grid", SkillGrid)
        cmd_grid = app.query_one("#command-grid", CommandGrid)

        skill_grid._pending[("project", "claude", "myskill")] = "link"
        cmd_grid._pending[("global", "standard", "mycmd")] = "unlink"

        notified: list[tuple[str, str]] = []

        def fake_notify(
            self_app: TUIApp,
            message: str,
            title: str | None = None,
            severity: str | None = None,
            timeout: int | None = None,
        ) -> None:
            notified.append((title or "", message))

        def fake_apply_skill(self_app: TUIApp) -> ApplyResult:
            skill_grid.clear_pending()
            return ApplyResult(
                ok=1, failed=0, errors=[], keys=[("project", "claude", "myskill")]
            )

        def fake_apply_command(self_app: TUIApp) -> ApplyResult:
            # Command fails: pending not cleared
            return ApplyResult(
                ok=0,
                failed=1,
                errors=["mycmd: failed to link"],
                keys=[("global", "standard", "mycmd")],
            )

        monkeypatch.setattr(TUIApp, "_apply_skill_pending", fake_apply_skill)
        monkeypatch.setattr(TUIApp, "_apply_command_pending", fake_apply_command)
        monkeypatch.setattr(TUIApp, "notify", fake_notify)

        app.action_apply()
        await pilot.pause()

        assert skill_grid.pending_entries() == {}
        assert ("global", "standard", "mycmd") in cmd_grid.pending_entries()

        footer = str(app.query_one("#footer-pending", Static).render())
        assert "apply failed" in footer
        assert "mycmd: failed to link" in footer

        assert len(notified) == 1
        assert "Apply: 1 ok, 1 failed" in notified[0][0]
        assert "mycmd: failed to link" in notified[0][1]
