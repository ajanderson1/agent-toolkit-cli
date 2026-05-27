# Owned-Monorepo Capability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a monorepo owned by AJ (`ajanderson1/*` or `--owned`) writable — `skill add` records it without `read_only`, `skill push` opens subpath-scoped PRs against the parent, `skill status` shows subpath-scoped dirty state, while read-only consumption of others' monorepos still refuses push.

**Architecture:** Additive, inside the existing lockfile-SSOT + `_parents/<owner>/<repo>/` shared-clone + symlink-projection model. A new pure `is_owned_owner()` helper drives ownership; owned monorepo lock entries carry `read_only=False`. `skill push`/`status` branch on `parent_url is not None and not read_only` to take subpath-scoped git paths, reusing existing `skill_git` patterns with two new pathspec-scoped helpers (`commit_paths`, `status_path`).

**Tech Stack:** Python 3.13, Click, pytest, `CliRunner`, `subprocess` git via `skill_git` (always `env=`-scrubbed per the #209 trap).

---

## File Structure

- **Create** `src/agent_toolkit_cli/skill_ownership.py` — one pure helper `is_owned_owner(owner) -> bool` + the `OWNED_OWNERS` constant. Tiny, single-responsibility, trivially testable, and the one place to extend ownership later.
- **Modify** `src/agent_toolkit_cli/skill_git.py` — add `commit_paths()` and `status_path()` (pathspec-scoped commit + status), mirroring the existing `commit_all()`/`status()` patterns.
- **Modify** `src/agent_toolkit_cli/commands/skill/__init__.py` — `--owned` flag on `add`; thread `owned` into `_add_monorepo`; compute `read_only` from ownership.
- **Modify** `src/agent_toolkit_cli/commands/skill/push_cmd.py` — owned-monorepo push branch (`_push_monorepo_via_pr` + `_push_monorepo_direct`).
- **Modify** `src/agent_toolkit_cli/commands/skill/status_cmd.py` — owned-monorepo subpath-scoped status + `(owned)` marker.
- **Create** `tests/test_cli/test_skill_ownership.py` — unit tests for `is_owned_owner`.
- **Create** `tests/test_cli/test_skill_git_pathspec.py` — unit tests for `commit_paths`/`status_path`.
- **Create** `tests/test_cli/test_skill_owned_monorepo.py` — integration tests for add/push/status/update on an owned `file://` monorepo + the regression guard.
- **Existing, must stay green unchanged:** `tests/test_cli/test_skill_push_monorepo.py` (the read-only refusal).

A shared `file://` parent fixture builder is needed by the integration tests. Reuse the pattern in `test_skill_push_monorepo.py::_setup_monorepo_parent` (copy `tests/fixtures/monorepo_skills`, `git init`, commit, set `AGENT_TOOLKIT_SKILLS_ROOT`). Task 4 defines a local copy of that helper inside the new test module rather than importing across test files.

---

## Task 1: Ownership helper

**Files:**
- Create: `src/agent_toolkit_cli/skill_ownership.py`
- Test: `tests/test_cli/test_skill_ownership.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli/test_skill_ownership.py
"""is_owned_owner: which monorepo parents are writable-by-default."""
from agent_toolkit_cli.skill_ownership import OWNED_OWNERS, is_owned_owner


def test_ajanderson1_is_owned():
    assert is_owned_owner("ajanderson1") is True


def test_owner_match_is_case_insensitive():
    assert is_owned_owner("AJAnderson1") is True


def test_other_owner_is_not_owned():
    assert is_owned_owner("anthropics") is False
    assert is_owned_owner("mattpocock") is False


def test_synthetic_local_owner_is_not_owned():
    # file:// sources synthesise owner "local"; not owned without --owned.
    assert is_owned_owner("local") is False


def test_owned_owners_constant_seeded():
    assert "ajanderson1" in OWNED_OWNERS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd .worktrees/feat-258-owned-monorepo-capability && uv run pytest tests/test_cli/test_skill_ownership.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_toolkit_cli.skill_ownership'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/agent_toolkit_cli/skill_ownership.py
"""Which monorepo parents are owned (writable) by default.

A monorepo is "owned" when its parent remote owner is in OWNED_OWNERS, or
when the user passes --owned to `skill add`. Owned monorepo lock entries are
written WITHOUT read_only, so `skill push` opens PRs against the parent
instead of refusing. This is the one place to extend ownership later.
"""
from __future__ import annotations

# Lower-cased GitHub owner logins that AJ authors skills under. Ownership is
# matched case-insensitively against this set.
OWNED_OWNERS: frozenset[str] = frozenset({"ajanderson1"})


def is_owned_owner(owner: str) -> bool:
    """True if `owner` is an owned (writable-by-default) monorepo parent owner."""
    return owner.lower() in OWNED_OWNERS
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd .worktrees/feat-258-owned-monorepo-capability && uv run pytest tests/test_cli/test_skill_ownership.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/skill_ownership.py tests/test_cli/test_skill_ownership.py
git commit -m "feat(258): is_owned_owner ownership helper"
```

---

## Task 2: Pathspec-scoped git helpers

**Files:**
- Modify: `src/agent_toolkit_cli/skill_git.py` (add two functions near `commit_all`/`status`)
- Test: `tests/test_cli/test_skill_git_pathspec.py`

These two helpers are the mechanism that makes a push touch **only** one skill's
subpath inside a shared parent clone. `commit_paths` stages + commits a pathspec;
`status_path` reports dirty state for a pathspec.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli/test_skill_git_pathspec.py
"""commit_paths / status_path operate scoped to a subpath of a repo."""
import subprocess
from pathlib import Path

from agent_toolkit_cli import skill_git

from tests.conftest import scrub_git_env


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "a").mkdir(parents=True)
    (repo / "b").mkdir(parents=True)
    (repo / "a" / "f.txt").write_text("a1\n")
    (repo / "b" / "f.txt").write_text("b1\n")
    env = scrub_git_env()
    for cmd in (
        ["git", "init", "-q", "-b", "main"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "init"],
    ):
        subprocess.run(cmd, cwd=repo, check=True, env=env)
    return repo


