# Git & Doctor Characterization + Test Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lock down the existing skill git lifecycle (`status`/`update`/`push`/`doctor`) with a comprehensive test suite, adding only the shared `divergence()` git helper as new production code, and record every surprising behaviour in a Gap Ledger.

**Architecture:** One new pure-ish git helper, `skill_git.divergence()`, classifies local-vs-upstream state via `git rev-list --left-right --count`. New `make_*` state-builder fixtures sit on the existing `git_sandbox` so tests declare divergence states declaratively. Characterization tests then assert *current* behaviour across three tiers — unit (`tests/`), real-git integration (`tests/integration/`), and end-to-end CLI (`tests/test_cli/`, the existing `CliRunner` idiom) — annotating known bugs as documented-current-behaviour.

**Tech Stack:** Python 3.12, pytest (`uv run pytest -q`), `click.testing.CliRunner`, real `git` subprocess against local bare repos (`file://`), no network. Source is `src/agent_toolkit_cli/`.

---

## Context the engineer needs

**You know nothing about this codebase. Read this first.**

- **Skill canonicals** are real git clones under `~/.agent-toolkit/skills/<slug>/` (global) or
  `~/.agent-toolkit/projects/<id>/skills/<slug>/` (project). Tests redirect these via the
  `AGENT_TOOLKIT_SKILLS_ROOT` env var and a monkeypatched `HOME`.
- **`src/agent_toolkit_cli/skill_git.py`** wraps `git`. Every call routes through `_run(cmd, env=...)`,
  which scrubs `GIT_*` env vars except the identity allowlist (`GIT_AUTHOR_*`, `GIT_COMMITTER_*`).
  Functions take `env` as a **keyword-only** argument and return either a `GitResult(stdout, stderr)`
  dataclass or a small enum. `GitError` is raised on non-zero exit. There are already these enums:
  ```python
  class GitWorkingTreeStatus(enum.Enum):
      CLEAN = "clean"
      DIRTY = "dirty"
  ```
- **`tests/conftest.py`** provides the `git_sandbox` fixture: a bare `upstream.git`, a working
  `clone` pre-seeded with `SKILL.md`, and `git_sandbox.env` (a dict with `GIT_*` scrubbed but
  identity + `HOME` set). It also has an autouse `_strip_git_env` that clears `GIT_*` from
  `os.environ` for every test. **Always pass `env=git_sandbox.env`** when shelling out in setup.
- **Setup shell-outs** in existing tests use raw `subprocess.run([...], check=True,
  env=git_sandbox.env, capture_output=True)`. Follow that exactly — do not call the production
  `skill_git` functions to *set up* state you're trying to characterize (only to assert).
- **E2E idiom** (see `tests/test_cli/test_cli_skill_status.py`): `CliRunner().invoke(main, [...])`,
  with `monkeypatch.setenv` for each `git_sandbox.env` key plus `AGENT_TOOLKIT_SKILLS_ROOT`, then
  `skill add` / `skill install` to reach a realistic install. Assert on `result.output` and
  `result.exit_code`.
- **`git rev-list --left-right --count HEAD...origin/<ref>`** prints `<ahead>\t<behind>`:
  `0\t0` = up to date, `N\t0` = ahead, `0\tM` = behind, `N\tM` = diverged. **Verified locally.**
- **Run tests with** `uv run pytest -q` (this is the pre-commit command too). Target one test with
  `uv run pytest tests/path::test_name -v`.
- **Branch:** work is on `spec/git-doctor-characterization`. Commit there. Do NOT commit to `main`.

---

## File Structure

| File | Responsibility | Action |
|------|----------------|--------|
| `src/agent_toolkit_cli/skill_git.py` | Add `Divergence` enum + `divergence()` helper | Modify |
| `tests/conftest.py` | Add `make_behind/ahead/diverged/conflict/dirty` state builders + `installed_skill`/`monorepo_skill`/`copymode_skill` fixtures | Modify |
| `tests/test_cli/test_skill_git.py` | Unit + integration tests for `divergence()` and env-leak regression | Modify |
| `tests/integration/test_git_states.py` | Real-git integration: state builders → command-layer behaviour (status/update/push) | Create |
| `tests/test_cli/test_cli_skill_status.py` | E2E: status across all states (current behaviour) | Modify |
| `tests/test_cli/test_cli_skill_update.py` | E2E: update across all states incl. conflict | Modify |
| `tests/test_cli/test_cli_skill_push.py` | E2E: push incl. clean-gap (documented bug) | Modify |
| `tests/test_cli/test_skill_doctor.py` | Assert doctor is offline / no drift findings today (locks taxonomy) | Modify |

The plan adds `divergence()` first (TDD), then fixtures, then characterization tier by tier.

---

## Task 1: Add `Divergence` enum and `divergence()` to `skill_git.py`

**Files:**
- Modify: `src/agent_toolkit_cli/skill_git.py` (add enum near `GitWorkingTreeStatus`, add function near `remote_head_sha`)
- Test: `tests/test_cli/test_skill_git.py`

- [ ] **Step 1: Write the failing integration tests**

