# Owned-monorepo capability — design spec (PR1 of #258)

**Issue:** #258 (v3.0.0 Phase A: writable first-party monorepo)
**Scope of this PR:** the *capability* half only — `skill add` ownership detection,
`skill push` for owned monorepos, `skill update` merge-survival, `skill status`
subpath-scoped state, plus the read-only regression guard.
**Deferred to PR2:** the one-shot `skill migrate-to-monorepo` command (depends on this).

## Problem

Today a monorepo skill (one upstream repo, skills as subdirectories — how the CLI
consumes `anthropics/skills`) is hardcoded `read_only=True` at
`src/agent_toolkit_cli/commands/skill/__init__.py:367` (`_add_monorepo`), and
`skill push` refuses it at `push_cmd.py:62-68`. That is correct for *consuming*
other people's monorepos, but it blocks AJ from *authoring* his own skills out of a
monorepo (`ajanderson1/agent-toolkit`). We need a **writable owned monorepo**: a
monorepo whose parent remote is under AJ's ownership, whose skills are push/update/
status-managed per-skill via subpath-scoped commits.

## The new concept: an "owned monorepo"

A monorepo is **owned** when either:

1. its parent remote owner is `ajanderson1` (case-insensitive), **or**
2. the user passed `--owned` to `skill add`.

Owned-monorepo lock entries are written **without** `read_only` (i.e. `read_only=False`,
which the v1/v3 writers already omit from JSON). Everything else about the entry is
unchanged: `parent_url`, `skill_path` (the subpath), the shared
`_parents/<owner>/<repo>/` clone, and the symlinked library canonical. This is
**additive** — no rewrite of the lockfile model or the projection mechanism.

### Ownership detection

A single pure helper, `is_owned_owner(owner: str) -> bool`, lives next to the lock
model (or in a small `skill_ownership.py`). It compares `owner.lower()` against an
owned-owners set seeded with `{"ajanderson1"}`. Kept as a named constant so it is one
edit to extend later. `--owned` on `skill add` forces ownership regardless of owner,
so a future rename or a fork under a different account still works.

The owner is derived from the parsed source's `owner_repo` (`owner, repo =
owner_repo.split("/", 1)`). For `file://` sources the synthetic owner is `local`
(see `_parse_file_url`), which is **not** owned by default — tests that want an owned
`file://` monorepo pass `--owned` explicitly.

## Command behaviour

### `skill add` — ownership detection + `--owned`

- New flag: `@click.option("--owned", is_flag=True, ...)` on the `add` command,
  threaded into `_add_monorepo(parsed, slug, *, owned: bool)`.
- In `_add_monorepo`, compute `owned_flag = owned or is_owned_owner(owner)` and write
  the entry with `read_only=not owned_flag`. Owned → `read_only=False`.
- `--owned` is only meaningful for monorepo adds (subpath / `--skill` / owner-repo-subpath).
  Passing `--owned` to a single-skill add (`_add_single`) is a `click.UsageError` —
  ownership only changes monorepo behaviour, and silently ignoring the flag would hide
  a user mistake (fail loud).
- The existing "entry exists, refusing to overwrite" guard is unchanged.

### `skill push <slug>` — owned monorepo → subpath-scoped PR

Today `push_cmd.py` rejects any `entry.read_only` entry. New control flow:

1. `entry.read_only` (an *un*owned monorepo) → keep the existing rejection verbatim.
2. `entry.parent_url is not None and not entry.read_only` (an **owned** monorepo) →
   new `_push_monorepo_via_pr(entry, slug, scope, ...)`:
   - Resolve the shared parent clone (`parent_clone_path(owner, repo, ref=entry.ref)`,
     project-scoped via `project_parents_root` when scope is project — mirror
     `status_cmd.py:64-71`).
   - Refuse if the parent clone is missing / not a git repo (clear message; non-zero).
   - **Subpath scoping is the core requirement.** Stage and commit **only**
     `entry.skill_path` within the parent clone, so a working tree dirty in *other*
     skills' subpaths does not get swept into this skill's commit. Implementation:
     `git -C <parent> add -- <skill_path>` then commit with `--only -- <skill_path>`
     (pathspec-scoped commit), via a new `skill_git.commit_paths(repo, message, paths,
     env)` helper. If the skill's subpath has nothing staged → "clean — nothing to
     push" (same UX as the per-repo path).
   - Branch name: reuse the existing `skill/self-improvement-<utc>-<slug>` scheme.
   - One PR branch per push, PR opened against the parent's `entry.ref or "main"` base,
     reusing `_open_pr` / `_branch_web_url` unchanged.
   - **Always restore the parent clone to its base ref afterward** (the existing
     `--direct` vs PR dance does this for per-repo; the owned path does the same) so a
     later `skill update` merges into the tracked ref, not the PR branch.
   - `--direct` for an owned monorepo: commit the subpath and push straight to base
     ref (parallel to `_push_direct`, but subpath-scoped). Update `entry.local_sha`
     from the parent clone HEAD.