def test_status_path_clean_then_dirty(tmp_path):
    repo = _init_repo(tmp_path)
    assert skill_git.status_path(repo, "a", env=None) == skill_git.GitWorkingTreeStatus.CLEAN
    (repo / "a" / "f.txt").write_text("a2\n")
    assert skill_git.status_path(repo, "a", env=None) == skill_git.GitWorkingTreeStatus.DIRTY
    # b is untouched, so scoped to b it is still clean.
    assert skill_git.status_path(repo, "b", env=None) == skill_git.GitWorkingTreeStatus.CLEAN


def test_commit_paths_only_commits_the_scoped_subpath(tmp_path):
    repo = _init_repo(tmp_path)
    # Make BOTH subpaths dirty, but commit only "a".
    (repo / "a" / "f.txt").write_text("a2\n")
    (repo / "b" / "f.txt").write_text("b2\n")
    skill_git.commit_paths(repo, message="edit a only", paths=["a"], env=None)
    # a is now clean (committed); b is still dirty (not committed).
    assert skill_git.status_path(repo, "a", env=None) == skill_git.GitWorkingTreeStatus.CLEAN
    assert skill_git.status_path(repo, "b", env=None) == skill_git.GitWorkingTreeStatus.DIRTY
    # The last commit changed only b/… no — assert it touched only a/f.txt.
    show = subprocess.run(
        ["git", "-C", str(repo), "show", "--name-only", "--format=", "HEAD"],
        capture_output=True, text=True, env=scrub_git_env(), check=True,
    )
    changed = [ln for ln in show.stdout.splitlines() if ln.strip()]
    assert changed == ["a/f.txt"]


