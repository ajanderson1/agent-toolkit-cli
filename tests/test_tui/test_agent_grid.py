"""Pilot tests for the AgentGrid widget and the agent TUI flow.

Covers (8 widget-level + 8 app-level = 16 tests):

Widget-level:
1. columns renders correctly (Agent + Standard (N) + INTERACTIVE_HARNESSES + Source)
2. row count
3. toggle unlinked cell queues 'link'
4. toggle linked cell queues 'unlink'
5. toggle twice clears pending
6. PendingChanged message carries count
7. toggle_column (action_a) queues all in column
8. set_scope clears pending

App-level:
9.  sidebar lists 3 asset types (skill / pi-extension / agent)
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
from types import SimpleNamespace
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


def _linked_row(slug: str, *, harness: str = INTERACTIVE_HARNESSES[0]) -> AgentRow:
    """Row with exactly one harness linked at global scope."""
    return AgentRow(
        slug=slug,
        source=f"ajanderson1/{slug}",
        ref="main",
        cells={(harness, "global"): AgentCell(linked=True)},
    )


def _unlinked_row(slug: str, *, harness: str = INTERACTIVE_HARNESSES[0]) -> AgentRow:
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
    """Grid must show Agent plus INTERACTIVE_HARNESSES plus Source."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield AgentGrid([_full_row("alpha")], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#agent-table", DataTable)
        labels = [str(c.label) for c in table.columns.values()]
        # Slug + N harness cols + State + Source = 3 + N  (#360: State column added)
        assert len(labels) == len(INTERACTIVE_HARNESSES) + 3
        assert "Agent ⓘ" in labels
        assert not any("AGENT" in lbl for lbl in labels)
        assert any(label.startswith("Standard (") for label in labels)
        assert any("State" in lbl for lbl in labels)
        assert any("Source" in lbl for lbl in labels)
        assert not any("Claude Code" in label for label in labels)
        assert not any("Gemini CLI" in label for label in labels)
        assert any("Pi ⓘ" == label for label in labels)


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

