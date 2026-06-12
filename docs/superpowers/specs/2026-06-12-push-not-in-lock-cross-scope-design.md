# push: cross-scope hint + non-zero exit for not-in-lock slugs — design

**Issue:** #371 · **Tier:** standard (family fix touches 3 command modules + 3 test files) · **Date:** 2026-06-12

## Problem

`skill push <slug>` with no `-g`/`-p` flag, run from a cwd that has a project
`skills-lock.json`, resolves to **project** scope. If the slug exists only in
the **global** lock, the command prints `<slug>: not in lock` and exits **0**
(`commands/skill/push_cmd.py:65-67` — the branch `continue`s without setting
`rejected`). The self-improvement silently goes unpublished: nothing was
pushed, the message doesn't say which scope's lock was checked, and the exit
code tells scripts everything is fine.

Verified on main @ dba6d20: **all three push commands share the identical
gap** — `commands/skill/push_cmd.py:65-67`, `commands/agent/push_cmd.py:63-64`,
`commands/pi_extension/push_cmd.py:62-63`. The instructions asset type has no
push verb, so the family is exactly these three.

The branch only fires for **explicitly named** slugs: bare `push` takes its
targets from the resolved lock itself, so a batch run cannot hit it.

## Decisions (AJ, 2026-06-12, via /aj-issue interview)

1. **Exit 1 when a named slug is not in the resolved scope's lock** — whether
   or not it exists in the other scope. An explicitly named slug that can't be
   pushed is a user error, same standing as the existing read-only rejection
   (`rejected = True`). Bare `push` never reaches this branch, so batch
   friendliness is unaffected.
2. **Fix as a family** — all three push commands get the identical change.

## Design

In each push command's `not in lock` branch:

1. **Probe the other scope's lock** (best-effort, never raises):
   - Resolved scope `project` → other lock is the global lock:
     `lock_file_path(scope="global", home=Path.home())`.
   - Resolved scope `global` → other lock is the project lock at the derived
     project root: `ctx_project or Path.cwd()` (re-derived because
     `scope_and_roots` returns `project_root=None` for global scope).
   - All three asset types share `skill_lock.read_lock`, which returns an
     **empty LockFile** for a missing/corrupt file — the probe cannot crash.
2. **Message** names the scope that was checked, and hints when the slug lives
   in the other scope:
   - Found in the other scope:
     `<slug>: not in the project lock (found in the global lock — re-run with -g)`
     and the inverse with `-p`.
   - Found nowhere: `<slug>: not in the project lock` (or `global`).
3. **Exit code:** both cases set `rejected = True`, feeding the existing
   `if rejected: ctx.exit(1)` tail. No new exit path.

Implementation shape: one small private helper per module (the three
push_cmds are deliberate near-clones; keep the clone discipline rather than
introducing a shared push-core module for ~15 lines). Each helper takes
`(slug, scope, ctx_project)` and returns the message string.

### Non-goals / out of scope

- Bare `push` (no slugs) behaviour — unchanged.
- Auto-retrying in the other scope ("did you mean" only; never push a scope
  the user didn't resolve to).
- Upward project-root discovery. The project-lock probe is root-anchored
  (`ctx_project or Path.cwd()`, matching existing scope-resolution
  semantics); invoking from a project **subdirectory** gets the scope-naming
  message without the hint. Accepted limitation — same as scope resolution
  itself.
- The sibling named-slug exit-0 dead-ends in the same loop: copy-mode
  ("cannot push", exit 0) and clean-but-BEHIND/DIVERGED ("not pushing",
  exit 0). Deliberately deferred — scripts still cannot treat push exit 0 as
  "published or clean" for those branches; a follow-up issue may extend the
  exit-code contract there (critical-review finding, 2026-06-12).
- Gating the "re-run with -g/-p" hint on the other-scope entry's pushability
  (npm row / read-only / copy-mode). Waived: the advised re-run produces a
  precise loud diagnosis for npm and read-only rows (exit 1), which is
  strictly better than today's silence; copy-mode's exit-0 "cannot push" is a
  pre-existing dead-end recorded in the previous bullet.
- `agent push`'s dead `except FileNotFoundError` around `read_lock`
  (`commands/agent/push_cmd.py:53-57` — `read_lock` never raises it); may be
  cleaned opportunistically if touched, not a requirement.
- The wider `list`/`status` scope-trap family (#216/#222 lineage) — push only.

## Test surface

Per asset type (3 CLI test files), HOME-isolated sandbox:

1. Slug in the **other** scope's lock only → message contains the cross-scope
   hint (`found in the global lock — re-run with -g` / inverse) and exit 1.
2. Slug in **neither** lock → scope-naming message, exit 1.
3. Bare `push` with an empty/populated lock → behaviour unchanged, exit 0
   (regression guard for the batch path).
4. Existing read-only / push-path tests stay green.

Skill tests extend `tests/test_cli/test_cli_skill_push.py`; agent and
pi-extension tests go in their existing CLI test modules.

## Acceptance criteria

1. `skill|agent|pi-extension push <slug>` where the slug is only in the other
   scope's lock prints the cross-scope hint naming both scopes and the flag to
   re-run with, and exits 1.
2. The same commands with a slug in neither lock name the checked scope and
   exit 1.
3. Bare `push` behaviour is byte-identical to today (targets from the lock;
   no new exit paths).
4. All three command modules carry the same change shape; tests cover all
   three.
5. Full suite green (modulo the 2 known HOME-isolation environment failures).