Append to `tests/test_cli/test_skill_git.py`. Add `Divergence` and `divergence` to the existing
import block from `agent_toolkit_cli.skill_git`, then add these tests. The `_advance_upstream`
helper pushes a new commit to the remote via a throwaway clone (mirrors the existing
`test_merge_fast_forwards_when_clean` pattern).

```python
def _advance_upstream(git_sandbox):
    """Push one new commit to upstream via a throwaway clone."""
    other = git_sandbox.upstream.parent / "advance-helper"
    subprocess.run(
        ["git", "clone", str(git_sandbox.upstream), str(other)],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    (other / "UPSTREAM.md").write_text("upstream advance\n")
    subprocess.run(["git", "-C", str(other), "add", "-A"],
                   check=True, env=git_sandbox.env, capture_output=True)
    subprocess.run(["git", "-C", str(other), "commit", "-m", "upstream"],
                   check=True, env=git_sandbox.env, capture_output=True)
    subprocess.run(["git", "-C", str(other), "push", "origin", "main"],
                   check=True, env=git_sandbox.env, capture_output=True)


def _commit_local(git_sandbox, name="LOCAL.md", body="local change\n"):
    """Create one local commit in the clone (not pushed)."""
    (git_sandbox.clone / name).write_text(body)
    subprocess.run(["git", "-C", str(git_sandbox.clone), "add", "-A"],
                   check=True, env=git_sandbox.env, capture_output=True)
    subprocess.run(["git", "-C", str(git_sandbox.clone), "commit", "-m", "local"],
                   check=True, env=git_sandbox.env, capture_output=True)


def test_divergence_up_to_date(git_sandbox):
    fetch(git_sandbox.clone, env=git_sandbox.env)
    assert divergence(git_sandbox.clone, ref="main", env=git_sandbox.env) \
        == Divergence.UP_TO_DATE


def test_divergence_ahead(git_sandbox):
    _commit_local(git_sandbox)
    fetch(git_sandbox.clone, env=git_sandbox.env)
    assert divergence(git_sandbox.clone, ref="main", env=git_sandbox.env) \
        == Divergence.AHEAD


def test_divergence_behind(git_sandbox):
    _advance_upstream(git_sandbox)
    fetch(git_sandbox.clone, env=git_sandbox.env)
    assert divergence(git_sandbox.clone, ref="main", env=git_sandbox.env) \
        == Divergence.BEHIND


def test_divergence_diverged(git_sandbox):
    _commit_local(git_sandbox)
    _advance_upstream(git_sandbox)
    fetch(git_sandbox.clone, env=git_sandbox.env)
    assert divergence(git_sandbox.clone, ref="main", env=git_sandbox.env) \
        == Divergence.DIVERGED


def test_divergence_does_not_fetch(git_sandbox):
    """divergence() reads only local refs — a behind clone reads UP_TO_DATE
    until the caller fetches. Pins the 'caller must fetch' contract."""
    _advance_upstream(git_sandbox)
    # No fetch: origin/main ref is stale, so we look up to date.
    assert divergence(git_sandbox.clone, ref="main", env=git_sandbox.env) \
        == Divergence.UP_TO_DATE
    fetch(git_sandbox.clone, env=git_sandbox.env)
    assert divergence(git_sandbox.clone, ref="main", env=git_sandbox.env) \
        == Divergence.BEHIND
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli/test_skill_git.py -k divergence -v`
Expected: FAIL — `ImportError: cannot import name 'Divergence'` (or `divergence`).

- [ ] **Step 3: Implement the enum and helper**

In `src/agent_toolkit_cli/skill_git.py`, add the enum directly after the `GitWorkingTreeStatus`
class (around line 34):

```python
class Divergence(enum.Enum):
    """Local HEAD relative to origin/<ref>, classified from
    `git rev-list --left-right --count`."""
    UP_TO_DATE = "up_to_date"
    BEHIND = "behind"      # upstream has commits we don't
    AHEAD = "ahead"        # we have commits upstream doesn't
    DIVERGED = "diverged"  # both sides moved
```

Add this function next to `remote_head_sha` (end of file, ~line 238):

```python
def divergence(
    repo: Path, *, ref: str, env: dict[str, str] | None
) -> Divergence:
    """Classify local HEAD vs origin/<ref> using
    `git rev-list --left-right --count HEAD...origin/<ref>`, which prints
    `<ahead>\\t<behind>`.

    Reads ONLY the local repo's refs — it does NOT fetch. Callers that need
    a live comparison must `fetch()` first; otherwise origin/<ref> is
    whatever the last fetch/clone recorded.
    """
    proc = _run(
        ["git", "-C", str(repo), "rev-list", "--left-right", "--count",
         f"HEAD...origin/{ref}"],
        env=env,
    )
    ahead_str, behind_str = proc.stdout.split()
    ahead, behind = int(ahead_str), int(behind_str)
    if ahead and behind:
        return Divergence.DIVERGED
    if ahead:
        return Divergence.AHEAD
    if behind:
        return Divergence.BEHIND
    return Divergence.UP_TO_DATE
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli/test_skill_git.py -k divergence -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Add a unit test for the parse boundary**

Append to `tests/test_cli/test_skill_git.py` a test that exercises the parse logic directly via a
monkeypatched `_run`, so the `<ahead>\t<behind>` → enum mapping is pinned without a real repo:

```python
def test_divergence_parses_left_right_count(monkeypatch):
    import agent_toolkit_cli.skill_git as g

    class _Fake:
        def __init__(self, out): self.stdout = out; self.stderr = ""

    cases = {"0\t0": g.Divergence.UP_TO_DATE, "2\t0": g.Divergence.AHEAD,
             "0\t3": g.Divergence.BEHIND, "2\t3": g.Divergence.DIVERGED}
    for out, expected in cases.items():
        monkeypatch.setattr(g, "_run", lambda *a, _o=out, **k: _Fake(_o))
        assert g.divergence(Path("/x"), ref="main", env=None) == expected
