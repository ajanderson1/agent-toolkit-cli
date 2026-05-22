# Plan — `commit_all()` latent identity-missing bug (#197)

See `../specs/2026-05-22-commit-all-latent-identity-bug-design.md`.

This is a single-file source change plus a single new regression test. No worktree-level orchestration needed.

## Tasks

### T1 — Rename and broaden the identity constant in `skill_git.py`

**File:** `src/agent_toolkit_cli/skill_git.py`

1. Rename `_DEFAULT_MERGE_IDENTITY` → `_DEFAULT_IDENTITY` (single ident; all references in this file).
2. Move the constant up one section so it precedes both `merge()` and `commit_all()` (currently it sits between `fetch()` and `merge()`; either keep it there or hoist closer to `_IDENTITY_ALLOWLIST` — either is fine, but it must stay above its first user).
3. Update `merge()`'s docstring to mention `commit_all()` as the second consumer, so future readers don't think it's merge-specific.

**Verify:** `grep _DEFAULT_MERGE_IDENTITY src/ tests/` returns nothing; `_DEFAULT_IDENTITY` has at least two `*_DEFAULT_IDENTITY` use sites after T2.

### T2 — Apply `_DEFAULT_IDENTITY` to `commit_all()`

**File:** `src/agent_toolkit_cli/skill_git.py`

The `commit_all()` body currently does:

```python
_run(["git", "-C", str(repo), "add", "-A"], env=env)
proc = _run(
    ["git", "-C", str(repo), "commit", "-m", message], env=env,
)
```

Change the **second** `_run` call to inject the synthetic identity, matching `merge()`:

```python
_run(["git", "-C", str(repo), "add", "-A"], env=env)
proc = _run(
    ["git", "-C", str(repo), *_DEFAULT_IDENTITY,
     "commit", "-m", message],
    env=env,
)
```

The `git add -A` call stays unmodified — it doesn't produce a commit and so doesn't read identity.

Update `commit_all()`'s docstring to note the synthetic identity (one sentence — match the tone of `merge()`'s docstring).

### T3 — Regression test: `commit_all()` succeeds without a global git identity

**File:** `tests/test_cli/test_skill_git.py`

Add `test_commit_all_succeeds_without_global_git_identity`. Pattern: `test_update_monorepo_merges_without_global_git_identity` in `tests/test_cli/test_skill_update_monorepo.py:254`.

Test must:

1. Use `tmp_path` + `monkeypatch` (no `git_sandbox` — that fixture injects `GIT_AUTHOR_*` and would mask the bug). Build a minimal local repo with a single seed commit.
2. Redirect `HOME` to an empty directory.
3. Strip every identity-relevant env var: `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME`, `GIT_COMMITTER_EMAIL`, `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_SYSTEM`.
4. Stage a new file in the repo (write a working-tree change).
5. Call `commit_all(repo, message="…", env=None)`.
6. Assert it succeeds — no `GitError` — and `git log -1 --format=%an <%ae>` returns exactly `agent-toolkit-cli <noreply@agent-toolkit-cli>`. The author-assertion locks in the synthetic-identity contract and is robust against hosts that have `/etc/gitconfig` set (without it, such a host would silently green the test even if the fix were reverted).

**Seed step:** the test creates the initial commit using inline `-c user.email=t@t -c user.name=t` flags (same approach as `test_update_monorepo_merges_without_global_git_identity`). Only the `commit_all()` call under test runs without identity.

## Out of scope

- Don't touch `push_cmd.py` or any other caller.
- Don't probe for existing identity. Always-inject is the deliberate design.
- Don't add fixtures to `conftest.py` — keep the test self-contained.

## Verification

- `uv run pytest tests/test_cli/test_skill_git.py -x` passes (new test + existing `test_commit_all_*` tests).
- `uv run pytest` (full suite) passes — no other tests reference `_DEFAULT_MERGE_IDENTITY` by name; rename should be transparent.
- `uv run ruff check src tests` clean.
