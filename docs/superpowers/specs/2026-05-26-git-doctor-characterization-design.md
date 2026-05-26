# Spec 1 — Git & Doctor Characterization + Test Foundation

**Date:** 2026-05-26
**Status:** Design (awaiting user review)
**Companion:** Spec 2 — Git/Doctor UX Improvements (forward-pointer at end; own brainstorm/plan cycle)

## Purpose

Lock down the existing behaviour of the skill git lifecycle (`add`/`install` → `status` →
`update` → `push`, plus `doctor`) with a comprehensive, three-tier test suite **before**
changing any behaviour. This is a test-first characterization pass: tests describe what the
code does *today*, surprising-but-current behaviour is captured and flagged in a Gap Ledger,
and the only production code added is the shared `divergence()` helper plus test
infrastructure that both this spec and Spec 2 depend on.

The principle (per AJ's conventions): *fail loudly rather than degrade silently*, and
*automate consistency wherever possible*. The git/doctor seam is exactly where silent
degradation hides — a clean-but-ahead tree reported as "nothing to push," drift that
`status` can't see. Characterization tests make that seam observable so Spec 2 can fix it
with confidence.

## Background

The skill management layer resolves to canonical clones under `~/.agent-toolkit/skills/`
(global) and `~/.agent-toolkit/projects/<project_id>/skills/` (project), projected into
agent homes via symlinks. Six git-aware verbs operate on those canonicals:

- `skill_git.py` — git subprocess primitives (`clone`, `fetch`, `merge`, `reset_hard`,
  `status`, `push`, `commit_all`, `head_sha`, `remote_head_sha`, …). All calls route through
  `_run()`, which scrubs `GIT_*` env vars except the identity allowlist.
- `commands/skill/status_cmd.py` — reports `clean | dirty | missing | copy` per skill.
- `commands/skill/update_cmd.py` — `fetch` + `merge origin/<ref>`; handles monorepo parents.
- `commands/skill/push_cmd.py` — PR-by-default or `--direct`; refuses read-only/copy-mode.
- `commands/skill/doctor_cmd.py` + `skill_doctor.py` — structural diagnosis + repair.

### Known sharp edges (from project memory, to be characterized here)

- **Push clean-gap** (`project_skill_push_clean_gap`): a clean working tree with local commits
  ahead of `origin` reports "clean — nothing to push" and silently drops the commits.
- **`status` is drift-blind**: only reports working-tree clean/dirty, never compares against
  upstream, so "a newer version exists" is invisible.
- **`update` always merges**: no "already up to date" vs "merged N commits" distinction.
- **Push ownership unverified**: the only refusal is the `read_only`/monorepo flag; there is
  no real GitHub ownership check despite the intended "refuse if we don't own upstream."
- **GIT_* env leak** (`feedback_git_env_leak`) and **subagent worktree corruption**
  (`feedback_subagent_git_isolation`): regression-test these so they can't silently return.

## Scope

### In scope (Spec 1)

1. **Test infrastructure**: `tests/integration/` and `tests/e2e/` directories; state-builder
   fixtures on top of the existing `git_sandbox`.
2. **`skill_git.divergence()`** — one tested helper classifying local-vs-upstream state.
   Built here because (a) it's the git seam both specs need, and (b) characterization tests
   need it to *express* behind/ahead/diverged setups cleanly.
3. **Exhaustive characterization** of `status`, `update`, `push`, `doctor` across the full
   state matrix, at unit + integration + e2e tiers.
4. **Gap Ledger** — every surprising/buggy behaviour the tests lock in, with a proposed
   follow-up, seeding Spec 2.

### Out of scope (deferred to Spec 2)

- Plain-language / git-agnostic message tables for `status`/`update`/`doctor`.
- The `claude -p` merge-conflict resolver line.
- Doctor parallel drift detection (`behind_upstream` / `diverged_upstream` findings) and
  in-progress reporting.
- Push clean-gap **fix** (Spec 1 *documents* it; Spec 2 fixes it using `divergence()`).
- Stray-symlink gap-closing audit and the `external_symlink_into_canonical` finding +
  report/offer-remove behaviour.
- Real GitHub push-ownership verification (remains a documented gap).

### Explicitly not touched

Lock format (`skill_lock.py`), path resolution (`skill_paths.py`), the install engine
(`skill_install.py`), and scope logic (`_common.scope_and_roots`) are **characterized by new
tests but not modified**.

### Already done (this session)

`~/GitHub/skill_library` (an unreferenced symlink → `~/.agent-toolkit/skills`) was deleted by
hand. The doctor guard against that *class* of external-symlink-into-canonical is Spec 2.

## Test Architecture

Three tiers, each with a distinct job:

| Tier | Proves | Git? | Location |
|------|--------|------|----------|
| **Unit** | Path/lock/plan logic; `divergence()` classification; message formatting | mocked / pure | `tests/test_skill_*.py` (existing convention) |
| **Integration** | Real clean/dirty/behind/ahead/diverged/conflict behaviour through `skill_git` + command functions | **real git subprocess** | `tests/integration/` (new) |
| **E2E CLI** | `agent-toolkit-cli skill status/update/push/doctor` happy + sad paths end to end | real git via `CliRunner` | `tests/e2e/` (new) |

### Fixtures (extend `tests/conftest.py`)

The existing `git_sandbox` (bare `upstream.git` + working `clone`, identity env set, `GIT_*`
scrubbed) stays the base. New state-builder helpers let a test declare the divergence state it
wants without hand-rolling git plumbing:

- `make_behind(sandbox)` — push a new commit to `upstream`, leave the clone behind.
- `make_ahead(sandbox)` — commit in the clone, do not push.
- `make_diverged(sandbox)` — both sides commit (non-conflicting paths).
- `make_conflict(sandbox)` — both sides edit the same line of `SKILL.md`.
- `make_dirty(sandbox)` — uncommitted working-tree change in the clone.

Higher-level fixtures that wire a realistic install (canonical clone + lock entry + agent
symlink), so doctor/status/update/push tests start where real usage starts:

- `installed_skill` — global-scope git-managed skill, fully projected.
- `monorepo_skill` — read-only parent-clone skill (refusal case).
- `copymode_skill` — plain-file skill with no `.git/` (refusal case).

**Determinism guards.** All fixtures inherit the autouse `_strip_git_env` scrub and synthetic
identity. The two historical failure modes are already neutralised and stay covered:

- *GIT_* env leak* (`feedback_git_env_leak`): a command shelled out with a leaked
  `GIT_DIR`/`GIT_INDEX_FILE` must not write into the outer repo. Already covered by
  `tests/test_conftest_git_env_scrub.py` (the autouse scrub + a subprocess-inheritance test).
  No new test needed — the new fixtures simply inherit the guard.
- *Subagent worktree corruption* (`feedback_subagent_git_isolation`): a leaked git config could
  mis-author commits. Mitigated at the production layer by the synthetic identity
  (`-c user.name=…`/`user.email=…`) that `commit_all()` and `merge()` already pin, plus the
  identity vars the `git_sandbox` env sets. This is a property assertion, not a behaviour test:
  the existing git tests that create commits and inspect them already exercise that the pinned
  identity wins, so no dedicated reproduction test is added.

## `divergence()` helper

New function in `skill_git.py`, matching existing conventions (`env=` kwarg-only, routes
through `_run()`, returns an enum like `GitWorkingTreeStatus`):

```python
class Divergence(enum.Enum):
    UP_TO_DATE = "up_to_date"
    BEHIND = "behind"      # upstream has commits we don't
    AHEAD = "ahead"        # we have commits upstream doesn't
    DIVERGED = "diverged"  # both sides moved

def divergence(repo: Path, *, ref: str, env: dict[str, str] | None) -> Divergence:
    """Classify local HEAD vs origin/<ref> using
    `git rev-list --left-right --count HEAD...origin/<ref>`.
    Caller is responsible for fetching first if live data is needed —
    divergence() reads only what's already in the local repo's refs."""
```

`divergence()` does **not** fetch — it classifies against whatever `origin/<ref>` the local
repo already knows. Fetch-then-classify is the caller's choice (and Spec 2's doctor concern).
This keeps the helper pure-ish and trivially testable: the integration fixtures set up each of
the four states and assert the classification, including the post-/pre-fetch distinction.

