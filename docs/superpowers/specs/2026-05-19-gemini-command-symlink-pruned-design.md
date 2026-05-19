# Fix: `(gemini, command)` link writes then prunes its own symlink

**Issue:** [#137](https://github.com/ajanderson1/agent-toolkit-cli/issues/137)
**Type:** bug fix
**Date:** 2026-05-19

## Problem

`agent-toolkit-cli link user gemini command:<slug>` exits 0 and reports
`Linked 1 new, updated 0, removed 1 stale (0 already in sync).` but no symlink
ever materialises at `~/.gemini/commands/<slug>.md`. The cache directory
`~/.gemini/.agent-toolkit-cache/command/` is created but empty.

The same pattern reproduces for project scope. `(claude, command)` and
`(opencode, command)` cells remain green. The `command-gemini` audit cell
now fails red on this gap, which is the right signal — the bug is in the
CLI projection, not in the demo.

## Root cause

Two related defects in `src/agent_toolkit_cli/commands/_link_lib.py` —
both stem from hardcoded `.md` extensions in code paths that should
defer to `_slot_filename(slug, kind, harness)`.

### Defect 1 — cache filename mismatch

`_render_to_cache` writes the cache file as `<slug>.md` for every
`layout == "file"` cell (line 183), but `_slot_filename` returns
`<slug>.toml` for `(gemini, command)`. `maybe_link` correctly uses
`_slot_filename` to compute the slot link path, so it tries to write
a symlink at `demo-command.toml` whose target points at a `.md`
cache file that doesn't have the matching name. The result is an
internal-state divergence between the link path and the cache path.

### Defect 2 — orphan sweep only recognises `.md`

The orphan sweep at line 654 only strips a `.md` suffix when matching
entries in the target directory back to discovered slugs. When the
sweep walks `~/.gemini/commands/` and sees `demo-command.toml`, the
suffix check fails, `canonical_slug` stays `None`, and the entry is
treated as an unknown translated-slot symlink — so it is pruned
inside the same pass that just wrote it.

The pair "Linked 1 new, removed 1 stale" in the user-facing output
is the two halves of this round trip.

### Why claude and opencode are unaffected

Both use `.md` for both the slot and the cache filename, so the
hardcoded `.md` in `_render_to_cache` and the `.md`-only sweep strip
both happen to match. `(gemini, command)` is the only file-layout
cell that uses a non-`.md` extension (`.toml`), so it is the only
cell that hits both defects.

## Fix

Two surgical changes in `_link_lib.py`, plus tests and an audit-demo
expectation update.

### 1. `_render_to_cache` (around line 183)

Replace the hardcoded `f"{slug}.md"` with the value returned by
`_slot_filename(slug, kind, harness)` so the cache filename and the
slot filename always agree, regardless of harness extension.

### 2. Orphan sweep (around line 654)

Generalise the slug-recovery branch so any entry whose stem
(filename without extension) matches a discovered slug is recognised
and not pruned. Concretely: replace the `.md`-only `endswith` check
with a `Path(bare_name).stem in discovered_slugs` lookup, setting
`canonical_slug = Path(bare_name).stem`.

This handles `.md`, `.toml`, and any future file-slot extension
uniformly. The existing per-extension assumptions elsewhere
(`_prune_symlink_slot` cache-root check) work regardless of suffix,
so no other call sites need to change.

### 3. Tests

Two new tests, modelled after the existing `(claude, command)`
coverage in `tests/test_link_lib.py`:

- **Slot suffix test** — analogue of
  `test_claude_command_slot_uses_md_suffix`. Asserts that
  `maybe_link` for `(gemini, command)` creates a symlink at
  `<target_dir>/<slug>.toml` pointing into the cache, that the cache
  file has the matching `.toml` extension, and that no `.md` file is
  left behind.
- **Orphan sweep test** — analogue of
  `test_orphan_sweep_prunes_legacy_bare_slug_for_claude_command`.
  Verifies that a freshly-linked `<slug>.toml` slot is *not* pruned
  by the sweep, while a stale `.toml` symlink for an unlinked slug
  *is* pruned.

### 4. Audit demo

`audit/demos/command-gemini.sh` currently expects a raw symlink to
`$AGENT_TOOLKIT_REPO/commands/demo-command.md`. The correct shape is
a translated slot — symlink at `~/.gemini/commands/demo-command.toml`
pointing into `~/.gemini/.agent-toolkit-cache/command/demo-command.toml`.
Update `TARGET`, `EXPECTED_TARGET`, and `assert_symlink_target`
accordingly so the audit cell flips green after the fix.

## Out of scope

- `_support.py` target-directory registration — already correct.
- `_translators.py` translation logic — already correct (the TOML
  output is what we want).
- Refactoring `_slot_filename` or its callers — only the two missing
  call sites are touched.
- New harness or kind support.
- Doctor / verify integration changes beyond the audit demo.

## Acceptance criteria

1. `agent-toolkit-cli link user gemini command:demo-command` exits 0,
   prints `Linked 1 new, updated 0, removed 0 stale (…)`, and leaves
   a symlink at `~/.gemini/commands/demo-command.toml` pointing into
   `~/.gemini/.agent-toolkit-cache/command/demo-command.toml`.
2. The same is true for `--project . link project gemini
   command:demo-command` at `.gemini/commands/demo-command.toml`.
3. `bash audit/demos/command-gemini.sh` returns 0 (all PASS).
4. The new tests pass; existing test suite still passes.
5. `(claude, command)` and `(opencode, command)` behaviour is unchanged.
