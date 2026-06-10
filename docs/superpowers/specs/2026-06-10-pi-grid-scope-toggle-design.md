# Pi-extensions grid joins the app-wide scope toggle (#349)

**Issue:** [#349](https://github.com/ajanderson1/agent-toolkit-cli/issues/349)
**Tier:** standard
**Note:** follow-up #352 (app-wide pending preservation) was filed under an
earlier PM scope ruling, then closed as superseded — the PM's corrected ruling
admits app-wide preservation into #349 because it is a single app-side
mechanism, not per-grid logic.

## Problem

The pi-extensions grid is the only TUI pane that renders global and project
scope as two side-by-side columns (`EXTENSION | Pi (global) | Pi (project) |
Origin | Source`) and ignores the app-wide **ctrl+g** scope toggle (#320).
Every other pane shows one scope at a time and flips with the rest of the app.
Two concrete defects fall out of the special-casing:

1. **Inconsistent UX** — pi is the only pane where scope is a column choice,
   not the app-wide toggle.
2. **`action_scope` stale else-branch** (`app.py:371-386`) — pressing ctrl+g
   while the pi pane is active falls into `else: self._refresh_skill_view()`,
   refreshing the *hidden* skill grid and silently clearing its pending ops.

## Decision history (brainstorm, 2026-06-10)

- **Pending across the toggle:** AJ chose *preserve app-wide* over the
  clear-on-toggle convention the grids follow today. PM ruling (corrected):
  app-wide preservation is in #349 **provided it stays one app-side
  save/restore site around the scope toggle** — no per-grid preservation
  logic. (It does: see Design §2.) Fallback if that constraint ever breaks:
  pi-only + follow-up issue.
- **Apply/diff/footer communication:** *scope-tagged text* — no modal.
- **#321 scroll preservation:** already present in `pi_grid._rebuild`
  (viewport save/restore around `clear()`); survives this change as-is.
- **Out of #349:** #351 (matrix restructure) is separate; keep the diff
  focused.

## Design

### 1. PiGrid becomes single-column, scope-following

- Columns: `EXTENSION ⓘ | Pi (<scope>) ⓘ | Origin | Source` (4, was 5). The
  scope column header reflects the active scope, e.g. `Pi (global) ⓘ`.
- `PiGrid` gains `set_scope(scope: Literal["global", "project"])` with the
  same contract as the other grids: sets `self._scope`, clears `_pending`.
  (Uniform widget semantics; preservation is the app's job, below.)
- `_toggle_at`, `action_info`, `_cell_glyph`, and the cursor-column clamp
  re-key off `self._scope` instead of `_COL_GLOBAL` / `_COL_PROJECT`. The
  pending key stays `(scope, slug)`. Untracked rows stay non-interactive.
- The #321 viewport save/restore in `_rebuild` is untouched; only the
  `max_col` clamp changes for the 4-column layout.
- **Cursor snap on scope change:** `set_scope` moves the cursor to the scope
  column (same row). Without this, a cursor on the removed project column
  (old index 2) silently lands on non-interactive Origin after the toggle
  and the user's next `space` is a no-op.

### 2. Pending preserved across ctrl+g — ONE app-side site, all four grids

`action_scope` wraps the (now kind-aware) refresh of the **active** grid in
the save/restore pattern the apply paths already use:

```python
grid = self._active_grid()           # the visible grid widget, by kind
saved = grid.pending_entries()
self._refresh_active_view()          # set_scope + set_rows clear (unchanged)
grid.restore_pending(saved)          # both scopes' ops come back
```

- **Single mechanism, zero per-grid logic.** `pending_entries()` /
  `restore_pending()` are a uniform API on all four grids; key shapes differ
  ((scope, slug) vs (scope, harness, slug)) but each grid round-trips its own
  dict, so the app never inspects keys here.
- Widget clearing semantics (`set_scope` / `set_rows`) stay exactly as they
  are — uniformity preserved at the widget layer.
- **Explicit ctrl+r refresh still clears pending** (unchanged semantics).
  Kind-switch clearing is also unchanged (pre-existing, out of scope).
- **ctrl+z revert clears BOTH scopes' ops in the active grid** — today's
  whole-dict `clear_pending()` semantics made explicit. Because the cleared
  set can now include invisible other-scope ops, the revert message is
  scope-tagged (§4) so the user sees what was destroyed.
- Hidden grids are untouched by the toggle (their refresh happens on kind
  switch, as today).
- The apply paths already group by scope from the pending key (all four), so
  multi-scope apply works without engine changes.
- Staleness note: a restored op whose ground state changed externally between
  toggles renders correctly (glyphs recompute) and Apply already guards
  per-slug (skips slugs missing from the lock; errors per-slug otherwise).

### 3. action_scope becomes kind-aware

The `else: self._refresh_skill_view()` branch is replaced with an explicit
per-kind dispatch (instruction / skill / pi-extension / agent) — small
`_active_grid()` / `_refresh_active_view()` helpers shared with the existing
dispatch sites (`action_refresh` already has this shape). ctrl+g on the pi
pane refreshes the pi grid and never touches a hidden grid's pending.

### 4. Scope-tagged text summaries

A single module-level helper computes the tag from any pending dict (scope is
`key[0]` in every grid's key shape):

```python
def _scope_tag(keys: Iterable[tuple[str, ...]]) -> str:
    """Return ' (a global, b project)' when ops span scopes, else ''."""
```

Applied at:

- Footer label (`_refresh_pending_label`, already sums all grids):
  `Pending: 4 (3 global, 1 project)` — plain `Pending: N` when single-scope.
- ctrl+d diff (`action_diff`): `diff: 2 would-link, 1 would-unlink (2 global,
  1 project)`.
- All four post-apply summaries: `applied: 3 ok, 0 failed (2 global,
  1 project)` — multi-scope pending is now reachable in every grid, so every
  apply path gets the tag.
- ctrl+z revert (`action_revert`, all four branches): `reverted: 4 pending
  cleared (3 global, 1 project)` — the one destructive surface that can
  consume invisible other-scope ops, so the tag matters most here.

### 5. Consistency fixes that fall out

- `_show_kind`: ScopeToggle becomes visible for the pi-extension kind
  (`scope_toggle.display = True`).
- Pi status bar: shows active-scope loaded count + pending (matching the
  other panes) instead of `N global · M project`.
- **Apply-failure restore parity (latent bug):** `_apply_pi_pending` skips
  `clear_pending()` on failure but then calls `_refresh_pi_view()`, whose
  `set_rows` clears pending anyway — failed ops are silently lost today. The
  other three apply paths wrap the refresh in `saved = pending_entries()` /
  `restore_pending(saved)`; the pi path adopts the same wrap.
- `pi_grid.py` module docstring: the "Both scope columns are always visible —
  no scope toggle" rationale is rewritten.

## Out of scope

- #351 (matrix restructure).
- Kind-switch pending semantics (clearing on kind change stays).
- ctrl+r refresh semantics (clearing on explicit refresh stays).
- Any change to `pi_extension_state.py`'s two-scope row model — rows keep
  carrying both scopes' state; only the rendered shape changes.
- A pre-apply confirmation modal (rejected in brainstorm; scope-tagged text
  chosen).

## Test surface

Headless Textual tests (`tests/test_tui/`), following the #321 learnings (scroll
tests need an overflowing container, a mid-pane cursor, and a proven-RED
baseline):

1. Pi grid renders 4 columns; the scope column header tracks the active scope
   after ctrl+g.
2. Toggle-queue in global → ctrl+g → ctrl+g round-trip: pending preserved
   (count + keys), glyphs re-render correctly in both directions — asserted
   for the pi grid AND one harness-keyed grid (skill) to prove the single
   app-side mechanism covers both key shapes.
3. Queue pi ops in both scopes → ctrl+s applies **all** of them; summary line
   is scope-tagged; pending clears on success.
4. Apply failure path: pending **survives** (restore-on-failure parity fix —
   proven RED first: today `_refresh_pi_view`'s `set_rows` clears pending even
   when apply failed).
5. ctrl+r explicitly clears pending (semantics unchanged) — pi + skill.
6. Kind-aware action_scope: with pi pane active and skill pending queued,
   ctrl+g leaves the skill grid's pending untouched (regression test for the
   stale else-branch).
7. Untracked rows remain non-interactive in the single-column layout.
8. `i` info pane shows the active scope's cell context.
9. `_scope_tag` unit tests: empty, single-scope, spanning.
10. ctrl+z revert with both-scope pending: clears all of the active grid's
    ops and the message is scope-tagged.
11. Round-trip and tag assertions are falsifiable: the round-trip test
    asserts the rendered pending glyph (not just dict state), and apply/diff
    tag tests use multi-scope pending (single-scope yields an empty tag, so
    only a spanning fixture can catch a missing tag).

## Affected files

- `src/agent_toolkit_tui/widgets/pi_grid.py` — column layout, `set_scope`,
  toggle/info/glyph re-keying, docstring.
- `src/agent_toolkit_tui/app.py` — `action_scope` kind-aware dispatch +
  single save/restore wrap, `_active_grid()` / `_refresh_active_view()`
  helpers, `_refresh_pi_view` scope pass-through, `_show_kind` ScopeToggle
  visibility, `_scope_tag` helper + call sites (`_refresh_pending_label`,
  `action_diff`, all four `_apply_*_pending`, all four `action_revert`
  branches), pi status bar branch, pi apply-failure restore parity.
- `tests/test_tui/…` — per the test surface above.
- `src/agent_toolkit_tui/pi_extension_state.py` — **unchanged**.
- Other grid widgets — **unchanged** (the whole point of the single app-side
  mechanism).
