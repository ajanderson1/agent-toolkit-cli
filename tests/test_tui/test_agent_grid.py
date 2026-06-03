"""Pilot tests for the AgentGrid widget and the agent TUI flow.

Covers (8 widget-level + 8 app-level = 16 tests):

Widget-level:
1. columns renders correctly (AGENT + INTERACTIVE_HARNESSES + Source)
2. row count
3. toggle unlinked cell queues 'link'
4. toggle linked cell queues 'unlink'
5. toggle twice clears pending
6. PendingChanged message carries count
7. toggle_column (action_a) queues all in column
8. set_scope clears pending

App-level:
9.  sidebar lists 4 kinds (instruction / skill / pi-extension / agent)
10. switch to agent shows AgentGrid, hides SkillGrid + PiGrid
11. switch back to skill shows SkillGrid
12. ctrl+s routes to _apply_agent_pending when agent active
13. apply link calls agent_install.apply
14. apply unlink calls agent_install.uninstall DIRECTLY (regression guard for orphan bug)
15. apply error surfaces notify + footer
16. apply project scope seeds canonical when missing
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from textual.app import App, ComposeResult
from textual.widgets import DataTable, OptionList, Static

from agent_toolkit_tui.agent_state import INTERACTIVE_HARNESSES, AgentCell, AgentRow
from agent_toolkit_tui.widgets.agent_grid import AgentGrid
from agent_toolkit_tui.widgets.pi_grid import PiGrid
from agent_toolkit_tui.widgets.skill_grid import SkillGrid


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _linked_row(slug: str, *, harness: str = "claude-code") -> AgentRow:
    """Row with exactly one harness linked at global scope."""
    return AgentRow(
        slug=slug,
        source=f"ajanderson1/{slug}",
        ref="main",
        cells={(harness, "global"): AgentCell(linked=True)},
    )


def _unlinked_row(slug: str, *, harness: str = "claude-code") -> AgentRow:
    """Row with exactly one harness unlinked at global scope."""
    return AgentRow(
        slug=slug,
        source=f"ajanderson1/{slug}",
        ref="main",
        cells={(harness, "global"): AgentCell(linked=False)},
    )


def _full_row(
    slug: str,
    *,
    linked: bool = False,
    scope: str = "global",
) -> AgentRow:
    """Row with all INTERACTIVE_HARNESSES, all at the same linked state."""
    cells = {
        (h, scope): AgentCell(linked=linked)
        for h in INTERACTIVE_HARNESSES
    }
    return AgentRow(
        slug=slug,
        source=f"ajanderson1/{slug}",
        ref="main",
        cells=cells,
    )


# ---------------------------------------------------------------------------
# Widget-level tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_grid_mounts_with_correct_columns():
    """Grid must show AGENT plus INTERACTIVE_HARNESSES plus Source."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield AgentGrid([_full_row("alpha")], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#agent-table", DataTable)
        labels = [str(c.label) for c in table.columns.values()]
        # Slug + N harness cols + Source = 2 + N
        assert len(labels) == len(INTERACTIVE_HARNESSES) + 2
        assert any("AGENT" in lbl for lbl in labels)
        assert any("Source" in lbl for lbl in labels)
        # All harness display names must appear somewhere in the column labels
        from agent_toolkit_cli.skill_agents import AGENTS
        for h in INTERACTIVE_HARNESSES:
            display = AGENTS[h].display_name
            assert any(display in lbl for lbl in labels), (
                f"Expected column for harness {h!r} (display={display!r})"
            )


@pytest.mark.asyncio
async def test_agent_grid_row_count():
    """Row count equals the number of rows passed in."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield AgentGrid(
                [_full_row("a"), _full_row("b"), _full_row("c")], id="g",
            )

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", AgentGrid)
        assert g.row_count == 3
        assert g.row_slugs == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_toggle_unlinked_cell_queues_link():
    """Space on an unlinked cell queues 'link'."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield AgentGrid([_full_row("alpha", linked=False)], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", AgentGrid)
        g.set_scope("global")
        table = app.query_one("#agent-table", DataTable)
        # Column 1 = first INTERACTIVE_HARNESSES entry
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        pending = g.pending_entries()
        first_harness = INTERACTIVE_HARNESSES[0]
        assert pending.get(("global", first_harness, "alpha")) == "link"