```

- [ ] **Step 6: Run and verify**

Run: `uv run pytest tests/test_cli/test_skill_git.py -k divergence -v`
Expected: PASS (6 tests).

- [ ] **Step 7: Commit**

```bash
git add src/agent_toolkit_cli/skill_git.py tests/test_cli/test_skill_git.py
git commit -m "feat(skill_git): add divergence() helper to classify local vs upstream"
```

---

## Task 2: Add state-builder fixtures to `conftest.py`

**Files:**
- Modify: `tests/conftest.py`
- Test: `tests/integration/test_git_states.py` (created in this task to verify the builders)

- [ ] **Step 1: Write the failing test for the builders**

Create `tests/integration/test_git_states.py`:

```python
"""Integration: state-builder fixtures produce the divergence state they name."""
from agent_toolkit_cli.skill_git import (
    Divergence,
    GitWorkingTreeStatus,
    divergence,
    fetch,
    status,
)


def test_make_behind_yields_behind(make_behind):
    sandbox = make_behind
    fetch(sandbox.clone, env=sandbox.env)
    assert divergence(sandbox.clone, ref="main", env=sandbox.env) == Divergence.BEHIND


def test_make_ahead_yields_ahead(make_ahead):
    sandbox = make_ahead
    fetch(sandbox.clone, env=sandbox.env)
    assert divergence(sandbox.clone, ref="main", env=sandbox.env) == Divergence.AHEAD


def test_make_diverged_yields_diverged(make_diverged):
    sandbox = make_diverged
    fetch(sandbox.clone, env=sandbox.env)
    assert divergence(sandbox.clone, ref="main", env=sandbox.env) == Divergence.DIVERGED


def test_make_dirty_yields_dirty(make_dirty):
    sandbox = make_dirty
    assert status(sandbox.clone, env=sandbox.env) == GitWorkingTreeStatus.DIRTY


def test_make_conflict_blocks_merge(make_conflict):
    """Both sides edited the same line — merge must raise GitError."""
    import pytest
    from agent_toolkit_cli.skill_git import GitError, merge
    sandbox = make_conflict
    fetch(sandbox.clone, env=sandbox.env)
    with pytest.raises(GitError):
        merge(sandbox.clone, ref="main", env=sandbox.env)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/integration/test_git_states.py -v`
Expected: FAIL — `fixture 'make_behind' not found`.

- [ ] **Step 3: Implement the fixtures**

Append to `tests/conftest.py`. These build on `git_sandbox` and reuse its `env`. Each commits
through raw `subprocess` (never the production helpers) so they characterize independently.

```python
def _git(sandbox, *args):
    subprocess.run(["git", "-C", str(sandbox.clone), *args],
                   check=True, env=sandbox.env, capture_output=True)


def _advance_remote(sandbox, name="UPSTREAM.md", body="upstream\n"):
    """Push one commit to upstream via a throwaway clone."""
    helper = sandbox.upstream.parent / "remote-advance-helper"
    if not helper.exists():
        subprocess.run(["git", "clone", str(sandbox.upstream), str(helper)],
                       check=True, env=sandbox.env, capture_output=True)
    (helper / name).write_text(body)
    subprocess.run(["git", "-C", str(helper), "add", "-A"],
                   check=True, env=sandbox.env, capture_output=True)
    subprocess.run(["git", "-C", str(helper), "commit", "-m", "upstream"],
                   check=True, env=sandbox.env, capture_output=True)
    subprocess.run(["git", "-C", str(helper), "push", "origin", "main"],
                   check=True, env=sandbox.env, capture_output=True)


@pytest.fixture
def make_behind(git_sandbox) -> GitSandbox:
    """Upstream advanced; clone left behind (not fetched)."""
    _advance_remote(git_sandbox)
    return git_sandbox


@pytest.fixture
def make_ahead(git_sandbox) -> GitSandbox:
    """Clone has a local commit not pushed to upstream."""
    (git_sandbox.clone / "LOCAL.md").write_text("local\n")
    _git(git_sandbox, "add", "-A")
    _git(git_sandbox, "commit", "-m", "local")
    return git_sandbox


@pytest.fixture
def make_diverged(git_sandbox) -> GitSandbox:
    """Both sides committed on non-conflicting paths."""
    (git_sandbox.clone / "LOCAL.md").write_text("local\n")
    _git(git_sandbox, "add", "-A")
    _git(git_sandbox, "commit", "-m", "local")
    _advance_remote(git_sandbox)
    return git_sandbox


