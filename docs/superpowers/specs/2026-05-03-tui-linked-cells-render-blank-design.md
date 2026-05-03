# Spec — TUI: linked cells render blank because Rich parses `[x]` as markup

**Issue:** #2
**Date:** 2026-05-03
**Severity:** medium — TUI is effectively unusable for batch link/unlink because the user can't see what's currently linked.

## Problem

In `agent_toolkit_tui`, the Skills pane (and any other kind tab) renders only one visible checkbox. `aj-workflow` shows `[ ]` under claude:user — but every other linked skill shows a blank cell where `[x]` should be (45 of 46 skills in the real SSOT). When the user toggles a visually-blank linked cell to queue an unlink, the cell shows `-` (the leading char of the pending-unlink glyph `-  `). The toggle looks broken; same root cause.

## Root cause

`src/agent_toolkit_tui/widgets/asset_grid.py:13-18`:

```python
_GLYPH = {
    "linked":       "[x]",
    "unlinked":     "[ ]",
    "unsupported":  "──",
    "broken":       "⚠ ",
}
```

Textual's `DataTable.add_row` runs cell strings through Rich's markup parser. Rich treats `[x]` as an opening tag for an unknown style and swallows it. `[ ]` survives because the space-after-`[` doesn't match Rich's tag grammar.

Reproducer:

```python
from rich.console import Console
Console().print('linked: [x]')      # prints "linked: " — the [x] is eaten
Console().print('unlinked: [ ]')    # prints "unlinked: [ ]"
```

## Fix

Escape the opening bracket on the `linked` glyph so Rich does not parse it as markup:

```python
_GLYPH = {
    "linked":       r"\[x]",
    "unlinked":     "[ ]",
    "unsupported":  "──",
    "broken":       "⚠ ",
}
```

`Console().print(r'\[x]')` renders `[x]` visibly. Pending overlays `+x ` / `-  ` are unaffected — neither has a leading `[`, so Rich won't parse them.

## Out of scope

- **Refactor to `rich.Text(...)` for cell content** to disable markup parsing entirely. This is the more thorough fix but a larger change. The single-character escape is sufficient to close the bug; the refactor can be filed as a follow-up if/when other glyphs grow brackets.
- Visual styling, colour, alternate glyph sets.

## Acceptance

- [ ] Every user-scope-linked skill shows `[x]` under claude in the Skills pane (45/46 in the real SSOT, instead of 0/46 today).
- [ ] Toggling a linked cell shows the pending `-  ` glyph layered over the now-visible `[x]` baseline.
- [ ] Regression test in `tests/test_tui/` asserts a `linked` cell renders visibly after `_rebuild()` — query the DataTable, assert the rendered content is `[x]` (not empty/whitespace). Cover unlinked too so `[ ]` doesn't regress.

## Verification

- `uv run pytest tests/test_tui/ -q` passes (existing TUI tests + new regression).
- `uv run pytest -q` passes (full suite — no collateral damage).
- Manual: `agent-toolkit-tui --headless --apply` exit codes / `agent-toolkit-tui` interactive smoke check; capture as terminal artifact for PR.
