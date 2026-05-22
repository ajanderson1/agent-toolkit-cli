# Spec — `commit_all()` latent identity-missing bug (#197)

## Problem

`skill_git.commit_all()` invokes `git commit -m <message>` without injecting a synthetic `user.name` / `user.email`. On hosts with no global git identity (CI runners, fresh dev VMs, agent sandboxes) it dies with:

```
fatal: empty ident name (for <runner@...>) not allowed
```

PR #189 already fixed the equivalent failure mode for `skill_git.merge()` by passing `-c user.name=… -c user.email=…` through a module-level `_DEFAULT_MERGE_IDENTITY` constant. `commit_all()` was not updated in the same pass, so the bug remains latent — the only caller today (`skill push`) isn't on the typical CI surface, so nobody has hit it yet. The first user who runs `skill push` from a no-identity host will.

## Goal

Make `commit_all()` succeed on hosts without a global git identity, matching the behaviour established by `merge()` in #189.

## Approach

1. **Rename** `_DEFAULT_MERGE_IDENTITY` → `_DEFAULT_IDENTITY` (the constant now serves more than just `merge()`).
2. **Apply** `*_DEFAULT_IDENTITY` to the `git commit` invocation inside `commit_all()`. The `git add -A` call above it does not need it (no commit produced).
3. **Update** `merge()`'s docstring to reflect the broader scope (mention `commit_all()` as the second caller).
4. **Add a regression test** under `tests/test_cli/test_skill_git.py` that strips `HOME` + every `GIT_*` env var (mirroring `test_update_monorepo_merges_without_global_git_identity`) and asserts:
   - `commit_all()` succeeds.
   - The resulting commit is authored by `agent-toolkit-cli <noreply@agent-toolkit-cli>` (locks in the synthetic-identity contract — robust against `/etc/gitconfig` variation on other hosts).

## Explicit non-goals

- **Probe-first detection** ("only inject when host has no identity"). Current always-inject is intentional; `GIT_AUTHOR_*` / `GIT_COMMITTER_*` env vars take precedence per git's documented rules, so callers who need to override still can.
- **Auditing other `_run` call sites**. `clone`, `fetch`, `reset_hard`, `pull_ff_only`, `status`, `push`, `head_sha`, `remote_head_sha` don't produce commits, so identity isn't required.
- **Changes to `push_cmd.py`** or any caller. The fix is entirely inside `skill_git.py`.

## Acceptance

- `_DEFAULT_IDENTITY` exists at module scope; `_DEFAULT_MERGE_IDENTITY` no longer exists.
- `commit_all()` uses `*_DEFAULT_IDENTITY` in its `git commit` call.
- `merge()` still uses the same constant under the new name.
- New regression test passes locally with no global git identity (HOME redirected, GIT_* stripped).
- Existing test suite stays green; no other behavioural changes.

## Origin

Surfaced during the PR #189 self-review (maintainability, correctness, agent-native reviewers). Issue: https://github.com/ajanderson1/agent-toolkit-cli/issues/197