@pytest.mark.asyncio
async def test_agent_cell_info_uses_harness_display_name():
    from textual.coordinate import Coordinate

    from agent_toolkit_tui.screens.cell_info import CellInfoScreen

    class _A(App):
        def compose(self) -> ComposeResult:
            yield AgentGrid([_full_row("alpha", linked=False)], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#agent-table", DataTable)
        pi_col = 1 + INTERACTIVE_HARNESSES.index("pi")
        table.cursor_coordinate = Coordinate(row=0, column=pi_col)
        table.focus()
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        assert isinstance(app.screen, CellInfoScreen)
        assert "Pi @ global" in app.screen._title
        assert "into Pi @ global" in app.screen._body_markup


# ---------------------------------------------------------------------------
# App-level tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_asset_type_sidebar_lists_three_asset_types():
    """The sidebar OptionList must include plural asset labels."""
    from agent_toolkit_tui.app import TUIApp

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        ol = app.query_one("#asset-types-list", OptionList)
        prompts = [str(ol.get_option_at_index(i).prompt) for i in range(ol.option_count)]
        assert any("Skills" in p for p in prompts)
        assert any("Pi Extensions" in p for p in prompts)
        assert any("Agents" in p for p in prompts)


@pytest.mark.asyncio
async def test_switch_to_agent_shows_agent_grid():
    """Switching to agent asset type makes AgentGrid visible, others hidden."""
    from agent_toolkit_tui.app import TUIApp

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_asset_type("agent")
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
        app.action_asset_type("agent")
        await pilot.pause()
        app.action_asset_type("skill")
        await pilot.pause()
        agent_grid = app.query_one("#agent-grid", AgentGrid)
        skill_grid = app.query_one("#skill-grid", SkillGrid)
        assert skill_grid.display is True
        assert agent_grid.display is False


@pytest.mark.asyncio
async def test_ctrl_s_routes_to_agent_apply_when_active(monkeypatch):
    """ctrl+s dispatches to _apply_agent_pending when agent asset type is active."""
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
        app._active_asset_type = "agent"
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
        app._active_asset_type = "agent"
        grid = app.query_one("#agent-grid", AgentGrid)
        grid.set_rows([_full_row("my-agent", linked=False)])
        grid.restore_pending({("global", "standard", "my-agent"): "link"})
        await pilot.pause()

        app._apply_agent_pending()
        footer = str(app.query_one("#footer-pending", Static).render())

    assert "applied:" in footer
    assert len(apply_calls) >= 1
    assert apply_calls[0]["slug"] == "my-agent"
    assert "standard" in apply_calls[0]["add_agents"]
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
        app._active_asset_type = "agent"
        grid = app.query_one("#agent-grid", AgentGrid)
        grid.set_rows([_full_row("my-agent", linked=True)])
        grid.restore_pending({("global", "standard", "my-agent"): "unlink"})
        await pilot.pause()

        app._apply_agent_pending()
        footer = str(app.query_one("#footer-pending", Static).render())

    # Uninstall MUST have been called directly — not via apply().removed.
    assert uninstall_calls, "agent_install.uninstall() was NOT called — orphan bug!"
    assert uninstall_calls[0]["slug"] == "my-agent"
    assert "standard" in uninstall_calls[0]["harnesses"]
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
        app._active_asset_type = "agent"
        grid = app.query_one("#agent-grid", AgentGrid)
        grid.set_rows([_full_row("my-agent", linked=False)])
        grid.restore_pending({("global", "standard", "my-agent"): "link"})
        await pilot.pause()

        app._apply_agent_pending()
        footer = str(app.query_one("#footer-pending", Static).render())

    assert "apply failed" in footer
    assert notify_calls, "expected notify to be called with error"
    assert notify_calls[-1].get("severity") == "error"


@pytest.mark.asyncio
async def test_apply_error_names_slug_exactly_once(monkeypatch, tmp_path):
    """#373 (PM review F1): the facade seam already prefixes the slug onto
    InstallError; the TUI must NOT prefix it again. Drives the REAL
    agent_install.apply (no mock) over a non-UTF8 canonical — gemini-cli's
    read raises InstallError, the seam tags it `my-agent: ...`, and the
    surfaced footer/notify must contain the slug EXACTLY ONCE."""
    from agent_toolkit_cli.agent_lock import (
        LockEntry, add_entry, read_lock, write_lock,
    )
    from agent_toolkit_cli.agent_paths import canonical_agent_dir, library_lock_path
    from agent_toolkit_tui.app import TUIApp

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

    # Real global canonical + lock entry, but the content file is non-UTF8 →
    # gemini-cli's read_text raises (the Task 1 fix → InstallError).
    canonical = canonical_agent_dir("my-agent", scope="global")
    canonical.mkdir(parents=True)
    (canonical / "my-agent.md").write_bytes(b"\xff\xfe not valid utf8")
    lock_path = library_lock_path()
    write_lock(lock_path, add_entry(
        read_lock(lock_path), "my-agent",
        LockEntry(
            source="https://github.com/test/my-agent",
            source_type="github", agent_path="my-agent.md",
        ),
    ))

    notify_calls: list[Any] = []

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        orig_notify = app.notify

        def spy_notify(*a, **k):
            notify_calls.append((a, k))
            return orig_notify(*a, **k)

        monkeypatch.setattr(app, "notify", spy_notify)
        app._active_asset_type = "agent"
        app._scope = "global"
        grid = app.query_one("#agent-grid", AgentGrid)
        grid.set_rows([_full_row("my-agent", linked=False)])
        grid.restore_pending({("global", "gemini-cli", "my-agent"): "link"})
        await pilot.pause()

        app._apply_agent_pending()
        await pilot.pause()
        footer = str(app.query_one("#footer-pending", Static).render())

    # The error surfaced...
    assert "apply failed" in footer
    err_msgs = [a[0] for (a, k) in notify_calls if k.get("severity") == "error"]
    assert err_msgs, f"expected an error notification, got {notify_calls!r}"
    # ...and the slug appears EXACTLY ONCE (not "my-agent: my-agent: ...").
    assert err_msgs[-1].count("my-agent") == 1, (
        f"slug duplicated in TUI error message: {err_msgs[-1]!r}"
    )


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
        app._active_asset_type = "agent"
        app._scope = "project"
        grid = app.query_one("#agent-grid", AgentGrid)
        grid.set_scope("project")
        # Row with project-scope cell so toggle is applicable.
        project_row = AgentRow(
            slug="my-agent",
            source="ajanderson1/my-agent",
            ref="main",
            cells={("standard", "project"): AgentCell(linked=False)},
        )
        grid.set_rows([project_row])
        grid.restore_pending({("project", "standard", "my-agent"): "link"})
        await pilot.pause()

        app._apply_agent_pending()
        footer = str(app.query_one("#footer-pending", Static).render())

    # copytree was called because project canonical was missing.
    assert copytree_calls, "expected shutil.copytree to seed project canonical"
    assert "applied:" in footer


@pytest.mark.asyncio
async def test_apply_unlink_refusal_surfaces_warning_and_cell_stays_linked(
    monkeypatch, tmp_path,
):
    """F5 pin (PM adversarial review): unlinking over a sentinel-less,
    content-DIVERGENT slot file makes the standard adapter refuse (leave the
    user's file in place). The TUI must NOT swallow that: a warning
    notification fires, the file is intact, and the re-scanned cell still
    shows linked (truthful grid state).

    Exercises the REAL agent_install.uninstall() + standard adapter — no
    mocks on the uninstall path.
    """
    from agent_toolkit_cli.agent_adapters import _sentinel_path
    from agent_toolkit_cli.agent_lock import (
        LockEntry, add_entry, read_lock, write_lock,
    )
    from agent_toolkit_cli.agent_paths import canonical_agent_dir, library_lock_path
    from agent_toolkit_tui.app import TUIApp

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

    # Real global canonical + lock entry (so the row exists in the grid).
    canonical = canonical_agent_dir("my-agent", scope="global")
    canonical.mkdir(parents=True)
    (canonical / "my-agent.md").write_text("---\nname: my-agent\n---\ncanonical\n")
    lock_path = library_lock_path()
    write_lock(lock_path, add_entry(
        read_lock(lock_path), "my-agent",
        LockEntry(
            source="https://github.com/test/my-agent",
            source_type="github", agent_path="my-agent.md",
        ),
    ))
    # The slot holds a sentinel-less file whose content DIVERGES from the
    # canonical — by the ownership contract it is the user's file.
    slot = tmp_path / ".claude" / "agents" / "my-agent.md"
    slot.parent.mkdir(parents=True)
    slot.write_text("user's own hand-authored agent\n")
    assert not _sentinel_path(slot).exists()

    notify_calls: list[Any] = []

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        orig_notify = app.notify

        def spy_notify(*a, **k):
            notify_calls.append((a, k))
            return orig_notify(*a, **k)

        monkeypatch.setattr(app, "notify", spy_notify)
        app._active_asset_type = "agent"
        app._scope = "global"
        app._refresh_agent_view()
        grid = app.query_one("#agent-grid", AgentGrid)
        await pilot.pause()
        # Sanity: the real scan sees the slot file as linked.
        row = next(r for r in grid._rows if r.slug == "my-agent")
        assert row.cells[("standard", "global")].linked

        grid.restore_pending({("global", "standard", "my-agent"): "unlink"})
        await pilot.pause()
        app._apply_agent_pending()
        await pilot.pause()

        # The refusal surfaced as a WARNING notification.
        warnings = [k for (a, k) in notify_calls if k.get("severity") == "warning"]
        assert warnings, f"expected a warning notification, got {notify_calls!r}"
        # The user's file is intact.
        assert slot.read_text() == "user's own hand-authored agent\n"
        # The re-scanned cell still shows linked — the grid stays truthful.
        row = next(r for r in grid._rows if r.slug == "my-agent")
        assert row.cells[("standard", "global")].linked


@pytest.mark.asyncio
async def test_state_column_rendered():
    """#360: agent grid renders a State column between harnesses and Source."""
    from textual.widgets import DataTable

    row = _linked_row("reviewer")
    row.state = "unlisted"

    class _A(App):
        def compose(self) -> ComposeResult:
            yield AgentGrid([row], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one(DataTable)
        labels = [str(c.label) for c in table.columns.values()]
        assert any("State" in lbl for lbl in labels)
        # State column sits immediately before Source.
        state_i = next(i for i, lbl in enumerate(labels) if "State" in lbl)
        source_i = next(i for i, lbl in enumerate(labels) if "Source" in lbl)
        assert source_i == state_i + 1


@pytest.mark.asyncio
async def test_agent_grid_resize_gives_source_remaining_width():
    """Resize shrinks Source column to remaining width instead of fixed 30."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield AgentGrid([_full_row("alpha")], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", AgentGrid)
        table = app.query_one("#agent-table", DataTable)

        g.on_resize(SimpleNamespace(size=SimpleNamespace(width=120)))

        source_column = list(table.columns.values())[-1]
        assert source_column.width == 32