def test_commit_paths_noop_when_subpath_clean(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "b" / "f.txt").write_text("b2\n")  # dirty elsewhere
    # Committing "a" (clean) should report nothing staged and not create a commit.
    committed = skill_git.commit_paths(repo, message="noop", paths=["a"], env=None)
    assert committed is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd .worktrees/feat-258-owned-monorepo-capability && uv run pytest tests/test_cli/test_skill_git_pathspec.py -v`
Expected: FAIL — `AttributeError: module 'agent_toolkit_cli.skill_git' has no attribute 'status_path'`

- [ ] **Step 3: Write minimal implementation**

Add to `src/agent_toolkit_cli/skill_git.py` directly after `commit_all` (around line 255). `commit_paths` returns `bool` (True if a commit was made, False if the subpath had nothing to stage) so callers can print "clean — nothing to push" without a second status call.

```python
def status_path(
    repo: Path, path: str, *, env: dict[str, str] | None,
) -> GitWorkingTreeStatus:
    """Working-tree status scoped to a pathspec within `repo`.

    `git status --porcelain -- <path>` — used so an owned-monorepo skill's
    dirty state reflects only its own subpath, not sibling skills sharing the
    parent clone. Goes through _run so GIT_* env is scrubbed (the #209 trap).
    """
    proc = _run(
        ["git", "-C", str(repo), "status", "--porcelain", "--", path],
        env=env,
    )
    return (
        GitWorkingTreeStatus.CLEAN if not proc.stdout.strip()
        else GitWorkingTreeStatus.DIRTY
    )


def commit_paths(
    repo: Path, *, message: str, paths: list[str], env: dict[str, str] | None,
) -> bool:
    """Stage + commit ONLY `paths` within `repo`. Returns True if a commit was
    made, False if nothing under `paths` was staged (clean subpath).

    `git add -- <paths>` then `git commit -- <paths>`. The trailing pathspec on
    commit keeps the commit scoped even if other parts of the tree are dirty —
    the mechanism that isolates an owned-monorepo skill's push to its own
    subpath. Pins the same synthetic identity as `commit_all()`/`merge()`.
    Goes through _run so GIT_* env is scrubbed (the #209 trap).
    """
    _run(["git", "-C", str(repo), "add", "--", *paths], env=env)
    # Detect whether anything is staged under the pathspec; if not, no-op.
    staged = subprocess.run(
        ["git", "-C", str(repo), "diff", "--cached", "--quiet", "--", *paths],
        env=_scrub(env), capture_output=True, text=True,
    )
    if staged.returncode == 0:
        return False  # nothing staged under the pathspec
    _run(
        ["git", "-C", str(repo), *_DEFAULT_IDENTITY,
         "commit", "-m", message, "--", *paths],
        env=env,
    )
    return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd .worktrees/feat-258-owned-monorepo-capability && uv run pytest tests/test_cli/test_skill_git_pathspec.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/skill_git.py tests/test_cli/test_skill_git_pathspec.py
