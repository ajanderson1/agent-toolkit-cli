---
issue: 280
type: fix
mode: --ship-it
date: 2026-05-29
---

# Spec — `skill push` clean-gap (committed-but-unpushed changes)

## Problem

`skill push` decides "nothing to push" purely from **working-tree cleanliness**, never from divergence vs origin. When the working tree is clean but local `HEAD` is ahead of `origin/<ref>` (the exact state a `commit-only` flow leaves things in — e.g. `skill-builder` improve-mode Phase I5), `push` prints `clean — nothing to push` (exit 0) and **silently ships nothing**.

This is data-loss-adjacent: the user follows the documented `commit → push` flow, the command says "clean", and the user reasonably believes their work is upstream when it is not. It is also the long-standing trap in project memory (`skill push` clean-gap → fall back to raw `git push origin main`) and the "Gap Ledger §4" item characterised by `test_push_clean_with_commits_ahead_drops_them` ("Spec 2 fixes this").

## Two affected sites (`commands/skill/push_cmd.py`)

1. **Standalone path** (`push_cmd`, ~L99–101): `if skill_git.status(canonical) == CLEAN: echo "clean — nothing to push"; continue`.
2. **Owned-monorepo path** (`_push_monorepo`, ~L197–200): `if skill_git.status_path(parent_dir, subpath) == CLEAN: echo "clean — nothing to push"; return`.

Both equate "clean working tree" with "nothing to publish".

## Building block (already exists)

`skill_git.divergence(repo, ref=...)` → `Divergence.{UP_TO_DATE,BEHIND,AHEAD,DIVERGED}`, classified from `git rev-list --left-right --count HEAD...origin/<ref>`. Reads local refs only (no fetch) — so an unpushed local commit reliably shows as `AHEAD` against the last-known origin. `#279` already wired this into `status_cmd.py` via `_divergence_suffix()`, mirroring the marker vocabulary `ahead (unpushed)`.

## Design

When the relevant working tree is clean, classify divergence before declaring "nothing to push". Behaviour per state:

| Working tree | Divergence | Behaviour |
|---|---|---|
| clean | `UP_TO_DATE` | `clean — nothing to push` (the only truly-nothing case) — **unchanged** |
| clean | `AHEAD` (N>0) | there is committed work to publish — **push it** |
| clean | `BEHIND` / `DIVERGED` | report honestly, do not claim "nothing to push" |
| dirty | (any) | unchanged — commit + push as today |

### Standalone path — clean + AHEAD

- `--direct`: the committed work is already on the tracked ref locally; push it with `skill_git.push(canonical, ref=entry.ref or "main")`, then advance `local_sha` and echo `pushed (committed-but-unpushed)`. (No new commit — the work is already committed.)
- default (PR mode): the committed work needs a PR branch. Create a branch **at the current HEAD** (which already carries the commits), push it, open the PR, then restore the canonical repo to base — mirroring `_push_via_pr` but without a `commit_all` (nothing is uncommitted). Print the branch/PR exactly like the dirty path.

### Owned-monorepo path — clean subpath + AHEAD

Divergence is a **whole-clone** property: the parent may be ahead because of a *sibling* skill's committed-but-unpushed work, not this skill's. Semantics:

- Never report `clean — nothing to push` when the clone is `AHEAD` of origin.
- `--direct`: push the parent's already-committed work to base (`skill_git.push(parent_dir, ref=base_ref)`); advance `local_sha`; echo `pushed (committed-but-unpushed)`. We do **not** create a new commit (subpath is clean — nothing to stage).
- default (PR mode): create a PR branch at the clone's current HEAD (carries the ahead commits), push, open PR, restore to base via the same plain-checkout discipline already used in `_push_monorepo` (preserve a dirty sibling). No `commit_paths` — nothing to stage.
- `BEHIND` / `DIVERGED`: surface honestly (`<slug>: behind origin` / `diverged`), do not push, do not claim "nothing to push".

### Shared marker vocabulary

Reuse `status`'s `ahead (unpushed)` vocabulary in messages so `status` and `push` read consistently. Per the issue's "consider unifying" acceptance item, a small shared classifier helper keeps the two from drifting — but the floor is correct behaviour at both sites.

## Acceptance

- A committed-but-unpushed change (standalone **and** owned-monorepo) is either pushed by `skill push` or reported as ahead/behind/diverged — **never** silently `clean — nothing to push`.
- `UP_TO_DATE` clean tree still says `clean — nothing to push`.
- Regression test per path (mirror `test_skill_status_monorepo_owned_ahead_unpushed`): commit in the clone, assert `push` does not report "nothing to push" and the commit reaches the remote (`--direct`) / a PR branch carries it (default).
- The existing bug-pinning test `test_push_clean_with_commits_ahead_drops_them` must be **flipped** to assert the fixed behaviour (the commit now reaches origin).

## Non-goals

- No fetch before divergence (matches `status`; live freshness is a separate concern).
- No upstream-ownership re-verification beyond what `_push_monorepo` already does (Gap Ledger §5, out of scope).
- `BEHIND`/`DIVERGED` handling beyond honest reporting (no auto-rebase/merge).
