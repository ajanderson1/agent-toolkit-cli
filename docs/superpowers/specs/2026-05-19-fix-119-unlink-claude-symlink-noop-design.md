# Fix #119 — `unlink <kind>:<slug>` is a no-op for symlink-kinds on claude

## Problem

`agent-toolkit-cli unlink user claude <kind>:<slug>` (per-asset selector) exits 0
with "Already in sync — 0 assets linked, nothing to change." but leaves the
on-disk symlink in place. Bulk `unlink user claude` (no slug) works. Severity
high: exit code 0 + reassuring message + actual no-op is the worst combination
for a destructive command. Reproduced on `agent × claude` and `command × claude`.

## Root cause

`commands/_link_lib.py::project_from_file` — the per-asset code path:

1. `_do_per_asset` (unlink.py) removes the slug from `.agent-toolkit.yaml`,
   then calls `project_from_file` with `previous_allowed=prev_snapshot`.
2. For each known asset whose slug is no longer in `allowed_slugs`, the
   projection loop tries to prune the slot:

   ```python
   slot_path_translated = target_dir / _slot_filename(asset.slug, kind, harness)
   slot_path_plain      = target_dir / asset.slug
   if not _prune_translated_slot(slot_path_translated, ...):
       _prune_if_into_repo(slot_path_plain, toolkit_root, ...)
   ```

3. For `claude`, `_slot_filename` returns `<slug>.md` (agents/commands), but
   `claude` has **no entry in `_CACHE_LAYOUT`** — so `_prune_translated_slot`
   raises `ValueError` (caught) and returns `False`.
4. The fallback then prunes `slot_path_plain` (`<slug>`, no extension), which
   does not exist on disk. The real slot at `<slug>.md` is never inspected.

Net effect: counters never increment, summary prints "Already in sync — 0
assets linked, nothing to change.", symlink stays.

The bulk `--all` path is unaffected because it iterates `target_dir.iterdir()`
directly and reads every entry's name from disk.

## Fix

In the per-asset prune branch of `project_from_file`, also try
`_prune_if_into_repo(slot_path_translated, ...)` when the translated-slot
helper does not act. This is safe because:

- `_prune_if_into_repo` is a no-op for non-symlinks, so it harmlessly skips
  when the slot doesn't exist (e.g. legacy bare-slug layout where the actual
  slot is at `slot_path_plain`).
- For harnesses with a real translation cache (opencode, codex, gemini),
  `_prune_translated_slot` handles them and returns `True`, so this extra
  call is never reached.
- For claude (no cache layout), `_prune_translated_slot` returns `False`,
  and the new `_prune_if_into_repo(slot_path_translated)` removes the
  `<slug>.md` symlink that points into the toolkit root.

We keep the existing `_prune_if_into_repo(slot_path_plain)` fallback so
legacy bare-slug layouts (pre-`.md`-suffix change) still get cleaned up.

## Scope

- Affects every symlink-kind on claude where `_slot_filename` returns
  `<slug>.md` (agents, commands). Skills/plugins use the bare slug, so the
  existing fallback covered them — those tests still pass.
- Not present on codex/opencode/pi/gemini because those have a cache layout
  and `_prune_translated_slot` handles their slots.

## Tests

- Regression test: `test_unlink_per_asset_claude_agent_removes_symlink`
  seeds a claude agent, links it, runs `unlink user claude agent:demo-agent`,
  asserts the `<slug>.md` symlink is gone and the YAML entry is removed.
- Existing 19 unlink tests still pass.
- Full suite: 863 passed, 1 skipped.

## Out of scope

- The "Already in sync" message wording. The wording becomes correct once
  the prune fires (counters.removed > 0 → "Linked 0 new, updated 0,
  removed 1 stale …").
- Rollup #2 (stale projections aren't pruned on reconcile) — separate issue.
- Rollup #3 (doctor symlink-integrity blind spot) — separate issue.

Closes #119.
