# unlink per-asset orphan sweep (issue #142)

## Problem

`agent-toolkit-cli unlink <scope> <harness> <kind>:<slug>` short-circuits with "not in allowlist — nothing to remove." and exits 0 when the slug is absent from the allowlist, even if a stale projection (symlink, MCP config entry) still exists on disk. Same class of bug as #135, which fixed the `--plan -` path in `_do_plan_entry` but not the per-asset path in `_do_per_asset`.

## Fix

Mirror the #135 shape inside `_do_per_asset` in `src/agent_toolkit_cli/commands/unlink.py`:

- Always read the allowlist and snapshot it (already done).
- If the slug is in the allowlist and not a dry run, call `remove_slug`.
- Drop the early `return` when the slug is absent.
- Always fall through to `project_from_file(..., previous_allowed=prev_snapshot)` so stale projections (symlinks, MCP adapter entries) get swept regardless.

The `previous_allowed=prev_snapshot` arg keeps the MCP adapter dispatch aware that the slug *was* projected, even when it isn't in the allowlist now.

## Regression test

Add a sibling to `tests/test_cli_unlink.py::test_unlink_plan_prunes_orphan_when_not_in_allowlist` that exercises the per-asset form (`unlink user codex skill:android-termux`, no `--plan`) against an empty allowlist + a stale symlink, and asserts the stale symlink is removed.

## Out of scope

- Refactoring the shared logic of `_do_per_asset` and `_do_plan_entry` into a single helper. Possible follow-up; not needed for the fix.
- Behaviour change on a clean-state (no orphan) per-asset unlink — output stays "nothing to remove" and exit 0 still, since `project_from_file` runs but finds nothing to prune.