3. `entry.parent_url is None` (a per-skill repo) → unchanged existing path.

The rejection-driven `ctx.exit(1)` at the end only fires for genuinely read-only
(unowned) entries, as today.

### `skill update <slug>` — merge, never reset (verify + lock in)

The monorepo branch in `update_cmd.py:56-99` already does `fetch` + `merge` on the
shared parent clone and never `reset`s. This PR's job is to **verify** that path
survives local owned edits (a dirty owned subpath) rather than silently dropping them,
and to add a regression test that proves merge-not-reset. No behaviour change expected;
if `merge` against a dirty tree surfaces a real git error, the existing handler already
reports it and exits non-zero (fail loud) — which is correct.

### `skill status <slug>` — subpath-scoped dirty state for owned monorepos

Today `status_cmd.py:64-75` reports the **whole parent clone's** status for any
`parent_url` entry. For an owned monorepo with many skills in one clone, that means
editing skill A shows skill B as "dirty" too. New behaviour for owned entries
(`parent_url is not None and not read_only`):

- Compute dirty state scoped to `entry.skill_path`:
  `git -C <parent> status --porcelain -- <skill_path>` (via a new
  `skill_git.status_path(repo, path, env)` helper) — non-empty → dirty.
- Surface that the skill is **writable**: emit `f"{slug}\t{state} (owned)"` so the
  writability is visible in one glance, without breaking the existing
  `<slug>\t<state>` tab-separated contract (consumers split on the first tab).
- Unowned monorepo entries (`read_only`) keep the existing whole-parent status — they
  are read-only, subpath-scoping buys nothing, and changing them risks the
  consumption path.

### Regression guard

Read-only consumption of **others'** monorepos (`anthropics/skills`,
`mattpocock/skills`, etc.) must still refuse `skill push`. The existing
`test_skill_push_monorepo.py` tests assert this for an unowned `file://` parent
(synthetic owner `local`, no `--owned`); they must stay green unchanged. Add an
explicit test that an unowned `ajanderson1`-shaped owner... is *owned* — so the guard
is specifically "unowned parent still refuses", proven via a non-`ajanderson1` owner.

## Out of scope (this PR)

- `skill migrate-to-monorepo` / `--rehome` — PR2.
- Any content migration in `~/GitHub/agent-toolkit/` (Phase B).
- TUI surfacing of writability (the grid) — follow-up if wanted; CLI `status` is enough
  for Phase A.
- `skill reset` for owned monorepos — `reset_cmd.py` also keys on `parent_url`; left
  as-is unless a test shows it corrupts owned edits (note it, don't expand scope).

## Verification

- `uv run pytest -q` green, including:
  - owned-monorepo `skill push` → subpath-scoped commit + one PR branch (file:// parent
    + `--owned`).
  - dirty *other* subpath is **not** swept into the pushed skill's commit.
  - `skill update` merges (not resets) into a locally-edited owned subpath.
  - `skill status` shows subpath-scoped dirty state + `(owned)` marker.
  - `skill add --owned <file://parent> --skill X` writes an entry with no `readOnly`.
  - `skill add ajanderson1/...` monorepo writes no `readOnly` (owner-based detection).
  - regression: unowned monorepo push still refused (existing tests + a non-owned owner).
- `uv run ruff check` clean.
- Manual: `skill --help` / `skill add --help` show `--owned`.

## Risks

- **Lockfile SSOT** — the only schema-touching change is *not* setting `read_only` for
  owned entries; the v1/v3 writers already omit `readOnly` when false, so no format
  change. Low risk.
- **Subpath pathspec commits** — `git commit --only -- <path>` is the precise tool;
  must scrub `GIT_*` env (use `skill_git`'s existing `_scrub`) so commits land in the
  parent clone, not an outer repo (the #209 trap; conftest autouse fixture guards tests).
- **Shared-clone PR-branch dance** — the PR path checks out a branch on the *shared*
  `_parents/<owner>/<repo>/` clone, commits the subpath, pushes, then restores base via a
  **plain** checkout (never `-f` — that would silently discard a sibling subpath's
  uncommitted edits, the multi-skill-session workflow). Git's checkout either preserves
  uncommitted work or refuses; it never drops it. **No concurrency lock** on the shared
  clone: a second `push`/`update` on a sibling skill of the same monorepo, running in the
  window between this push's branch-create and checkout-back, could advance `base_ref` and
  make the checkout-back refuse — leaving the clone stranded on the PR branch
  (**recoverable by hand; no data loss**). Unreachable in the normal single-user sequential
  flow (the branch only ever moves the target subpath, so sibling files stay byte-identical
  to base). A guarded stash-recovery is a deliberate follow-up, not gold-plated here.
