# Spec — TUI Visual Refresh v2: Navigator layout

**Issue:** #43 (reopened)
**Date:** 2026-05-05
**Mode:** `flow --auto`
**Supersedes:** #47 (V3 Dashboard, merged in error — wrong layout)

## Goal

Replace the current V3 Dashboard layout with the **V1 Navigator** layout from `/tmp/atui-mockups/1/`. Sidebar OptionList drives a swappable content pane. No top tabs, no global harness chips. Theme defaults to **gruvbox** (matches `claude_tui_tools`). Display the package version somewhere visible.

## Why

PR #47 shipped the wrong mockup. The user picked V1 (Navigator), not V3 (Dashboard). The merged design also reintroduced "harnesses: claude codex …" chips at the top, which the user explicitly does not want. Theme should match the reference project.

## Reference

| What | Where |
|---|---|
| V1 mockup app | `/tmp/atui-mockups/1/app.py` |
| V1 mockup CSS | `/tmp/atui-mockups/1/app.tcss` |
| Theme constant in reference | `/Users/ajanderson/GitHub/projects/claude_tui_tools/packages/settings/src/claude_tui_settings/app.py` (`DEFAULT_THEME = "gruvbox"`) |
| Current (post-#47) app | `src/agent_toolkit_tui/app.py`, `src/agent_toolkit_tui/css/app.tcss` |
| Current widgets | `src/agent_toolkit_tui/widgets/{kinds_tabs,asset_grid}.py` |

## Layout (V1 Navigator)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  agent-toolkit-tui                                          v0.3.0       │  ← Header
├──────────────┬──────────────────────────────────────────────────────────┤
│ KINDS        │  Skills   ·  47 items                                    │  ← content-header
│ ─────        │  scope: [ project ]  [  user  ]                          │  ← scope-bar
│              │                                                          │
│ Skills   47  │  ┌──────────────────────────────────────────────────┐   │
│ Agents   27  │  │ filter…                                          │   │  ← #grid-filter
│ Commands 89  │  └──────────────────────────────────────────────────┘   │
│ Hooks     3  │  ┌──────────────────────────────────────────────────┐   │
│ Plugins   0  │  │ SKILL          claude codex cursor opencode      │   │  ← #grid-table
│ Pi Ext    1  │  │ aj-workflow    ✔     ☐     ──     ☐              │   │
│              │  │ apk-deep-audit ☐     ☐     ──     ☐              │   │
│              │  │  …                                               │   │
│              │  └──────────────────────────────────────────────────┘   │
├──────────────┴──────────────────────────────────────────────────────────┤
│ Pending: 0   ·   ↑↓ kinds  u/p scope  ⏎ toggle           agent-toolkit  │  ← footer-info (left)
│ ⏎ Apply  ^d Diff  ^r Refresh  ^z Revert  / Filter  q Quit         …    │  ← Footer (Textual)
└─────────────────────────────────────────────────────────────────────────┘
```

**Key differences from current (V3):**
- Top tab strip → vertical OptionList sidebar
- Top breadcrumb with global "harnesses: claude codex …" chips → DROPPED
- Scope chips move into the content pane header (per-pane)
- Status bar (linked / pending / drifted / broken) merges into footer-info or sits just above the Footer

## Requirements

### R1: Navigator layout
- Sidebar `OptionList` lists kinds + counts. Active option drives content pane.
- Content pane swaps based on selected kind (currently only one swap: header text + table columns).
- 1/2/…/6 number-key bindings still select kinds (unchanged from V3 — keep as accelerators).
- The existing `KindChanged` message contract is preserved; the new sidebar widget posts the same message.

### R2: No global harness chips
- The breadcrumb's "harnesses: …" line is removed entirely.
- Per-harness columns in the asset grid table remain.
- Scope chips (`[ project ] [ user ]`) live in the content pane header only.

### R3: Visible version
- Shown in either the `Header` subtitle (`SUB_TITLE`) or the footer-info line.
- Pulled at runtime from `importlib.metadata.version("agent-toolkit")`, with a fallback to `"unknown"` if the package metadata is not installed.
- Formatted as `v<X.Y.Z>` (currently `v0.3.0`).

### R4: Default theme = gruvbox
- `on_mount` sets `self.theme = "gruvbox"` (was `"tokyo-night"`).
- The `t` binding to cycle themes remains untouched (already wired? check existing implementation).

### R5: No data-model / no widget API changes (per issue body)
- `runner.py`, `state.py`, `messages.py`: untouched.
- `AssetGrid` public API (`set_kind`, `set_scope`, `update_state`, `pending_entries`, `clear_pending`): untouched.
- `KindsTabs` is replaced by a new `KindsSidebar` widget (V3-introduced widget gets renamed/replaced — this is internal refactor, not API change).

### R6: Headless mode untouched
- `_parse_args`, `_read_plan`, `--headless` path: byte-for-byte unchanged.
- All Layer-3 bats smoke tests must still pass.

## Out of scope

- Theme switching mechanics beyond the `t` binding (already works per Textual default).
- Adding new kinds, harnesses, columns.
- Refactoring the data model or messages.
- Changing the Apply / Diff / Refresh / Revert behaviour.

## Definition of done

1. App launches with gruvbox palette by default.
2. Sidebar visible on left; tabs gone from top.
3. No "harnesses: …" chips visible anywhere outside the grid columns.
4. Version string `v0.3.0` visible (header subtitle or footer).
5. All existing TUI tests pass; new tests for sidebar + version display added.
6. Before/after screenshots in PR comparing V3 → V1 layout.
7. Headless mode regression: `agent-toolkit-tui --headless --plan -` still works.
8. `t` binding cycles themes (gruvbox → next → …).

## Open questions / decisions captured up front

| Q | Decision |
|---|---|
| Kill `KindsTabs` entirely or keep both? | **Replace.** `KindsTabs` is dead — V3 was wrong. New `KindsSidebar` widget; old file deleted. |
| Where does the version live? | **Header subtitle.** Most visible spot; uses Textual's built-in `SUB_TITLE`. |
| Where does the status bar go? | **Just above Footer**, full-width. Same as V3 but visually integrated into the footer-info row. |
| Filter input position? | **Inside content pane**, between scope-bar and grid-table — same as V1 mockup. |
| Default focus on mount? | **DataTable** (`#grid-table`), not the sidebar's OptionList — `q` must work as a binding. Filter input gets focus only on `/`. |
