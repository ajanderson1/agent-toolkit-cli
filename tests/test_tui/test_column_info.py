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
    # Token stays "universal" (load-bearing bundle key); the display title is
    # "General" after the v3 universal→general rename (#304 bug 3).
    info = get_column_info("universal")
    assert isinstance(info, ColumnInfo)
    assert info.title.lower().startswith("general")
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


def test_state_entry_is_registered():
    assert "state" in COLUMN_INFO


def test_get_column_info_state_returns_columninfo():
    info = get_column_info("state")
    assert isinstance(info, ColumnInfo)
    assert info.title == "State badges"


def test_get_column_info_state_lists_all_five_badges():
    info = get_column_info("state")
    text = "\n".join(info.lines)
    for badge in ("clean", "dirty", "missing", "copy", "library"):
        assert badge in text, f"badge {badge!r} missing from state info"


def test_get_column_info_state_badge_order_matches_state_markup():
    """Order matches _STATE_MARKUP declaration order, with `library` last."""
    info = get_column_info("state")
    bullets = [ln for ln in info.lines if ln.lstrip().startswith("•")]
    badges = [ln.split("—")[0].strip().lstrip("• ").strip() for ln in bullets]
    assert badges == ["clean", "dirty", "missing", "copy", "library"]


def test_universal_info_includes_global_marker_when_context_says_globally_linked():
    """Universal info shows the 🌐 paragraph when the focused row IS globally installed."""
    info = get_column_info("universal", context={"global_linked": True})
    assert info is not None
    joined = "\n".join(info.lines)
    assert "🌐" in joined, f"info missing global marker glyph: {info.lines}"
    assert "global" in joined.lower(), (
        f"info should explain the marker mentions global scope: {info.lines}"
    )


def test_universal_info_omits_global_marker_when_context_says_not_globally_linked():
    """Universal info OMITS the 🌐 paragraph when the focused row is NOT globally installed (#212)."""
    info = get_column_info("universal", context={"global_linked": False})
    assert info is not None
    joined = "\n".join(info.lines)
    assert "🌐" not in joined, (
        f"info should omit 🌐 marker when not globally linked, got: {info.lines}"
    )


def test_universal_info_includes_global_marker_when_no_context():
    """Without context (e.g. legacy callers) the 🌐 paragraph still appears (back-compat)."""
    info = get_column_info("universal")
    assert info is not None
    joined = "\n".join(info.lines)
    assert "🌐" in joined, f"info missing global marker glyph: {info.lines}"
