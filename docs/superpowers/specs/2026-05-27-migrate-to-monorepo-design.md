# `skill migrate-to-monorepo` — design

**Date:** 2026-05-27
**Epic:** #258 (Writable first-party monorepo) — this is **PR2** (the migration command). PR1 (the owned-monorepo capability for `add`/`push`/`update`/`status`) merged at `ed03bf5`.
**Status:** approved design, ready for implementation plan.

## Goal

Provide a durable, idempotent, per-machine command that re-homes owned per-skill lock entries into the `ajanderson1/agent-toolkit` monorepo — rewriting each entry from own-repo shape to owned-monorepo-subpath shape, replacing its clone dir with a symlink into the shared `_parents/` clone, and re-projecting harness symlinks — **without ever silently dropping unpushed local work**.

## Two tracks

This effort splits into two operations with very different blast radii. **Only Track B ships in this PR.** Track A is a one-time operational fix performed by hand (and documented here so it is reproducible), not a CLI feature.

### Track A — one-time fix (operational, not code)

The `-skill` suffix on the standalone repo names (`ajanderson1/<slug>-skill`) is the root of the naming confusion: the slug is `journal`, the monorepo subpath is `skills/journal`, but the standalone repo and the lockfile `source` carry `journal-skill`. We eliminate the suffix at the root rather than papering over it.

1. **Rename all 17 standalone repos on GitHub:** `ajanderson1/<slug>-skill` → `ajanderson1/<slug>` via `gh repo rename`. GitHub keeps a redirect from the old name, so in-flight clones keep fetching.
2. **Fix the 8 orphan lockfile sources:** the 8 owned skills *not* yet in the monorepo stay standalone. Rewrite their lockfile `source` from `ajanderson1/<slug>-skill` → `ajanderson1/<slug>` and re-point their local clone remotes. They remain standalone, correctly named, until a later fold pass.

There is no recurring need for either step, so neither becomes a CLI command (would violate *simple defaults over flexible systems*).

### Track B — the durable CLI feature (this PR)

`skill migrate-to-monorepo` re-homes the owned skills that **already exist in the monorepo**. As of 2026-05-27 that is 9 of the 17 owned per-skill entries:

`aj-workflow`, `bitwarden`, `conventions`, `journal`, `kuma-uptime`, `mkdocs`, `obsidian`, `pocketsmith`, `skill-builder`

The other 8 (`agent-builder`, `autonomous-run`, `claude-orchestrated-pi-agents`, `cmux-pm`, `contexts`, `dev-server`, `domain-manager`, `repo-recon`) are not folded into the monorepo yet and are reported as skipped until a later fold pass makes them eligible.

## Command

```
skill migrate-to-monorepo ajanderson1/agent-toolkit [--dry-run]
```

- **Global-only.** Operates on `~/.agent-toolkit/` like every owned-skill verb. No `-g`/`-p`.
- **Parent arg required and explicit.** No defaulting to a hardcoded repo name.
- **`--dry-run`** prints the per-skill plan (migrate / skip + reason) and writes nothing. Worth having because the live run rewrites the lockfile and deletes clone dirs.

### Eligibility

An entry is migrated only when **all** hold:

- `source` matches `ajanderson1/<slug>` or `ajanderson1/<slug>-skill` (tolerant of pre- or post-rename source — a stale source must not break migration), **and**
- it has `local_sha` set and **no** `parent_url` (a per-skill clone, not an already-migrated monorepo entry), **and**
- `skills/<slug>/SKILL.md` exists in the monorepo clone.

Everything else is left untouched: read-only third-party entries, already-migrated entries, and the 8 orphans absent from the monorepo (reported "not yet in monorepo").

### Per-skill flow

Each skill is processed independently; one failure or skip never blocks the others.

1. **Refusal check** (see Safety). If the skill has local work not reflected in the monorepo → **skip**, print what is unreconciled plus a reconcile hint, mutate nothing.
2. **Ensure shared parent clone.** Clone `ajanderson1/agent-toolkit` into `_parents/ajanderson1/agent-toolkit/` once if absent; otherwise reuse (fetch). Subsequent skills reuse the same clone.
3. **Rewrite the lock entry** to owned-monorepo-subpath shape — identical to what `_add_monorepo(..., owned=True)` writes:
   - `source: ajanderson1/agent-toolkit`
   - `skillPath: skills/<slug>`
   - `parentUrl: https://github.com/ajanderson1/agent-toolkit`
   - `upstreamSha: <parent HEAD>`
   - drop `localSha`
   - **no `readOnly`** (owned → writable)