@pytest.mark.asyncio
async def test_toggle_linked_cell_queues_unlink():
    """Space on a linked cell queues 'unlink'."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield AgentGrid([_full_row("alpha", linked=True)], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", AgentGrid)
        g.set_scope("global")
        table = app.query_one("#agent-table", DataTable)
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        pending = g.pending_entries()
        first_harness = INTERACTIVE_HARNESSES[0]
        assert pending.get(("global", first_harness, "alpha")) == "unlink"


@pytest.mark.asyncio
async def test_toggle_twice_clears_pending():
    """Toggling the same cell twice returns to empty pending."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield AgentGrid([_full_row("alpha", linked=False)], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", AgentGrid)
        g.set_scope("global")
        table = app.query_one("#agent-table", DataTable)
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        await pilot.press("space")
        assert g.pending_entries() == {}


def test_pending_changed_message_carries_count():
    """PendingChanged(count) stores the count."""
    msg = AgentGrid.PendingChanged(7)
    assert msg.count == 7


@pytest.mark.asyncio
async def test_pending_changed_fires_on_toggle():
    """PendingChanged is posted when a cell is toggled."""
    received: list[int] = []

    class _A(App):
        def compose(self) -> ComposeResult:
            yield AgentGrid([_full_row("alpha")], id="g")

        def on_agent_grid_pending_changed(
            self, event: AgentGrid.PendingChanged
        ) -> None:
            received.append(event.count)

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", AgentGrid)
        g.set_scope("global")
        table = app.query_one("#agent-table", DataTable)
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=1)
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
            yield AgentGrid(
                [
                    _full_row("a", linked=False),
                    _full_row("b", linked=False),
                ],
                id="g",
            )

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", AgentGrid)
        g.set_scope("global")
        table = app.query_one("#agent-table", DataTable)
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("a")
        pending = g.pending_entries()
        first_harness = INTERACTIVE_HARNESSES[0]
        assert pending.get(("global", first_harness, "a")) == "link"
        assert pending.get(("global", first_harness, "b")) == "link"


