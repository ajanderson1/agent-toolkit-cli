# Spec: pytest autouse fixture to scrub GIT_* env across the test suite

Closes #209.

## Background

PR #206 fixed the symptom in `tests/test_cli/test_skill_git.py`: a regression test shelling out to `git commit` from inside `pytest` (running under lefthook pre-commit) inherited `GIT_DIR` / `GIT_INDEX_FILE` from the lefthook parent, and silently wrote a stray commit (`b2bb7eb` by `t <t@t>`) into the outer agent-toolkit-cli repo. The narrow fix was to explicitly pass `env=scrub_git_env(...)` to every `subprocess.run([...])` in that test.

That fixed one test. The repo still has 11 other test files (96 raw `subprocess.run(["git", ...])` call sites in `tests/`) where the same trap is one new test away from re-firing. Test authors must currently remember to scrub on every new subprocess call. The recommended path in the issue (option 1) is an autouse fixture in `tests/conftest.py` that strips `GIT_*` from `os.environ` for the duration of every test, so the trap closes by default.

## Goal

When pytest runs — regardless of how it is invoked (direct, lefthook, CI, agent harness) — `os.environ` inside every test is scrubbed of `GIT_*` variables before the test runs. Tests that shell out to git inherit a clean env automatically. The lefthook-pre-commit path that originally triggered #197's bad commit becomes physically impossible without an explicit opt-in.

## Approach

### 1. Autouse fixture in `tests/conftest.py`

Add a module-level autouse fixture that runs for every test:

```python
@pytest.fixture(autouse=True)
def _scrub_git_env_from_os_environ(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip inherited GIT_* env vars from os.environ for every test.

    Closes the lefthook-leak trap (#209). Without this fixture, a test that
    runs under `lefthook pre-commit` would inherit GIT_DIR / GIT_INDEX_FILE
    from the parent git process and silently write commits into the outer
    repo. With it, subprocess.run(["git", ...]) inherits a clean env by
    default — the original symptom that produced PR #206 cannot recur.
    """
    for var in list(os.environ):
        if var.startswith("GIT_"):
            monkeypatch.delenv(var, raising=False)
```

- **`monkeypatch.delenv` over a direct dict mutation:** monkeypatch restores `os.environ` at test teardown, so the fixture is non-destructive across tests and across pytest sessions sharing a process.
- **autouse + module-level:** applied to every test under `tests/`; no test author opt-in required.
- **Behavioral contract:** the fixture changes `os.environ` *only*. Tests that already pass an explicit `env=` (like the regression test for #197) are unaffected — their env dict is constructed independently. Tests that omit `env=` and rely on inheritance now get a scrubbed view of the host env.

### 2. Regression test that proves the fixture works

Add `tests/test_conftest_git_env_scrub.py` with two tests:

- **`test_os_environ_has_no_git_vars_in_tests`** — assert at test time that `os.environ` contains no key starting with `GIT_`. Trivial, but it locks the behavior: removing the autouse fixture immediately turns this red on any host that exports `GIT_*` (e.g. running under `lefthook` or `git rebase -x`).
- **`test_subprocess_inherits_clean_git_env`** — set a sentinel like `GIT_DIR=/does/not/exist` *before* the test starts, then verify the autouse fixture has scrubbed it before the test body runs. (Use `pytest.MonkeyPatch.context()` outside the autouse-managed scope, or set the var via `os.environ` in a module-level setup and confirm the fixture wins.)

Together these guarantee: the fixture exists, it runs first, and it removes `GIT_*` from the env the test sees.

### 3. Update existing `git_sandbox` fixture

`git_sandbox` currently calls `scrub_git_env()` itself to build its env dict. After the autouse fixture lands, `scrub_git_env(os.environ)` and `dict(os.environ)` produce the same result (no `GIT_*` keys present). Keep the explicit call — it's defense-in-depth and documents intent. Add a one-line comment noting that the autouse fixture is the first line of defense.

### 4. Document in AGENTS.md

One paragraph under a new `## Testing` section explaining the autouse fixture, what it does, and the implication for test authors:

> Every test runs with `GIT_*` env vars stripped from `os.environ`. This is enforced by an autouse fixture in `tests/conftest.py` and closes the lefthook-leak trap from #209. Test authors do **not** need to pass `env=scrub_git_env(...)` to `subprocess.run([...])` to be safe — `os.environ` is already clean. Continue to pass an explicit `env=` only when a test needs to **set** GIT_AUTHOR_NAME/EMAIL or similar (i.e. when the test is asserting on identity), not when it merely needs to **prevent leakage**.

### What this spec does NOT do

- **Does not** add a `run_git_subprocess()` helper (issue option 2). Premature abstraction; the autouse fixture closes the trap at its root and no caller in tests needs the indirection.
- **Does not** add a lint rule (issue option 3). Once the autouse fixture is in place, the bare `subprocess.run(["git", ...])` pattern is **correct** in tests — there's nothing to lint against.
- **Does not** scrub at the production-code level. `agent_toolkit_cli/skill_git.py` is unchanged. Production code is already hardened where it matters (PR #189, PR #206); this spec is purely about the test surface.
- **Does not** touch lefthook config. Hook timing is the *trigger*; the fixture closes the *vulnerability*. Touching lefthook would just move the bug around.

## Acceptance

- [ ] `tests/conftest.py` exports the autouse fixture.
- [ ] `tests/test_conftest_git_env_scrub.py` exists and passes.
- [ ] Existing tests still pass (`uv run pytest -q`).
- [ ] `AGENTS.md` documents the fixture under a `## Testing` section.
- [ ] A test author writing `subprocess.run(["git", "commit", ...], cwd=tmp_path)` (no `env=`) no longer writes into the host repo when pytest runs under lefthook.

## Notes

- **Why monkeypatch over os.environ.pop:** pytest's `monkeypatch` fixture restores env at teardown. A direct `os.environ.pop` would leak across tests within the same session and persist if pytest crashed.
- **Interaction with `--collect-only` / xdist:** autouse fixtures fire per test item, not per worker. `pytest-xdist` workers fork a clean Python process, so each worker sees the parent env once at startup; the fixture then runs per test as expected.
- **No `--force` to opt out.** A test that genuinely needs `GIT_DIR` in its env should set it via `monkeypatch.setenv("GIT_DIR", ...)` inside the test body — `monkeypatch` undoes that at teardown, so the next test still gets a clean env.
