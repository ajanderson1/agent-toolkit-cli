"""Regression tests for asset_grid glyph rendering.

The bug we guard against: Rich's markup parser (run by Textual's DataTable on
every cell string) treats `[x]` as an unknown style tag and swallows it,
leaving linked cells visually blank. The fix escapes the leading bracket on
the `linked` glyph (`r"\\[x]"`) so the rendered output is the literal `[x]`.

These tests pin the *rendered* glyph for `linked` and `unlinked` so a future
edit that drops the escape — or grows brackets on another glyph — fails loudly.
"""
from __future__ import annotations

from rich.text import Text

from agent_toolkit_tui.widgets.asset_grid import _GLYPH


def _rendered(markup: str) -> str:
    """Run a glyph string through Rich's markup parser the same way DataTable does."""
    return Text.from_markup(markup).plain


def test_linked_glyph_renders_as_visible_x():
    assert _rendered(_GLYPH["linked"]) == "[x]"


def test_unlinked_glyph_renders_as_visible_empty_box():
    assert _rendered(_GLYPH["unlinked"]) == "[ ]"


def test_unsupported_glyph_renders_unchanged():
    assert _rendered(_GLYPH["unsupported"]) == "──"


def test_broken_glyph_renders_unchanged():
    assert _rendered(_GLYPH["broken"]) == "⚠ "


def test_no_glyph_silently_collapses_to_empty():
    """Smoke-test: any glyph that round-trips to empty under Rich is broken.

    Catches future regressions where a new glyph (or a careless edit) reintroduces
    the original bug — e.g. someone adds `"locked": "[lock]"` and Rich eats it.
    """
    for status, glyph in _GLYPH.items():
        rendered = _rendered(glyph)
        assert rendered.strip(), (
            f"glyph for status={status!r} ({glyph!r}) renders as whitespace — "
            "Rich is probably parsing it as markup and swallowing it"
        )
