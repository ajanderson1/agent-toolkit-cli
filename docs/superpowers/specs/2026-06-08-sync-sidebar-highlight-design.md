# Spec — sync sidebar Kind highlight to the active kind (#328)

**Mode:** `--ship-it` · **Type:** fix · **Issue:** #328

## Problem

The TUI Kind sidebar (`OptionList#kinds-list`) highlight does not track the grid
shown in the main pane.

- On mount, `on_mount` calls `_show_kind("skill")` and renders the `SkillGrid`
  (`app.py:168`). The main pane shows **skill**.
- But the sidebar `OptionList` is never told which option is active, so its
  highlight defaults to the first option — `instruction` (`app.py:142-148`).
- Result: pane shows **skill**, sidebar highlights **instruction**. They diverge.

The same divergence can occur whenever the active kind changes by a path other
than clicking the sidebar option directly (e.g. via `action_kind`), because
nothing sets the OptionList's highlighted index from the active kind.

## Goal

The sidebar highlight **always** reflects the kind shown in the main pane —
on mount and after every kind change — not just the last clicked option.

## Approach

Sync the highlight inside `_show_kind`, the single choke point that both
`on_mount` and `action_kind` already call to swap the visible grid. Map the
active kind to its option index in the OptionList, accounting for the disabled
separator at index 1:

| kind          | option index |
|---------------|--------------|
| instruction   | 0            |
| skill         | 2            |
| pi-extension  | 3            |
| agent         | 4            |

Set `OptionList.highlighted` to that index. Centralising it in `_show_kind`
means any current or future caller that swaps the grid keeps the sidebar in
lock-step automatically — satisfying "track the displayed grid, not just the
last clicked option".

## Non-goals

- No change to which grid is shown, scope handling, or refresh logic.
- No new keybindings or sidebar options.

## Acceptance

1. On mount, the OptionList's highlighted option is `skill` (index 2), matching
   the rendered `SkillGrid`.
2. After `action_kind("instruction" | "pi-extension" | "agent")`, the
   highlighted option matches the now-active kind.
3. Existing TUI behaviour (grid swap, scope toggle visibility, refresh) is
   unchanged.

## Verification

CLI binary smoke (`agent-toolkit-tui --version` / package import) plus a pilot
test driving the real `TUIApp` via `App.run_test()` asserting
`OptionList.highlighted` on mount and after `action_kind`.