4. **Replace clone dir with symlink.** Symlink `~/.agent-toolkit/skills/<slug>/` to `_parents/ajanderson1/agent-toolkit/skills/<slug>` — the same materialization read-only monorepo entries already use (e.g. `aj-issue`). The old per-skill clone dir is removed.
5. **Re-project harness symlinks.** Call the same projection path `add`/`apply` uses so agent-visibility symlinks point at the new canonical.

### Idempotency

Re-running is a no-op: already-migrated entries carry `parent_url` and fail eligibility; the symlink already points into `_parents`.

## Safety — never silently drop local work

Step 4 deletes the old per-skill clone dir. If that dir held the only copy of unpushed self-improvement, deleting it is unrecoverable. Three layers guarantee that never happens.

### Layer 1 — refusal check, before any mutation

A skill is eligible only when its local state is fully reflected in the monorepo. Both must pass:

- `local_sha == upstream_sha` — the recorded local pin matches what is pushed.
- The clone working tree is **clean** — `git status --porcelain` in the clone dir is empty (catches on-disk edits that were never committed, which the SHA comparison alone misses).

If either fails → skip, no mutation, print the unreconciled detail + a reconcile hint. `journal` (currently `localSha ≠ upstreamSha`) hits this and is skipped until reconciled.

### Layer 2 — content equivalence, not just SHA trust

SHA equality proves the *commit* is pushed to the standalone repo, but the migration's real claim is "the monorepo's `skills/<slug>` contains this skill's work." The standalone repo and the monorepo subpath are **independent git histories** (the monorepo was folded fresh in Phase B), so cross-history SHA comparison is meaningless. Instead, **content-diff** the clone dir's tree against `_parents/ajanderson1/agent-toolkit/skills/<slug>/` (excluding `.git`). If they differ, the monorepo copy is stale or diverged → **skip** with a hint, even if Layer 1 passed.

This is the check that actually protects against "the monorepo fold missed your latest edit." It goes beyond the issue's wording (which said only `localSha ≠ upstreamSha` or uncommitted work) because the two histories are independent and the fold is hand-done — so "is this work in the monorepo?" is an empirical question, answered by comparing reality, per *fail loudly rather than degrade silently*.

### Layer 3 — destructive delete last, after verifying the symlink

Within a migrated skill, order operations so the irreversible step is last and gated:

1. Rewrite the lock entry (cheap, reversible — just JSON).
2. Create the symlink to `_parents/.../skills/<slug>` under a temp name, verify `<tmp>/SKILL.md` resolves, then atomically swap into place.
3. Only once the symlink is verified good, `rm -rf` the old clone dir.

If anything fails mid-way, the old clone dir still exists; worst case is a half-migrated entry that re-running cleans up — never lost work.

## Testing

Mirrors PR1's style in `tests/test_cli/test_skill_owned_monorepo.py`, using a fixture monorepo plus per-skill clones.

- **Happy path:** clean owned per-skill entry whose skill exists in the fixture monorepo → entry rewritten to subpath shape (no `readOnly`, `parentUrl` set, `localSha` dropped, `skillPath: skills/<slug>`); clone dir replaced by a symlink into `_parents`; harness symlinks re-projected.
- **Refusal — SHA divergence:** `local_sha ≠ upstream_sha` → skipped, entry + clone dir untouched, hint printed.
- **Refusal — dirty tree:** clone working tree has uncommitted edits → skipped, untouched.
- **Refusal — content drift (Layer 2, load-bearing):** SHAs match + tree clean, but monorepo subpath content differs from the clone → skipped, untouched. Proves we verify reality, not metadata.
- **Skip — not in monorepo:** owned entry whose `skills/<slug>` is absent from the parent → left as-is, reported "not yet in monorepo."
- **Idempotency:** two runs → second is a clean no-op.
- **Regression guard:** a read-only third-party entry (`anthropics/skills`) is never touched.
- **`--dry-run`:** prints the plan, writes nothing, lockfile + dirs unchanged.

## Reporting

End-of-run summary, bold per the CLI-output convention:

```
Migrated 8: aj-workflow, bitwarden, conventions, kuma-uptime, mkdocs, obsidian, pocketsmith, skill-builder
Skipped 1:  journal — local commits not in monorepo (reconcile, then re-run)
```

## Out of scope

- The Track A renames and orphan-source fixes (operational, done by hand).
- Folding the 8 missing skills into the monorepo (Phase B, in the `agent-toolkit` repo).
- Deleting the old standalone repos (Phase D, only after every machine has migrated).
