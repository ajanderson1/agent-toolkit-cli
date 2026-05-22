# skill push — PR-branch default · implementation plan

**Spec:** [`docs/superpowers/specs/2026-05-22-skill-push-pr-branch-default-design.md`](../specs/2026-05-22-skill-push-pr-branch-default-design.md)
**Issue:** [#221](https://github.com/ajanderson1/agent-toolkit-cli/issues/221)

## File touch list

| File | Change |
|---|---|
| `src/agent_toolkit_cli/skill_git.py` | Add helpers: `checkout_new_branch`, `current_branch`, `push_new_branch` (or generalise `push` to accept `set_upstream`). Keep `_run` env scrubbing intact. |
| `src/agent_toolkit_cli/commands/skill/push_cmd.py` | Branch on `--direct`. Default path: new branch → commit → push → `gh pr create` or fallback hint. Direct path: existing behaviour. |
| `tests/test_cli/test_cli_skill_push.py` | New cases per spec table. Mock `gh` via PATH stub. Existing tests adjusted to use `--direct` where they assert direct-to-ref push. |
| `tests/conftest.py` | No change expected. The `git_sandbox` upstream is a bare repo, already accepts new branches. |

No changes to `skill_lock.py` — schema is already permissive enough; we just stop writing `local_sha` on the default path.

No changes to `docs/agent-toolkit/cli.md` yet — wait until tests pass, then update the `push` section's blurb. Doc sync is a small final commit, not blocking on test green.

## Step-by-step

### 1. `skill_git.py` helpers

Add two narrow helpers; no generalisation of existing functions:

```python
def checkout_new_branch(
    repo: Path, *, name: str, env: dict[str, str] | None,
) -> GitResult:
    """`git checkout -b <name>`. Caller ensures the working tree is in
    the right starting state."""
    proc = _run(
        ["git", "-C", str(repo), "checkout", "-b", name], env=env,
    )
    return GitResult(stdout=proc.stdout, stderr=proc.stderr)


def current_branch(repo: Path, *, env: dict[str, str] | None) -> str:
    proc = _run(
        ["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"],
        env=env,
    )
    return proc.stdout.strip()
```

`push()` already takes a `ref` — calling `push(repo, ref=<new-branch>, env=...)` after a checkout pushes the new branch. Git's default behaviour for a first-time push of a new branch to origin matches what we want; no `--set-upstream` needed for this workflow because the PR is the contract, not the upstream tracking.

Actually — re-checking — `git push origin <branch>` for a never-pushed branch works without `-u`. The branch is created on the remote. `-u` is only needed if subsequent invocations want `git pull` shorthand, which `push_cmd` doesn't use. Keep it simple: no `--set-upstream`.

### 2. `push_cmd.py` — wire the branch

Wrap the existing per-slug body in an outer branch on `direct`. Pseudo-code:

```python
@click.command("push", epilog=...)
@click.argument("slugs", nargs=-1)
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.option("--direct", is_flag=True,
              help="Push directly to the tracked ref. Default opens a PR.")
@click.pass_context
def push_cmd(ctx, slugs, global_, project_flag, direct):
    ...
    for slug in targets:
        ...
        if direct:
            _push_direct(canonical, entry, slug, lock, lock_path)
        else:
            _push_via_pr(canonical, entry, slug)
```

`_push_direct(...)` is the body of the current loop — extract verbatim, no behaviour change. `_push_via_pr(...)` is new:

```python
def _push_via_pr(canonical, entry, slug):
    branch = f"skill/self-improvement-{_utc_basic_iso()}"
    skill_git.checkout_new_branch(canonical, name=branch, env=None)
    msg = f"self-improvement: {_utc_iso()}"
    skill_git.commit_all(canonical, message=msg, env=None)
    skill_git.push(canonical, ref=branch, env=None)
    pr_url = _open_pr_or_hint(canonical, branch, base=entry.ref or "main")
    click.echo(f"{slug}: pushed branch {branch}")
    if pr_url:
        click.echo(f"  PR: {pr_url}")
    else:
        web = _branch_web_url(canonical, branch)
        if web:
            click.echo(f"  → open a PR: {web}")
        click.echo(f"  (rerun with --direct to push to {entry.ref or 'main'})")
```

Helpers added to `push_cmd.py` itself (kept private — only this command needs them):

- `_utc_basic_iso()` → `datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")`.
- `_utc_iso()` → `datetime.now(UTC).isoformat()` (same as today).
- `_gh_available()` → `shutil.which("gh") is not None and subprocess.run(["gh","auth","status"], capture_output=True).returncode == 0`.
- `_open_pr_or_hint(repo, branch, *, base) -> str | None` → returns PR URL on success, None on any failure path (no gh, gh not authed, gh errored).
- `_branch_web_url(repo, branch) -> str | None` → parse `git remote get-url origin`, derive `https://github.com/<owner>/<repo>/tree/<branch>`. Returns None for non-GitHub remotes.

The `_gh_available()` + `_open_pr_or_hint` split keeps the test seam clean: tests can monkeypatch one boundary and exercise both paths.

### 3. After the PR push: do NOT update `local_sha`

The current code writes `entry.local_sha = skill_git.head_sha(...)` after push. In `_push_via_pr` we **skip** this — the tracked ref hasn't moved, so the recorded SHA shouldn't either. A subsequent `skill update` will fetch the merged commit normally.

In `_push_direct` we keep the existing write.

### 4. Tests

New file structure mirrors existing `test_cli_skill_push.py`. Each test follows the established pattern: `git_sandbox` fixture, `_add_and_install_project` helper, dirty-up the skill, invoke `skill push`, assert.

`gh` stub recipe (for the PR-success path):

```python
def _install_gh_stub(tmp_path, monkeypatch, *, success=True, pr_url=...):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    gh = bin_dir / "gh"
    if success:
        gh.write_text(
            "#!/bin/sh\n"
            "case \"$1\" in\n"
            "  auth) exit 0;;\n"
            f"  pr)   echo {pr_url}; exit 0;;\n"
            "esac\n"
        )
    else:
        gh.write_text("#!/bin/sh\nexit 1\n")
    gh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
```

Tests:

1. **`test_push_default_opens_pr_branch`** — install stub gh returning a PR URL; dirty the skill; run `skill push demo -p`. Assert exit 0; assert `skill/self-improvement-` branch exists on upstream (via a side-channel `git ls-remote --heads`); assert the upstream's `main` did NOT advance; assert PR URL appears in stdout; assert `entry.local_sha` is unchanged in the lock.

2. **`test_push_default_without_gh_prints_branch_hint`** — install a stub that exits 1 from `auth status` (or remove gh from PATH entirely). Run `skill push demo -p`. Assert exit 0; assert pushed branch exists on upstream; assert stdout contains the branch name; assert stdout contains "open a PR".

3. **`test_push_direct_pushes_to_tracked_ref`** — preserves the contract of the current `test_push_publishes_local_edits`. Use `--direct`; assert upstream `main` advanced and contains the change.

4. **`test_push_direct_updates_lockfile_local_sha`** — pair test: after `--direct`, lock's `local_sha` is the new HEAD; after the default path (covered by test 1's assertion), it is unchanged.

