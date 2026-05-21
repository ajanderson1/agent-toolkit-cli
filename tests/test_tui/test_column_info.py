"""Tests for the per-column info registry."""
from __future__ import annotations

from agent_toolkit_tui.column_info import (
    COLUMN_INFO,
    ColumnInfo,
    get_column_info,
)


def test_universal_entry_is_registered():
    assert "universal" in COLUMN_INFO


def test_get_column_info_universal_returns_columninfo():
    info = get_column_info("universal")
    assert isinstance(info, ColumnInfo)
    assert info.title.lower().startswith("universal")
    # At least one harness should be listed.
    assert info.lines
    # The description block is the first paragraph above the bullet list.
    assert any(line.startswith("•") or line.startswith("-") or line.strip()
               for line in info.lines)


def test_get_column_info_universal_lists_known_harnesses():
    from agent_toolkit_cli.skill_agents import get_universal_agents
    info = get_column_info("universal")
    text = "\n".join(info.lines)
    for name in get_universal_agents():
        assert name in text, f"universal harness {name!r} missing from info"


def test_get_column_info_unknown_returns_none():
    assert get_column_info("does-not-exist") is None


def test_get_column_info_is_recomputed_each_call():
    """Registry stores a factory, so a later catalog change is reflected."""
    info_a = get_column_info("universal")
    info_b = get_column_info("universal")
    # Distinct objects (factory called twice), but equal content.
    assert info_a is not info_b
    assert info_a.title == info_b.title
    assert info_a.lines == info_b.lines
