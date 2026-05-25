# Project-Scope Monorepo Install Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `skill install --scope project` lay out monorepo skills correctly — a `_parents/` clone plus a canonical symlink into the nested `skillPath` — so the per-agent symlinks resolve to a directory containing `SKILL.md`.

**Architecture:** Mirror the global library's monorepo mechanics at project scope. `ensure_project_canonical()` currently clones the repo root flat into `<project>/.agents/skills/<slug>/` and drops `parentUrl`. We teach it to branch on `entry.parent_url`: when set, clone the parent into `<project>/.agents/skills/_parents/<owner>/<repo>[@ref]/` and make `<project>/.agents/skills/<slug>` a symlink into `parent/<skillPath>`. The project lock entry gains `parentUrl` so downstream commands (status/update/reset/doctor) can detect monorepo skills. `parent_clone_path()` grows an optional `root` parameter so it can resolve a project-local `_parents/` tree instead of always the global library root.

**Tech Stack:** Python 3, Click, pytest, `git` via `skill_git`, file:// fixture repos (`tests/fixtures/monorepo_skills`), `scrub_git_env()` from `tests/conftest.py`.

---

## File Structure

- `src/agent_toolkit_cli/skill_paths.py` — `parent_clone_path()` gains optional `root: Path | None`. When `root` is given, `_parents/` lives under it; otherwise the global `library_root()` (unchanged default). Add `project_parents_root(project)` helper returning `<project>/.agents/skills`.
- `src/agent_toolkit_cli/skill_install.py` — `ensure_project_canonical()` branches on `entry.parent_url`. Flat-clone path unchanged for non-monorepo skills; new parent-clone-+-symlink path for monorepo skills. Project lock entry now carries `parent_url`.
- `tests/test_cli/test_skill_install_project_monorepo.py` — new file. End-to-end coverage of project-scope monorepo install, mirroring `test_skill_add_monorepo.py` conventions.
- `tests/test_cli/test_skill_paths.py` — add unit coverage for `parent_clone_path(root=...)` and `project_parents_root()`.

Non-monorepo project installs (flat `skillPath="SKILL.md"`) must keep working unchanged — the branch is purely additive.

---

### Task 1: `parent_clone_path` accepts a project-local root

**Files:**
- Modify: `src/agent_toolkit_cli/skill_paths.py:103-114`
- Test: `tests/test_cli/test_skill_paths.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli/test_skill_paths.py`:

```python
def test_parent_clone_path_project_root(tmp_path):
    from agent_toolkit_cli.skill_paths import parent_clone_path, project_parents_root

    project = tmp_path / "proj"
    root = project_parents_root(project)
    assert root == project / ".agents" / "skills"

    p = parent_clone_path("vercel-labs", "agent-browser", ref=None, root=root)
    assert p == project / ".agents" / "skills" / "_parents" / "vercel-labs" / "agent-browser"

    p_ref = parent_clone_path("o", "r", ref="dev", root=root)
    assert p_ref == project / ".agents" / "skills" / "_parents" / "o" / "r@dev"


def test_parent_clone_path_default_root_unchanged(tmp_path, monkeypatch):
    from agent_toolkit_cli.skill_paths import parent_clone_path, library_root

    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(tmp_path / "lib" / "skills"))
    p = parent_clone_path("o", "r", ref=None)
    assert p == library_root() / "_parents" / "o" / "r"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_skill_paths.py::test_parent_clone_path_project_root -v`
Expected: FAIL — `ImportError: cannot import name 'project_parents_root'` (or `TypeError: parent_clone_path() got an unexpected keyword argument 'root'`).

- [ ] **Step 3: Write minimal implementation**

In `src/agent_toolkit_cli/skill_paths.py`, replace the existing `parent_clone_path` definition (lines 103-114) with:

```python
def parent_clone_path(
    owner: str, repo: str, *, ref: str | None,
    env: dict[str, str] | None = None,
    root: Path | None = None,
) -> Path:
    """Where a monorepo parent is cloned, shared across all skills from it.

    Global scope (root=None): <library_root>/_parents/<owner>/<repo>[@<ref>]/
    so the cache is inside the AGENT_TOOLKIT_SKILLS_ROOT blast radius and
    travels with --toolkit-repo overrides.

    Project scope: pass root=<project>/.agents/skills (see project_parents_root)
    so the cache is <project>/.agents/skills/_parents/<owner>/<repo>[@<ref>]/.
    """
    base = root if root is not None else library_root(env)
    leaf = repo if ref is None else f"{repo}@{ref}"
    return base / "_parents" / owner / leaf


def project_parents_root(project: Path) -> Path:
    """Root under which a project's monorepo `_parents/` cache lives.

    This is the same directory that holds project canonical skill dirs:
    <project>/.agents/skills. Passed as `root=` to parent_clone_path().
    """
    return project / ".agents" / "skills"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli/test_skill_paths.py -v`