@pytest.fixture
def make_conflict(git_sandbox) -> GitSandbox:
    """Both sides edited the same line of SKILL.md."""
    (git_sandbox.clone / "SKILL.md").write_text("local edit\n")
    _git(git_sandbox, "add", "-A")
    _git(git_sandbox, "commit", "-m", "local SKILL edit")
    _advance_remote(git_sandbox, name="SKILL.md", body="upstream edit\n")
    return git_sandbox


@pytest.fixture
def make_dirty(git_sandbox) -> GitSandbox:
    """Uncommitted working-tree change."""
    (git_sandbox.clone / "SKILL.md").write_text("uncommitted edit\n")
    return git_sandbox
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/integration/test_git_states.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add tests/conftest.py tests/integration/test_git_states.py
git commit -m "test: add git divergence state-builder fixtures"
```

---

## Task 3: Add install-shaped fixtures (`installed_skill`, `monorepo_skill`, `copymode_skill`)

**Files:**
- Modify: `tests/conftest.py`
- Test: `tests/integration/test_install_fixtures.py` (created to verify)

These give behavioural tests a realistic starting point (canonical + lock + projection) using the
**real CLI** (`CliRunner`) so the fixtures stay faithful to how installs actually happen.

- [ ] **Step 1: Write the failing verification test**

Create `tests/integration/test_install_fixtures.py`:

```python
"""Integration: install-shaped fixtures land a real canonical + lock entry."""
from agent_toolkit_cli.skill_git import is_git_repo


def test_installed_skill_has_git_canonical(installed_skill):
    assert is_git_repo(installed_skill.canonical)
    assert installed_skill.slug in installed_skill.lock_text


def test_copymode_skill_has_no_git(copymode_skill):
    assert not is_git_repo(copymode_skill.canonical)


def test_monorepo_skill_is_read_only(monorepo_skill):
    assert monorepo_skill.read_only is True
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/integration/test_install_fixtures.py -v`
Expected: FAIL — `fixture 'installed_skill' not found`.

- [ ] **Step 3: Implement the fixtures**

Append to `tests/conftest.py`. Add the import and a small result dataclass at the top of the new
block. The global-scope install writes the canonical to `<root>/<slug>` and the lock to
`<root>/skills-lock.json` (root = `AGENT_TOOLKIT_SKILLS_ROOT`). `_init_parent` for the monorepo
case is reused from the existing test module per the established pattern.

```python
from dataclasses import dataclass as _dataclass


@_dataclass
class InstalledSkill:
    slug: str
    canonical: Path
    lock_path: Path
    lock_text: str
    read_only: bool


@pytest.fixture
def _cli_env(git_sandbox, tmp_path, monkeypatch):
    """Monkeypatch env so the real CLI installs into a sandbox library root."""
    root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(root))
    return root


@pytest.fixture
def installed_skill(git_sandbox, _cli_env) -> InstalledSkill:
    from click.testing import CliRunner
    from agent_toolkit_cli.cli import main
    root = _cli_env
    runner = CliRunner()
    r = runner.invoke(main, ["skill", "add", str(git_sandbox.upstream),
                             "--slug", "demo"])
    assert r.exit_code == 0, r.output
    canonical = root / "demo"
    lock_path = root / "skills-lock.json"
    return InstalledSkill(
        slug="demo", canonical=canonical, lock_path=lock_path,
        lock_text=lock_path.read_text(), read_only=False,
    )


@pytest.fixture
def copymode_skill(_cli_env) -> InstalledSkill:
    """A canonical with plain files and no .git/ (copy-mode)."""
    root = _cli_env
    canonical = root / "copydemo"
    canonical.mkdir(parents=True)
    (canonical / "SKILL.md").write_text(
        "---\nname: copydemo\ndescription: copy.\n---\n# copydemo\n"
    )
    lock_path = root / "skills-lock.json"
    lock_path.write_text('{"version": 3, "skills": {"copydemo": {}}}')
    return InstalledSkill(
        slug="copydemo", canonical=canonical, lock_path=lock_path,
        lock_text=lock_path.read_text(), read_only=False,
    )


@pytest.fixture
def monorepo_skill(tmp_path, monkeypatch) -> InstalledSkill:
    """A read-only monorepo skill added via the real CLI."""
    from click.testing import CliRunner
    from agent_toolkit_cli.cli import main
    from tests.test_cli.test_skill_update_monorepo import _init_parent
    parent = _init_parent(tmp_path)
    root = tmp_path / "library" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(root))
    runner = CliRunner()
    r = runner.invoke(main, ["skill", "add", f"file://{parent}",
                             "--skill", "mkdocs"])
    assert r.exit_code == 0, r.output
    lock_path = root / "skills-lock.json"
    return InstalledSkill(
        slug="mkdocs", canonical=root / "mkdocs", lock_path=lock_path,
        lock_text=lock_path.read_text(), read_only=True,
    )
```

> **Note:** if `skill add` writes the global lock to `~/.agent-toolkit/skills-lock.json` (via a
> monkeypatched `HOME`) rather than under `AGENT_TOOLKIT_SKILLS_ROOT`, adjust `lock_path` to the
> path the CLI actually wrote — verify with the failing run's filesystem before hardcoding. The
> existing `test_cli_skill_status.py` confirms the canonical lands at `<root>/<slug>`; mirror it.

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/integration/test_install_fixtures.py -v`
Expected: PASS (3 tests). If a `lock_path` assertion fails, correct the path per the note above,
then re-run.

