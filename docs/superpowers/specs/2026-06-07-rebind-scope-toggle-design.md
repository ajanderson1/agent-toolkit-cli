# Design — Rebind scope toggle `s` → `ctrl+g` (#320)

**Issue:** #320 · **Type:** fix · **Mode:** `--auto` · **Date:** 2026-06-07

## Problem

On TUI load, focus lands in the skills-section filter `Input` (`app.on_mount`
focuses `#skill-filter`). An `Input` captures every unmodified key as text
entry, so pressing `s` — currently bound to `scope_toggle` via
`Binding("s", "scope_toggle", ...)` at `app.py:126` — just types an `s` into
the filter instead of toggling scope. The toggle is unreachable from its
documented key while the filter has focus (i.e. immediately on open).

## Goal

Move the scope-toggle binding from the unmodified `s` to the `ctrl+g` chord, so
it fires regardless of filter focus (a modifier chord is not swallowed as text
entry). After the change, typing `s` in the filter inserts a literal `s`.

## Change

Single binding edit in `TUIApp.BINDINGS` (`app.py:126`):

```python
-        Binding("s", "scope_toggle", "toggle scope"),
+        Binding("ctrl+g", "scope_toggle", "toggle scope", priority=True),
```

`priority=True` matches the other app-level chord bindings (`ctrl+s`, `ctrl+d`,
`ctrl+r`, `ctrl+z`) so the App handles it even when a focused `Input` is in the
chain — the same mechanism those already rely on. The action
(`action_scope_toggle` → `action_scope`) and the click-driven `ScopeToggle`
widget are unchanged.

## Why `ctrl+g` is safe

`ctrl+g` is not bound anywhere in the TUI (verified: grep of
`src/agent_toolkit_tui/` finds no `ctrl+g`/`"g"` binding). The existing app
chords are `ctrl+s/d/r/z` + `slash` + `i` + `q`; no collision. The scope
toggle is mouse-clickable via the `ScopeToggle` labels regardless, so this only
restores keyboard access.

## Out of scope

Reworking the filter block's general single-char key handling — this change
only moves the one binding. (Stated in the issue.)

## Definition of done (from issue)

- [x] `ctrl+g` toggles scope reliably even when the skills filter block has
  focus on load.
- [x] Typing `s` in the filter block inserts a literal `s` (no longer bound to
  the toggle).

## Verification

- New Pilot test: open the app (focus is in `#skill-filter`), press `s` →
  assert the filter value contains `s` AND scope is unchanged; press `ctrl+g` →
  assert scope toggled.
- Existing `tests/test_tui/test_scope_toggle.py` still green (widget contract
  unchanged).
- Full suite green.
- Headless smoke into `run.log`: assert the binding key is `ctrl+g` and
  `action_scope_toggle` flips `_scope`.