Expected: PASS (both new tests plus all pre-existing path tests).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/skill_paths.py tests/test_cli/test_skill_paths.py
git commit -m "feat(skill paths): parent_clone_path accepts project-local root"
```

---

### Task 2: `ensure_project_canonical` handles monorepo skills

**Files:**
- Modify: `src/agent_toolkit_cli/skill_install.py:365-409`
- Test: `tests/test_cli/test_skill_install_project_monorepo.py` (created in Task 3 covers end-to-end; this task adds the engine branch and a focused unit test below)

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli/test_skill_install_project_monorepo.py` with this first test (the file is fleshed out further in Task 3):

```python
"""Project-scope monorepo install: _parents clone + canonical symlink."""
import json
import subprocess
from pathlib import Path

import pytest

from agent_toolkit_cli import skill_install
from agent_toolkit_cli.skill_lock import (
    LockEntry, add_entry, read_lock, write_lock,
)
from agent_toolkit_cli.skill_paths import library_lock_path

from tests.conftest import scrub_git_env


FIXTURE = Path(__file__).parent.parent / "fixtures" / "monorepo_skills"


def _make_parent_repo(tmp_path: Path) -> str:
    parent_src = tmp_path / "parent-src"
    subprocess.run(["cp", "-R", str(FIXTURE), str(parent_src)], check=True)
    env = scrub_git_env()
    subprocess.run(["git", "init", "-q", "-b", "main"],
                   cwd=parent_src, check=True, env=env)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "add", "."], cwd=parent_src, check=True, env=env)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "-m", "init"],
                   cwd=parent_src, check=True, env=env)
    return f"file://{parent_src}"


@pytest.fixture
def isolated_library(tmp_path, monkeypatch):
    library = tmp_path / "library"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library / "skills"))
    return library


def _seed_global_monorepo_entry(library: Path, parent_url: str, slug: str,
                                 subpath: str) -> None:
    """Write a global lock entry as `skill add` would for a monorepo skill."""
    lock_path = library_lock_path()
    lock = read_lock(lock_path)
    entry = LockEntry(
        source="vercel-labs/agent-browser",
        source_type="github",
        ref=None,
        skill_path=subpath,
        upstream_sha=None,
        local_sha=None,
        parent_url=parent_url,
        read_only=True,
    )
    write_lock(lock_path, add_entry(lock, slug, entry))


def test_ensure_project_canonical_monorepo_symlinks_into_parent(
    tmp_path, isolated_library,
):
    library = isolated_library
    parent_url = _make_parent_repo(tmp_path)
    _seed_global_monorepo_entry(library, parent_url, "mkdocs", "mkdocs")

    project = tmp_path / "proj"
    project.mkdir()

    canonical = skill_install.ensure_project_canonical(
        slug="mkdocs",
        project=project,
        global_lock_path=library_lock_path(),
        env=scrub_git_env(),
    )

    # Canonical is a symlink into the project-local parent clone.
    assert canonical.is_symlink()
    assert (canonical / "SKILL.md").exists()
    assert (canonical / "SKILL.md").read_text().startswith("---\nname: mkdocs")

    parents = project / ".agents" / "skills" / "_parents"
    parent_clones = list(parents.glob("*/*"))
    assert len(parent_clones) == 1
    assert (parent_clones[0] / "mkdocs" / "SKILL.md").exists()

    # Project lock carries parentUrl + skillPath so downstream cmds detect it.
    proj_lock = json.loads((project / "skills-lock.json").read_text())
    e = proj_lock["skills"]["mkdocs"]
    assert e["skillPath"] == "mkdocs"
    assert e["parentUrl"].endswith("/parent-src")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_skill_install_project_monorepo.py::test_ensure_project_canonical_monorepo_symlinks_into_parent -v`
Expected: FAIL — `canonical.is_symlink()` is False (current code flat-clones the repo root), and `parentUrl` absent from the project lock.

- [ ] **Step 3: Write minimal implementation**

In `src/agent_toolkit_cli/skill_install.py`, replace the body of `ensure_project_canonical` (the clone block at lines 390-407) so it branches on `entry.parent_url`. Replace:

```python
    project_canonical = project / ".agents" / "skills" / slug
    if not project_canonical.exists():
        project_canonical.parent.mkdir(parents=True, exist_ok=True)
        source_url = clone_url_from_entry(entry)
        skill_git.clone(source_url, project_canonical, ref=entry.ref, env=env)

    project_lock_path = lock_file_path(scope="project", project=project)
    project_lock = read_lock(project_lock_path)
    if slug not in project_lock.skills:
        proj_entry = LockEntry(
            source=entry.source,
            source_type=entry.source_type,
            ref=entry.ref,
            skill_path=entry.skill_path,
            upstream_sha=None,
            local_sha=None,
        )
        write_lock(project_lock_path, add_entry(project_lock, slug, proj_entry))

    return project_canonical
```

