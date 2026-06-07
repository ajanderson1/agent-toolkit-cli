"""Pilot tests for the InstructionGrid widget and the instruction TUI flow.

Covers (widget-level + app-level):

Widget-level:
1.  columns renders correctly (INSTRUCTION + general + INTERACTIVE_HARNESSES + Source)
2.  row count
3.  toggle unlinked cell queues 'link'
4.  toggle linked cell queues 'unlink'
5.  toggle twice clears pending
6.  PendingChanged message carries count
7.  toggle_column (action_a) queues all in column
8.  set_scope clears pending
9.  conflict cell is non-toggleable (no-op)
10. general column is non-toggleable (no-op)

App-level:
11. sidebar lists instruction first, separator second, then others
12. switching to instruction shows InstructionGrid, hides others
13. ctrl+s routes to _apply_instruction_pending when instruction active
14. apply link writes lock + calls instructions_install.apply (pointer created)
15. apply unlink removes pointer
16. canonical-missing surfaces notify + footer
17. conflict slot is not clobbered after no-op apply
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from textual.app import App, ComposeResult
from textual.widgets import DataTable, OptionList, Static

from agent_toolkit_tui.instruction_state import (
    INTERACTIVE_HARNESSES,
    InstructionCell,
    InstructionRow,
)
from agent_toolkit_tui.widgets.instruction_grid import InstructionGrid


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unlinked_row(slug: str = "AGENTS.md", *, scope: str = "global") -> InstructionRow:
    """Row with all INTERACTIVE_HARNESSES unlinked at the given scope."""
    cells = {
        (h, scope): InstructionCell(linked=False, conflict=False)
        for h in INTERACTIVE_HARNESSES
    }
    return InstructionRow(
        slug=slug,
        source="AGENTS.md",
        canonical_exists=True,
        cells=cells,
    )


def _linked_row(slug: str = "AGENTS.md", *, scope: str = "global") -> InstructionRow:
    """Row with all INTERACTIVE_HARNESSES linked at the given scope."""
    cells = {
        (h, scope): InstructionCell(linked=True, conflict=False)
        for h in INTERACTIVE_HARNESSES
    }
    return InstructionRow(
        slug=slug,
        source="AGENTS.md",
        canonical_exists=True,
        cells=cells,
    )


def _conflict_row(slug: str = "AGENTS.md", *, scope: str = "global") -> InstructionRow:
    """Row with all INTERACTIVE_HARNESSES in conflict state."""
    cells = {
        (h, scope): InstructionCell(linked=False, conflict=True)
        for h in INTERACTIVE_HARNESSES
    }
    return InstructionRow(
        slug=slug,
        source="AGENTS.md",
        canonical_exists=True,
        cells=cells,
    )


# ---------------------------------------------------------------------------
# Widget-level tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_instruction_grid_mounts_with_correct_columns():
    """Grid must show INSTRUCTION + general + INTERACTIVE_HARNESSES + Source."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid([_unlinked_row()], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#instruction-table", DataTable)
        labels = [str(c.label) for c in table.columns.values()]
        # Slug + general + N harness cols + Source
        assert len(labels) == len(INTERACTIVE_HARNESSES) + 3
        assert any("INSTRUCTION" in lbl for lbl in labels)
        assert any("general" in lbl for lbl in labels)
        assert any("Source" in lbl for lbl in labels)


@pytest.mark.asyncio
async def test_instruction_grid_row_count():
    """Row count equals the number of rows passed in."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid([_unlinked_row()], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", InstructionGrid)
        assert g.row_count == 1
        assert g.row_slugs == ["AGENTS.md"]


@pytest.mark.asyncio
async def test_toggle_unlinked_cell_queues_link():
    """Space on an unlinked harness cell queues 'link'."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid([_unlinked_row()], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", InstructionGrid)
        g.set_scope("global")
        table = app.query_one("#instruction-table", DataTable)
        # Column layout: [0]=slug, [1]=general, [2]=first harness, ...
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=2)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        pending = g.pending_entries()
        first_harness = INTERACTIVE_HARNESSES[0]
        assert pending.get(("global", first_harness, "AGENTS.md")) == "link"