5. **`test_push_clean_is_noop`** — keep as-is, both default and `--direct` honour the early-return.

6. **`test_push_monorepo_rejection_unchanged`** — rejection still fires under `--direct`. Add a one-liner assertion to `test_skill_push_monorepo.py` (or extend its existing case).

7. **`test_push_does_not_leak_into_outer_repo`** — keep as-is; works under either path. Add a paired version that runs with `--direct` to be explicit.

`test_cli_skill_push.py` may grow ~150 lines. Acceptable.

### 5. Doc sync (last commit)

After tests pass, update `docs/agent-toolkit/cli.md` `skill push` section (if present — verify) and `README.md` if it documents `skill push` defaults. The `--help` epilog in `push_cmd.py` also gets a one-line "by default opens a PR; use --direct to push to the tracked ref" line.

## Sequencing

Per `superpowers:subagent-driven-development`, the natural slice is:

1. **Skill-git helpers + unit test for `checkout_new_branch` / `current_branch`.** Smallest landable slice.
2. **`push_cmd` refactor + gh stub fixture.** New `_push_via_pr` path + helpers + test 1 (PR success).
3. **Fallback path.** Test 2 (no gh).
4. **`--direct` flag wiring + tests 3 + 4 + 6.** Old tests adjusted.
5. **Lockfile semantics test.** Test 4.
6. **Doc + help text.** Last commit.

Slices 1–3 are independent of 4–6 only in name — they all touch `push_cmd.py`. Sequencing matters; do them in order, one commit per slice or one combined commit if the slices are trivially small. No parallel subagents — the file overlap is too tight.

## Verification recipe

`.claude/testing.md` not present (verified — checked at flow Step 9 dispatch). Fall back to `verify.sh` (not present either). Final fallback: terminal recipe.

Recipe: `uv run agent-toolkit-cli skill push --help` — assert exit 0 and that the help text mentions `--direct`. Capture to `assets/verification/221/skill-push-help.log`.

This is the lightest possible smoke test for a CLI verb fix. The real safety net is the new pytest cases.

## Out of scope

- No new `--draft` flag. The PR is opened ready-for-review by default; if the user wants a draft, they can flip it in the GitHub UI.
- No `--label` / `--assignee` plumbing. Could be added later if there's real demand.
- No `--no-pr` alias for `--direct`. One flag, one name.

## Risk and rollback

The behaviour change is opt-out via a single flag. If a downstream automation breaks (it shouldn't — `skill push` is interactive), rollback is a one-line edit to the default of `direct` (`is_flag=True` → `default=True`). Easy.

The lockfile semantics shift (default path no longer writes `local_sha`) could surprise a user who scripts against `skill status` after `skill push`. Mitigation: the default path prints the branch name and PR URL — a user reading stdout sees the divergence immediately. A user who automates this workflow already needs to add `--direct` to keep working, which makes the semantics consistent.
