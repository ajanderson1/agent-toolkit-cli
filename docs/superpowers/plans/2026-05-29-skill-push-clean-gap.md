# Plan — `skill push` clean-gap fix (#280)

Spec: `docs/superpowers/specs/2026-05-29-skill-push-clean-gap-design.md`

TDD throughout. Tests first at each task.

## Task 1 — Shared divergence-aware "what to do when clean" helper

In `push_cmd.py`, add a small private helper that both push sites call once the relevant working tree is clean, so the two paths can't drift (issue's "consider unifying" item):

```python
def _clean_action(repo: Path, ref: str) -> skill_git.Divergence:
    """Classify a clean repo's HEAD vs origin/<ref>. Reads local refs only
    (no fetch), so a committed-but-unpushed change shows as AHEAD."""
    try:
        return skill_git.divergence(repo, ref=ref, env=None)
    except skill_git.GitError:
        return skill_git.Divergence.UP_TO_DATE  # can't classify → treat as nothing-to-push
```

Rationale for the `GitError` fallback: `status_cmd._divergence_suffix` swallows the same failure to `""` (treat as up-to-date) so an un-fetched / ref-less clone never crashes the loop. Mirror that conservative stance — a clone we can't classify must not start pushing.

**Test (`test_cli_skill_push.py`):** unit-style — monkeypatch `skill_git.divergence` to raise `GitError`; assert helper returns `UP_TO_DATE`. (Keep light; the integration tests below are the real coverage.)

## Task 2 — Standalone path: push committed-but-unpushed work

Replace the standalone clean branch (push_cmd ~L99-101):

```python
if skill_git.status(canonical, env=None) == skill_git.GitWorkingTreeStatus.CLEAN:
    ref = entry.ref or "main"
    div = _clean_action(canonical, ref)
    if div is skill_git.Divergence.UP_TO_DATE:
        click.echo(f"{slug}: clean — nothing to push")
        continue
    if div in (skill_git.Divergence.BEHIND, skill_git.Divergence.DIVERGED):
        click.echo(f"{slug}: clean but {div.value} origin — not pushing")
        continue
    # AHEAD: committed-but-unpushed work to publish.
    if direct:
        _push_committed_direct(canonical, entry, slug, lock, lock_path, ref)
    else:
        _push_committed_via_pr(canonical, entry, slug, ref)
    continue
```

Add helpers mirroring `_push_direct` / `_push_via_pr` but with **no commit step** (work is already committed):

- `_push_committed_direct`: `skill_git.push(canonical, ref=ref)`; `entry.local_sha = head_sha`; `write_lock`; echo `pushed (committed-but-unpushed)`.
- `_push_committed_via_pr`: branch at current HEAD (`checkout_new_branch`), push branch, `_open_pr`, restore to base in `finally` — identical control flow to `_push_via_pr` minus `commit_all`.

**Tests (`test_cli_skill_push.py`):**
1. **Flip `test_push_clean_with_commits_ahead_drops_them`** → rename/repurpose to `test_push_clean_with_commits_ahead_pushes_them`: after `push --direct`, `HEAD == origin/main` and output contains `pushed`. (The bug is now fixed; the old assertion `"nothing to push"` is removed.)
2. New `test_push_clean_ahead_default_opens_pr_branch`: clean tree + ahead commit, default (PR) mode with gh stub → a `skill/self-improvement-*` branch on upstream carries the commit; `main` unchanged; PR URL printed.
3. Guard: `test_push_clean_up_to_date_still_noop` — genuinely up-to-date clone still prints `clean — nothing to push` (keep `test_push_clean_is_noop` doing this; add explicit divergence assertion if useful).

## Task 3 — Owned-monorepo path: push committed-but-unpushed work

Replace the monorepo clean branch (`_push_monorepo` ~L197-200):

```python
if skill_git.status_path(parent_dir, subpath, env=None) == \
        skill_git.GitWorkingTreeStatus.CLEAN:
    div = _clean_action(parent_dir, base_ref)  # base_ref computed just above? — move it up
    if div is skill_git.Divergence.UP_TO_DATE:
        click.echo(f"{slug}: clean — nothing to push")
        return
    if div in (skill_git.Divergence.BEHIND, skill_git.Divergence.DIVERGED):
        click.echo(f"{slug}: clean but {div.value} origin — not pushing")
        return
    # AHEAD: the parent clone has committed-but-unpushed work (this skill's
    # and/or a sibling's). Publish the clone's unpushed commits honestly.
    if direct:
        skill_git.push(parent_dir, ref=base_ref, env=None)
        entry.local_sha = skill_git.head_sha(parent_dir, env=None)
        write_lock(lock_path, lock)
        click.echo(f"{slug}: pushed (committed-but-unpushed → {base_ref})")
        return
    # default: PR branch at current HEAD (carries the ahead commits)
    _push_monorepo_committed_via_pr(parent_dir, entry, slug, base_ref)
    return
```

`base_ref = entry.ref or "main"` is currently computed *after* the clean check — move it above the check so the clean branch can use it.

`_push_monorepo_committed_via_pr`: branch at HEAD, push, `_open_pr`, restore to base via the **plain** checkout (preserve dirty sibling — same discipline/comment as `_push_monorepo`). No `commit_paths` — nothing to stage.

**Note on whole-clone semantics:** divergence is a whole-clone property; the ahead commits may be a sibling's. The spec's floor — "never report clean-nothing-to-push when the clone is ahead" — is satisfied by pushing the clone's unpushed commits regardless of which skill triggered it. Document this in the code comment (the `--direct` push and the PR branch both publish whatever the clone has committed ahead of origin).

**Tests (`test_skill_owned_monorepo.py`):**
1. `test_owned_push_committed_ahead_direct_pushes`: add owned mkdocs; commit an edit to the subpath in the clone (clean tree, ahead 1); `push --direct mkdocs` → output not "nothing to push", and the upstream now has the commit (`receive.denyCurrentBranch=updateInstead` is already set by `_setup_parent`). Assert clone `HEAD == origin/main` after.
2. `test_owned_push_committed_ahead_default_opens_pr` (gh hidden): same setup, default mode → `pushed branch skill/self-improvement-*`, clone restored to `main`, PR branch carries the commit.
3. Guard: `test_owned_push_clean_subpath_reports_nothing` already asserts up-to-date → "nothing to push"; keep green (it adds owned then immediately pushes with no commits → UP_TO_DATE).

## Task 4 — Verify against `status` consistency

Manual/asserted: after a committed-but-unpushed state, `skill status` says `ahead (unpushed)` and `skill push` no longer says `clean — nothing to push`. The status test `test_skill_status_monorepo_owned_ahead_unpushed` already covers the status half; the new push tests cover the push half. No new status code.

## Task 5 — Full suite + lint

`uv run pytest -q` green; ruff clean (repo uses ruff per conventions; lefthook runs pytest on pre-commit). Confirm no other test asserted the old buggy `"nothing to push"` for an ahead clone (grep).

## Risk / edge notes

- `divergence()` does not fetch — correct here; we want "ahead of last-known origin", and an unpushed commit is always ahead regardless of fetch freshness.
- A clone with **no** `origin/<ref>` (e.g. detached / missing remote-tracking ref) makes `git rev-list HEAD...origin/<ref>` fail → `GitError` → `_clean_action` returns `UP_TO_DATE` → falls back to today's "nothing to push". Acceptable: a repo whose origin ref can't be resolved is not a safe push target, and this matches `status`'s swallow-to-empty stance.
- Monorepo PR-branch restore must stay a **plain** checkout (not `-f`) to preserve a dirty sibling — reuse the existing comment.