**Unit tests** assert the parse of `rev-list --left-right --count` output (e.g. `"0\t2"` →
`BEHIND`). **Integration tests** drive real repos through each `make_*` builder and assert the
returned enum. Because `divergence()` never fetches, a `make_behind` clone classifies as
`UP_TO_DATE` until the test explicitly calls `skill_git.fetch()`, then as `BEHIND` — both
assertions are made, pinning the "caller must fetch for live data" contract.

## Scenario Matrix — characterization (current behaviour)

Each cell is one or more tests asserting **what the code does today**. Where a cell is a known
bug, the test is annotated `# documents current behaviour — see Gap Ledger §N` so a future
reader never mistakes the lock-in for intent.

### `skill status` (read-only)

| State | Current observable output |
|-------|---------------------------|
| clean, up-to-date | `clean` |
| dirty | `dirty` |
| clean, behind | `clean` — **drift invisible** (Gap Ledger §1) |
| clean, ahead | `clean` — **commits-ahead invisible** (Gap Ledger §1) |
| clean, diverged | `clean` — **divergence invisible** (Gap Ledger §1) |
| missing canonical | `missing` |
| copy-mode | `copy` |
| monorepo | status read from parent clone; `clean`/`dirty`/`copy` |

### `skill update`

| State | Current behaviour |
|-------|-------------------|
| up-to-date | merges anyway; prints `updated` — no "already current" (Gap Ledger §2) |
| behind | fast-forward merge; `updated`; lock SHAs refreshed |
| ahead | no-op merge ("Already up to date" from git); `updated` |
| diverged (clean merge) | merge commit created; `updated` |
| conflict | `GitError` → `conflict during merge (resolve in working copy)`; exit 1; stderr echoed; tree left mid-merge (Gap Ledger §3 — terse, git-literate message) |
| copy-mode | refuse: `copy-mode (no .git/) — cannot update`; exit 1 |
| monorepo, global | parent fetch+merge; copy-mode re-copy if materialised; `updated (parent …)` |
| monorepo, non-global | refuse: `monorepo update only supported at global scope`; exit 1 |
| not in lock | `not in lock`; exit 1 |