- [ ] **Step 5: Commit**

```bash
git add tests/conftest.py tests/integration/test_install_fixtures.py
git commit -m "test: add install-shaped fixtures (installed/copymode/monorepo)"
```

---

## Task 4: Integration characterization — command-layer behaviour across states

**Files:**
- Modify: `tests/integration/test_git_states.py`

Drive the **command-layer functions** (not the CLI yet) through each state and assert current
behaviour. Use the `skill_git` helpers directly since these tests characterize the git seam.

- [ ] **Step 1: Write the tests**

Append to `tests/integration/test_git_states.py`:

```python
import subprocess

import pytest

from agent_toolkit_cli.skill_git import (
    GitError,
    head_sha,
    merge,
    push,
)


def test_behind_then_merge_fast_forwards(make_behind):
    s = make_behind
    fetch(s.clone, env=s.env)
    before = head_sha(s.clone, env=s.env)
    merge(s.clone, ref="main", env=s.env)
    after = head_sha(s.clone, env=s.env)
    assert before != after  # fast-forwarded to upstream
    assert (s.clone / "UPSTREAM.md").exists()


def test_ahead_merge_is_noop(make_ahead):
    s = make_ahead
    fetch(s.clone, env=s.env)
    before = head_sha(s.clone, env=s.env)
    merge(s.clone, ref="main", env=s.env)  # "Already up to date"
    assert head_sha(s.clone, env=s.env) == before


def test_diverged_merge_creates_merge_commit(make_diverged):
    s = make_diverged
    fetch(s.clone, env=s.env)
    merge(s.clone, ref="main", env=s.env)
    # Merge commit has two parents.
    parents = subprocess.run(
        ["git", "-C", str(s.clone), "rev-list", "--parents", "-n", "1", "HEAD"],
        check=True, env=s.env, capture_output=True, text=True,
    ).stdout.split()
    assert len(parents) == 3  # self + 2 parents


def test_conflict_merge_leaves_recoverable_tree(make_conflict):
    """Documents current behaviour: merge raises, tree is mid-merge but
    `git merge --abort` recovers it. See Gap Ledger §3."""
    s = make_conflict
    fetch(s.clone, env=s.env)
    with pytest.raises(GitError):
        merge(s.clone, ref="main", env=s.env)
    # Recoverable: abort succeeds and returns rc 0.
    abort = subprocess.run(
        ["git", "-C", str(s.clone), "merge", "--abort"],
        env=s.env, capture_output=True,
    )
    assert abort.returncode == 0


def test_ahead_push_succeeds_no_ownership_check(make_ahead):
    """Documents current behaviour: push proceeds whenever git push works —
    there is no upstream-ownership verification. See Gap Ledger §5."""
    s = make_ahead
    push(s.clone, ref="main", env=s.env)
    fetch(s.clone, env=s.env)
    from agent_toolkit_cli.skill_git import divergence, Divergence
    assert divergence(s.clone, ref="main", env=s.env) == Divergence.UP_TO_DATE
```

- [ ] **Step 2: Run to verify**

Run: `uv run pytest tests/integration/test_git_states.py -v`
Expected: PASS (all). If `test_diverged_merge_creates_merge_commit` shows a fast-forward instead
(2 tokens not 3), the seed/remote ordering produced a linear history — that itself documents
behaviour; adjust the assertion to match observed reality and note it in the Gap Ledger.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_git_states.py
git commit -m "test(integration): characterize merge/push behaviour across git states"
```

---

## Task 5: E2E characterization — `skill status` across states

**Files:**
- Modify: `tests/test_cli/test_cli_skill_status.py`

The file already covers clean/dirty/monorepo. Add the divergence states and **document that
status is drift-blind today** (Gap Ledger §1). Reuse the existing module's helpers; replicate the
env setup pattern already in the file.

- [ ] **Step 1: Write the tests**

Append to `tests/test_cli/test_cli_skill_status.py`:

```python
def _advance_upstream(env, upstream):
    import subprocess
    helper = upstream.parent / "status-advance-helper"
    subprocess.run(["git", "clone", str(upstream), str(helper)],
                   check=True, env=env, capture_output=True)
    (helper / "UPSTREAM.md").write_text("upstream\n")
    subprocess.run(["git", "-C", str(helper), "add", "-A"],
                   check=True, env=env, capture_output=True)
    subprocess.run(["git", "-C", str(helper), "commit", "-m", "up"],
                   check=True, env=env, capture_output=True)
    subprocess.run(["git", "-C", str(helper), "push", "origin", "main"],
                   check=True, env=env, capture_output=True)


