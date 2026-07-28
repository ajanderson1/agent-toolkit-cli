# Spec: focus the filter box on asset-type switch

Issue: #477

## Problem

`agent-toolkit-tui` focuses the Skills filter box once, at startup
(`TUIApp.on_mount`, `src/agent_toolkit_tui/app.py:222-224`, added for #249).
Every subsequent asset-type switch — sidebar click, number key `1`–`6`, or any
other caller of `action_asset_type` — swaps the visible grid without touching
focus (`app.py:325-335`).

Consequences:

- Focus remains on `#asset-types-list` (after a sidebar click or number key) or
  on the previous grid's `DataTable` (after a `ctrl+w` → arrow → click path).
- The near-universal next action — type a few characters to narrow the list —
  requires an extra `/` keypress (`action_focus_filter`, `app.py:569-580`).
- Keystrokes typed before that `/` land on the sidebar `OptionList`, where
  digits `1`–`6` are bound to *further* asset-type switches, so an impatient
  user can bounce between tabs instead of filtering.

## Goal

Make "select an asset type" always end with the caret in that asset type's
filter input, using one code path shared with startup.

## Current facts

- `TUIApp.BINDINGS` binds `slash` → `action_focus_filter` and `ctrl+w` →
  `action_focus_sidebar` (`app.py:166-167`).
- `SidebarOptionList.BINDINGS` binds `1`–`6` → `action_asset_type(...)`
  (`app.py:143-153`).
- `on_option_list_option_selected` (`app.py:302-322`) funnels every sidebar
  click into `action_asset_type`.
- `action_asset_type` early-returns when the requested type is already active
  (`app.py:328-329`).
- `action_focus_filter` already owns the complete `AssetType -> filter selector`
  map: `instruction`→`#instruction-filter`, `skill`→`#skill-filter`,
  `command`→`#command-filter`, `pi-extension`→`#pi-filter`,
  `agent`→`#agent-filter`, `mcp`→`#mcp-filter`.
- Every grid yields a `GridFilterInput` immediately before its `DataTable`
  (#458); `GridFilterInput.on_key` hands focus to the table on `Down`/`Tab`
  (`src/agent_toolkit_tui/widgets/filter_input.py`).
- Focusing an `Input` means single-letter grid bindings (`space`, `i`, `a`, and
  the Pi grid's `space`/`i`) are consumed by the input while it holds focus.
  This is **already** the startup condition on the Skills tab, so this change
  does not introduce a new class of behaviour — it makes the existing one
  consistent.

## Requirements

### R1 — Selector map has one owner

The `AssetType -> filter selector` mapping becomes a single module-level
constant (e.g. `_FILTER_SELECTORS`) consumed by both `action_focus_filter` and
the new focus-on-switch path. No second copy of the map.

### R2 — Every asset-type switch focuses that tab's filter

`action_asset_type(<type>)` ends with `self.query_one(<selector>, Input).focus()`
for the newly-active type, for all six types, whichever route triggered it
(sidebar click, number key, or a direct programmatic call).

**Ordering constraint (load-bearing).** Textual will not focus a widget that is
not displayed. Every grid except the active one is `display = False`
(`_show_asset_type`, `app.py:229-300`), so the focus call MUST run **after**
`_show_asset_type(asset_type)`, never before it. Focusing first is a silent
no-op, not an error — which is exactly the failure mode a bare `except` would
hide (see R6).

### R3 — Re-selecting the active tab still focuses the filter

**Decision (agent, recorded for AJ):** re-selecting the already-active asset
type re-focuses its filter box but performs no view refresh.

Rationale: the rule the user learns is "picking a tab puts me in the filter",
with no exception for the tab already shown; and re-focus is idempotent and
cheap, whereas `_refresh_active_view()` is not.

Implementation shape (given R2's ordering constraint) is therefore **two** call
sites, not one hoisted call: focus-then-return on the already-active branch
(that grid is already displayed), and focus as the final statement on the
switch branch (after `_show_asset_type`).

### R4 — Startup uses the same path

`on_mount` no longer hardcodes `#skill-filter`. It sets the active type and
focuses through the shared helper, so startup and switch cannot drift.

### R5 — Focus is non-destructive

The **focus call itself** must not:

- clear or alter the filter text (`grid.set_filter` is not called),
- clear or alter the grid's pending queue (`pending_entries()` unchanged),
- change the grid's scope or cursor coordinate.

Scoping note: this is a property of `_focus_filter`, **not** of a tab switch.
A real switch calls `_refresh_active_view()` → `grid.set_rows()`, which clears
`_pending` **by existing contract** (`app.py:552-556`). That pre-existing
behaviour is out of scope here; tests must assert R5 on the already-active
(early-return) path, where no refresh runs, or they will encode a false
expectation.

### R5a — The escape hatch stays open

Because the caret now lands in an `Input` on every tab switch, the routes back
to the table must work on all six tabs: `Down`, `Tab`, and `Enter` all move
focus to that tab's `DataTable`; `/` returns to the filter; `ctrl+w` returns to
the sidebar.

### R6 — Failure is silent but narrow

If the filter input is absent (a grid mid-mount), the focus attempt is a no-op
and the asset-type switch still completes. Catch `NoMatches` specifically —
not bare `Exception` — so a real error is not swallowed. (`on_mount`'s current
bare `except Exception` at `app.py:223-225` is replaced.)

### R7 — Regression protection

Tests cover all six asset types, the re-select case, the number-key route, the
sidebar-click route, the non-destructive properties in R5, and the R5a escape
hatch.

## Accepted trade-off: the number-key chain

Today, pressing `1` leaves focus on the sidebar, so `2` immediately switches
again. After this change the caret is in the filter, so a second digit is typed
as *text* rather than switching tabs. This is a real regression of the #465
number-key flow and is **accepted**, not overlooked:

- Number keys are an entry point, not a navigation loop — the switch is the
  action, and filtering is the near-universal next step (the premise of #249
  and #458).
- `ctrl+w` returns focus to the sidebar, where the digit chain works exactly as
  before. The escape is one keypress.
- The alternative — binding `1`–`6` at App level with `priority=True` — is
  worse: it would make digits unusable inside every filter box, and asset slugs
  can contain digits (e.g. `n8n`, `s3-sync`).

This trade-off must be stated in the PR body so it is not rediscovered as a
bug.

## Non-goals

- Changing `/` (`action_focus_filter`) behaviour or its binding.
- Changing `ctrl+w` (`action_focus_sidebar`).
- Changing what the filter matches, or adding fuzzy/highlighted search.
- Changing the sidebar's highlight-sync behaviour (#328).
- Auto-clearing the filter text on tab switch (explicitly rejected: filter text
  is per-grid state and users expect it preserved — see #352 for the
  equivalent pending-state precedent).
- Preserving the pending queue across an asset-type switch. `set_rows()` clears
  it by existing contract; changing that is a separate issue (#352 solved the
  *scope*-toggle case only).
- Keeping the `1`–`6` digit chain live after a switch — see the accepted
  trade-off above.

## Open decisions

None. R3 records the one product choice; it is reversible by moving a single
call back below the early return.
