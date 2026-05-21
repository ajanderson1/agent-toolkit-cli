# skill reset — force-sync to upstream

**Issue:** [#170](https://github.com/ajanderson1/agent-toolkit-cli/issues/170) ·
**Milestone:** v2.3.0 · **Type:** feat

## Problem

`skill update` performs a 3-way merge and surfaces conflicts; `skill push`
publishes local edits upstream. Neither offers an escape hatch when the user
has botched a merge, made experimental edits they want to throw away, or
simply wants the library clone snapped back to upstream HEAD. The workaround
today is to `cd` into the library clone and run `git fetch && git reset --hard`
by hand — which defeats the per-skill, lock-file-managed model.

## Goal

Add a new subcommand `skill reset <slug>…` that fetches upstream and runs
`git reset --hard origin/<ref>` in the named library clone(s), then refreshes
the lock entry's `local_sha` and `upstream_sha`. This is the canonical
"discard local work, snap to upstream" verb, paired with `update` (merge) and
`push` (publish).

## Non-goals

- Restoring agent symlinks. `reset` only touches the library clone; the
  symlinks under `~/.claude/skills/<slug>`, the universal bundle link, etc.
  are unaffected (they point at the same library dir).
- Project-scope independent clones beyond the existing `-g/-p` scope flags
  already wired through `scope_and_roots`.
- Reset from the TUI grid — separate UX work.

## User-facing surface

```
skill reset <slugs…>            # fetch + hard reset each named slug
skill reset <slugs…> --force    # also accept dirty working trees
skill reset                     # (out of scope for this PR — see below)
```

Flags (mirroring `update` / `push`):

| Flag | Meaning |
|---|---|
| `-g/--global` | Operate on the global library lock (default scope). |
| `-p/--project` | Operate on the project lock at `<project>/skills-lock.json`. |
| `--force` | Reset even when the working tree is dirty. Mirrors `skill remove --force`. |

**No-arg form.** The issue body says "no-arg form resets all in scope." The
orchestrator brief drops this. Resolution: **out of scope for this PR.** A
no-arg `reset` is dangerous semantics (silently nukes every skill's local
work) and deserves its own UX pass (confirmation prompt, picker, batch
report). The current PR ships the explicit multi-slug form only; calling
`skill reset` with no slugs prints a usage error pointing the user at
`skill list` for available slugs. Follow-up issue can introduce the wizard
form if real-world friction warrants it.

## Behaviour

For each slug in `slugs`:

1. **Resolve lock entry.** If the slug is not in the lock, print
   `<slug>: not in lock` and mark the run as failed (exit non-zero at end,
   matching `update`'s pattern).
2. **Resolve canonical path** via `canonical_skill_dir(slug, scope=…)`.
3. **Check it's a git repo.** Copy-mode installs (no `.git/`) cannot be
   reset; print the same "cannot update; remove and re-add" message
   `update_cmd.py` uses and continue.
4. **Dirty check.** Call `skill_git.status(canonical)`. If `DIRTY` and
   `--force` is not set, print
   `<slug>: dirty — commit, push, or use --force to discard` (matches
   `remove`'s wording shape) and mark the run as failed.
5. **Fetch.** `skill_git.fetch(canonical)`. Surface `GitError` as a
   `ClickException` so the message bubbles up cleanly.
6. **Hard reset.** Run `git -C <canonical> reset --hard origin/<ref>` via
   a new `skill_git.reset_hard(repo, ref=…)` helper (new function, same
   pattern as `merge`/`push`).
7. **Update lock.** Set `entry.local_sha = head_sha(canonical)` and
   `entry.upstream_sha = remote_head_sha(canonical, ref=…)`. Persist with
   `write_lock(...)`.
8. **Echo** `<slug>: reset to <short-sha>`.

After the loop: if any iteration failed (missing-from-lock, copy-mode,
dirty-without-force), `ctx.exit(1)`.

### Why `reset --hard origin/<ref>` (not just `--hard`)

The canonical "upstream HEAD" is `origin/<ref>` (typically `origin/main`).
Plain `git reset --hard` resets to `HEAD`, which doesn't move us toward
upstream. The `ref` comes from the lock entry (`entry.ref or "main"`),
matching `update_cmd.py`.

### Why the dirty check is *before* fetch

Fetch is read-only and safe, but ordering matters for UX: we want the dirty
refusal to fire immediately, not after a network round-trip. Mirrors the
shape of `skill remove`, which checks dirty before deleting.

## Lock-file semantics

After a successful reset, the lock entry's invariants are:

- `local_sha == upstream_sha`
- Both equal `git rev-parse origin/<ref>` at the moment of reset.

This is the same post-condition `update` produces when the merge is a
fast-forward.

## Error model

Following the codebase's idioms (see `commands/skill/update_cmd.py`,
`remove_cmd.py`):

| Condition | Behaviour | Exit |
|---|---|---|
| Slug missing from lock | `<slug>: not in lock` echoed, loop continues | non-zero at end |
| Canonical missing `.git/` (copy-mode) | echo + skip | non-zero at end |
| Working tree dirty + no `--force` | echo + skip | non-zero at end |
| `git fetch` raises `GitError` | raise `ClickException` (loud, stops loop) | non-zero |
| `git reset --hard` raises `GitError` | raise `ClickException` | non-zero |
| Success | `<slug>: reset to <short-sha>` | 0 (if no other slug failed) |

## Tests (acceptance criteria mapping)

New file: `tests/test_cli/test_cli_skill_reset.py`. Follows the pattern of
`test_cli_skill_update.py` (reuses `git_sandbox` fixture + the
`_add_and_install_project` / `_advance_upstream` helpers — likely lifted into
a small local helper section, not a shared conftest, to minimise blast
radius).

| # | Test | DoD bullet |
|---|---|---|
| 1 | `test_reset_clean_snaps_to_upstream` — clean tree, upstream has advanced; after reset, the working copy contains the advanced file and exit code is 0. | clean reset succeeds |
| 2 | `test_reset_refuses_dirty_without_force` — dirty tree (uncommitted edit), `reset` exits non-zero, the dirty file is *unchanged*. | dirty refused |
| 3 | `test_reset_force_discards_dirty_tree` — same setup as #2, but with `--force`; dirty edit is gone, tree matches upstream. | dirty `--force` works |
| 4 | `test_reset_updates_lock_shas` — after reset, lock entry's `local_sha == upstream_sha == origin/main` head. | lock updated |
| 5 | `test_reset_missing_slug_errors` — `skill reset bogus` exits non-zero with a "not in lock" message. | missing-from-lock loud |
| 6 | `test_reset_multi_slug` (stretch) — two slugs, both clean, both reset; both lock entries updated. | multi-slug form |

Each test uses `monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", …)` and the
`git_sandbox` env exactly like `test_cli_skill_update.py` does — including
the GIT_* env-leak scrub already wired into `_scrub_git_env`.

## Files touched

| File | Change |
|---|---|
| `src/agent_toolkit_cli/skill_git.py` | Add `reset_hard(repo, *, ref, env)` helper. |
| `src/agent_toolkit_cli/commands/skill/reset_cmd.py` | **New** Click command. |
| `src/agent_toolkit_cli/commands/skill/__init__.py` | Register `reset_cmd` on the `skill` group. |
| `tests/test_cli/test_cli_skill_reset.py` | **New** test module (6 tests above). |
| `tests/test_skill_git.py` | Add a unit test for `reset_hard`. |

No changes to lock schema, no migration, no version bump (handled by
release-please from the conventional-commit prefix `feat:` on merge).

## Out of scope (explicit)

- The bare-repo `.git/config` oddity in the parent repo. Out of scope per
  the orchestrator brief.
- Hooks / dispatch into TUI grid.
- Resetting the universal-bundle symlink target. The symlink already
  points at the library dir; reset is in-place.
- Confirmation prompt before destruction. `--force` is the gate; dirty
  refusal without `--force` is enough; an interactive prompt would
  contradict the "snap to upstream, no ceremony" verb the issue describes.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| GIT_* env leak hijacks the reset into the parent repo | New `reset_hard` goes through `skill_git._run` like every other call, so the existing `_scrub` runs unconditionally. The test fixture's `_scrub_git_env` enforces this in tests too. |
| User loses local edits they didn't realise were there | The dirty-without-`--force` refusal is the safety net; once they type `--force` they've opted in. Matches `skill remove --force` semantics — already a precedent. |
| Lock falls out of sync if reset succeeds but lock write fails | Lock write happens *after* the file-system reset (matches `update`'s order). A failed lock write surfaces as a `ClickException` and the next `skill update`/`reset` re-syncs the SHAs. Acceptable. |
| Parallel PR #169 lands first and edits `commands/skill/__init__.py` | Standard merge; the conflict surface is one import line + one `add_command` call. Mitigation is in the orchestrator brief (1 rebase retry). |

## Done when

All six DoD bullets from the issue are covered by automated tests, the new
command is wired into the `skill` group, and `agent-toolkit-cli skill reset
--help` renders. CI green; self-review PASS or needs-changes (non-blocking
per `--ship-it`).