git commit -m "feat(258): commit_paths + status_path pathspec-scoped git helpers"
```

---

## Task 3: `skill add --owned` + ownership-based read_only

**Files:**
- Modify: `src/agent_toolkit_cli/commands/skill/__init__.py` (the `add` command ~line 189-237; `_add_single` ~240; `_add_monorepo` ~293-371)
- Test: `tests/test_cli/test_skill_owned_monorepo.py` (created here; extended in Task 4-6)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli/test_skill_owned_monorepo.py
"""Owned monorepo: add records writable (no readOnly); --owned forces it."""
import json
import subprocess
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main as cli
from agent_toolkit_cli.skill_paths import library_lock_path

from tests.conftest import scrub_git_env

FIXTURE = Path(__file__).parent.parent / "fixtures" / "monorepo_skills"


def _setup_parent(tmp_path, monkeypatch) -> tuple[str, Path]:
    parent = tmp_path / "parent"
    subprocess.run(["cp", "-R", str(FIXTURE), str(parent)], check=True)
    env = scrub_git_env()
    for cmd in (
        ["git", "init", "-q", "-b", "main"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "init"],
    ):
        subprocess.run(cmd, cwd=parent, check=True, env=env)
    library = tmp_path / "library"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library / "skills"))
    return f"file://{parent}", parent


def _lock() -> dict:
    return json.loads(library_lock_path().read_text())


def test_add_owned_writes_entry_without_readonly(tmp_path, monkeypatch):
    parent_url, _ = _setup_parent(tmp_path, monkeypatch)
    r = CliRunner().invoke(
        cli, ["skill", "add", parent_url, "--skill", "mkdocs", "--owned"],
    )
    assert r.exit_code == 0, r.output
    entry = _lock()["skills"]["mkdocs"]
    assert "readOnly" not in entry  # writers omit readOnly when False
    assert entry["parentUrl"] == parent_url


def test_add_unowned_monorepo_keeps_readonly(tmp_path, monkeypatch):
    parent_url, _ = _setup_parent(tmp_path, monkeypatch)
    r = CliRunner().invoke(cli, ["skill", "add", parent_url, "--skill", "mkdocs"])
    assert r.exit_code == 0, r.output
    entry = _lock()["skills"]["mkdocs"]
    assert entry.get("readOnly") is True  # local owner is not owned


def test_owned_flag_on_single_skill_add_is_error(tmp_path, monkeypatch):
    _setup_parent(tmp_path, monkeypatch)
    # A single-skill add (no subpath/--skill) with --owned must fail loud.
    r = CliRunner().invoke(
        cli, ["skill", "add", "ajanderson1/journal-skill", "--owned"],
    )
    assert r.exit_code != 0
    assert "owned" in r.output.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd .worktrees/feat-258-owned-monorepo-capability && uv run pytest tests/test_cli/test_skill_owned_monorepo.py -v`
Expected: FAIL — `add` has no `--owned` option (`no such option: --owned`), and `test_add_owned_writes_entry_without_readonly` fails because `_add_monorepo` always writes `read_only=True`.

- [ ] **Step 3: Write minimal implementation**

In `src/agent_toolkit_cli/commands/skill/__init__.py`:

a) Add the import near the other skill imports at module top:

```python
from agent_toolkit_cli.skill_ownership import is_owned_owner
```

b) Add the `--owned` option + param to `add` (after the `--skill` option/param):

```python
@click.option("--owned", is_flag=True,
              help="Treat the monorepo parent as owned (writable). Implied "
                   "for known owned owners; this forces it for any parent.")
```

```python
def add(
    ctx: click.Context, source: str, slug: str | None,
    ref: str | None, skill_name_flag: str | None, owned: bool,
) -> None:
```

c) At the dispatch at the bottom of `add`, route `owned` and reject it for single adds:

```python
    if parsed.subpath or parsed.skill_name:
        _add_monorepo(parsed, slug, owned=owned)
    else:
        if owned:
            raise click.UsageError(
                "--owned only applies to a monorepo add (use --skill, a "
                "subpath, or owner/repo/<path>); a single-skill repo is "
                "pushed via its own remote."
            )
        _add_single(parsed, slug)
```

d) Update `_add_monorepo`'s signature and the entry write. Change the signature:

```python
def _add_monorepo(parsed: ParsedSource, slug: str | None, *, owned: bool = False) -> None:
```

Then compute ownership right after `owner, repo = parsed.owner_repo.split("/", 1)` (line ~301):

```python
    owned_flag = owned or is_owned_owner(owner)
```

And change the `LockEntry(...)` `read_only=True` (line 367) to:

```python
        read_only=not owned_flag,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd .worktrees/feat-258-owned-monorepo-capability && uv run pytest tests/test_cli/test_skill_owned_monorepo.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Run the full suite to confirm no regression**

Run: `cd .worktrees/feat-258-owned-monorepo-capability && uv run pytest -q`
Expected: PASS — existing `test_skill_push_monorepo.py` and `test_skill_add_monorepo.py` still green (unowned `file://` parent → still `read_only`).

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/commands/skill/__init__.py tests/test_cli/test_skill_owned_monorepo.py
git commit -m "feat(258): skill add --owned + ownership-based read_only"
```

---

## Task 4: `skill push` — owned monorepo subpath-scoped PR

**Files:**
- Modify: `src/agent_toolkit_cli/commands/skill/push_cmd.py`
- Test: `tests/test_cli/test_skill_owned_monorepo.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli/test_skill_owned_monorepo.py`:

```python
def _add_owned(parent_url: str, skill: str = "mkdocs") -> None:
    r = CliRunner().invoke(
        cli, ["skill", "add", parent_url, "--skill", skill, "--owned"],
    )
    assert r.exit_code == 0, r.output


