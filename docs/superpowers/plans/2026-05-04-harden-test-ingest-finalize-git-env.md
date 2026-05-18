# Plan: Un-skip tests/test_ingest_finalize.py

**Spec:** `docs/superpowers/specs/2026-05-04-harden-test-ingest-finalize-git-env-design.md`
**Issue:** #24
**Branch:** `chore/24-harden-test-ingest-finalize-git-env`

## Tasks

### 1. Remove the skip marker

**File:** `tests/test_ingest_finalize.py`
**Lines:** 9-18 (the explanatory comment block plus the `pytestmark = pytest.mark.skip(...)` call).

**Before:**

```python
"""Tests for ingest FINALISE."""
import os
import subprocess

import pytest

from agent_toolkit_cli.ingest.types import Proposal

# These tests run `git init` + `git config user.email/name` + `git commit` in
# subprocesses with cwd=tmp_path. When the host repo is a parent of tmp_path,
# git's parent-walk can land on the host's `.git/`, polluting `.git/config`
# with `[user] test@example.com` and (somehow) `bare = true`, and writing real
# commits onto the host's current branch as `Test <test@example.com>`. This
# breaks every subsequent git op on the host repo. Skipping until the fixture
# is hardened to use isolated GIT_DIR. Filed as follow-up on issue #9.
pytestmark = pytest.mark.skip(
    reason="leaks git config and rogue commits to host repo; see issue #9 follow-up"
)
```

**After:**

```python
"""Tests for ingest FINALISE."""
import os
import subprocess

from agent_toolkit_cli.ingest.types import Proposal
```

`import pytest` is removed too — once the `pytestmark` line is gone, nothing else in the file references `pytest.*`. `os` and `subprocess` stay (used by `_git_env`, `_init_git_repo`, the inline subprocess calls).

### 2. Run the now-un-skipped tests in isolation

```bash
uv run pytest tests/test_ingest_finalize.py -q
```

Expected: 2 passed, 0 skipped. Both tests already had complete env-scrub via `_git_env()` (the helper introduced in PR #14); removing the skip simply lets them run.

### 3. Verify no host-repo pollution after the run

In the worktree directory after the test run:

```bash
grep -E "bare = true|test@example.com" .git/config
```

Expected: no output (exit 1 — grep finds nothing).

```bash
git log --format='%an' -3
```

Expected: real author name, not `Test`.

### 4. Run the full suite + lefthook simulation

```bash
uv run pytest -q
```

Expected: same green, two fewer skips than before (was `319 passed, 2 skipped`; now should be `321 passed, 0 skipped`).

Then commit the change — the commit hook itself runs `uv run pytest -q` via lefthook, which is the **exact** scenario that originally broke. If the commit succeeds and post-commit `git status` is clean, the un-skip is safe.

### 5. Belt-and-braces verification (Step 9 of flow.md)

After commit, in the worktree's `.git/config` from the parent repo's perspective, also confirm:

```bash
git --git-dir=$PWD/../../.git config --get core.bare
git --git-dir=$PWD/../../.git config --get-all user.email
```

The first should return nothing (no `core.bare` flipped). The second should return only the user's real email or nothing (no `test@example.com`).

## Rollback

If verification fails (host repo polluted), the recovery from `feedback_subagent_git_isolation.md` applies:

```bash
git --git-dir=<projectroot>/.git config --unset core.bare
git --git-dir=<projectroot>/.git config --remove-section user
git checkout HEAD -- .
```

…then re-instate the skip with a more specific reason and file a fresh issue scoped to the residual pollution mechanism. The spec already calls out this contingency.

## What this plan deliberately does NOT do

- **No conftest.py autouse fixture** to scrub `GIT_*` for the whole suite. That's the issue's "optional hardening" callout. If it's needed, it's a separate change.
- **No fixture refactor** from `cwd=tmp_path` to `git -C tmp_path`. The issue's snippet was written against the pre-fix file. The current code is already correct.
- **No removal of `_git_env()` helper** even though it's now used by only one file. Deleting helpers that defend against a known recurring bug class is a regression magnet. Leave it.
- **No promotion of `_git_env()` to `conftest.py` autouse**. Note: `_git_env()` only addresses the GIT_*-env-override mechanism. The sibling failure mode in `feedback_subagent_git_isolation.md` — `git config --local` writing into the worktree's `.git/config` even with env scrubbed — is a different mechanism env-scrub does not catch. If that resurfaces, file a fresh issue for the autouse-fixture work the issue body called "optional hardening."

## Definition of done

All boxes from the spec's "Done when" list checked, plus the plan's verification steps clean.