### `skill push`

| State | Current behaviour |
|-------|-------------------|
| clean, no commits ahead | `clean — nothing to push` (correct) |
| **clean, commits ahead** | `clean — nothing to push` — **drops commits** (Gap Ledger §4, the clean-gap bug) |
| dirty, PR mode | new branch + `commit_all` + push + `gh pr create`; checks back to base ref |
| dirty, `--direct` | `commit_all` + push to ref; lock `local_sha` updated; `pushed` |
| read-only / monorepo | refuse: `read-only (monorepo skill …)`; exit 1 |
| copy-mode | refuse: `copy-mode (no .git/) — cannot push` |
| not in lock | `not in lock` |
| not-owned upstream | **no check performed** — push proceeds if git push succeeds (Gap Ledger §5) |

### `skill doctor` (structural, offline — current)

Characterize each existing `Finding` kind and its fix action against the live `skill_doctor.py`
taxonomy: `missing_canonical`, `drifted_symlink`, `wrong_type_bundle`, `orphan_symlink`,
`foreign_symlink`, `dirty_tree`, `lock_source_mismatch`, `stray_symlink`, `orphan_canonical`,
`stray_bundle_dir`. For each: a fixture that induces the condition, an assertion on the
finding kind + message, and an assertion that the fix action (idempotent closure) repairs it
and is a no-op on re-run.