def test_status_behind_still_reports_clean(git_sandbox, tmp_path, monkeypatch):
    """Documents current behaviour: status is drift-blind — a clone behind
    upstream reads 'clean'. See Gap Ledger §1."""
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    runner = CliRunner()
    r = runner.invoke(main, ["skill", "add", str(git_sandbox.upstream),
                             "--slug", "demo"])
    assert r.exit_code == 0, r.output

    # Advance upstream after the canonical was cloned.
    _advance_upstream(git_sandbox.env, git_sandbox.upstream)

    result = runner.invoke(main, ["skill", "status", "demo", "-g"])
    assert result.exit_code == 0, result.output
    assert "clean" in result.output      # drift invisible today
    assert "behind" not in result.output  # the gap, pinned


def test_status_missing_reports_missing(git_sandbox, tmp_path, monkeypatch):
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    runner = CliRunner()
    r = runner.invoke(main, ["skill", "add", str(git_sandbox.upstream),
                             "--slug", "demo"])
    assert r.exit_code == 0, r.output
    import shutil
    shutil.rmtree(library_root / "demo")
    result = runner.invoke(main, ["skill", "status", "demo", "-g"])
    assert result.exit_code == 0, result.output
    assert "missing" in result.output
```

- [ ] **Step 2: Run to verify**

Run: `uv run pytest tests/test_cli/test_cli_skill_status.py -v`
Expected: PASS. If `skill add` writes the lock somewhere other than `<root>`, the `status -g`
default-scope lookup may not find `demo` — confirm with the existing passing tests in this file
(they prove `-g` works after `add`).

- [ ] **Step 3: Commit**

```bash
git add tests/test_cli/test_cli_skill_status.py
git commit -m "test(e2e): characterize status across drift states (documents §1)"
```

---

## Task 6: E2E characterization — `skill update` across states incl. conflict

**Files:**
- Modify: `tests/test_cli/test_cli_skill_update.py`

- [ ] **Step 1: Write the tests**

Append to `tests/test_cli/test_cli_skill_update.py`. Match the env-setup idiom used by the
existing tests in this file (read its top to confirm the helper names; if it has an
`_add_global` helper, reuse it — otherwise inline the `skill add` invoke as below).

```python
import shutil
import subprocess
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def _setup_global(git_sandbox, tmp_path, monkeypatch):
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    runner = CliRunner()
    r = runner.invoke(main, ["skill", "add", str(git_sandbox.upstream),
                             "--slug", "demo"])
    assert r.exit_code == 0, r.output
    return runner, library_root


def _advance_upstream(env, upstream, name="UPSTREAM.md", body="upstream\n"):
    helper = upstream.parent / "update-advance-helper"
    if not helper.exists():
        subprocess.run(["git", "clone", str(upstream), str(helper)],
                       check=True, env=env, capture_output=True)
    (helper / name).write_text(body)
    subprocess.run(["git", "-C", str(helper), "add", "-A"],
                   check=True, env=env, capture_output=True)
    subprocess.run(["git", "-C", str(helper), "commit", "-m", "up"],
                   check=True, env=env, capture_output=True)
    subprocess.run(["git", "-C", str(helper), "push", "origin", "main"],
                   check=True, env=env, capture_output=True)


def test_update_behind_fast_forwards(git_sandbox, tmp_path, monkeypatch):
    runner, root = _setup_global(git_sandbox, tmp_path, monkeypatch)
    _advance_upstream(git_sandbox.env, git_sandbox.upstream)
    result = runner.invoke(main, ["skill", "update", "demo", "-g"])
    assert result.exit_code == 0, result.output
    assert "updated" in result.output
    assert (root / "demo" / "UPSTREAM.md").exists()


def test_update_up_to_date_still_says_updated(git_sandbox, tmp_path, monkeypatch):
    """Documents current behaviour: update prints 'updated' even when already
    current — no 'already up to date'. See Gap Ledger §2."""
    runner, root = _setup_global(git_sandbox, tmp_path, monkeypatch)
    result = runner.invoke(main, ["skill", "update", "demo", "-g"])
    assert result.exit_code == 0, result.output
    assert "updated" in result.output


def test_update_conflict_exits_nonzero_and_is_terse(git_sandbox, tmp_path, monkeypatch):
    """Documents current behaviour: conflict → exit 1 + git-literate message,
    no copy-paste resolver. See Gap Ledger §3."""
    runner, root = _setup_global(git_sandbox, tmp_path, monkeypatch)
    # Local edit in canonical, conflicting upstream edit on same file.
    (root / "demo" / "SKILL.md").write_text("local edit\n")
    subprocess.run(["git", "-C", str(root / "demo"), "commit", "-am", "local"],
                   check=True, env=git_sandbox.env, capture_output=True)
    _advance_upstream(git_sandbox.env, git_sandbox.upstream,
                      name="SKILL.md", body="upstream edit\n")
    result = runner.invoke(main, ["skill", "update", "demo", "-g"])
    assert result.exit_code == 1
    assert "conflict" in result.output.lower()
    assert "claude" not in result.output.lower()  # no resolver yet — the gap


def test_update_copymode_refuses(copymode_skill, monkeypatch):
    """copy-mode (no .git/) → refuse with re-add guidance, exit 1."""
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT",
                       str(copymode_skill.canonical.parent))
    runner = CliRunner()
    result = runner.invoke(main, ["skill", "update", "copydemo", "-g"])
    assert result.exit_code == 1
    assert "copy-mode" in result.output
