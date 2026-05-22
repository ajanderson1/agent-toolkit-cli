# Doctor: classify dying-bundle-target as drift, not foreign

Issue: [#192](https://github.com/ajanderson1/agent-toolkit-cli/issues/192)
Type: `fix` · Severity: P3 (cosmetic noise on first run; auto-heals on second)

## Problem

On a v2.1 → v2.2 migration the user's filesystem looks like:

```
~/.agent-toolkit/skills/<slug>/            library canonical
~/.agents/skills/<slug>/                   real directory (v2.1 leftover)
~/.claude/skills/<slug>  → ~/.agents/skills/<slug>   per-harness symlink
```

`skill doctor` runs `_check_slug` in `src/agent_toolkit_cli/skill_doctor.py`. For the
`~/.claude/skills/<slug>` symlink it follows the link via `link.resolve()`, then
asks `_is_inside(target, expected_root)`. `expected_root` for global scope is
the library (`~/.agent-toolkit/skills`). The bundle dir `~/.agents/skills/<slug>`
is **not** inside the library, so the symlink is classified `foreign_symlink`
(report-only, no fix).

The drift is self-healing: once `wrong_type_bundle` repairs the bundle into a
symlink to the library, `link.resolve()` chains through and reports as drift on
the next run. But the first run shows misleading "report-only" framing that
nudges users toward `--repair-foreign` when all they really need is to apply the
bundle fix.

## Decision

Apply **Option 2** from the issue: *Detect bundle-target intent.*

If a per-harness symlink resolves to a path of the form
`{home}/.agents/skills/<some-slug>` — the v2.1 bundle shape — classify it as
`drifted_symlink` (fixable: re-link to the canonical library path) regardless of
whether `_is_inside(target, expected_root)` is true.

Why this option:

- **Cheap.** A single conditional in `_check_slug`, reusing
  `_universal_bundle_link` semantics (the canonical bundle root is already
  `Path.home() / ".agents" / "skills"`).
- **Targeted.** Matches the v2.1 layout shape, not just one slug — robust to any
  skill the user migrated.
- **No new permanent special case in `_expected_target_root`.** That function
  stays a pure "where should things live?" map; the v2.1 awareness lives where
  the classification actually happens.
- **No engine restructure.** Option 3 (two-pass diagnose) is cleaner but breaks
  the "diagnose is pure" contract and adds complexity for a P3 cosmetic fix.

## Implementation sketch

In `_check_slug`, after detecting a symlink whose `target != canonical_real`
and `not _is_inside(target, expected_root)`:

1. Before emitting `foreign_symlink`, check whether `target` looks like a v2.1
   bundle target — i.e. `target` lives inside the universal-bundle root
   (`Path.home() / ".agents" / "skills"`).
2. If yes → emit `drifted_symlink` with the existing `_make_relink_action`
   pointing at the canonical library path. The fix is exactly the same
   re-link operation; only the classification changes.
3. If no → existing `foreign_symlink` branch fires unchanged.

Helper: a small private predicate `_is_universal_bundle_target(target: Path) -> bool`
that returns whether `target` resolves under `Path.home() / ".agents" / "skills"`.
Keep it private to `skill_doctor`.

## Acceptance

- A symlink pointing at `~/.agents/skills/<slug>` is classified `drifted_symlink`,
  not `foreign_symlink`.
- The `drifted_symlink` fix re-links to canonical and is idempotent (existing
  behaviour, unchanged).
- Existing `test_diagnose_foreign_symlink_report_only` (foreign target is OUTSIDE
  `~/.agents/skills`) still passes.
- Existing `test_diagnose_foreign_symlink_repair_foreign` still passes.
- New test: a v2.1-style bundle target gets the drift classification (asserts
  `kind == "drifted_symlink"`, the fix action is present, and applying it
  relinks to the library canonical).
- Update the existing `test_doctor_journal_v21_to_v22_repro` so it reflects the
  new behaviour:
  - The claude link is no longer reported as `foreign_symlink`. Instead, it is
    reported as `drifted_symlink` (and prompted, not skipped).
  - With `'y\n'` the user is prompted twice (once for `drifted_symlink`, once
    for `wrong_type_bundle`). Adjust the input string and the exit-code
    expectation to `0` (nothing skipped).
  - The "1 skipped" / "foreign_symlink" assertions are replaced with
    `drifted_symlink` assertions and a `0 skipped` (or "fixed" only) check.

## Non-goals

- Any change to `_expected_target_root` or its callers.
- Any change to `foreign_symlink` semantics for targets outside the v2.1 bundle
  shape — those remain report-only, fixable only with `--repair-foreign`.
- Two-pass diagnose / engine restructure.
- Touching the wrong_type_bundle classification or its fix action.

## Risk

Low. The change is additive within an existing branch, reuses the existing
re-link action, and only narrows when `foreign_symlink` fires.