with:

```python
    from agent_toolkit_cli.skill_paths import (
        parent_clone_path, project_parents_root,
    )

    project_canonical = project / ".agents" / "skills" / slug

    if entry.parent_url is not None:
        # Monorepo skill: clone the parent into the project-local _parents/
        # cache and symlink the canonical into parent/<skillPath>, mirroring
        # the global library layout.
        if entry.skill_path is None:
            raise InstallError(
                f"{slug}: monorepo lock entry missing skillPath"
            )
        owner, repo = entry.source.split("/", 1)
        parent_dir = parent_clone_path(
            owner, repo, ref=entry.ref,
            root=project_parents_root(project), env=env,
        )
        if not parent_dir.exists():
            parent_dir.parent.mkdir(parents=True, exist_ok=True)
            skill_git.clone(
                entry.parent_url, parent_dir, ref=entry.ref, env=env,
            )
        skill_root = parent_dir / entry.skill_path
        if not (skill_root / "SKILL.md").exists():
            raise InstallError(
                f"{slug}: {entry.skill_path}/SKILL.md not found in parent "
                f"clone at {parent_dir}"
            )
        if not project_canonical.exists() and not project_canonical.is_symlink():
            project_canonical.parent.mkdir(parents=True, exist_ok=True)
            project_canonical.symlink_to(skill_root)
    elif not project_canonical.exists():
        # Single-skill repo: clone the repo root flat into the canonical dir.
        project_canonical.parent.mkdir(parents=True, exist_ok=True)
        source_url = clone_url_from_entry(entry)
        skill_git.clone(source_url, project_canonical, ref=entry.ref, env=env)

    project_lock_path = lock_file_path(scope="project", project=project)
    project_lock = read_lock(project_lock_path)
    if slug not in project_lock.skills:
        proj_entry = LockEntry(
            source=entry.source,
            source_type=entry.source_type,
            ref=entry.ref,
            skill_path=entry.skill_path,
            upstream_sha=None,
            local_sha=None,
            parent_url=entry.parent_url,
            read_only=entry.read_only,
        )
        write_lock(project_lock_path, add_entry(project_lock, slug, proj_entry))

    return project_canonical
```

Note: `read_only` is a field on `LockEntry` (confirmed in `skill_lock.py`). If the engineer finds the constructor rejects it, check the actual field name in `skill_lock.py` and match it; the intent is to propagate the global entry's read-only flag.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_skill_install_project_monorepo.py::test_ensure_project_canonical_monorepo_symlinks_into_parent -v`
Expected: PASS.

- [ ] **Step 5: Run the regression guard for non-monorepo project installs**

Run: `uv run pytest tests/test_cli/test_skill_install_engine.py -v`
Expected: PASS — the flat-clone path for single-skill repos is unchanged.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/skill_install.py tests/test_cli/test_skill_install_project_monorepo.py
git commit -m "fix(skill install): project-scope monorepo clones parent + symlinks canonical"
```

---

### Task 3: End-to-end `skill install -p` and per-agent symlink resolution

**Files:**
- Modify: `tests/test_cli/test_skill_install_project_monorepo.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli/test_skill_install_project_monorepo.py`:

```python
from click.testing import CliRunner

from agent_toolkit_cli.cli import main as cli


def test_install_p_monorepo_claude_symlink_resolves_to_skill_md(
    tmp_path, isolated_library, monkeypatch,
):
    library = isolated_library
    parent_url = _make_parent_repo(tmp_path)
    _seed_global_monorepo_entry(library, parent_url, "mkdocs", "mkdocs")

    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.chdir(project)

    runner = CliRunner(env=scrub_git_env())
    result = runner.invoke(cli, [
        "skill", "install", "mkdocs", "--agents", "claude-code", "-p",
    ])
    assert result.exit_code == 0, result.output

    # The claude-code projection symlink must resolve to a dir with SKILL.md.
    link = project / ".claude" / "skills" / "mkdocs"
    assert link.is_symlink()
    assert (link / "SKILL.md").exists(), (
        "claude-code symlink does not resolve to SKILL.md — the original bug"
    )
    assert (link / "SKILL.md").read_text().startswith("---\nname: mkdocs")