@pytest.mark.asyncio
async def test_toggle_linked_cell_queues_unlink():
    """Space on a linked cell queues 'unlink'."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid([_linked_row()], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", InstructionGrid)
        g.set_scope("global")
        table = app.query_one("#instruction-table", DataTable)
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=2)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        pending = g.pending_entries()
        first_harness = INTERACTIVE_HARNESSES[0]
        assert pending.get(("global", first_harness, "AGENTS.md")) == "unlink"


@pytest.mark.asyncio
async def test_toggle_twice_clears_pending():
    """Toggling the same cell twice returns to empty pending."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid([_unlinked_row()], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", InstructionGrid)
        g.set_scope("global")
        table = app.query_one("#instruction-table", DataTable)
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=2)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        await pilot.press("space")
        assert g.pending_entries() == {}


def test_pending_changed_message_carries_count():
    """PendingChanged(count) stores the count."""
    msg = InstructionGrid.PendingChanged(5)
    assert msg.count == 5


@pytest.mark.asyncio
async def test_pending_changed_fires_on_toggle():
    """PendingChanged is posted when a cell is toggled."""
    received: list[int] = []

    class _A(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid([_unlinked_row()], id="g")

        def on_instruction_grid_pending_changed(
            self, event: InstructionGrid.PendingChanged
        ) -> None:
            received.append(event.count)

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", InstructionGrid)
        g.set_scope("global")
        table = app.query_one("#instruction-table", DataTable)
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=2)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()

    assert 1 in received


@pytest.mark.asyncio
async def test_toggle_column_queues_all_in_column():
    """'a' key on a harness column toggles all rows in that column."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid(
                [_unlinked_row("AGENTS.md")],
                id="g",
            )

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", InstructionGrid)
        g.set_scope("global")
        table = app.query_one("#instruction-table", DataTable)
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=2)
        table.focus()
        await pilot.pause()
        await pilot.press("a")
        pending = g.pending_entries()
        first_harness = INTERACTIVE_HARNESSES[0]
        assert pending.get(("global", first_harness, "AGENTS.md")) == "link"


@pytest.mark.asyncio
async def test_set_scope_clears_pending():
    """set_scope clears any pending entries."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid([_unlinked_row()], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", InstructionGrid)
        g.set_scope("global")
        table = app.query_one("#instruction-table", DataTable)
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=2)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        assert g.pending_entries() != {}
        g.set_scope("project")
        assert g.pending_entries() == {}


@pytest.mark.asyncio
async def test_conflict_cell_is_not_toggled():
    """Space on a conflict cell is a no-op (never queues a toggle)."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid([_conflict_row()], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", InstructionGrid)
        g.set_scope("global")
        table = app.query_one("#instruction-table", DataTable)
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=2)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        # No toggle queued for conflict cell
        assert g.pending_entries() == {}


@pytest.mark.asyncio
async def test_general_column_is_not_toggled():
    """Space on the general (column 1) is a no-op."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid([_unlinked_row()], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", InstructionGrid)
        g.set_scope("global")
        table = app.query_one("#instruction-table", DataTable)
        # Column 1 = general
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        assert g.pending_entries() == {}


