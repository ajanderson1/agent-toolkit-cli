"""Shared table-rendering helper for CLI list commands.

Exposes:
  render_table(rows, headers=None) -> str
  display_width(s) -> int  (East-Asian-Width-aware)

No runtime dependencies beyond the stdlib — no Rich, no wcwidth.
"""
from __future__ import annotations

import unicodedata


def display_width(s: str) -> int:
    """Return the display (terminal column) width of string *s*.

    East-Asian Wide ("W") and Fullwidth ("F") code points count as 2 columns;
    all other code points count as 1. This keeps columns aligned when cells
    contain genuinely wide glyphs (CJK, fullwidth Latin). Note the status
    glyphs ✔ (U+2714) and ☐ (U+2610) used in pi-extension/agent list report
    East_Asian_Width = N (width 1), so they pad like ordinary characters —
    the wide-path exists for any future width-2 cell content.
    """
    width = 0
    for ch in s:
        eaw = unicodedata.east_asian_width(ch)
        width += 2 if eaw in ("W", "F") else 1
    return width


def render_table(
    rows: list[list[str]],
    headers: list[str] | None = None,
) -> str:
    """Render *rows* as a left-aligned, column-padded plain-text table.

    Args:
        rows: A list of rows; each row is a list of string cells.  All rows
              must have the same number of cells.
        headers: Optional column headers.  When given, the header row appears
                 first and is included when computing per-column widths.

    Returns:
        A single ``\\n``-joined string with no trailing newline.  Returns ``""``
        when *rows* is empty (regardless of *headers*).

    Formatting rules:
    - Per-column width = max display_width across all cells in that column
      (header included when given).
    - Each cell is left-padded to the column width by appending spaces:
      ``pad = col_width - display_width(cell)`` trailing spaces appended.
    - Columns are separated by two spaces (``"  "``).
    - The **last** column is never right-padded (no trailing whitespace).
    """
    if not rows:
        return ""

    n_cols = len(rows[0])

    # Compute per-column max display width.
    col_widths: list[int] = [0] * n_cols
    all_rows = rows if headers is None else [headers, *rows]
    for row in all_rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], display_width(cell))

    def _render_row(row: list[str]) -> str:
        parts: list[str] = []
        for i, cell in enumerate(row):
            if i < n_cols - 1:
                # Pad all but the last column.
                pad = col_widths[i] - display_width(cell)
                parts.append(cell + " " * pad)
            else:
                # Last column: no trailing padding.
                parts.append(cell)
        return "  ".join(parts)

    lines: list[str] = []
    if headers is not None:
        lines.append(_render_row(headers))
    for row in rows:
        lines.append(_render_row(row))

    return "\n".join(lines)