def test_owned_push_direct_commits_subpath_only(tmp_path, monkeypatch):
    """--direct push of an owned-monorepo skill commits ONLY that skill's
    subpath in the parent clone, even when a sibling subpath is dirty."""
    from agent_toolkit_cli.skill_paths import parent_clone_path

    parent_url, parent = _setup_parent(tmp_path, monkeypatch)
    _add_owned(parent_url, "mkdocs")
    entry = _lock()["skills"]["mkdocs"]
    sub = entry["skillPath"]  # e.g. "mkdocs"
    owner, repo = entry["source"].split("/", 1)
    clone = parent_clone_path(owner, repo, ref=entry.get("ref"), env=None)

    # Dirty the pushed skill's subpath AND a sibling file in the clone.
    (clone / sub / "SKILL.md").write_text("edited mkdocs\n")
    sibling = next(
        p for p in clone.iterdir()
        if p.is_dir() and p.name not in (".git", sub)
    )
    (sibling / "SKILL.md").write_text("edited sibling\n")

    r = CliRunner().invoke(cli, ["skill", "push", "--direct", "mkdocs", "-g"])
    assert r.exit_code == 0, r.output

    show = subprocess.run(
        ["git", "-C", str(clone), "show", "--name-only", "--format=", "HEAD"],
        capture_output=True, text=True, env=scrub_git_env(), check=True,
    )
    changed = [ln for ln in show.stdout.splitlines() if ln.strip()]
    assert all(p.startswith(f"{sub}/") for p in changed), changed
    assert any(p.startswith(f"{sub}/") for p in changed)


def test_owned_push_clean_subpath_reports_nothing(tmp_path, monkeypatch):
    parent_url, _ = _setup_parent(tmp_path, monkeypatch)
    _add_owned(parent_url, "mkdocs")
    r = CliRunner().invoke(cli, ["skill", "push", "--direct", "mkdocs", "-g"])
    assert r.exit_code == 0, r.output
    assert "nothing to push" in r.output.lower()
