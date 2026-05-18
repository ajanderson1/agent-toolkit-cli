# Spec: Harden tests/test_ingest_finalize.py — un-skip with confidence

**Issue:** #24
**Branch:** `chore/24-harden-test-ingest-finalize-git-env`
**Mode:** `--auto`

## Background

PR #14 fixed the production-code side of GIT_* env leaks: `agent_toolkit_cli.ingest.finalize._auto_commit` now scrubs `GIT_DIR`/`GIT_INDEX_FILE`/`GIT_WORK_TREE` before `subprocess.run(["git", "commit", ...])`. PR #15 (which closed #9) shipped a band-aid: `pytestmark = pytest.mark.skip(...)` at the top of `tests/test_ingest_finalize.py`, taking both tests out of the suite to stop them corrupting the host repo when run under lefthook pre-commit.

Issue #24 is the follow-up: remove the skip, and make sure removing it is safe.

## Current state (verified by reading the file 2026-05-04)

`tests/test_ingest_finalize.py` already contains the env-scrub helper and uses it everywhere:

- `_git_env()` returns `os.environ` with `GIT_*` keys filtered out (lines 21-25).
- `_init_git_repo()` calls `git init`, `git config user.email`, `git config user.name` with `cwd=tmp_path, env=env` (lines 28-32).
- `test_finalize_writes_commit_when_not_skipped` adds `git add -A`, `git commit -q`, `git log` — also with `cwd=tmp_path, env=env` (lines 84-91).

The env-leak hardening the issue asks for **is already in place.** The only line of code blocking the tests from running is the skip marker at lines 16-18.

## What's actually left to do

1. **Delete the skip marker** at `tests/test_ingest_finalize.py:16-18` (and the explanatory comment at lines 9-15 that references the now-resolved bug).
2. **Verify the un-skipped tests do not pollute the host repo** when run under the same conditions that triggered the original incident:
   - Plain `uv run pytest tests/test_ingest_finalize.py -q` (no parent git context).
   - Under `lefthook run pre-commit` (parent git context — the original failure mode).
3. **Acceptance checks pass** (from the issue body):
   - `pytest tests/test_ingest_finalize.py` passes with the skip removed.
   - After the run: `grep -E "bare = true|test@example.com" .git/config` returns nothing.
   - After the run: `git log --format='%an' -3` shows real authors, not `Test`.
   - Lefthook's pre-commit run leaves the host repo intact.

## Out of scope

- The autouse `conftest.py` GIT_* scrub the issue mentions as "optional hardening." The memory note `feedback_subagent_git_isolation.md` flags a *separate* failure mode (`git config --local` writing into the worktree's `.git/config` even with env scrubbed). That's a real concern but a different bug class — file separately if it re-surfaces. This spec stays narrow: un-skip the two tests, verify they don't pollute.
- Refactoring the fixture style (e.g. switching from `cwd=` to `git -C` flag, as the issue body's snippet shows). The existing `cwd=` + `env=env` pattern is already correct given env scrub; the issue's snippet was written against the pre-fix file, not the current one. Don't churn the diff for cosmetic alignment.

## Risk

**Low.** The env-scrub fix is already merged. The only remaining action is deleting three lines of skip marker. The worst case is that the un-skipped tests reveal a *different* pollution mechanism (the `git config --local` path the memory note describes), in which case we re-skip with a more specific reason and file a fresh issue.

**Recovery if pollution occurs during verification:**

```
git --git-dir=<projectroot>/.git config --unset core.bare
git --git-dir=<projectroot>/.git config --remove-section user
git checkout HEAD -- .
```

The host repo can be restored without losing work. Reflog stays intact.

## Done when

- [ ] `pytestmark = pytest.mark.skip(...)` block removed from `tests/test_ingest_finalize.py`.
- [ ] Stale "Skipping until the fixture is hardened…" comment removed.
- [ ] `uv run pytest tests/test_ingest_finalize.py -q` passes locally.
- [ ] Both acceptance checks against `.git/config` and `git log` come up clean after a test run.
- [ ] Pre-flight CI (full pytest suite + any lint) green.
- [ ] PR open referencing #24 with `Closes #24`.