```

- [ ] **Step 2: Run to verify**

Run: `uv run pytest tests/test_cli/test_cli_skill_update.py -v`
Expected: PASS. If `test_update_copymode_refuses` can't find the lock (the `copymode_skill`
fixture wrote a minimal lock), and the CLI reports "not in lock", make the fixture's lock entry
match the shape `update` reads (it only needs the slug key to reach the copy-mode branch) — adjust
the fixture's lock JSON, re-run.

- [ ] **Step 3: Commit**

```bash
git add tests/test_cli/test_cli_skill_update.py tests/conftest.py
git commit -m "test(e2e): characterize update across states + conflict (documents §2,§3)"
```

---

## Task 7: E2E characterization — `skill push` incl. clean-gap bug

**Files:**
- Modify: `tests/test_cli/test_cli_skill_push.py`

- [ ] **Step 1: Write the tests**

Append to `tests/test_cli/test_cli_skill_push.py`. The headline is the clean-gap (Gap Ledger §4):
a canonical with committed-but-unpushed work reports "nothing to push" and drops it.

```python
import subprocess

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def _setup_global(git_sandbox, tmp_path, monkeypatch):
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    runner = CliRunner()
    r = runner.invoke(main, ["skill", "add", str(git_sandbox.upstream),
                             "--slug", "demo"])
    assert r.exit_code == 0, r.output
    return runner, library_root


def test_push_clean_with_commits_ahead_drops_them(git_sandbox, tmp_path, monkeypatch):
    """Documents the clean-gap BUG: a clean tree with local commits ahead of
    origin reports 'nothing to push' and the commits never reach the remote.
    See Gap Ledger §4 — Spec 2 fixes this."""
    runner, root = _setup_global(git_sandbox, tmp_path, monkeypatch)
    canonical = root / "demo"
    # Commit locally (clean working tree, but ahead of origin).
    (canonical / "NEW.md").write_text("ahead commit\n")
    subprocess.run(["git", "-C", str(canonical), "add", "-A"],
                   check=True, env=git_sandbox.env, capture_output=True)
    subprocess.run(["git", "-C", str(canonical), "commit", "-m", "ahead"],
                   check=True, env=git_sandbox.env, capture_output=True)

    result = runner.invoke(main, ["skill", "push", "demo", "-g", "--direct"])
    assert result.exit_code == 0, result.output
    assert "nothing to push" in result.output  # the bug, pinned

    # Prove the commit did NOT reach the remote.
    head_local = subprocess.run(
        ["git", "-C", str(canonical), "rev-parse", "HEAD"],
        check=True, env=git_sandbox.env, capture_output=True, text=True).stdout.strip()
    head_remote = subprocess.run(
        ["git", "-C", str(canonical), "rev-parse", "origin/main"],
        check=True, env=git_sandbox.env, capture_output=True, text=True).stdout.strip()
    assert head_local != head_remote  # commit stranded locally


def test_push_dirty_direct_pushes(git_sandbox, tmp_path, monkeypatch):
    runner, root = _setup_global(git_sandbox, tmp_path, monkeypatch)
    canonical = root / "demo"
    (canonical / "SKILL.md").write_text("self-improvement\n")  # dirty
    result = runner.invoke(main, ["skill", "push", "demo", "-g", "--direct"])
    assert result.exit_code == 0, result.output
    assert "pushed" in result.output
    head_remote = subprocess.run(
        ["git", "-C", str(canonical), "rev-parse", "origin/main"],
        check=True, env=git_sandbox.env, capture_output=True, text=True).stdout.strip()
    head_local = subprocess.run(
        ["git", "-C", str(canonical), "rev-parse", "HEAD"],
        check=True, env=git_sandbox.env, capture_output=True, text=True).stdout.strip()
    assert head_local == head_remote


def test_push_monorepo_refused(monorepo_skill, monkeypatch):
    """read-only monorepo skill → push refused, exit 1."""
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT",
                       str(monorepo_skill.canonical.parent))
    runner = CliRunner()
    result = runner.invoke(main, ["skill", "push", "mkdocs", "-g"])
    assert result.exit_code == 1
    assert "read-only" in result.output
