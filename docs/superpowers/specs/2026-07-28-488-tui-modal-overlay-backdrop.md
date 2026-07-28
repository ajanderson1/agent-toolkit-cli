# Spec — #488 TUI modal overlay backdrop

**Issue:** #488 · **Size:** M (fix) · **Date:** 2026-07-28

## Problem

Pressing `i` (or opening any other info / confirm popup) blanks the TUI: the
underlying grid, sidebar, and chrome disappear for the life of the popup. The
user loses the context the popup is explaining.

Root cause: `src/agent_toolkit_tui/css/app.tcss` has a global

```css
Screen {
    background: $surface;
}
```

Textual's CSS type selectors match subclasses, so every `ModalScreen` inherits
this solid `$surface` paint and overrides Textual's default dim backdrop
(`ModalScreen { background: $background 60%; }`). The three named popups —
`CellInfoScreen`, `ColumnInfoModal`, `ConfirmDiscardScreen` — only style their
inner card; the screen itself becomes an opaque plate. `SettingsScreen`
(#480) has the same defect as a free rider of the same rule.

## Goal

True overlay: the grid stays visible under a lightly dimmed backdrop; only the
popup card is opaque.

## Requirements

### R1 — Dim backdrop on every ModalScreen

Every `ModalScreen` subclass in the TUI must resolve to a translucent backdrop
matching Textual's default: `background: $background 60%;` (alpha ≈ 0.6). Not
fully transparent; not solid `$surface`.

### R2 — Main app screen stays solid

The base screen (grid + sidebar + chrome) must keep solid `$surface`. No
visible flash or colour change when a modal opens/closes.

### R3 — Card stays opaque and readable

Inner cards (`Vertical` with `background: $panel`) are unchanged. No content
or binding changes.

### R4 — Scope of named screens

Must apply to at least:

- `CellInfoScreen`
- `ColumnInfoModal`
- `ConfirmDiscardScreen`

A single `ModalScreen` CSS rule also covers `SettingsScreen` — that is
desired, not accidental scope creep.

### R5 — Close restores prior view

Dismiss (Esc / `q` / `i` / Yes|No) returns to the previous screen with no
redraw flash and no lost cursor/scroll. Behaviour is already correct; this
issue must not regress it.

## Non-goals

- Changing modal *content* (covered by #167, #479).
- Theme-specific backdrop colours beyond the `$background 60%` token (theme
  picker from #480 already rebinds `$background`).
- Fully transparent backdrops.
- Per-modal CSS overrides if a single `ModalScreen` rule suffices.

## Design decision (AFK-authorized by PM)

1. Keep `Screen { background: $surface; }` for the solid main surface.
2. Add immediately after it:

   ```css
   ModalScreen {
       background: $background 60%;
   }
   ```

   Textual has no `:not()`; an explicit `ModalScreen` rule reasserts the
   framework default after the broader `Screen` rule. Specificity of a more
   specific type name wins for `ModalScreen` subclasses.

3. No Python changes to the three modal classes.

## Acceptance criteria

- [ ] Opening CellInfo / ColumnInfo / ConfirmDiscard leaves the grid, sidebar,
  and chrome visible under a dim backdrop.
- [ ] Resolved modal backdrop has alpha < 1.0 (≈ 0.6).
- [ ] Base screen backdrop remains opaque (`alpha == 1.0`) before and after.
- [ ] Inner card still renders on `$panel`.
- [ ] Existing dismiss / focus / scroll behaviour unchanged.
- [ ] SettingsScreen also gets the dim backdrop (via the same rule).