Doctor today is **offline** — no fetch, no upstream-drift findings. Tests assert that absence
(so Spec 2's additions are a deliberate, reviewed change rather than silent scope creep). The
gap-closing *audit* of symlink pathologies is Spec 2; Spec 1 only records that the current
taxonomy is what's being locked in.

## Components & boundaries

- **`skill_git.divergence()`** — new, pure-ish classifier. Input: repo + ref. Output: enum.
  No side effects, no fetch. Consumed by status/update/push (Spec 2) and doctor (Spec 2).
- **State-builder fixtures** — input: a `GitSandbox`; effect: mutate clone/upstream into a
  named divergence state. Each is independently understandable and composable.
- **Install fixtures** — input: `tmp_path` + monkeypatched home/roots; output: a realistic
  installed skill (canonical + lock + symlink). Hide the wiring so behavioural tests read
  cleanly.
- **Characterization tests** — read-only over production code (except importing
  `divergence()`); assert observable outputs (stdout, exit code, on-disk lock, symlink state).

## Error handling & failure modes

- Merge conflicts: assert exit code, that stderr is surfaced, and that the working tree is in a
  *recoverable* state (mid-merge, not corrupted). The resolver-line *improvement* is Spec 2;
  Spec 1 locks in the current terse message.
- Git subprocess failures (auth, unreachable remote): assert `GitError` propagation and that
  no lock mutation occurs on failure (fail loud, don't half-write state).
- Env-leak / identity regressions: dedicated tests per the memory entries.

## Testing strategy (meta)

- `divergence()` is built **TDD** — failing unit test first (parse), then integration tests
  (real states), then implementation.
- Characterization tests are written against current `main` behaviour and must pass on the
  current code with no production changes beyond `divergence()`.
- Each known-bug test carries a `# documents current behaviour — see Gap Ledger §N` comment.
- Runs locally via the project's `verify.sh` / pytest contract; no network in unit tier;
  integration/e2e use only local bare repos (`file://`), never real GitHub.

## Gap Ledger (seeds Spec 2)

**Reconciliation (post-implementation, 2026-05-26):** Every characterization test passed exactly
as this matrix predicted — no implementer reported a behavioural deviation, so no ledger row
required correction. Each gap is now pinned by a concrete test (last column); Spec 2 updates that
test when it lands the fix, which doubles as a checklist. Full suite at completion: **423 passed,
2 skipped.** The diverged-merge case produced a true two-parent merge commit as the matrix assumed
(`test_diverged_merge_creates_merge_commit`).

| § | Gap | Current behaviour locked in | Pinned by test | Proposed follow-up (Spec 2) |
|---|-----|------------------------------|----------------|------------------------------|
| 1 | `status` drift-blind | reports only working-tree clean/dirty | `test_status_behind_still_reports_clean` | use `divergence()`; report `update available` / `ahead` / `diverged` in plain language |
| 2 | `update` always merges | prints `updated` even when current | `test_update_up_to_date_still_says_updated` | distinguish "already up to date" from "merged N commits" |
| 3 | conflict message is git-literate | `conflict during merge (resolve in working copy)` | `test_update_conflict_exits_nonzero_and_is_terse` | emit `claude -p` copy-paste resolver scoped to the canonical path |
| 4 | push clean-gap | clean+ahead → "nothing to push", drops commits | `test_push_clean_with_commits_ahead_drops_them` | push when **dirty OR ahead** (via `divergence()`); report commit count |
| 5 | push ownership unverified | proceeds whenever `git push` succeeds | `test_ahead_push_succeeds_no_ownership_check` (integration) + `test_push_dirty_direct_pushes` (e2e) | `gh`-based repo-permission check; refuse with clear message when not owned (own brainstorm — larger) |
| 6 | doctor offline / drift-blind | no fetch, no upstream findings | `test_doctor_does_not_report_upstream_drift` | parallel fetch + `behind_upstream` / `diverged_upstream` findings with in-progress reporting; offline fallback |
| 7 | doctor stray-symlink coverage gaps | current taxonomy only | *(no new test — covered by existing doctor taxonomy tests; audit deferred to Spec 2)* | audit pathologies (real-dir-where-symlink in per-agent dirs, broken chains, symlink→symlink); add `external_symlink_into_canonical` (report + offer remove) |

## Spec 2 forward-pointer

Spec 2 — *Git/Doctor UX Improvements* — consumes this foundation: plain-language message
tables (git-agnostic; "unsaved changes" vs "newer version available"), the `claude -p`
conflict resolver, doctor parallel drift detection with progress reporting and offline
fallback, the push clean-gap fix, the stray-symlink gap-closing audit, and the
`external_symlink_into_canonical` finding. Push-ownership (§5) likely warrants its own smaller
spec. Spec 2 gets its own brainstorm → plan → implement cycle, informed by the realised Gap
Ledger once Spec 1's tests exist.