```

> PR-branch creation against a `file://` parent is exercised via `--direct`
> (which commits + pushes to the base ref). The non-`--direct` branch path
> reuses the unchanged `checkout_new_branch`/`push`/`_open_pr` helpers; `gh`
> is unavailable in the test env so `_open_pr` returns None and the command
> prints the branch URL — covered by an assertion on the "pushed branch"
> line. (Add that assertion only if a `file://` push of a branch succeeds in
> the sandbox; if `git push` to a non-bare `file://` repo's checked-out branch
> fails, keep the test on `--direct` to base ref pushing to a side branch is
> out of scope here.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd .worktrees/feat-258-owned-monorepo-capability && uv run pytest tests/test_cli/test_skill_owned_monorepo.py -k owned_push -v`
Expected: FAIL — push currently routes owned entries (read_only False, parent_url set) into the per-repo `canonical` path, where `is_git_repo(canonical)` is False (it's a symlink into the parent), so it prints "copy-mode … cannot push" and never touches the subpath.

- [ ] **Step 3: Write minimal implementation**

In `push_cmd.py`, add imports at top:

```python
from agent_toolkit_cli.skill_paths import (
    canonical_skill_dir, lock_file_path, parent_clone_path, project_parents_root,
)
```

Insert an owned-monorepo branch in `push_cmd` after the `entry.read_only` block (after line 68, before the `canonical = canonical_skill_dir(...)` block):

```python
        if entry.parent_url is not None:
            # Owned monorepo (read_only already excluded above): push the
            # skill's subpath within the shared parent clone.
            _push_monorepo(
                entry, slug, scope=scope, project_root=project_root,
                direct=direct,
            )
            continue
```

Add the two functions (after `_push_via_pr`):

```python
def _monorepo_parent_dir(entry, scope, project_root) -> Path:
    owner, repo = entry.source.split("/", 1)
    return parent_clone_path(
        owner, repo, ref=entry.ref, env=None,
        root=project_parents_root(project_root) if scope == "project" else None,
    )


def _push_monorepo(entry, slug, *, scope, project_root, direct: bool) -> None:
    parent_dir = _monorepo_parent_dir(entry, scope, project_root)
    if not skill_git.is_git_repo(parent_dir):
        click.echo(
            f"{slug}: parent clone missing or not a git repo at {parent_dir}"
        )
        return
    subpath = entry.skill_path or "."
    if skill_git.status_path(parent_dir, subpath, env=None) == \
            skill_git.GitWorkingTreeStatus.CLEAN:
        click.echo(f"{slug}: clean — nothing to push")
        return
    base_ref = entry.ref or "main"
    msg = f"skill({slug}): self-improvement {_utc_iso()}"
    if direct:
        skill_git.commit_paths(parent_dir, message=msg, paths=[subpath], env=None)
        skill_git.push(parent_dir, ref=base_ref, env=None)
        click.echo(f"{slug}: pushed (subpath {subpath} → {base_ref})")
        return
    branch = f"skill/self-improvement-{_utc_basic_iso()}-{_slug_for_ref(slug)}"
    skill_git.checkout_new_branch(parent_dir, name=branch, env=None)
    try:
        skill_git.commit_paths(parent_dir, message=msg, paths=[subpath], env=None)
        skill_git.push(parent_dir, ref=branch, env=None)
        click.echo(f"{slug}: pushed branch {branch}")
        pr_url = _open_pr(parent_dir, branch, base=base_ref, slug=slug)
        if pr_url:
            click.echo(f"  PR: {pr_url}")
        else:
            web = _branch_web_url(parent_dir, branch)
            if web:
                click.echo(f"  → open a PR: {web}")
    finally:
        skill_git.checkout(parent_dir, ref=base_ref, env=None)
```

Note: `_push_monorepo` needs `scope`/`project_root` from `push_cmd`. They are already in scope (`scope, home, project_root = scope_and_roots(...)`). Pass them through as shown in the inserted call.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd .worktrees/feat-258-owned-monorepo-capability && uv run pytest tests/test_cli/test_skill_owned_monorepo.py -k owned_push -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Run the regression guard**

Run: `cd .worktrees/feat-258-owned-monorepo-capability && uv run pytest tests/test_cli/test_skill_push_monorepo.py -v`
Expected: PASS — unowned (`read_only`) monorepo push still refused, because the new branch is guarded by `entry.parent_url is not None` placed **after** the `entry.read_only` refusal, so read-only entries never reach it.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/commands/skill/push_cmd.py tests/test_cli/test_skill_owned_monorepo.py
git commit -m "feat(258): skill push subpath-scoped PR for owned monorepos"
```

---

## Task 5: `skill status` — owned monorepo subpath-scoped + `(owned)` marker

**Files:**
- Modify: `src/agent_toolkit_cli/commands/skill/status_cmd.py`
- Test: `tests/test_cli/test_skill_owned_monorepo.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli/test_skill_owned_monorepo.py`:

```python
def test_owned_status_subpath_scoped_and_marked(tmp_path, monkeypatch):
    from agent_toolkit_cli.skill_paths import parent_clone_path

    parent_url, _ = _setup_parent(tmp_path, monkeypatch)
    _add_owned(parent_url, "mkdocs")
    entry = _lock()["skills"]["mkdocs"]
    sub = entry["skillPath"]
    owner, repo = entry["source"].split("/", 1)
    clone = parent_clone_path(owner, repo, ref=entry.get("ref"), env=None)

    # Clean to start, and marked (owned).
    r = CliRunner().invoke(cli, ["skill", "status", "mkdocs", "-g"])
    assert r.exit_code == 0, r.output
    assert "clean" in r.output
    assert "(owned)" in r.output

    # Dirty a SIBLING subpath only → mkdocs must still read clean.
    sibling = next(
        p for p in clone.iterdir()
        if p.is_dir() and p.name not in (".git", sub)
    )
    (sibling / "SKILL.md").write_text("edited sibling\n")
    r2 = CliRunner().invoke(cli, ["skill", "status", "mkdocs", "-g"])
    assert "clean" in r2.output and "dirty" not in r2.output

    # Dirty mkdocs' own subpath → now dirty.
    (clone / sub / "SKILL.md").write_text("edited mkdocs\n")
    r3 = CliRunner().invoke(cli, ["skill", "status", "mkdocs", "-g"])
    assert "dirty" in r3.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd .worktrees/feat-258-owned-monorepo-capability && uv run pytest tests/test_cli/test_skill_owned_monorepo.py -k owned_status -v`
Expected: FAIL — current status reports whole-parent state (so a dirty sibling shows mkdocs as dirty) and never prints `(owned)`.

- [ ] **Step 3: Write minimal implementation**

In `status_cmd.py`, replace the monorepo branch (lines 64-80) so owned entries are subpath-scoped + marked:

```python
        if entry.parent_url is not None:
            # Monorepo skill — status lives in the parent clone, not the
            # symlinked subpath (which has no `.git/` of its own).
            owner, repo = entry.source.split("/", 1)
            parent_dir = parent_clone_path(
                owner, repo, ref=entry.ref, env=None,
                root=project_parents_root(project_root) if scope == "project" else None,
            )
            if not skill_git.is_git_repo(parent_dir):
                click.echo(f"{slug}\tcopy")
                continue
            if not entry.read_only:
                # Owned monorepo: scope dirty state to this skill's subpath so
                # sibling edits don't bleed in, and mark it writable.
                subpath = entry.skill_path or "."
                wt = skill_git.status_path(parent_dir, subpath, env=None)
                state = (
                    "dirty" if wt == skill_git.GitWorkingTreeStatus.DIRTY
                    else "clean"
                )
                click.echo(f"{slug}\t{state} (owned)")
                continue
            wt = skill_git.status(parent_dir, env=None)
        elif not skill_git.is_git_repo(canonical):
            click.echo(f"{slug}\tcopy")
            continue
        else:
            wt = skill_git.status(canonical, env=None)
        state = (
            "dirty" if wt == skill_git.GitWorkingTreeStatus.DIRTY else "clean"
        )
        click.echo(f"{slug}\t{state}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd .worktrees/feat-258-owned-monorepo-capability && uv run pytest tests/test_cli/test_skill_owned_monorepo.py -k owned_status -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Regression — existing status tests still green**

Run: `cd .worktrees/feat-258-owned-monorepo-capability && uv run pytest tests/test_cli/test_cli_skill_status.py -v`
Expected: PASS — unowned monorepo + per-repo statuses unchanged.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/commands/skill/status_cmd.py tests/test_cli/test_skill_owned_monorepo.py
git commit -m "feat(258): skill status subpath-scoped + (owned) marker for owned monorepos"
```

---

## Task 6: `skill update` — verify merge-not-reset survives owned edits

**Files:**
- Test only: `tests/test_cli/test_skill_owned_monorepo.py` (append). No production change expected — this task locks in the existing behaviour with a regression test.

- [ ] **Step 1: Write the failing-or-passing test**

Append to `tests/test_cli/test_skill_owned_monorepo.py`:

```python
def test_owned_update_merges_not_resets_local_edits(tmp_path, monkeypatch):
    """skill update on an owned monorepo must NOT discard a local committed
    edit in the parent clone — it fetches + merges, never resets."""
    from agent_toolkit_cli.skill_paths import parent_clone_path

    parent_url, parent = _setup_parent(tmp_path, monkeypatch)
    _add_owned(parent_url, "mkdocs")
    entry = _lock()["skills"]["mkdocs"]
    sub = entry["skillPath"]
    owner, repo = entry["source"].split("/", 1)
    clone = parent_clone_path(owner, repo, ref=entry.get("ref"), env=None)

    # Commit a local edit in the clone (a self-improvement not yet pushed).
    marker = clone / sub / "LOCAL_EDIT.md"
    marker.write_text("local self-improvement\n")
    skill_git_commit = scrub_git_env()
    for cmd in (
        ["git", "-C", str(clone), "add", "--", sub],
        ["git", "-C", str(clone), "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "local edit"],
    ):
        subprocess.run(cmd, check=True, env=skill_git_commit)

    # Advance the upstream parent with an unrelated commit so update has
    # something to merge.
    (parent / "TOPLEVEL.md").write_text("upstream change\n")
    for cmd in (
        ["git", "-C", str(parent), "add", "."],
        ["git", "-C", str(parent), "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "upstream"],
    ):
        subprocess.run(cmd, check=True, env=skill_git_commit)

    r = CliRunner().invoke(cli, ["skill", "update", "mkdocs", "-g"])
    assert r.exit_code == 0, r.output
    # The local edit survived the update (merge, not reset).
    assert marker.exists(), "skill update discarded a local owned edit"
```

- [ ] **Step 2: Run the test**

Run: `cd .worktrees/feat-258-owned-monorepo-capability && uv run pytest tests/test_cli/test_skill_owned_monorepo.py -k owned_update -v`
Expected: PASS (the existing `update_cmd.py` monorepo branch already does `fetch` + `merge`, never `reset`). **If it FAILS**, the merge path has a real bug — fix `update_cmd.py` so the local commit survives (do not switch to reset), then re-run. Capture any disagreement in `flow.log`.

- [ ] **Step 3: Commit**

```bash
git add tests/test_cli/test_skill_owned_monorepo.py
git commit -m "test(258): skill update merges (not resets) owned-monorepo local edits"
```

---

## Task 7: Docs + final full-suite + lint

**Files:**
- Modify: `docs/agent-toolkit/skill-lock.md` (document the owned-monorepo entry shape) — only if the file documents `readOnly`/`parentUrl`; check first.

- [ ] **Step 1: Check whether skill-lock docs mention readOnly/parentUrl**

Run: `grep -n "readOnly\|parentUrl\|monorepo\|read_only" docs/agent-toolkit/skill-lock.md`
If matches exist, add a short paragraph: an owned monorepo entry has `parentUrl` + `skillPath` but **no** `readOnly`; `skill push` opens a subpath-scoped PR against the parent; ownership is decided by `is_owned_owner()` or `skill add --owned`. If the file has no such section, skip this edit (do not invent a section).

- [ ] **Step 2: Full suite**

Run: `cd .worktrees/feat-258-owned-monorepo-capability && uv run pytest -q`
Expected: PASS — all prior tests plus the new owned-monorepo suite.

- [ ] **Step 3: Lint**

Run: `cd .worktrees/feat-258-owned-monorepo-capability && uv run ruff check`
Expected: clean (fix any findings in the changed files).

- [ ] **Step 4: Commit any docs/lint fixups**

```bash
git add -A
git commit -m "docs(258): document owned-monorepo lock entry shape" || echo "nothing to commit"
```

---

## Self-Review (completed during authoring)

- **Spec coverage:** add `--owned`/ownership → Task 3; push subpath-scoped PR + regression → Task 4; status subpath-scoped + writable marker → Task 5; update merge-not-reset → Task 6; regression guard → Tasks 3/4/5 (existing tests stay green + non-owned-owner assertions). `skill migrate-to-monorepo` is explicitly out of scope (PR2).
- **Placeholder scan:** every code step shows full code; no TBD/TODO. The Task 4 branch-push note documents a real `file://`-sandbox limitation rather than hand-waving.
- **Type consistency:** `is_owned_owner(owner: str) -> bool`, `status_path(repo, path, *, env)`, `commit_paths(repo, *, message, paths, env) -> bool` are referenced with the same signatures in Tasks 4/5. `_push_monorepo(entry, slug, *, scope, project_root, direct)` matches its call site.
