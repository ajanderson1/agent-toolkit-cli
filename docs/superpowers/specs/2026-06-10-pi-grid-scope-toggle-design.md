# Pi-extensions grid joins the app-wide scope toggle (#349)

**Issue:** [#349](https://github.com/ajanderson1/agent-toolkit-cli/issues/349)
**Tier:** standard
**Follow-up:** [#352](https://github.com/ajanderson1/agent-toolkit-cli/issues/352) — extend pending-preservation to the skill/instruction/agent grids.

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
  clear-on-toggle convention the other grids follow today. PM scope ruling:
  **#349 implements preservation for the pi grid only**; #352 extends the same
  mechanism to the other three grids. Within #349 the pi grid therefore
  diverges (deliberately, temporarily) from the other grids' clear-on-toggle
  behaviour.
- **Apply/diff/footer communication:** *scope-tagged text* — no modal.
- **#321 scroll preservation:** already present in `pi_grid._rebuild`
  (viewport save/restore around `clear()`); survives this change as-is.

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

### 2. Pending preserved across ctrl+g — pi grid only, orchestrated in app.py

`action_scope`'s pi branch wraps the refresh in the save/restore pattern the
apply paths already use:

```python
saved = pi_grid.pending_entries()
pi_grid.set_scope(scope)          # clears (uniform widget contract)
self._refresh_pi_view()           # set_rows clears again
pi_grid.restore_pending(saved)    # puts both scopes' ops back
```

- No new widget API; `restore_pending` already exists on all grids.
- `_refresh_pi_view()` passes scope through to `set_scope` (or the app calls
  it directly, mirroring `_refresh_skill_view`'s shape).
- **Explicit ctrl+r refresh still clears pending** (unchanged semantics).
  Kind-switch clearing is also unchanged (pre-existing, out of scope).
- Staleness note: a restored op whose ground state changed externally between
  toggles renders correctly (glyphs recompute) and Apply already guards
  per-slug (skips slugs missing from the lock; errors per-slug otherwise).

### 3. action_scope becomes kind-aware

The `else: self._refresh_skill_view()` branch is replaced with an explicit
per-kind dispatch (instruction / skill / pi-extension / agent), so ctrl+g on
the pi pane refreshes the pi grid (with the wrap above) and never touches a
hidden grid's pending.

### 4. Scope-tagged text summaries

When pi pending ops span both scopes, the text surfaces attribute them:

- Footer label: `Pending: 4 (3 global, 1 project)` — plain `Pending: N` when
  single-scope or zero.
- ctrl+d diff: `diff: 2 would-link, 1 would-unlink (2 global, 1 project)`.
- Post-apply: `applied: 3 ok, 0 failed (2 global, 1 project)`.

Formatting lives in a small shared helper so #352 can reuse it. Other grids
cannot span scopes until #352, so their output is unchanged in practice.

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

- Extending pending-preservation (and scope-tagged summaries) to the
  skill/instruction/agent grids — **#352**.
- Kind-switch pending semantics (clearing on kind change stays).
- ctrl+r refresh semantics (clearing on explicit refresh stays).
- Any change to `pi_extension_state.py`'s two-scope row model — rows keep
  carrying both scopes' state; only the rendered shape changes.

## Test surface

Headless Textual tests (`tests/tui/`), following the #321 learnings (scroll
tests need an overflowing container, a mid-pane cursor, and a proven-RED
baseline):

1. Pi grid renders 4 columns; the scope column header tracks the active scope
   after ctrl+g.
2. Toggle-queue in global → ctrl+g → ctrl+g round-trip: pending preserved
   (count + keys), glyphs re-render correctly in both directions.
3. Queue ops in both scopes → ctrl+s applies **all** of them; summary line is
   scope-tagged; pending clears on success.
4. Apply failure path: pending **survives** (restore-on-failure parity fix —
   proven RED first: today `_refresh_pi_view`'s `set_rows` clears pending even
   when apply failed).
5. ctrl+r explicitly clears pi pending (semantics unchanged).
6. Kind-aware action_scope: with pi pane active and skill pending queued,
   ctrl+g leaves the skill grid's pending untouched (regression test for the
   stale else-branch).
7. Untracked rows remain non-interactive in the single-column layout.
8. `i` info pane shows the active scope's cell context.

## Affected files

- `src/agent_toolkit_tui/widgets/pi_grid.py` — column layout, `set_scope`,
  toggle/info/glyph re-keying, docstring.
- `src/agent_toolkit_tui/app.py` — `action_scope` kind-aware dispatch + pi
  save/restore wrap, `_refresh_pi_view` scope pass-through, `_show_kind`
  ScopeToggle visibility, scope-tagged summary helper + call sites
  (`_refresh_pending_label`, `action_diff`, `_apply_pi_pending`), pi status
  bar branch.
- `tests/tui/…` — per the test surface above.
- `src/agent_toolkit_tui/pi_extension_state.py` — **unchanged**.