```

- [ ] **Step 2: Run test to verify it fails — or passes**

Run: `uv run pytest tests/test_cli/test_skill_install_project_monorepo.py::test_install_p_monorepo_claude_symlink_resolves_to_skill_md -v`
Expected: PASS, because Task 2 already fixed `ensure_project_canonical`, which `install_cmd` calls. This test exists to lock in the end-to-end guarantee at the command boundary (the exact symptom the user hit). If it FAILS, the projection symlink in `apply()` is pointing at the canonical dir itself — confirm `agent_projection_dir` resolves through the canonical symlink; do not change `apply()` unless this test fails.

- [ ] **Step 3: (Conditional) only if Step 2 failed**

If and only if the test failed, inspect `skill_install.apply()` symlink creation (lines 280-299): the projection link is created with `link.symlink_to(canonical)`. Since `canonical` is itself now a symlink to `skill_root`, the OS resolves it transitively, so `link/SKILL.md` should exist. If the failure is a `conflicting symlink` error instead, it means a stale projection from a prior run exists — the test's `tmp_path` isolation should prevent that; re-read the error and fix the test setup, not production code.

- [ ] **Step 4: Run the full project-monorepo test file**

Run: `uv run pytest tests/test_cli/test_skill_install_project_monorepo.py -v`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add tests/test_cli/test_skill_install_project_monorepo.py
git commit -m "test(skill install): e2e project monorepo symlink resolves to SKILL.md"
```

---

### Task 4: Full suite + lint, then renormalize ryanair_fares

**Files:** none (verification + manual repair re-run)

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest -q`
Expected: PASS, no regressions. If `test_skill_update_monorepo.py` / `test_skill_reset_monorepo.py` assert "monorepo X only supported at global scope", they remain valid — this plan does NOT enable project-scope update/reset (out of scope; see Note below). Confirm those tests still pass unchanged.

- [ ] **Step 2: Run the linter**

Run: `uv run ruff check src/ tests/`
Expected: clean. Fix any import-ordering or unused-import findings introduced by the edits.

- [ ] **Step 3: Renormalize the user's ryanair_fares project**

The earlier manual symlink repair fixed visibility but left flat repo-root clones and a `parentUrl`-less project lock. After the CLI fix is installed, do a clean reinstall so the project matches the new layout. Run from the agent-toolkit-cli repo:

```bash
uv tool install --reinstall --from . agent-toolkit-cli
```

Then, for the user's project — remove the manually-repaired entries and reinstall via the fixed CLI:

```bash
cd /Users/ajanderson/GitHub/projects/ryanair_fares
agent-toolkit-cli skill uninstall agent-browser --agents claude-code -p
agent-toolkit-cli skill uninstall frontend-design --agents claude-code -p
# remove the flat repo-root clones left by the old buggy install
rm -rf .agents/skills/agent-browser .agents/skills/frontend-design
agent-toolkit-cli skill install agent-browser --agents claude-code -p
agent-toolkit-cli skill install frontend-design --agents claude-code -p
```

- [ ] **Step 4: Verify ryanair_fares is fully normalized**

```bash
cd /Users/ajanderson/GitHub/projects/ryanair_fares
ls -la .agents/skills/_parents/*/*
test -f .claude/skills/agent-browser/SKILL.md && echo "agent-browser OK"
test -f .claude/skills/frontend-design/SKILL.md && echo "frontend-design OK"
python3 -c "import json; e=json.load(open('skills-lock.json'))['skills']['agent-browser']; assert e.get('parentUrl'), e; print('lock parentUrl OK')"
```

Expected: `_parents/` clones present, both SKILL.md resolve, lock carries `parentUrl`.

- [ ] **Step 5: Commit any remaining test/lint fixes**

```bash
git add -A
git commit -m "chore: lint + suite green for project monorepo install"
```

---

## Note on out-of-scope follow-ups

`skill update` and `skill reset` still print "monorepo X only supported at global scope" and `parent_clone_path()` calls in those commands still use the global root. With this fix, project-scope monorepo skills now exist as `_parents` clones, so enabling project-scope update/reset is a natural follow-up — but it is NOT required to fix the reported bug (install visibility) and is deliberately excluded. `skill doctor -p` stray-symlink detection ([[project_tui_apply_error_clobber]]) should be sanity-checked against the new `_parents` layout in that follow-up too. File as a separate issue/PR.

---

## Self-Review

**Spec coverage:** Reported bug = monorepo project install produces unusable layout (symlink → repo root, no SKILL.md). Task 1 enables a project-local `_parents` root; Task 2 makes `ensure_project_canonical` build the parent-clone-+-symlink layout and record `parentUrl`; Task 3 locks the end-to-end symptom (claude-code symlink resolves to SKILL.md); Task 4 verifies no regressions and renormalizes the user's project. Covered.

**Placeholder scan:** No TBD/TODO; all code steps contain full code; all commands have expected output. The one conditional (Task 3 Step 3) is explicitly gated and explains when it applies.

**Type consistency:** `parent_clone_path(root=...)`, `project_parents_root(project)`, `entry.parent_url`, `entry.skill_path`, `entry.read_only`, `LockEntry(...)` — all match `skill_paths.py` / `skill_lock.py` as read during planning. `read_only` propagation has an explicit fallback note in Task 2 Step 3 in case the field name differs.