@pytest.mark.asyncio
async def test_slug_info_at_project_scope_does_not_crash():
    """`i` on the slug column at project scope opens the info modal.

    Regression: the project-scope branch resolved the canonical path with
    project_canonical_agents_md(None), which raises (it requires a real Path).
    It must use the project root (cwd) instead.
    """

    class _A(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid([_unlinked_row(scope="project")], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", InstructionGrid)
        g.set_scope("project")
        table = app.query_one("#instruction-table", DataTable)
        # Column 0 = slug (INSTRUCTION).
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=0)
        table.focus()
        await pilot.pause()
        # Must not raise; a CellInfoScreen should be pushed onto the stack
        # (it would have raised TypeError before the fix).
        await pilot.press("i")
        await pilot.pause()
        from agent_toolkit_tui.screens.cell_info import CellInfoScreen

        screen = app.screen
        assert isinstance(screen, CellInfoScreen)
        # The slug-column body names the canonical AGENTS.md at the project root.
        assert "AGENTS.md" in screen._body_markup
        assert str(Path.cwd()) in screen._body_markup


# ---------------------------------------------------------------------------
# App-level tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kind_sidebar_lists_instruction_first():
    """Sidebar OptionList must list instruction first, then separator, then others."""
    from agent_toolkit_tui.app import TUIApp

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        ol = app.query_one("#kinds-list", OptionList)
        # First option must be instruction
        first_option = ol.get_option_at_index(0)
        assert first_option.id == "kind-instruction"
        # Second entry must be the separator (disabled)
        separator = ol.get_option_at_index(1)
        assert separator.disabled is True
        # Collect all non-separator prompts
        prompts = []
        ids = []
        for i in range(ol.option_count):
            try:
                opt = ol.get_option_at_index(i)
                if opt.id not in (None, "kind-separator") and not opt.disabled:
                    prompts.append(str(opt.prompt))
                    ids.append(opt.id)
            except Exception:
                pass
        assert "instruction" in prompts
        assert "skill" in prompts
        assert "pi-extension" in prompts
        assert "agent" in prompts
        # instruction must be first among selectable options
        assert ids[0] == "kind-instruction"


@pytest.mark.asyncio
async def test_switch_to_instruction_shows_instruction_grid():
    """Switching to instruction kind makes InstructionGrid visible, others hidden."""
    from agent_toolkit_tui.app import TUIApp
    from agent_toolkit_tui.widgets.agent_grid import AgentGrid
    from agent_toolkit_tui.widgets.pi_grid import PiGrid
    from agent_toolkit_tui.widgets.skill_grid import SkillGrid

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_kind("instruction")
        await pilot.pause()
        instruction_grid = app.query_one("#instruction-grid", InstructionGrid)
        skill_grid = app.query_one("#skill-grid", SkillGrid)
        pi_grid = app.query_one("#pi-grid", PiGrid)
        agent_grid = app.query_one("#agent-grid", AgentGrid)
        assert instruction_grid.display is True
        assert skill_grid.display is False
        assert pi_grid.display is False
        assert agent_grid.display is False


@pytest.mark.asyncio
async def test_switch_to_instruction_then_back_to_skill():
    """Can round-trip skill → instruction → skill."""
    from agent_toolkit_tui.app import TUIApp
    from agent_toolkit_tui.widgets.skill_grid import SkillGrid

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_kind("instruction")
        await pilot.pause()
        app.action_kind("skill")
        await pilot.pause()
        instruction_grid = app.query_one("#instruction-grid", InstructionGrid)
        skill_grid = app.query_one("#skill-grid", SkillGrid)
        assert skill_grid.display is True
        assert instruction_grid.display is False


@pytest.mark.asyncio
async def test_ctrl_s_routes_to_instruction_apply_when_active(monkeypatch):
    """ctrl+s dispatches to _apply_instruction_pending when instruction kind is active."""
    from agent_toolkit_tui.app import TUIApp

    called: list[str] = []

    def fake_apply_instruction(self) -> None:  # noqa: ANN001
        called.append("instruction")

    def fake_apply_skill(self) -> None:  # noqa: ANN001
        called.append("skill")

    def fake_apply_agent(self) -> None:  # noqa: ANN001
        called.append("agent")

    monkeypatch.setattr(TUIApp, "_apply_instruction_pending", fake_apply_instruction)
    monkeypatch.setattr(TUIApp, "_apply_skill_pending", fake_apply_skill)
    monkeypatch.setattr(TUIApp, "_apply_agent_pending", fake_apply_agent)

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app._active_kind = "instruction"
        await pilot.press("ctrl+s")
        await pilot.pause()

    assert "instruction" in called
    assert "skill" not in called
    assert "agent" not in called


@pytest.mark.asyncio
async def test_apply_link_creates_pointer(monkeypatch, tmp_path: Path):
    """Apply a 'link' pending entry writes lock and calls instructions_install.apply."""
    from agent_toolkit_tui.app import TUIApp
    import agent_toolkit_cli.instructions_install as _ii
    import agent_toolkit_cli.instructions_paths as _ip

    apply_calls: list[Any] = []

    def fake_apply(*, scope, project_root=None, home=None):
        apply_calls.append({"scope": scope, "project_root": project_root})
        action = MagicMock()
        action.action = "create"
        p = MagicMock()
        p.actions = [action]
        return p

    monkeypatch.setattr(_ii, "apply", fake_apply)
    monkeypatch.setattr(
        "agent_toolkit_tui.app.build_instruction_rows",
        lambda **kw: [],
    )

    # Redirect lock paths to tmp_path
    lock_file = tmp_path / "instructions-lock.json"
    monkeypatch.setattr(
        _ip, "lock_file_path",
        lambda scope, project_root: lock_file,
    )

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app._active_kind = "instruction"
        app._scope = "global"
        grid = app.query_one("#instruction-grid", InstructionGrid)
        grid.set_rows([_unlinked_row()])
        grid.restore_pending({("global", "claude-code", "AGENTS.md"): "link"})
        await pilot.pause()

        app._apply_instruction_pending()
        footer = str(app.query_one("#footer-pending", Static).render())

    assert "applied:" in footer
    assert len(apply_calls) >= 1
    # Lock must have been written with claude-code in harnesses
    lock_data = json.loads(lock_file.read_text())
    assert "AGENTS.md" in lock_data["instructions"]
    assert "claude-code" in lock_data["instructions"]["AGENTS.md"]["harnesses"]


@pytest.mark.asyncio
async def test_apply_unlink_removes_from_lock(monkeypatch, tmp_path: Path):
    """Apply an 'unlink' pending entry removes harness from lock."""
    from agent_toolkit_tui.app import TUIApp
    import agent_toolkit_cli.instructions_install as _ii
    import agent_toolkit_cli.instructions_paths as _ip

    apply_calls: list[Any] = []

    def fake_apply(*, scope, project_root=None, home=None):
        apply_calls.append({"scope": scope})
        action = MagicMock()
        action.action = "remove"
        p = MagicMock()
        p.actions = [action]
        return p

    monkeypatch.setattr(_ii, "apply", fake_apply)
    monkeypatch.setattr(
        "agent_toolkit_tui.app.build_instruction_rows",
        lambda **kw: [],
    )

    # Pre-populate lock with claude-code
    lock_file = tmp_path / "instructions-lock.json"
    lock_file.write_text(json.dumps({
        "version": 1,
        "instructions": {
            "AGENTS.md": {
                "scope": "global",
                "source": "AGENTS.md",
                "harnesses": ["claude-code", "gemini-cli"],
            }
        },
    }) + "\n")

    monkeypatch.setattr(
        _ip, "lock_file_path",
        lambda scope, project_root: lock_file,
    )

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app._active_kind = "instruction"
        app._scope = "global"
        grid = app.query_one("#instruction-grid", InstructionGrid)
        grid.set_rows([_linked_row()])
        grid.restore_pending({("global", "claude-code", "AGENTS.md"): "unlink"})
        await pilot.pause()

        app._apply_instruction_pending()
        footer = str(app.query_one("#footer-pending", Static).render())

    assert "applied:" in footer
    lock_data = json.loads(lock_file.read_text())
    harnesses = lock_data["instructions"]["AGENTS.md"]["harnesses"]
    assert "claude-code" not in harnesses
    assert "gemini-cli" in harnesses


@pytest.mark.asyncio
async def test_apply_canonical_missing_surfaces_error(monkeypatch, tmp_path: Path):
    """CanonicalMissingError surfaces via notify + footer."""
    from agent_toolkit_tui.app import TUIApp
    import agent_toolkit_cli.instructions_install as _ii
    import agent_toolkit_cli.instructions_paths as _ip

    notify_calls: list[Any] = []

    def fake_apply(*, scope, project_root=None, home=None):
        raise _ii.CanonicalMissingError("no AGENTS.md")

    monkeypatch.setattr(_ii, "apply", fake_apply)
    monkeypatch.setattr(
        "agent_toolkit_tui.app.build_instruction_rows",
        lambda **kw: [],
    )

    lock_file = tmp_path / "instructions-lock.json"
    monkeypatch.setattr(
        _ip, "lock_file_path",
        lambda scope, project_root: lock_file,
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
        app._scope = "global"
        grid = app.query_one("#instruction-grid", InstructionGrid)
        grid.set_rows([_unlinked_row()])
        grid.restore_pending({("global", "claude-code", "AGENTS.md"): "link"})
        await pilot.pause()

        app._apply_instruction_pending()
        footer = str(app.query_one("#footer-pending", Static).render())

    assert "apply failed" in footer
    assert notify_calls, "expected notify to be called with error"
    assert notify_calls[-1].get("severity") == "error"


@pytest.mark.asyncio
async def test_apply_rolls_back_lock_on_reconcile_failure(monkeypatch, tmp_path: Path):
    """A failed reconcile must restore the lock so it never claims an install
    that did not land on disk (mirrors install_cmd.py's rollback contract)."""
    from agent_toolkit_tui.app import TUIApp
    import agent_toolkit_cli.instructions_install as _ii
    import agent_toolkit_cli.instructions_paths as _ip

    def fake_apply(*, scope, project_root=None, home=None):
        raise _ii.CanonicalMissingError("no AGENTS.md")

    monkeypatch.setattr(_ii, "apply", fake_apply)
    monkeypatch.setattr(
        "agent_toolkit_tui.app.build_instruction_rows",
        lambda **kw: [],
    )

    lock_file = tmp_path / "instructions-lock.json"
    monkeypatch.setattr(
        _ip, "lock_file_path",
        lambda scope, project_root: lock_file,
    )

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app._active_kind = "instruction"
        app._scope = "global"
        grid = app.query_one("#instruction-grid", InstructionGrid)
        grid.set_rows([_unlinked_row()])
        # Fresh scope: lock does not exist yet, user queues a link.
        grid.restore_pending({("global", "claude-code", "AGENTS.md"): "link"})
        await pilot.pause()

        app._apply_instruction_pending()

    # The lock must NOT exist afterward — it was absent before, the reconcile
    # failed, so rollback deletes it rather than leaving a lying entry.
    assert not lock_file.exists(), "lock must be rolled back (deleted) on reconcile failure"


@pytest.mark.asyncio
async def test_apply_rolls_back_to_prior_lock_on_failure(monkeypatch, tmp_path: Path):
    """When a lock already existed, a failed reconcile restores its prior content."""
    from agent_toolkit_tui.app import TUIApp
    import agent_toolkit_cli.instructions_install as _ii
    import agent_toolkit_cli.instructions_paths as _ip

    def fake_apply(*, scope, project_root=None, home=None):
        raise _ii.CanonicalMissingError("no AGENTS.md")

    monkeypatch.setattr(_ii, "apply", fake_apply)
    monkeypatch.setattr(
        "agent_toolkit_tui.app.build_instruction_rows",
        lambda **kw: [],
    )

    lock_file = tmp_path / "instructions-lock.json"
    prior_payload = {
        "version": 1,
        "instructions": {
            "AGENTS.md": {
                "scope": "global",
                "source": "AGENTS.md",
                "harnesses": ["gemini-cli"],
            }
        },
    }
    lock_file.write_text(json.dumps(prior_payload) + "\n")

    monkeypatch.setattr(
        _ip, "lock_file_path",
        lambda scope, project_root: lock_file,
    )

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app._active_kind = "instruction"
        app._scope = "global"
        grid = app.query_one("#instruction-grid", InstructionGrid)
        grid.set_rows([_unlinked_row()])
        grid.restore_pending({("global", "claude-code", "AGENTS.md"): "link"})
        await pilot.pause()

        app._apply_instruction_pending()

    # Prior content restored verbatim — no claude-code leaked in.
    restored = json.loads(lock_file.read_text())
    assert restored["instructions"]["AGENTS.md"]["harnesses"] == ["gemini-cli"]


@pytest.mark.asyncio
async def test_apply_unlink_last_harness_prunes_lock(monkeypatch, tmp_path: Path):
    """Removing the sole harness deletes the lock file rather than leaving an
    empty stub (matches the CLI uninstall #312 contract)."""
    from agent_toolkit_tui.app import TUIApp
    import agent_toolkit_cli.instructions_install as _ii
    import agent_toolkit_cli.instructions_paths as _ip

    def fake_apply(*, scope, project_root=None, home=None):
        action = MagicMock()
        action.action = "remove"
        p = MagicMock()
        p.actions = [action]
        return p

    monkeypatch.setattr(_ii, "apply", fake_apply)
    monkeypatch.setattr(
        "agent_toolkit_tui.app.build_instruction_rows",
        lambda **kw: [],
    )

    lock_file = tmp_path / "instructions-lock.json"
    lock_file.write_text(json.dumps({
        "version": 1,
        "instructions": {
            "AGENTS.md": {
                "scope": "global",
                "source": "AGENTS.md",
                "harnesses": ["claude-code"],
            }
        },
    }) + "\n")

    monkeypatch.setattr(
        _ip, "lock_file_path",
        lambda scope, project_root: lock_file,
    )

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app._active_kind = "instruction"
        app._scope = "global"
        grid = app.query_one("#instruction-grid", InstructionGrid)
        grid.set_rows([_linked_row()])
        grid.restore_pending({("global", "claude-code", "AGENTS.md"): "unlink"})
        await pilot.pause()

        app._apply_instruction_pending()
        footer = str(app.query_one("#footer-pending", Static).render())

    assert "applied:" in footer
    # Lock emptied → deleted, not written back as an empty stub.
    assert not lock_file.exists(), "lock must be deleted when no harnesses remain (#312)"


@pytest.mark.asyncio
async def test_conflict_slot_not_clobbered(monkeypatch, tmp_path: Path):
    """A conflict cell queued for link is a no-op: real file must still exist."""
    from agent_toolkit_tui.app import TUIApp
    import agent_toolkit_cli.instructions_install as _ii
    import agent_toolkit_cli.instructions_paths as _ip

    apply_calls: list[Any] = []

    def fake_apply(*, scope, project_root=None, home=None):
        # Should not be reached because conflict cells cannot be toggled.
        apply_calls.append({"scope": scope})
        p = MagicMock()
        p.actions = []
        return p

    monkeypatch.setattr(_ii, "apply", fake_apply)
    monkeypatch.setattr(
        "agent_toolkit_tui.app.build_instruction_rows",
        lambda **kw: [],
    )

    lock_file = tmp_path / "instructions-lock.json"
    monkeypatch.setattr(
        _ip, "lock_file_path",
        lambda scope, project_root: lock_file,
    )

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app._active_kind = "instruction"
        app._scope = "global"
        grid = app.query_one("#instruction-grid", InstructionGrid)
        # Conflict row — pending is empty (conflict cells can't be toggled)
        grid.set_rows([_conflict_row()])
        # No pending entries (conflict cells block toggle at widget level)
        assert grid.pending_entries() == {}
        await pilot.pause()

        app._apply_instruction_pending()

    # apply() should not have been called because there's nothing pending
    assert apply_calls == [], "instructions_install.apply should not be called with no pending"
