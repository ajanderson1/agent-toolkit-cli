"""Unit tests for agent_toolkit_cli.table — render_table + display_width."""
from __future__ import annotations

from agent_toolkit_cli.table import display_width, render_table


# ---------------------------------------------------------------------------
# display_width
# ---------------------------------------------------------------------------


def test_display_width_ascii():
    assert display_width("hello") == 5


def test_display_width_empty():
    assert display_width("") == 0


def test_display_width_checkmark():
    # U+2714 HEAVY CHECK MARK — East_Asian_Width = N (Neutral), counts as 1.
    # The spec described these as "W" but unicodedata reports them as Neutral.
    # They display as 1 column in most terminals; display_width reflects that.
    assert display_width("✔") == 1


def test_display_width_ballot_box():
    # U+2610 BALLOT BOX — East_Asian_Width = N (Neutral), counts as 1.
    assert display_width("☐") == 1


def test_display_width_mixed():
    # "✔ ok" = 1 + 1 + 1 + 1 = 4
    assert display_width("✔ ok") == 4


def test_display_width_genuinely_wide_codepoint():
    # U+4E2D (CJK UNIFIED IDEOGRAPH) is definitively East_Asian_Width = W → 2.
    assert display_width("中") == 2


def test_display_width_fullwidth_codepoint():
    # U+FF21 FULLWIDTH LATIN CAPITAL LETTER A → East_Asian_Width = F → 2.
    assert display_width("Ａ") == 2


# ---------------------------------------------------------------------------
# render_table — basic alignment
# ---------------------------------------------------------------------------


def test_empty_rows_returns_empty_string():
    assert render_table([]) == ""


def test_empty_rows_with_headers_returns_empty_string():
    """No data rows and only a header → empty string (nothing to display)."""
    assert render_table([], headers=["COL1", "COL2"]) == ""


def test_aligns_mixed_width_columns():
    """In the rendered output every row's second column must start at the same offset."""
    rows = [
        ["a", "x"],
        ["longer-slug", "y"],
        ["mid", "z"],
    ]
    rendered = render_table(rows)
    lines = rendered.splitlines()
    assert len(lines) == 3
    # The longest first cell is "longer-slug" (11 chars) + 2-space gutter = 13.
    # So second column starts at offset 13 for every line.
    # Each line: first column padded to max_width, then "  ", then second column.
    max_w = max(len(r[0]) for r in rows)
    for line in lines:
        assert line[max_w : max_w + 2] == "  ", (
            f"expected two-space gutter after column 0 (width {max_w}): {line!r}"
        )


def test_glyph_column_alignment():
    """A glyph column (✔/☐, display-width 1 each) aligns the next column correctly.

    unicodedata.east_asian_width reports ✔ (U+2714) and ☐ (U+2610) as Neutral
    (not Wide), so they have display_width == 1 and len() == 1 — alignment is
    straightforward.  This test verifies the gutter is present and the second
    column content is correct regardless.
    """
    rows = [
        ["✔", "apple"],
        ["☐", "banana"],
        ["✔", "c"],
    ]
    rendered = render_table(rows)
    lines = rendered.splitlines()
    # All first-column cells have the same display width (1), so gutter is right after.
    for line in lines:
        assert "  " in line, f"expected gutter in line: {line!r}"
    # Split on first double-space and confirm second column content is intact.
    second_cols = [line.split("  ", 1)[1] for line in lines]
    assert set(second_cols) == {"apple", "banana", "c"}


def test_genuinely_wide_codepoints_do_not_break_alignment():
    """A column with CJK chars (display-width 2) must align the next column correctly."""
    rows = [
        ["中", "x"],
        ["a", "y"],
    ]
    rendered = render_table(rows)
    lines = rendered.splitlines()
    # "中" has display_width=2, "a" has display_width=1.
    # Col 0 width = 2. "a" gets 1 trailing space, "中" gets 0.
    # Both lines should have "  " gutter after the padded col 0.
    assert "中  x" in lines[0]
    # "a" padded to width 2 → "a " then gutter "  " → "a   y"
    assert "a   y" in lines[1]


def test_header_row_widens_columns():
    """A header longer than any cell forces the column wider; cells align under the header."""
    rows = [
        ["x", "y"],
        ["ab", "cd"],
    ]
    rendered = render_table(rows, headers=["LONGHEADER", "COL"])
    lines = rendered.splitlines()
    # Header line must be first.
    assert lines[0].startswith("LONGHEADER")
    # All lines (including header) must have the same gutter position.
    max_w = len("LONGHEADER")  # widest first-column value
    for line in lines:
        assert line[max_w : max_w + 2] == "  ", (
            f"expected two-space gutter after column 0 (width {max_w}): {line!r}"
        )


def test_no_trailing_whitespace():
    """Last column is not right-padded; no line ends in a space."""
    rows = [
        ["short", "final"],
        ["a-much-longer-slug", "end"],
    ]
    rendered = render_table(rows)
    for line in rendered.splitlines():
        assert not line.endswith(" "), f"trailing whitespace in: {line!r}"


def test_no_trailing_whitespace_with_glyph_first_col():
    """Trailing-space guard holds even when first column has wide glyphs."""
    rows = [
        ["✔", "short"],
        ["☐", "a-longer-last-value"],
    ]
    rendered = render_table(rows)
    for line in rendered.splitlines():
        assert not line.endswith(" "), f"trailing whitespace in: {line!r}"


def test_single_column_no_gutter():
    """A single-column table renders each cell with no trailing space."""
    rows = [["only"], ["cells"]]
    rendered = render_table(rows)
    lines = rendered.splitlines()
    assert lines[0] == "only"
    assert lines[1] == "cells"


def test_header_only_in_result():
    """With headers and one data row, header appears first."""
    rows = [["val1", "val2"]]
    rendered = render_table(rows, headers=["H1", "H2"])
    lines = rendered.splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("H1")
    assert "val1" in lines[1]


def test_returns_newline_joined_string():
    """render_table returns a single string joined by newlines with no trailing newline."""
    rows = [["a", "b"], ["c", "d"]]
    rendered = render_table(rows)
    assert "\n" in rendered
    assert not rendered.endswith("\n")
