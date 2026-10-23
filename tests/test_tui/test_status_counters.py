"""Regression tests for TUI status counters (#250).

Two bugs, same status-bar / apply path:

1. Footer "Pending: N" never updated as cells were toggled (the toggle lived
   in the SkillGrid widget and never told the App to refresh).
2. The post-apply summary counted one per skill, not one per (skill × harness)
   write, so 1 skill across 3 harnesses read "applied: 1 ok" instead of 3.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from rich.text import Text
from textual.app import App, ComposeResult
from textual.widgets import Static

import agent_toolkit_cli.skill_install as skill_install
from agent_toolkit_cli.skill_install import InstallResult
from agent_toolkit_tui.app import TUIApp
from agent_toolkit_tui.skill_state import interactive_agents, SkillCell, SkillRow
from agent_toolkit_tui.widgets.skill_grid import SkillGrid

# Paperclip is a project-only, company-scoped harness (#474): it is present in
# interactive_agents() but never toggleable at global scope. These counters are
# about the globally-linkable harness set, so exclude it here.
_GLOBAL_AGENTS: tuple[str, ...] = tuple(
    a for a in interactive_agents() if a != "paperclip"
)


def _row(slug: str, *, scope: str = "global",
         linked: tuple[str, ...] = ()) -> SkillRow:
    cells = {}
    for a in interactive_agents():
        # Mirror real availability: Paperclip is unavailable at global scope.
        available = not (a == "paperclip" and scope == "global")
        cells[(a, scope)] = SkillCell(
            linked=(a in linked), drift=False, skipped=False,
            available=available,
        )
    return SkillRow(
        slug=slug, source=f"x/{slug}", ref="main", state="clean", cells=cells,
    )


class _FooterHost(App):
    """Minimal host mirroring the real app's grid + footer-pending wiring.

    Reuses TUIApp's handler + footer-refresh methods so the test exercises the
    real message contract, not a re-implementation.
    """

    def __init__(self, rows: list[SkillRow]) -> None:
        super().__init__()
        self._rows = rows

    def compose(self) -> ComposeResult:
        yield SkillGrid(self._rows, id="skill-grid")
        yield Static("", id="proj-path")
        yield Static("", id="status-bar")
        yield Static("", id="footer-pending")

    def on_mount(self) -> None:
        self._refresh_proj_path()
        self._refresh_pending_label()
        self._refresh_status_bar()

    # Reuse the real implementations so the wiring under test is the shipped one.
    on_skill_grid_pending_changed = TUIApp.on_skill_grid_pending_changed
    _get_all_pending_edits = TUIApp._get_all_pending_edits
    _refresh_pending_label = TUIApp._refresh_pending_label
    _refresh_status_bar = TUIApp._refresh_status_bar
    _refresh_proj_path = TUIApp._refresh_proj_path
    _build_proj_path_markup = TUIApp._build_proj_path_markup
    _scope_to_roots = TUIApp._scope_to_roots
    _scope = "global"


def _footer_text(app: App) -> str:
    return str(app.query_one("#footer-pending", Static).render())


# ----- Bug 1: live Pending count -------------------------------------------

@pytest.mark.asyncio
async def test_footer_pending_updates_on_toggle_up_and_down():
    app = _FooterHost([_row("j")])
    async with app.run_test() as pilot:
        await pilot.pause()
        assert "Pending:" not in _footer_text(app)
        bar = str(app.query_one("#status-bar", Static).render())
        assert "0 pending" in bar

        grid = app.query_one("#skill-grid", SkillGrid)
        grid.cursor_to_cell(row_slug="j", agent_name="claude-code")
        await pilot.pause()

        await pilot.press("space")
        await pilot.pause()
        assert "Pending:" not in _footer_text(app)
        bar = str(app.query_one("#status-bar", Static).render())
        assert "1 pending" in bar

        # Toggling back must drive it down again.
        await pilot.press("space")
        await pilot.pause()
        assert "Pending:" not in _footer_text(app)
        bar = str(app.query_one("#status-bar", Static).render())
        assert "0 pending" in bar


@pytest.mark.asyncio
async def test_footer_pending_counts_global_harnesses():
    """One skill toggled across all three global harness columns → 3 pending in status bar."""
    app = _FooterHost([_row("j")])
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#skill-grid", SkillGrid)
        for agent in _GLOBAL_AGENTS:
            grid.cursor_to_cell(row_slug="j", agent_name=agent)
            await pilot.pause()
            await pilot.press("space")
            await pilot.pause()
        assert "Pending:" not in _footer_text(app)
        bar = str(app.query_one("#status-bar", Static).render())
        assert "3 pending" in bar


def test_pending_changed_message_carries_count():
    # The count travels with the message so the App can render "Pending: N".
    msg = SkillGrid.PendingChanged(2)
    assert msg.count == 2


# ----- Bug 2: per-harness applied count ------------------------------------

@pytest.mark.asyncio
async def test_apply_counts_per_harness_write(monkeypatch):
    """1 skill × 3 harness links → 'applied: 3 ok, 0 failed'.

    The footer text is read synchronously right after the apply call: the
    apply's clear_pending posts an async PendingChanged that would re-render
    'Pending: 0' on the next event-loop turn (the real TUI shows the summary
    line until the next toggle, which is correct).
    """
    def fake_apply(plan, *, home=None, project=None, env=None):
        # One symlink created per add-agent.
        created = tuple(Path(f"/tmp/{a}") for a in plan.add_agents)
        return InstallResult(
            plan=plan, canonical_path=Path("/tmp/canon"),
            created=created, removed=(), skipped=(), lock_action="unchanged",
        )

    monkeypatch.setattr(skill_install, "apply", fake_apply)

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app._scope = "global"
        grid = app.query_one("#skill-grid", SkillGrid)
        # Queue a global link for the same slug across all three global harnesses.
        pending = {("global", a, "demo"): "link" for a in _GLOBAL_AGENTS}
        grid.restore_pending(pending)
        await pilot.pause()

        app._apply_skill_pending()
        footer = _footer_text(app)  # read before queued messages drain

    assert "applied: 3 ok, 0 failed" in footer


@pytest.mark.asyncio
async def test_apply_failed_count_is_symmetric(monkeypatch):
    """A group that raises contributes its intended write count to failed.

    On the error path the summary is carried by the notify() title
    ("Apply: 0 ok, 3 failed"); the footer shows the collapsed error line.
    """
    titles: list[str] = []

    def fake_apply(plan, *, home=None, project=None, env=None):
        raise skill_install.InstallError("boom")

    monkeypatch.setattr(skill_install, "apply", fake_apply)

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app._scope = "global"
        orig_notify = app.notify

        def spy_notify(*a, **k):
            titles.append(k.get("title", ""))
            return orig_notify(*a, **k)

        monkeypatch.setattr(app, "notify", spy_notify)
        grid = app.query_one("#skill-grid", SkillGrid)
        grid.restore_pending(
            {("global", a, "demo"): "link" for a in _GLOBAL_AGENTS}
        )
        await pilot.pause()

        app._apply_skill_pending()
        footer = _footer_text(app)  # read before queued messages drain

    assert "apply failed" in footer
    assert titles, "expected an error notify with a summary title"
    assert "3 failed" in titles[-1]


@pytest.mark.asyncio
async def test_pi_status_bar_shows_active_scope_only(monkeypatch):
    """Pi status counts library links separately, in the active scope only."""
    from textual.widgets import Static

    from agent_toolkit_tui.app import TUIApp
    from agent_toolkit_tui.pi_extension_state import PiCell, PiExtensionRow

    def _row(slug: str, *, g: bool, p: bool) -> PiExtensionRow:
        cell = PiCell(global_loaded=g, project_loaded=p, origin="store-owned")
        return PiExtensionRow(slug=slug, origin="store-owned",
                              source=f"git@github.com:x/{slug}",
                              global_cell=cell, project_cell=cell)

    monkeypatch.setattr(
        "agent_toolkit_tui.app.build_pi_rows",
        lambda **kwargs: [_row("a", g=True, p=False), _row("b", g=True, p=True)],
    )
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_asset_type("pi-extension")
        await pilot.pause()
        bar = Text.from_markup(str(app.query_one("#status-bar", Static).render())).plain
        # Project scope is active on startup: one library link, no settings refs.
        assert "0 enabled" in bar and "1 linked" in bar and "0 pending" in bar
        assert "global" not in bar

        await pilot.press("ctrl+g")
        await pilot.pause()
        bar = Text.from_markup(str(app.query_one("#status-bar", Static).render())).plain
        assert "0 enabled" in bar and "2 linked" in bar
