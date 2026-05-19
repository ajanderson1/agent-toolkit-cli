"""Unit tests for the Pi tab Textual widget.

Exercises the `rows()` test surface so we don't have to spin up a full
Textual `App` to assert basic rendering correctness.
"""
from __future__ import annotations

from agent_toolkit_tui.widgets.pi_tab import PiTab


def test_pi_tab_renders_one_row_per_record() -> None:
    records = [
        {
            "slug": "status-bar",
            "origin": "first-party",
            "source": "extension:status-bar",
            "user_loaded": True,
            "project_loaded": False,
            "user_installed_at": "/home/.pi/agent/extensions/status-bar",
            "project_installed_at": None,
            "toolkit_intent": "user",
        },
        {
            "slug": "pi-subagents",
            "origin": "third-party",
            "source": "npm:pi-subagents",
            "user_loaded": True,
            "project_loaded": False,
            "user_installed_at": "/home/.pi/agent/npm/node_modules/pi-subagents",
            "project_installed_at": None,
            "toolkit_intent": "user",
        },
    ]

    tab = PiTab(records=records)
    rows = tab.rows()

    assert len(rows) == 2
    assert any("status-bar" in r and "1P" in r for r in rows)
    assert any("pi-subagents" in r and "3P" in r for r in rows)


def test_pi_tab_empty_state() -> None:
    tab = PiTab(records=[])
    rows = tab.rows()
    assert rows == [] or "no" in rows[0].lower()


def test_pi_tab_user_loaded_glyph() -> None:
    records = [
        {
            "slug": "loaded-user-only",
            "origin": "first-party",
            "source": "extension:loaded-user-only",
            "user_loaded": True,
            "project_loaded": False,
            "toolkit_intent": "user",
        },
    ]
    rows = PiTab(records=records).rows()
    assert "✓" in rows[0]
