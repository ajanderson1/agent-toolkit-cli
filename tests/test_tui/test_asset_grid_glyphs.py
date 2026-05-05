"""Regression tests for asset_grid glyph rendering.

DataTable runs every cell string through Rich's markup parser, so any glyph
containing `[...]` risks being parsed as a style tag and swallowed. These
tests pin the *rendered* output for each glyph so a future edit that
introduces unescaped brackets (or otherwise breaks rendering) fails loudly.
"""
from __future__ import annotations

from rich.text import Text

from agent_toolkit_tui.widgets.asset_grid import (
    _GLYPH,
    _PENDING_LINK,
    _PENDING_UNLINK,
)


def _rendered(markup: str) -> str:
    """Run a glyph string through Rich's markup parser the same way DataTable does."""
    return Text.from_markup(markup).plain


def test_linked_glyph_renders_as_ticked_box():
    assert _rendered(_GLYPH["linked"]) == "☑"


def test_unlinked_glyph_renders_as_empty_box():
    assert _rendered(_GLYPH["unlinked"]) == "☐"


def test_unsupported_glyph_renders_unchanged():
    assert _rendered(_GLYPH["unsupported"]) == "──"


def test_broken_glyph_renders_unchanged():
    assert _rendered(_GLYPH["broken"]) == "⚠ "


def test_pending_link_renders_as_ticked_box():
    """Pending-link wraps the linked glyph in color markup; plain text == glyph."""
    assert _rendered(_PENDING_LINK) == "☑"


def test_pending_unlink_renders_as_empty_box():
    assert _rendered(_PENDING_UNLINK) == "☐"


def test_linked_matches_glyph_renders_as_ticked_box():
    assert _rendered(_GLYPH["linked-matches"]) == "☑"


def test_linked_drifted_glyph_renders_as_tilde_bar():
    assert _rendered(_GLYPH["linked-drifted"]) == "≁"


def test_unlinked_allowlisted_glyph_renders_as_empty_box():
    assert _rendered(_GLYPH["unlinked-allowlisted"]) == "☐"


def test_installed_not_allowlisted_glyph_renders_as_exclamation():
    assert _rendered(_GLYPH["installed-not-allowlisted"]) == "!"


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
    for name, glyph in [("pending_link", _PENDING_LINK), ("pending_unlink", _PENDING_UNLINK)]:
        rendered = _rendered(glyph)
        assert rendered.strip(), (
            f"pending glyph {name!r} ({glyph!r}) renders as whitespace — "
            "Rich is probably parsing it as markup and swallowing it"
        )