@pytest.mark.asyncio
async def test_set_scope_clears_pending():
    """set_scope clears any pending entries."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield AgentGrid([_full_row("alpha", linked=False)], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", AgentGrid)
        g.set_scope("global")
        table = app.query_one("#agent-table", DataTable)
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        assert g.pending_entries() != {}
        g.set_scope("project")
        assert g.pending_entries() == {}


# ---------------------------------------------------------------------------
# App-level tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kind_sidebar_lists_three_kinds():
    """The sidebar OptionList must include all four kinds: instruction, skill, pi-extension, agent.

    Updated in #319: instruction is now first in the sidebar (above skill).
    Original assertion "three kinds" updated to four to match the new ordering.
    """
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
        # Instruction must appear first (above skill).
        assert prompts.index("Instruction") < prompts.index("skill")


@pytest.mark.asyncio
async def test_switch_to_agent_shows_agent_grid():
    """Switching to agent kind makes AgentGrid visible, others hidden."""
    from agent_toolkit_tui.app import TUIApp

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_kind("agent")
        await pilot.pause()
        agent_grid = app.query_one("#agent-grid", AgentGrid)
        skill_grid = app.query_one("#skill-grid", SkillGrid)
        pi_grid = app.query_one("#pi-grid", PiGrid)
        assert agent_grid.display is True
        assert skill_grid.display is False
        assert pi_grid.display is False


@pytest.mark.asyncio
async def test_switch_to_agent_then_back_to_skill():
    """Can round-trip skill → agent → skill."""
    from agent_toolkit_tui.app import TUIApp

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_kind("agent")
        await pilot.pause()
        app.action_kind("skill")
        await pilot.pause()
        agent_grid = app.query_one("#agent-grid", AgentGrid)
        skill_grid = app.query_one("#skill-grid", SkillGrid)
        assert skill_grid.display is True
        assert agent_grid.display is False


@pytest.mark.asyncio
async def test_ctrl_s_routes_to_agent_apply_when_active(monkeypatch):
    """ctrl+s dispatches to _apply_agent_pending when agent kind is active."""
    from agent_toolkit_tui.app import TUIApp

    called: list[str] = []

    def fake_apply_agent(self) -> None:  # noqa: ANN001
        called.append("agent")

    def fake_apply_skill(self) -> None:  # noqa: ANN001
        called.append("skill")

    def fake_apply_pi(self) -> None:  # noqa: ANN001
        called.append("pi")

    monkeypatch.setattr(TUIApp, "_apply_agent_pending", fake_apply_agent)
    monkeypatch.setattr(TUIApp, "_apply_skill_pending", fake_apply_skill)
    monkeypatch.setattr(TUIApp, "_apply_pi_pending", fake_apply_pi)

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app._active_kind = "agent"
        await pilot.press("ctrl+s")
        await pilot.pause()

    assert "agent" in called
    assert "skill" not in called
    assert "pi" not in called


@pytest.mark.asyncio
async def test_apply_link_calls_agent_install_apply(monkeypatch):
    """Apply a 'link' pending entry calls agent_install.apply()."""
    from agent_toolkit_tui.app import TUIApp
    import agent_toolkit_cli.agent_install as _ai

    apply_calls: list[Any] = []

    def fake_apply(p, *, home=None, project=None):
        apply_calls.append({"slug": p.slug, "add_agents": p.add_agents, "home": home})
        result = MagicMock()
        result.created = [Path("/fake/dest/my-agent.md")]
        return result

    monkeypatch.setattr(_ai, "apply", fake_apply)

    # Stub out build_agent_rows so refresh doesn't blow up.
    monkeypatch.setattr(
        "agent_toolkit_tui.app.build_agent_rows",
        lambda **kw: [],
    )

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app._active_kind = "agent"
        grid = app.query_one("#agent-grid", AgentGrid)
        grid.set_rows([_full_row("my-agent", linked=False)])
        grid.restore_pending({("global", "claude-code", "my-agent"): "link"})
        await pilot.pause()

        app._apply_agent_pending()
        footer = str(app.query_one("#footer-pending", Static).render())

    assert "applied:" in footer
    assert len(apply_calls) >= 1
    assert apply_calls[0]["slug"] == "my-agent"
    assert "claude-code" in apply_calls[0]["add_agents"]
    # Global scope MUST pass home=Path.home() (not None).
    assert apply_calls[0]["home"] == Path.home()


@pytest.mark.asyncio
async def test_apply_unlink_calls_agent_install_uninstall_directly(monkeypatch):
    """Apply an 'unlink' pending entry calls agent_install.uninstall() DIRECTLY.

    This is the orphan-bug regression guard (#268-class gap):
    apply().removed is ALWAYS EMPTY, so using it would silently orphan
    projected files. The TUI must call agent_install.uninstall() directly.
    """
    from agent_toolkit_tui.app import TUIApp
    import agent_toolkit_cli.agent_install as _ai

    uninstall_calls: list[Any] = []
    apply_calls: list[Any] = []

    def fake_uninstall(*, slug, scope, home=None, project=None, harnesses=()):
        uninstall_calls.append({
            "slug": slug, "scope": scope, "home": home, "harnesses": harnesses,
        })

    def fake_apply(p, *, home=None, project=None):
        apply_calls.append(p)
        result = MagicMock()
        result.created = []
        # result.removed is intentionally empty — the known gap.
        result.removed = []
        return result

    monkeypatch.setattr(_ai, "uninstall", fake_uninstall)
    monkeypatch.setattr(_ai, "apply", fake_apply)
    monkeypatch.setattr(
        "agent_toolkit_tui.app.build_agent_rows",
        lambda **kw: [],
    )

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app._active_kind = "agent"
        grid = app.query_one("#agent-grid", AgentGrid)
        grid.set_rows([_full_row("my-agent", linked=True)])
        grid.restore_pending({("global", "claude-code", "my-agent"): "unlink"})
        await pilot.pause()

        app._apply_agent_pending()
        footer = str(app.query_one("#footer-pending", Static).render())

    # Uninstall MUST have been called directly — not via apply().removed.
    assert uninstall_calls, "agent_install.uninstall() was NOT called — orphan bug!"
    assert uninstall_calls[0]["slug"] == "my-agent"
    assert "claude-code" in uninstall_calls[0]["harnesses"]
    # apply() should NOT have been called (no adds in this pending).
    assert apply_calls == [], "apply() should not be called for unlink-only pending"
    assert "applied:" in footer


@pytest.mark.asyncio
async def test_apply_error_surfaces_notify_and_footer(monkeypatch):
    """InstallError from agent_install.apply must surface via notify + footer."""
    from agent_toolkit_tui.app import TUIApp
    import agent_toolkit_cli.agent_install as _ai
    from agent_toolkit_cli._install_core import InstallError

    notify_calls: list[Any] = []

    def fake_apply_err(p, *, home=None, project=None):
        raise InstallError("conflict at /fake/agents/my-agent.md")

    monkeypatch.setattr(_ai, "apply", fake_apply_err)
    monkeypatch.setattr(
        "agent_toolkit_tui.app.build_agent_rows",
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
        app._active_kind = "agent"
        grid = app.query_one("#agent-grid", AgentGrid)
        grid.set_rows([_full_row("my-agent", linked=False)])
        grid.restore_pending({("global", "claude-code", "my-agent"): "link"})
        await pilot.pause()

        app._apply_agent_pending()
        footer = str(app.query_one("#footer-pending", Static).render())

    assert "apply failed" in footer
    assert notify_calls, "expected notify to be called with error"
    assert notify_calls[-1].get("severity") == "error"


@pytest.mark.asyncio
async def test_apply_project_scope_seeds_canonical(monkeypatch, tmp_path):
    """Project scope apply copies global canonical to project when missing."""
    from agent_toolkit_tui.app import TUIApp
    import agent_toolkit_cli.agent_install as _ai
    import agent_toolkit_cli.agent_paths as _ap
    import shutil as _shutil

    apply_calls: list[Any] = []
    copytree_calls: list[Any] = []

    def fake_apply(p, *, home=None, project=None):
        apply_calls.append({"slug": p.slug, "scope": p.scope})
        result = MagicMock()
        result.created = [tmp_path / "dest" / "my-agent.md"]
        return result

    # Make global canonical exist so copytree has a source.
    global_canonical = tmp_path / "global" / "my-agent"
    global_canonical.mkdir(parents=True)
    (global_canonical / "my-agent.md").write_text("# my-agent")

    def fake_canonical_agent_dir(slug, *, scope, home=None, project=None):
        if scope == "global":
            return global_canonical
        return tmp_path / "project_store" / slug

    def spy_copytree(src, dst, **kw):
        copytree_calls.append((src, dst))
        # Don't actually copy — just create dest dir.
        dst.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(_ai, "apply", fake_apply)
    # Patch at the source module so the local import in _apply_agent_pending picks it up.
    monkeypatch.setattr(_ap, "canonical_agent_dir", fake_canonical_agent_dir)
    # shutil is imported inside _apply_agent_pending; patch at the shutil module level.
    monkeypatch.setattr(_shutil, "copytree", spy_copytree)
    monkeypatch.setattr(
        "agent_toolkit_tui.app.build_agent_rows",
        lambda **kw: [],
    )

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app._active_kind = "agent"
        app._scope = "project"
        grid = app.query_one("#agent-grid", AgentGrid)
        grid.set_scope("project")
        # Row with project-scope cell so toggle is applicable.
        project_row = AgentRow(
            slug="my-agent",
            source="ajanderson1/my-agent",
            ref="main",
            cells={("claude-code", "project"): AgentCell(linked=False)},
        )
        grid.set_rows([project_row])
        grid.restore_pending({("project", "claude-code", "my-agent"): "link"})
        await pilot.pause()

        app._apply_agent_pending()
        footer = str(app.query_one("#footer-pending", Static).render())

    # copytree was called because project canonical was missing.
    assert copytree_calls, "expected shutil.copytree to seed project canonical"
    assert "applied:" in footer
