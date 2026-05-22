# Plan: pytest autouse GIT_* env scrub

Spec: `docs/superpowers/specs/2026-05-22-pytest-git-env-autouse-design.md` · Issue #209 · Mode `--ship-it`.

Tiny, single-file change with one new test file and one doc paragraph. No parallel subagents; linear and short.

## Task 1 — Add autouse fixture to `tests/conftest.py`

**Files:** `tests/conftest.py`

**Change:** Inside the existing file, add — at module scope, after the imports and the `scrub_git_env` helper, before the `git_sandbox` fixture — a new autouse pytest fixture:

```python
@pytest.fixture(autouse=True)
def _strip_git_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip inherited GIT_* env vars from os.environ for every test.

    Closes #209 — prevents lefthook-leak when a test shells out to git
    without an explicit env= argument. monkeypatch restores env at teardown.
    """
    for var in [k for k in os.environ if k.startswith("GIT_")]:
        monkeypatch.delenv(var, raising=False)
```

Note the **leading underscore** in the fixture name — pytest still discovers it (autouse fixtures are matched on the `@pytest.fixture(autouse=True)` decorator, not the name), and the underscore signals "fixture, but tests don't refer to it by name."

**Verify:** `uv run pytest tests/conftest.py --collect-only` returns 0; the existing test suite still collects.

## Task 2 — Add regression test `tests/test_conftest_git_env_scrub.py`

**Files:** `tests/test_conftest_git_env_scrub.py` (new)

**Change:** Two tests, no fixture dependencies:

```python
"""Regression tests for the autouse GIT_* env scrub fixture (#209)."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


def test_os_environ_has_no_git_vars() -> None:
    """The autouse fixture must remove all GIT_* keys from os.environ."""
    leaked = [k for k in os.environ if k.startswith("GIT_")]
    assert leaked == [], (
        f"Autouse fixture failed to scrub GIT_* env vars: {leaked}. "
        "See tests/conftest.py and docs/superpowers/specs/2026-05-22-pytest-git-env-autouse-design.md."
    )


def test_subprocess_git_inherits_clean_env(tmp_path: Path) -> None:
    """A bare subprocess.run(['git', ...]) with no env= must not see
    GIT_* from the parent. This is the lefthook-leak scenario.

    We don't simulate lefthook (that would require nested git invocations).
    We simply verify that env-less subprocess.run inherits os.environ,
    which the autouse fixture has cleaned. If a future change re-introduces
    the leak by removing the fixture, this test fails because the parent
    will have GIT_* set (under lefthook) and the child will see it.
    """
    # Initialise a throwaway repo so `git rev-parse` succeeds.
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "init", "-q", "-b", "main", str(tmp_path)],
        check=True, capture_output=True,
    )
    # Ask git for its view of the environment. printenv inside `git` is
    # cumbersome; easier: confirm the subprocess.run env (which inherits
    # from os.environ) is GIT_*-free.
    proc = subprocess.run(
        ["env"], capture_output=True, text=True, check=True,
    )
    leaked = [line for line in proc.stdout.splitlines() if line.startswith("GIT_")]
    assert leaked == [], (
        f"Subprocess inherited GIT_* env vars from parent: {leaked}"
    )
```

**Verify:** `uv run pytest tests/test_conftest_git_env_scrub.py -v` → both tests pass.

**Also verify the negative path manually:** temporarily set `GIT_DIR=/tmp/sentinel` in the shell, run pytest, confirm the test *still* passes (proving the autouse fixture cleaned it). Then remove the autouse fixture from `conftest.py` and re-run with `GIT_DIR=/tmp/sentinel` set → confirm the test now fails. Restore the fixture afterwards. Record both observations in `assets/verification/209/flow.log`.

## Task 3 — Document in `AGENTS.md`

**Files:** `AGENTS.md`

**Change:** Insert a `## Testing` section after the existing `## Development workflow` section (and before `## Adding a new \`skill\` subcommand`). Body:

```markdown
## Testing

`tests/conftest.py` includes an autouse fixture that strips `GIT_*` env vars
from `os.environ` before every test runs. This closes the lefthook-leak
trap (#209): a test that shells out to `git` without an explicit `env=`
argument no longer inherits `GIT_DIR` / `GIT_INDEX_FILE` from a parent
hook and cannot accidentally write commits into the outer repo.

For most tests this means `subprocess.run(["git", ...], cwd=tmp_path)`
is now safe by default. Pass an explicit `env=` only when the test needs
to **set** identity vars (e.g. `GIT_AUTHOR_NAME` for a deterministic
commit) — not when it merely needs to **prevent leakage**.
```

**Verify:** `head -60 AGENTS.md` shows the new section in the correct position.

## Task 4 — Smoke-run the full suite

`uv run pytest -q` from the worktree. Expectation: green. Capture to `assets/verification/209/pytest-full.log`.

If anything red: investigate. The autouse fixture is additive and shouldn't break existing tests, but a test that asserts on the presence of `GIT_*` in its own env would. None found in the audit; flag if discovered.

## Out of scope

- No changes to `agent_toolkit_cli/skill_git.py` or any production code.
- No changes to `lefthook.yml`.
- No subprocess helper module.
- No lint rules.
- No edits to the existing `git_sandbox` fixture (the `scrub_git_env()` call inside it remains as defense-in-depth and a self-documenting marker).

## Risks

- **Test pollution:** if pytest is run with `-p no:cacheprovider` or in a way that bypasses fixture teardown, the env scrub still works (monkeypatch is part of pytest core, not the cache plugin).
- **xdist:** workers fork before pytest collects; the autouse fixture runs per item inside each worker, which is correct.
- **Ordering edge case:** if another autouse fixture sets a `GIT_*` var before `_strip_git_env` runs, the scrub would wipe it. None exist today; document the precedence in the spec.
