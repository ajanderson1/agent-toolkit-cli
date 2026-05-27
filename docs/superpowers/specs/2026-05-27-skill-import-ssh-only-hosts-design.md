# Spec — `skill import` hangs on SSH-only hosts (#251)

**Type:** fix · **Priority:** high · **Mode:** `--ship-it`

## Problem

`skill import` (v2.12.0) reconstructs each skill in the incoming lock by `git clone`-ing
a synthesised URL. For github/gitlab sources `clone_url_from_entry` returns an **HTTPS**
URL (`https://github.com/<owner>/<repo>.git`). On a fresh, SSH-only host (the exact
cross-machine-sync target the feature exists for):

1. **Hang.** A private-repo HTTPS clone with no cached credential helper blocks on an
   interactive `Username for 'https://github.com':` prompt — indefinitely under
   automation. There is no `GIT_TERMINAL_PROMPT=0`, so git is allowed to prompt.
2. **Non-atomic abort.** `write_lock` runs only after the whole import loop completes
   (`import_cmd.py` line 132–133). `^C` at the hang leaves orphaned skill dirs +
   `_parents/` clones on disk but **no lock entry** for any of them — a partial import is
   unrecoverable; a re-run can't tell what already landed.

## Root cause

- `clone_url_from_entry` (`skill_lock.py`) hardcodes the HTTPS scheme for github/gitlab
  short-form sources and never consults the user's git `insteadOf` rewrites.
- `skill_git.clone` runs `git clone` with the inherited environment minus `GIT_*`, so
  git's default interactive-prompt behaviour is in force.
- The lock is persisted once, at the end of the loop — not after each skill.

## Decision (the three fixes)

### Fix #2 — fail loudly, never hang (non-negotiable, load-bearing)

`skill_git.clone` sets, for the clone subprocess only:

- `GIT_TERMINAL_PROMPT=0` — git refuses to prompt for HTTPS credentials and exits
  non-zero instead of blocking. A missing-cred clone now raises `GitError` (surfaced by
  import as a per-skill `failed`, exit 1) rather than hanging forever.
- `GIT_SSH_COMMAND="ssh -o BatchMode=yes"` (only if the caller has not already set
  `GIT_SSH_COMMAND`) — the SSH transport equivalent: never prompt for a passphrase or
  unknown-host confirmation; fail loudly instead.

This is the single fix that resolves the hang. It lives in `clone()` so **every** clone
in the codebase (add, import, project-canonical, doctor) inherits it — fail-loudly is a
property of cloning, not of import.

### Fix #1 — honour SSH for private repos (chosen option: **(a) respect git's `insteadOf`**)

Considered:
- **(a) respect `insteadOf`** — git already applies `url.<base>.insteadOf` natively
  during `clone`; we additionally make `clone_url_from_entry` *actively* apply the
  user's configured rewrites so the resolved URL is explicit and unit-testable.
- (b) prefer SSH URL when SSH-to-GitHub works — breaks public-repo clones on
  HTTPS-capable / SSH-absent hosts and needs live auth probing (fragile, slow).
- (c) make scheme configurable — adds a flag/config knob for a case option (a) covers
  for free.

**Picked (a).** It is the simplest default that always works: a user on an SSH-only host
who has the standard `url."git@github.com:".insteadOf = "https://github.com/"` rewrite
(the canonical SSH-only setup) gets SSH clones automatically, with zero new config
surface and zero behaviour change for everyone else. It aligns with AJ's "simple
defaults over flexible systems" and "automate consistency" principles, and — unlike (b)
— never regresses the public-repo-over-HTTPS path. A user with **no** `insteadOf` and an
SSH-only host now gets a *loud failure* (Fix #2) instead of a hang, which they resolve by
adding the one-line rewrite git already documents for this exact scenario.

Implementation: a small `_apply_insteadof(url)` helper reads
`git config --get-regexp '^url\..*\.insteadof$'`, sorts candidate bases by longest match
(git's own precedence rule), and rewrites the URL prefix. `clone_url_from_entry` applies
it to the synthesised github/gitlab HTTPS URL before returning. Explicit `sourceUrl` from
extras and local paths pass through unchanged (still subject to native git rewriting at
clone time, but we don't second-guess an explicit URL).

### Fix #3 — incremental persistence (recoverable partial import)

`import_cmd` writes the lock **after each successfully added skill**, not once at the end.
A `^C` (or a crash) mid-import now leaves the lock recording exactly the skills that
landed on disk; a re-run skips them (additive-merge, skip-if-exists) and resumes the rest.
This is the lighter of the two options in the issue (incremental write vs. rollback) and
matches the existing additive-merge / partial-success contract — no new cleanup path,
no behaviour change to the success case.

## Definition of done

- [x] Clones never prompt → never hang; credential/SSH gaps raise `GitError` and surface
      as a `failed` line + exit 1.
- [x] `insteadOf`-configured hosts clone github/gitlab sources over their rewritten
      (SSH) transport.
- [x] Partial/aborted import is recoverable: lock written after each added skill.
- [x] Tests: clone-URL selection (insteadOf rewrite + passthrough) and
      incremental-persistence behaviour. Tests set their own clean env (no GIT_* leak).

## Out of scope

- No `export` command (import consumes another machine's `skills-lock.json` directly).
- No live SSH-auth probing. No new flags/config.
- Issue #251 has no milestone — left as-is.
