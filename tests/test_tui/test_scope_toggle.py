"""Unit tests for ScopeToggle — paired-toggle widget for the TUI content header.

These tests exercise the widget in isolation (no app, no runner) to lock its
contract: it composes two labels, exposes set_active(scope), and dispatches
clicks to the app's action_scope action.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Label

from agent_toolkit_tui.app import TUIApp
from agent_toolkit_tui.widgets import ScopeToggle


class _Host(App):
    """Minimal host app so the widget can be mounted in a pilot."""

    def __init__(self) -> None:
        super().__init__()
        self.scope_calls: list[str] = []

    def compose(self) -> ComposeResult:
        yield ScopeToggle(active="project", id="scope-toggle")

    def action_scope(self, scope: str) -> None:
        self.scope_calls.append(scope)


@pytest.mark.asyncio
async def test_scope_toggle_renders_both_labels():
    """ScopeToggle composes one Label per scope value (project, global)."""
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause()
        labels = list(app.query(ScopeToggle).first().query(Label))
        texts = {str(label.render()).strip() for label in labels}
        assert {"project", "global"}.issubset(texts)


@pytest.mark.asyncio
async def test_scope_toggle_set_active_marks_classes():
    """set_active(scope) flips the -active / -inactive classes on each label."""
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause()
        toggle = app.query_one(ScopeToggle)

        toggle.set_active("global")
        await pilot.pause()
        project_label = toggle.query_one("#scope-toggle-project", Label)
        global_label = toggle.query_one("#scope-toggle-global", Label)
        assert "-active" in global_label.classes
        assert "-inactive" in project_label.classes
        assert "-active" not in project_label.classes
        assert "-inactive" not in global_label.classes


@pytest.mark.asyncio
async def test_scope_toggle_click_dispatches_action_scope():
    """Clicking a scope label calls app.action_scope with that scope name."""
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause()
        # Click the inactive ('global') label directly.
        await pilot.click("#scope-toggle-global")
        await pilot.pause()
        assert app.scope_calls == ["global"]


def test_scope_to_roots_project_mode_passes_home():
    """In project scope the TUI must pass Path.home() so build_skill_rows
    can populate (agent, 'global') cells for the indicator (#188)."""
    app = TUIApp()
    app._scope = "project"  # type: ignore[attr-defined]
    scope, home, project = app._scope_to_roots()  # type: ignore[attr-defined]
    assert scope == "project"
    assert home == Path.home(), f"expected Path.home(), got {home!r}"
    assert project == Path.cwd(), f"expected Path.cwd(), got {project!r}"


def test_scope_to_roots_global_mode_unchanged():
    app = TUIApp()
    app._scope = "global"  # type: ignore[attr-defined]
    scope, home, project = app._scope_to_roots()  # type: ignore[attr-defined]
    assert scope == "global"
    assert home == Path.home()
    assert project is None
