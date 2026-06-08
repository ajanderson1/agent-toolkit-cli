# Plan — sync sidebar Kind highlight (#328)

Spec: `docs/superpowers/specs/2026-06-08-sync-sidebar-highlight-design.md`

## TDD steps

1. **RED** — Add `tests/test_tui/test_sidebar_highlight_sync.py`:
   - `test_mount_highlights_active_skill_kind`: run the real `TUIApp` via
     `app.run_test()`; assert `OptionList#kinds-list`.highlighted == index of
     `kind-skill` (2). Fails today (highlight is 0 / instruction).
   - `test_action_kind_syncs_highlight`: call `app.action_kind("instruction")`,
     `("pi-extension")`, `("agent")`; assert highlighted tracks each. The
     instruction case fails today only if mount is wrong; assert the full set so
     the test pins the contract for every kind.
   - Resolve indices by option id (`kind-<kind>`) rather than hardcoding, so the
     test survives sidebar reordering.

2. **GREEN** — In `app.py` `_show_kind`, after the display swap, set the
   OptionList highlighted index from the kind. Use the option-id lookup
   (`get_option_index("kind-<kind>")`) so the mapping stays correct if options
   move. Guard with the existing `NoMatches` try/except style.

3. **REFACTOR** — Keep it minimal: one helper or inline map. No behaviour change
   beyond the highlight.

## Files

- `src/agent_toolkit_tui/app.py` — `_show_kind` (the choke point).
- `tests/test_tui/test_sidebar_highlight_sync.py` — new pilot test.

## Verification

- `uv run pytest tests/test_tui/test_sidebar_highlight_sync.py -q` green.
- Full `uv run pytest -q` green (no regression).
- Pre-flight lint (ruff) + full test suite per CI.