```

- [ ] **Step 2: Run to verify**

Run: `uv run pytest tests/test_cli/test_cli_skill_push.py -v`
Expected: PASS. The `--direct` path commits then pushes; for `test_push_dirty_direct_pushes` the
working-tree edit is committed by `push --direct` itself, so HEAD should equal origin/main after.

- [ ] **Step 3: Commit**

```bash
git add tests/test_cli/test_cli_skill_push.py
git commit -m "test(e2e): characterize push incl. clean-gap bug (documents §4,§5)"
```

---

## Task 8: Lock in doctor's offline/no-drift taxonomy

**Files:**
- Modify: `tests/test_cli/test_skill_doctor.py`

This pins that doctor is **structural and offline today** — no fetch, no `behind_upstream` /
`diverged_upstream` findings — so Spec 2's additions are a reviewed change, not silent creep
(Gap Ledger §6, §7).

- [ ] **Step 1: Read the existing doctor test to learn the `diagnose()` entry point**

Run: `uv run pytest tests/test_cli/test_skill_doctor.py -q` to confirm it passes, and read its
imports to learn how it calls `diagnose(...)` and what `Finding` looks like.

Run: `grep -n "def diagnose\|class Finding\|kind" src/agent_toolkit_cli/skill_doctor.py | head`

- [ ] **Step 2: Write the test asserting absence of drift findings**

Append to `tests/test_cli/test_skill_doctor.py`. Use the same `diagnose(...)` call signature the
existing tests use (slugs/scope/home/project). The assertion: even when the canonical is behind
upstream, `diagnose` emits **no** drift finding (it never fetches).

```python
def test_doctor_does_not_report_upstream_drift(git_sandbox, tmp_path, monkeypatch):
    """Documents current behaviour: doctor is offline — a canonical behind
    upstream produces NO drift finding. See Gap Ledger §6 (Spec 2 adds it)."""
    import subprocess
    from click.testing import CliRunner
    from agent_toolkit_cli.cli import main

    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    runner = CliRunner()
    assert runner.invoke(main, ["skill", "add", str(git_sandbox.upstream),
                                "--slug", "demo"]).exit_code == 0

    # Advance upstream so the canonical is behind.
    helper = git_sandbox.upstream.parent / "doctor-advance-helper"
    subprocess.run(["git", "clone", str(git_sandbox.upstream), str(helper)],
                   check=True, env=git_sandbox.env, capture_output=True)
    (helper / "UP.md").write_text("up\n")
    subprocess.run(["git", "-C", str(helper), "add", "-A"],
                   check=True, env=git_sandbox.env, capture_output=True)
    subprocess.run(["git", "-C", str(helper), "commit", "-m", "up"],
                   check=True, env=git_sandbox.env, capture_output=True)
    subprocess.run(["git", "-C", str(helper), "push", "origin", "main"],
                   check=True, env=git_sandbox.env, capture_output=True)

    result = runner.invoke(main, ["skill", "doctor", "-g"])
    assert result.exit_code == 0, result.output
    out = result.output.lower()
    assert "behind" not in out
    assert "newer version" not in out
    assert "update available" not in out
```

- [ ] **Step 3: Run to verify**

Run: `uv run pytest tests/test_cli/test_skill_doctor.py::test_doctor_does_not_report_upstream_drift -v`
Expected: PASS. If `skill doctor -g` requires confirmation/interactive input, pass
`input="n\n"` to `runner.invoke` (the existing doctor CLI tests show the right incantation —
mirror them).

- [ ] **Step 4: Commit**

```bash
git add tests/test_cli/test_skill_doctor.py
git commit -m "test: pin doctor as offline/no-drift today (documents §6,§7)"
```

---

## Task 9: Full suite green + Gap Ledger reconciliation

**Files:**
- Modify: `docs/superpowers/specs/2026-05-26-git-doctor-characterization-design.md` (only if a test
  revealed behaviour differing from the spec's matrix)

- [ ] **Step 1: Run the entire suite**

Run: `uv run pytest -q`
Expected: PASS, no regressions in existing tests.

- [ ] **Step 2: Reconcile the Gap Ledger with reality**

For every test annotated `# documents current behaviour — see Gap Ledger §N`, confirm the matching
row in the spec's "Scenario Matrix" and "Gap Ledger" still describes what the test actually
observed. If any test had to be adjusted (e.g. diverged produced a fast-forward, or a message
string differs), update the corresponding spec row so the ledger stays truthful. This is the
test-first payoff — the ledger must match observed reality, not the original guess.

- [ ] **Step 3: Commit any spec reconciliation**

```bash
git add docs/superpowers/specs/2026-05-26-git-doctor-characterization-design.md
git commit -m "docs(spec): reconcile gap ledger with observed characterization behaviour"
```

- [ ] **Step 4: Final verification**

Run: `uv run pytest -q`
Expected: PASS. Confirm `git log --oneline` shows the task commits on
`spec/git-doctor-characterization`.

---

## Self-Review notes (for the executor)

- **Spec coverage:** Task 1 = `divergence()`; Task 2 = state-builder fixtures; Task 3 = install
  fixtures; Tasks 4–8 = the scenario matrix (integration + e2e for status/update/push/doctor);
  Task 9 = full-suite green + Gap Ledger reconciliation. Env-leak regression is exercised
  implicitly by every fixture (autouse `_strip_git_env`); the existing
  `tests/test_conftest_git_env_scrub.py` already covers it explicitly — no new task needed.
- **Type consistency:** `Divergence.{UP_TO_DATE,AHEAD,BEHIND,DIVERGED}` is used identically in
  Tasks 1, 2, 4. `InstalledSkill(slug, canonical, lock_path, lock_text, read_only)` is defined in
  Task 3 and consumed in Tasks 6–7.
- **Path caveat (flagged twice):** the exact lock-file path written by `skill add` must be verified
  against the failing run before hardcoding in fixtures — the existing `test_cli_skill_status.py`
  proves the canonical lands at `<AGENT_TOOLKIT_SKILLS_ROOT>/<slug>`, mirror its expectations.
- **Out of scope (Spec 2), do NOT implement:** plain-language messages, `claude -p` resolver,
  doctor drift findings, the clean-gap fix, the stray-symlink audit, push-ownership check.
