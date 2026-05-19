# Design — #90 `at list` text mode via `_build_inventory()` + SSOT for `USER_LINKED_STATUSES`

**Issue:** #90
**Branch:** `chore/90-at-list-text-build-inventory-ssot`
**Type:** chore (refactor + tiny behaviour fix)

## Problem

Two cleanups discovered during #86.

### (1) Text-mode `at list` has a parallel install-state path

`commands/list.py:_install_state()` (L38-73) is a bespoke "is this asset installed" check that:

- Reads the YAML allowlist.
- Iterates `harness_target_dirs` (from `_link_lib`) and checks `is_symlink()`.

That works for symlink-backed assets (skills, agents, commands) but **misses hook and MCP user-scope installs**, which are not symlinks — they are JSON entries in harness config files read via adapter `list_installed()`. The TUI and `at list --format=json` already consume `_build_inventory()` (in `_list_json.py`) which is adapter-aware and gets this right. Only the plain text branch is the outlier.

`_install_state()` also uses `_link_lib.harness_target_dirs` instead of `_support._slot_dirs`, so dual-write alias slots added in #75/#82 may be missed.

### (2) `USER_LINKED_STATUSES` is triplicated

The same `frozenset({"linked", "linked-matches", "linked-drifted"})` appears at:

- `src/agent_toolkit_cli/commands/_list_json.py:432`
- `src/agent_toolkit_cli/doctor/user_scope_coverage.py:13`
- `src/agent_toolkit_tui/widgets/asset_grid.py:31`

(Scout confirmed: the literals at `asset_grid.py` lines 123/139/183/268 are *different* sets — "non-toggleable" / "unlinked family". They are not duplicates of `USER_LINKED_STATUSES` and stay as-is.)

## Approach

### (1) Text mode delegates to `_build_inventory()`

`list.py` text mode pre-calls `_build_inventory(toolkit, harness=…, …)` once, then iterates the returned `assets` list. For each asset, render the row using a small per-cell glyph helper that consults `cell["status"]`:

| `cells[i].status` (for the relevant scope) | text glyph |
|---|---|
| `linked`, `linked-matches`, `linked-drifted` | `"✓"` |
| `unlinked`, `unlinked-allowlisted`, `installed-not-allowlisted`, `unsupported`, `broken` | `"—"` |

The 🌐 marker (cross-scope link indicator) becomes: any cell with `scope=="user"` has `status in USER_LINKED_STATUSES` *and* any cell with `scope=="project"` has `status in USER_LINKED_STATUSES`.

`_install_state()` is removed. Its only caller is the text loop; the JSON / report branches already use `_build_inventory()`.

**Harness filter:** `_build_inventory()` accepts `harness=…` and only populates cells for that harness, so the existing text-mode `--harness` flag composes cleanly.

### (2) `USER_LINKED_STATUSES` SSOT lives in `agent_toolkit_cli._support`

Reasons (per scout):
- `_support` already serves as the SSOT for `ALL_HARNESSES`, `ALL_KINDS`, slot-dir maps.
- CLI modules already import constants from `_support`. TUI already imports from CLI (`app.py:19` → `_repo_resolution`). No new cross-package direction is introduced.
- Putting it in `agent_toolkit_tui.state` next to `CellStatus` would force CLI → TUI imports, reversing the established direction.
- A bespoke new module (`agent_toolkit_cli.cell_statuses`) is unnecessary churn.

Name dropped of leading underscore: **`USER_LINKED_STATUSES`** (public).

All three current declaration sites import from `_support`:
- `_list_json.py` — also keeps a `# noqa: F401` re-export so legacy importers (if any) still work.
- `doctor/user_scope_coverage.py` — import + delete local def.
- `agent_toolkit_tui/widgets/asset_grid.py` — import + delete local def.

The five usages in `asset_grid.py` (lines 127, 143, 192, 254, 265) keep referring to the local symbol `_USER_LINKED_STATUSES` until we drop the alias — simplest is to rename them to `USER_LINKED_STATUSES` or keep a `USER_LINKED_STATUSES as _USER_LINKED_STATUSES` import. Default: rename the references (one search-and-replace, no shim).

`CellStatus = Literal[...]` in `agent_toolkit_tui/state.py` stays — it's a type-level enum, not a runtime set. They are parallel and need to stay in sync by hand. (Not in scope to fuse them now.)

## Out of scope

- `--format=json` output (already correct).
- TUI render-path changes beyond the SSOT swap.
- #69 (policy enforcement of cross-scope installs).
- Fusing `CellStatus` and `USER_LINKED_STATUSES` into one source.

## Definition of done

- `commands/list.py` text mode consumes `_build_inventory()`; `_install_state()` is deleted.
- One `USER_LINKED_STATUSES` definition in the repo (in `_support.py`); all three previous sites import it.
- Tests added:
  - `at list` for a Claude hook installed at user scope shows `user:✓` in text mode.
  - `at list` for a Codex MCP installed at user scope shows `user:✓` in text mode.
- Existing `test_cli_list.py` tests still pass without modification (or with minimal/justified diff).
- `verify.sh` / project test recipes green.
