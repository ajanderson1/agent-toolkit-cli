# Plan — unlink per-asset orphan sweep (#142)

1. **Edit `src/agent_toolkit_cli/commands/unlink.py::_do_per_asset`** (lines ~226-261):
   - Restructure the post-snapshot block to mirror `_do_plan_entry`:
     - If `slug in slugs_in_section and not dry_run`: call `remove_slug` (existing error handling unchanged).
     - Drop the `return` that fires when slug is absent from the allowlist.
     - Always print the `Unlinking ...` header.
     - Always call `project_from_file(..., previous_allowed=prev_snapshot)`.
     - Always emit the summary.
   - Keep the existing `allowlist_path.is_file()` early-exit (no allowlist at all → nothing to do, exit 1) unchanged.

2. **Add regression test** in `tests/test_cli_unlink.py`:
   - `test_unlink_per_asset_prunes_orphan_when_not_in_allowlist` — clone of the `_plan_` sibling but using the per-asset form (no `--plan`, target as positional `skill:android-termux`).
   - Assert exit code 0 and stale symlink removed.

3. **Verify**:
   - Run `uv run pytest tests/test_cli_unlink.py -q` — all green, new test passes.
   - Run full suite `uv run pytest -q` to catch any unintended side effects.
   - Manually reproduce the bug repro from the issue body in a temp HOME if time permits (not required since the regression test covers it).

4. **Commit** as a single `fix(unlink): ...` commit closing #142.
