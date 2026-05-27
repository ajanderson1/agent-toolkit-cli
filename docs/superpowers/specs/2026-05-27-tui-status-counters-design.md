# Spec — Fix TUI status counters (#250)

`type:fix` · TUI status bar / apply path · display-and-counting only.

## Problem

Two related counter bugs in `src/agent_toolkit_tui/app.py`:

1. **Footer `Pending: N` is stale.** `_refresh_pending_label()` computes the
   right number (`len(grid.pending_entries())`), but it is only called from
   `on_mount`, `action_apply`, `action_refresh`, and `action_revert`. Toggling
   a cell with `space` is handled inside `SkillGrid.action_toggle_cell` /
   `action_toggle_column` (both `priority=True` bindings on the widget), which
   mutate `_pending` but never tell the `App` to refresh the footer. So the
   footer keeps reading `Pending: 0` no matter how many cells the user toggles.

2. **Apply summary undercounts.** `_apply_skill_pending()` groups pending
   entries by `(scope, slug)` and increments `ok`/`failed` **once per group**
   (one `engine_apply` call per skill). One skill toggled across three harnesses
   is a single group → `applied: 1 ok` instead of `applied: 3 ok`. The count
   must be per `(skill × harness)` write.

## Approach

Display/counting only. No change to how toggles or applies mutate skills.

### Bug 1 — live Pending count

Make the grid notify the app whenever `_pending` changes, and have the app
refresh the footer in response.

- `SkillGrid` posts a custom `SkillGrid.PendingChanged` message (carrying the
  current pending count) after every mutation of `_pending`: `_toggle_at`,
  `action_toggle_column`, `clear_pending`, `restore_pending`, `set_rows`,
  `set_scope`. Posting from the widget keeps the App as the single owner of the
  footer text.
- `TUIApp` handles `on_skill_grid_pending_changed` by calling
  `_refresh_pending_label()` (and `_refresh_status_bar()`, since the status bar
  also shows a `pending` rollup that goes stale for the same reason).
- The footer-pending `Static` is shared between the live `Pending: N` label and
  the transient apply/diff/revert result lines. A toggle after an apply will
  overwrite the result line with the fresh `Pending: N` — that is correct and
  expected (the user is now editing a new pending set).

Naming guard (prior incident): avoid `_render_*` method names on Textual
widgets. The handler name is `on_skill_grid_pending_changed` and the message
class is `PendingChanged` — neither collides.

### Bug 2 — per-harness applied count

In `_apply_skill_pending()`, count per harness write instead of per group.

- On success, `engine_apply` returns an `InstallResult` whose `created` and
  `removed` tuples are the actual symlink writes for that group. Add
  `len(result.created) + len(result.removed)` to `ok`.
- On `InstallError` (or the `ensure_project_canonical` failure), the whole group
  failed: add the group's intended write count `len(adds) + len(removes)` to
  `failed`. This is the symmetric mirror of the success count.
- Universal no-op-at-project-scope writes naturally do not appear in `created`/
  `removed`, so they don't inflate `ok` — faithful to "per-harness write".

The canonical example holds: 1 skill × 3 harness adds → one group →
`engine_apply` creates 3 symlinks → `ok = 3` → `applied: 3 ok, 0 failed`.

## Definition of done

- Footer `Pending` updates live on every toggle (up and down), verified in TUI.
- Apply summary counts per-harness writes; 1 skill × 3 harnesses →
  `applied: 3 ok, 0 failed`.
- Failed harness writes reflected in `failed` symmetrically.

## Out of scope

- Fuzzy-filter search box (#249).
- Any change to toggle/apply mutation behaviour — counting/display only.
