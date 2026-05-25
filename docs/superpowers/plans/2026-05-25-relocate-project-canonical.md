# Relocate Project Canonical Out of the Project Tree — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move a project-scope skill's canonical clone and `_parents/` cache out of `<project>/.agents/skills/` to a per-project store under `~/.agent-toolkit/projects/<id>/skills/`, so the project tree holds only symlinks + the lock file, and uninstall never destroys a clone.

**Architecture:** Add `project_id()` + `project_store_root()` to `skill_paths.py` and repoint `canonical_skill_dir(scope="project")` and `project_parents_root()` at the new store. Invert the project-universal symlink-skip rule so every agent (universal included) gets a projection symlink → external canonical. Add idempotent `migrate_project_canonical()` (move in-tree clone out, back up collisions) called from `ensure_project_canonical`. Make project-scope `uninstall()` non-destructive (symlinks + lock entry only). Add an orphan sweep to `skill doctor -p`. Fix `status -p`'s missing `root=` on `parent_clone_path`.

**Tech Stack:** Python 3, Click, pytest, `git` via `skill_git`, file:// fixture repos (`tests/fixtures/monorepo_skills`), `scrub_git_env()` from `tests/conftest.py`, `hashlib`, `shutil`.

**Spec:** `docs/superpowers/specs/2026-05-25-relocate-project-canonical-design.md`

---

## File Structure

- `src/agent_toolkit_cli/skill_paths.py` — new `project_id()`, `project_store_root()`; repoint `canonical_skill_dir(scope="project")` and `project_parents_root()`.
- `src/agent_toolkit_cli/skill_install.py` — invert `_should_skip_symlink`/`_current_linked_agents` project-universal branches; new `migrate_project_canonical()`; `ensure_project_canonical` uses the store + calls migration; `uninstall()` non-destructive at project scope; update module header comment.
- `src/agent_toolkit_cli/skill_doctor.py` — new `_scan_orphan_canonicals()` + `Finding`/`FixAction`, wired into `diagnose()`.
- `src/agent_toolkit_cli/commands/skill/status_cmd.py` — pass `root=` to `parent_clone_path` at project scope.
- `tests/test_cli/test_skill_paths.py` — unit tests for the new helpers.
- `tests/test_cli/test_relocate_project_canonical.py` — new file: install layout, universal symlink, migration, uninstall, doctor orphan sweep, status fix.

Non-project-scope behavior (global install/uninstall/doctor/status) must remain unchanged — every change is gated on `scope == "project"`.

---

### Task 1: `project_id` + `project_store_root` path helpers

**Files:**
- Modify: `src/agent_toolkit_cli/skill_paths.py` (add after `library_skill_path`, ~line 100)
- Test: `tests/test_cli/test_skill_paths.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli/test_skill_paths.py`:

```python
def test_project_id_stable_and_sanitized(tmp_path):
    from agent_toolkit_cli.skill_paths import project_id

    p = tmp_path / "GitHub" / "ryanair_fares"
    p.mkdir(parents=True)
    pid1 = project_id(p)
    pid2 = project_id(p)
    assert pid1 == pid2, "same path must yield same id"
    # Sanitized prefix is human-readable: no slashes, ends with -<6 hex>.
    assert "/" not in pid1
    prefix, _, suffix = pid1.rpartition("-")
    assert len(suffix) == 6 and all(c in "0123456789abcdef" for c in suffix)
    assert "ryanair_fares" in prefix


def test_project_id_distinct_paths_distinct_ids(tmp_path):
    from agent_toolkit_cli.skill_paths import project_id

    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    assert project_id(a) != project_id(b)


def test_project_store_root_under_library_parent(tmp_path, monkeypatch):
    from agent_toolkit_cli.skill_paths import (
        project_store_root, project_id, library_root,
    )

    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(tmp_path / "lib" / "skills"))
    project = tmp_path / "proj"
    project.mkdir()
    root = project_store_root(project)
    assert root == library_root().parent / "projects" / project_id(project) / "skills"
    # i.e. <tmp>/lib/projects/<id>/skills
    assert root == tmp_path / "lib" / "projects" / project_id(project) / "skills"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli/test_skill_paths.py::test_project_id_stable_and_sanitized tests/test_cli/test_skill_paths.py::test_project_store_root_under_library_parent -v`
Expected: FAIL — `ImportError: cannot import name 'project_id'` / `'project_store_root'`.

- [ ] **Step 3: Add the helpers**

In `src/agent_toolkit_cli/skill_paths.py`, add `import hashlib` near the top (after `import os`), then add after `library_skill_path` (~line 100):

```python
def project_id(project: Path) -> str:
    """Stable, collision-free directory name for a project's skill store.

    Sanitized absolute path + 6-hex-char sha256 suffix. The sanitized prefix
    keeps doctor output and on-disk inspection human-readable; the hash suffix
    guarantees uniqueness even if two distinct paths sanitize to the same
    string. Taken over project.resolve() so symlinked/relative invocations of
    the same project map to one id.
    """
    real = project.resolve()
    abs_str = str(real)
    sanitized = "".join(
        c if (c.isalnum() or c in "._-") else "-" for c in abs_str
    ).strip("-")
    digest = hashlib.sha256(abs_str.encode()).hexdigest()[:6]
    return f"{sanitized}-{digest}"


def project_store_root(project: Path, *, env: dict[str, str] | None = None) -> Path:
    """Per-project skill store: <library_root>.parent/projects/<id>/skills.

    Holds project canonical skill dirs AND the project's _parents/ cache.
    Lives under ~/.agent-toolkit (library_root().parent) by default, OUTSIDE
    the project tree, so removing a skill never touches project files.
    Honors $AGENT_TOOLKIT_SKILLS_ROOT via library_root(env).
    """
    return library_root(env).parent / "projects" / project_id(project) / "skills"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli/test_skill_paths.py -v`
Expected: PASS (3 new tests + all pre-existing path tests).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/skill_paths.py tests/test_cli/test_skill_paths.py
git commit -m "feat(skill paths): project_id + project_store_root for external canonical"
```

---

### Task 2: Repoint `canonical_skill_dir` + `project_parents_root` at the store

**Files:**
- Modify: `src/agent_toolkit_cli/skill_paths.py:54-58` (`canonical_skill_dir` project branch) and `:123-129` (`project_parents_root`)
- Test: `tests/test_cli/test_skill_paths.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli/test_skill_paths.py`:

```python
def test_canonical_skill_dir_project_uses_store(tmp_path, monkeypatch):
    from agent_toolkit_cli.skill_paths import (
        canonical_skill_dir, project_store_root,
    )

    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(tmp_path / "lib" / "skills"))
    project = tmp_path / "proj"
    project.mkdir()
    got = canonical_skill_dir("mkdocs", scope="project", project=project)
    assert got == project_store_root(project) / "mkdocs"
    # Specifically NOT inside the project tree.
    assert ".agents" not in str(got)


def test_project_parents_root_uses_store(tmp_path, monkeypatch):
    from agent_toolkit_cli.skill_paths import (
        project_parents_root, project_store_root,
    )

    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(tmp_path / "lib" / "skills"))
    project = tmp_path / "proj"
    project.mkdir()
    assert project_parents_root(project) == project_store_root(project)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli/test_skill_paths.py::test_canonical_skill_dir_project_uses_store tests/test_cli/test_skill_paths.py::test_project_parents_root_uses_store -v`
Expected: FAIL — both still return the old `<project>/.agents/skills/...` paths.

- [ ] **Step 3: Repoint both functions**

In `canonical_skill_dir`, replace the project-scope return (line 58):

```python
    return project / ".agents" / "skills" / slug
```

with:

```python
    return project_store_root(project) / slug
```

And update its docstring line `Project scope: <project>/.agents/skills/<slug>/ (unchanged from v2.1).` to `Project scope: <store_root>/<slug> (external store; see project_store_root).`

Replace the body of `project_parents_root` (lines 123-129):

```python
def project_parents_root(project: Path) -> Path:
    """Root under which a project's monorepo `_parents/` cache lives.

    This is the per-project external store (project_store_root), the same
    directory that holds project canonical skill dirs. Passed as `root=` to
    parent_clone_path().
    """
    return project_store_root(project)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli/test_skill_paths.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/skill_paths.py tests/test_cli/test_skill_paths.py
git commit -m "feat(skill paths): project canonical + parents resolve to external store"
```

---

### Task 3: Invert the project-universal symlink-skip rule

**Files:**
- Modify: `src/agent_toolkit_cli/skill_install.py:91-117` (`_should_skip_symlink`), `:151-196` (`_current_linked_agents`), `:240-264` (`apply` universal-token project branch), `:8-11` (header comment)
- Test: `tests/test_cli/test_relocate_project_canonical.py` (created here)

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli/test_relocate_project_canonical.py`:

```python
"""Relocated project canonical: external store + uniform projection symlinks."""
import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli import skill_install
from agent_toolkit_cli.cli import main as cli
from agent_toolkit_cli.skill_lock import LockEntry, add_entry, read_lock, write_lock
from agent_toolkit_cli.skill_paths import (
    canonical_skill_dir, library_lock_path, project_store_root,
)

from tests.conftest import scrub_git_env

FIXTURE = Path(__file__).parent.parent / "fixtures" / "monorepo_skills"


def _make_parent_repo(tmp_path: Path) -> str:
    parent_src = tmp_path / "parent-src"
    subprocess.run(["cp", "-R", str(FIXTURE), str(parent_src)], check=True)
    env = scrub_git_env()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=parent_src, check=True, env=env)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
                   cwd=parent_src, check=True, env=env)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "-m", "init"], cwd=parent_src, check=True, env=env)
    return f"file://{parent_src}"


@pytest.fixture
def isolated_library(tmp_path, monkeypatch):
    library = tmp_path / "library"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library / "skills"))
    return library


def _seed_global_monorepo_entry(parent_url: str, slug: str, subpath: str) -> None:
    lock_path = library_lock_path()
    lock = read_lock(lock_path)
    entry = LockEntry(
        source="vercel-labs/agent-browser", source_type="github", ref=None,
        skill_path=subpath, upstream_sha=None, local_sha=None,
        parent_url=parent_url, read_only=True,
    )
    write_lock(lock_path, add_entry(lock, slug, entry))


def test_project_universal_gets_symlink_into_external_store(
    tmp_path, isolated_library, monkeypatch,
):
    parent_url = _make_parent_repo(tmp_path)
    _seed_global_monorepo_entry(parent_url, "mkdocs", "mkdocs")
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.chdir(project)

    runner = CliRunner(env=scrub_git_env())
    result = runner.invoke(cli, ["skill", "install", "mkdocs",
                                 "--agents", "claude-code", "-p"])
    assert result.exit_code == 0, result.output

    # Canonical lives in the EXTERNAL store, not the project tree.
    canonical = canonical_skill_dir("mkdocs", scope="project", project=project)
    assert canonical == project_store_root(project) / "mkdocs"
    assert (canonical / "SKILL.md").exists()

    # The universal-agent dir (.agents/skills) now holds a real symlink → store.
    uni = project / ".agents" / "skills" / "mkdocs"
    assert uni.is_symlink(), "project-universal must now get a projection symlink"
    assert (uni / "SKILL.md").exists()

    # Project tree holds NO real git clone — only symlinks.
    assert not (project / ".agents" / "skills" / "_parents").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_relocate_project_canonical.py::test_project_universal_gets_symlink_into_external_store -v`
Expected: FAIL — `uni.is_symlink()` is False (project-universal is skipped today), and/or canonical assertion fails because `ensure_project_canonical` still writes into `.agents/skills` (fixed in Task 4).

- [ ] **Step 3: Invert the skip rule**

In `_should_skip_symlink` (lines 108-117), replace:

```python
    if cfg.is_universal:
        # Project canonical IS the universal-agent install path — no symlink.
        if scope == "project":
            return True, "universal-project"
        # Global universal agents get a symlink ~/.agents/skills/<slug> → library,
        # created via the universal bundle path in apply(). Per-agent universal
        # symlinks (e.g. cfg.global_skills_dir) resolve through ~/.agents/skills/
        # already at the OS level, so we skip the redundant per-agent write.
        return True, "universal-global"
    return False, ""
```

with:

```python
    if cfg.is_universal and scope == "global":
        # Global universal agents get a symlink ~/.agents/skills/<slug> → library,
        # created via the universal bundle path in apply(). Per-agent universal
        # symlinks resolve through ~/.agents/skills/ already at the OS level, so
        # we skip the redundant per-agent write.
        return True, "universal-global"
    # Project-scope universal agents are NOT skipped: the canonical now lives in
    # the external store, so the universal agent reaches it via a per-slug
    # symlink in <project>/.agents/skills/<slug> like every other agent.
    return False, ""
```

In `_current_linked_agents` (lines 182-189), remove the project-universal special case. Replace:

```python
        skip, _ = _should_skip_symlink(
            agent_name=name, scope=scope, project=project,
        )
        if skip:
            # For project-scope universal agents, 'linked' means canonical exists.
            if scope == "project" and canonical_exists:
                linked.append(name)
            continue
```

with:

```python
        skip, _ = _should_skip_symlink(
            agent_name=name, scope=scope, project=project,
        )
        if skip:
            continue
```

(`canonical_exists` may now be unused; if ruff/pyright flags it, delete the `canonical_exists = canonical.exists()` line at ~167 — but verify it isn't referenced elsewhere in the function first.)

In `apply`, the universal-token project branch (lines 261-264) currently does `skipped.append(name)` for project scope. That branch handles the synthetic `"universal"` bundle token, which is only meaningful at global scope; leave it as-is (project-scope universal-token is still a no-op — the *per-agent* universal symlink is what now gets created via the normal loop). No change needed here, but confirm the test passes; if the synthetic token path interferes, the fix is isolated to that branch.

Update the module header comment (lines 8-11) so the project+universal line reads:

```python
#   - Project + universal               → symlink → external canonical (store)
```

- [ ] **Step 4: Run test — expect it to still fail on the canonical location**

Run: `uv run pytest tests/test_cli/test_relocate_project_canonical.py::test_project_universal_gets_symlink_into_external_store -v`
Expected: the symlink assertion may now pass, but the canonical-location assertion still FAILS because `ensure_project_canonical` writes into `.agents/skills`. That is fixed in Task 4. If the whole test passes already (because `canonical_skill_dir` is used by `apply` for symlink targets), great — proceed. Either way, do NOT modify production code further in this task.

- [ ] **Step 5: Run the global-scope regression guard**

Run: `uv run pytest tests/test_cli/test_skill_install_engine.py -v`
Expected: PASS — global universal behavior is unchanged.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/skill_install.py tests/test_cli/test_relocate_project_canonical.py
git commit -m "feat(skill install): project-universal agents get projection symlink"
```

---

### Task 4: `ensure_project_canonical` uses the external store + calls migration

**Files:**
- Modify: `src/agent_toolkit_cli/skill_install.py:356-453` (`ensure_project_canonical`)
- Test: `tests/test_cli/test_relocate_project_canonical.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli/test_relocate_project_canonical.py`:

```python
def test_ensure_project_canonical_writes_to_external_store(
    tmp_path, isolated_library,
):
    parent_url = _make_parent_repo(tmp_path)
    _seed_global_monorepo_entry(parent_url, "mkdocs", "mkdocs")
    project = tmp_path / "proj"
    project.mkdir()

    canonical = skill_install.ensure_project_canonical(
        slug="mkdocs", project=project,
        global_lock_path=library_lock_path(), env=scrub_git_env(),
    )
    assert canonical == project_store_root(project) / "mkdocs"
    assert canonical.is_symlink()  # monorepo → symlink into store _parents
    assert (canonical / "SKILL.md").exists()
    # _parents cache is in the store, not the project tree.
    assert (project_store_root(project) / "_parents").exists()
    assert not (project / ".agents" / "skills" / "_parents").exists()
    # Project lock still carries parentUrl.
    e = json.loads((project / "skills-lock.json").read_text())["skills"]["mkdocs"]
    assert e["parentUrl"].endswith("/parent-src")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_relocate_project_canonical.py::test_ensure_project_canonical_writes_to_external_store -v`
Expected: FAIL — canonical resolves under `<project>/.agents/skills` (hardcoded at line 387), so the `project_store_root` assertion fails.

- [ ] **Step 3: Switch `ensure_project_canonical` to the store + call migration**

In `ensure_project_canonical`, replace the hardcoded canonical (line 387):

```python
    project_canonical = project / ".agents" / "skills" / slug
```

with:

```python
    from agent_toolkit_cli.skill_paths import canonical_skill_dir
    migrate_project_canonical(project=project, slug=slug)
    project_canonical = canonical_skill_dir(slug, scope="project", project=project)
```

`migrate_project_canonical` is defined in Task 5; for this task, add a temporary stub at module level so the import resolves (Task 5 replaces the body):

```python
def migrate_project_canonical(*, project: Path, slug: str) -> None:
    """Stub — full body added in Task 5."""
    return None
```

The rest of `ensure_project_canonical` already uses `project_canonical` and `project_parents_root(project)` (which now points at the store via Task 2), so the monorepo and single-skill branches now operate against the external store with no further edits.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_relocate_project_canonical.py::test_ensure_project_canonical_writes_to_external_store -v`
Expected: PASS.

- [ ] **Step 5: Run the e2e universal test from Task 3 (now fully green)**

Run: `uv run pytest tests/test_cli/test_relocate_project_canonical.py::test_project_universal_gets_symlink_into_external_store -v`
Expected: PASS — canonical is now in the store; projection symlink resolves.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/skill_install.py tests/test_cli/test_relocate_project_canonical.py
git commit -m "feat(skill install): ensure_project_canonical targets external store"
```

---

### Task 5: `migrate_project_canonical` — move in-tree clone out, back up collisions

**Files:**
- Modify: `src/agent_toolkit_cli/skill_install.py` (replace the Task 4 stub)
- Test: `tests/test_cli/test_relocate_project_canonical.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli/test_relocate_project_canonical.py`:

```python
def _make_intree_clone(project: Path, slug: str, marker: str) -> Path:
    """Simulate an old-layout in-tree single-skill clone with a marker file."""
    old = project / ".agents" / "skills" / slug
    old.mkdir(parents=True)
    (old / "SKILL.md").write_text(f"---\nname: {slug}\n---\n")
    (old / "MARKER.txt").write_text(marker)
    env = scrub_git_env()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=old, check=True, env=env)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "add", "."], cwd=old, check=True, env=env)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "-m", "x"], cwd=old, check=True, env=env)
    return old


def test_migrate_moves_intree_clone_to_store(tmp_path, isolated_library):
    project = tmp_path / "proj"
    project.mkdir()
    _make_intree_clone(project, "solo", "keepme")

    skill_install.migrate_project_canonical(project=project, slug="solo")

    dest = project_store_root(project) / "solo"
    assert dest.is_dir() and not dest.is_symlink()
    assert (dest / "MARKER.txt").read_text() == "keepme"  # dirty work preserved
    assert (dest / ".git").exists()  # git history travels
    # Old in-tree path is now a symlink → store.
    old = project / ".agents" / "skills" / "solo"
    assert old.is_symlink()
    assert old.resolve() == dest.resolve()


def test_migrate_is_idempotent(tmp_path, isolated_library):
    project = tmp_path / "proj"
    project.mkdir()
    _make_intree_clone(project, "solo", "v1")
    skill_install.migrate_project_canonical(project=project, slug="solo")
    # Second run: old is already a symlink into the store → no-op.
    skill_install.migrate_project_canonical(project=project, slug="solo")
    dest = project_store_root(project) / "solo"
    assert (dest / "MARKER.txt").read_text() == "v1"
    assert not list((project_store_root(project)).glob("solo.bak-*"))


def test_migrate_backs_up_destination_collision(tmp_path, isolated_library):
    project = tmp_path / "proj"
    project.mkdir()
    # Pre-existing dest in the store.
    dest = project_store_root(project) / "solo"
    dest.mkdir(parents=True)
    (dest / "OLD.txt").write_text("old-dest")
    # In-tree clone with different content.
    _make_intree_clone(project, "solo", "new-intree")

    skill_install.migrate_project_canonical(project=project, slug="solo")

    # Dest now holds the migrated in-tree content...
    assert (dest / "MARKER.txt").read_text() == "new-intree"
    # ...and the prior dest was backed up, not destroyed.
    baks = list(project_store_root(project).glob("solo.bak-*"))
    assert len(baks) == 1
    assert (baks[0] / "OLD.txt").read_text() == "old-dest"


def test_migrate_intree_symlink_is_removed(tmp_path, isolated_library):
    """v2.9.0 monorepo layout: in-tree path is a symlink (holds no work)."""
    project = tmp_path / "proj"
    project.mkdir()
    target = tmp_path / "somewhere"
    target.mkdir()
    old = project / ".agents" / "skills" / "mono"
    old.parent.mkdir(parents=True)
    old.symlink_to(target)

    skill_install.migrate_project_canonical(project=project, slug="mono")

    # In-tree symlink removed; nothing left to mislead the installer.
    assert not old.exists() and not old.is_symlink()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli/test_relocate_project_canonical.py -k migrate -v`
Expected: FAIL — the stub returns `None` and does nothing, so every assertion about moved/backed-up/removed paths fails.

- [ ] **Step 3: Implement `migrate_project_canonical`**

In `src/agent_toolkit_cli/skill_install.py`, replace the Task 4 stub with:

```python
def migrate_project_canonical(*, project: Path, slug: str) -> None:
    """Migrate an old in-tree project canonical to the external store.

    Idempotent. Old layout put the canonical at <project>/.agents/skills/<slug>
    as a real clone (single-skill) or a symlink into the in-tree _parents/ cache
    (v2.9.0 monorepo). The new layout keeps the canonical in the external store
    (project_store_root) and leaves only a projection symlink in the tree.

    - Old is already a symlink into the store: no-op (already migrated).
    - Old is any other symlink (v2.9.0 monorepo, or stale): remove it; the
      installer recreates the new-layout symlink and re-clones the parent into
      the store's _parents/.
    - Old is a real directory (single-skill clone, possibly dirty): if the
      store dest already exists, rename it to <slug>.bak-<UTC-timestamp> first
      (never overwrite); then move the clone into the store (git history + dirty
      work travel intact); leave a symlink behind so stale references resolve.
    """
    import datetime

    from agent_toolkit_cli.skill_paths import project_store_root

    old = project / ".agents" / "skills" / slug
    if not old.is_symlink() and not old.exists():
        return  # nothing to migrate

    dest = project_store_root(project) / slug

    if old.is_symlink():
        try:
            resolved = old.resolve()
        except OSError:
            resolved = None
        if resolved is not None and resolved == dest.resolve():
            return  # already migrated → no-op
        old.unlink()  # v2.9.0 monorepo symlink / stale: holds no work
        return

    # old is a real directory: move it into the store.
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() or dest.is_symlink():
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = dest.parent / f"{slug}.bak-{ts}"
        shutil.move(str(dest), str(backup))
        click.echo(
            f"{slug}: existing store entry backed up to {backup} before migration"
        )
    shutil.move(str(old), str(dest))
    old.parent.mkdir(parents=True, exist_ok=True)
    old.symlink_to(dest)
```

Ensure `import click` and `import shutil` are present at the top of `skill_install.py` (shutil already is — it's used by `uninstall`; add `import click` if absent).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli/test_relocate_project_canonical.py -k migrate -v`
Expected: PASS (4 migrate tests).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/skill_install.py tests/test_cli/test_relocate_project_canonical.py
git commit -m "feat(skill install): migrate_project_canonical moves in-tree clone to store"
```

---

### Task 6: Non-destructive project-scope uninstall

**Files:**
- Modify: `src/agent_toolkit_cli/skill_install.py:495-516` (`uninstall`)
- Test: `tests/test_cli/test_relocate_project_canonical.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli/test_relocate_project_canonical.py`:

```python
def test_project_uninstall_preserves_external_canonical(
    tmp_path, isolated_library, monkeypatch,
):
    parent_url = _make_parent_repo(tmp_path)
    _seed_global_monorepo_entry(parent_url, "mkdocs", "mkdocs")
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.chdir(project)
    runner = CliRunner(env=scrub_git_env())
    assert runner.invoke(cli, ["skill", "install", "mkdocs",
                               "--agents", "claude-code", "-p"]).exit_code == 0

    canonical = canonical_skill_dir("mkdocs", scope="project", project=project)
    assert (canonical / "SKILL.md").exists()

    result = runner.invoke(cli, ["skill", "uninstall", "mkdocs",
                                 "--agents", "claude-code", "-p"])
    assert result.exit_code == 0, result.output

    # Projection symlinks gone; lock entry gone.
    assert not (project / ".claude" / "skills" / "mkdocs").exists()
    proj_lock = json.loads((project / "skills-lock.json").read_text())
    assert "mkdocs" not in proj_lock.get("skills", {})
    # External canonical PRESERVED (the whole point).
    assert (canonical / "SKILL.md").exists(), "external canonical must survive uninstall"
```

> Note: confirm the uninstall CLI subcommand name and flags against `commands/skill/__init__.py` (`uninstall`/`remove`/`rm`). If `--agents` is not accepted by uninstall, drop it — the test only needs the slug + `-p`. Adjust the invoke args to match the real command surface; do not change production CLI signatures to fit the test.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_relocate_project_canonical.py::test_project_uninstall_preserves_external_canonical -v`
Expected: FAIL — current `uninstall()` rmtree's the canonical, so the final assertion fails. (Also the lock-entry assertion may fail — `uninstall` does not prune the project lock today.)

- [ ] **Step 3: Make project-scope uninstall non-destructive + prune lock**

Replace the body of `uninstall` (lines 504-515) with:

```python
    p = plan(
        slug=slug, scope=scope,
        source=None, ref=None,
        target_agents=(),
        home=home, project=project,
    )
    apply(p, home=home, project=project, env=None)

    if scope == "project":
        # Non-destructive: remove only the projection symlinks (done by apply
        # above) and the project lock entry. The external canonical in the
        # per-project store is preserved so any dirty work survives; the doctor
        # orphan sweep reclaims it later if unreferenced.
        from agent_toolkit_cli.skill_lock import read_lock, remove_entry, write_lock

        lock_path = lock_file_path(scope="project", project=project)
        lock = read_lock(lock_path)
        if slug in lock.skills:
            write_lock(lock_path, remove_entry(lock, slug))
        return

    canonical = canonical_skill_dir(
        slug, scope=scope, home=home, project=project,
    )
    if canonical.exists():
        shutil.rmtree(canonical)
```

Confirm `lock_file_path` is imported at module top (it is — line 29).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_relocate_project_canonical.py::test_project_uninstall_preserves_external_canonical -v`
Expected: PASS.

- [ ] **Step 5: Run the global uninstall regression guard**

Run: `uv run pytest tests/test_cli/ -k uninstall -v`
Expected: PASS — global uninstall still rmtree's the library canonical.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/skill_install.py tests/test_cli/test_relocate_project_canonical.py
git commit -m "feat(skill install): project uninstall preserves external canonical"
```

---

### Task 7: Orphan sweep in `skill doctor -p`

**Files:**
- Modify: `src/agent_toolkit_cli/skill_doctor.py` (add `_scan_orphan_canonicals`, wire into `diagnose` at lines 78-81)
- Test: `tests/test_cli/test_relocate_project_canonical.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli/test_relocate_project_canonical.py`:

```python
from agent_toolkit_cli import skill_doctor


def test_doctor_orphan_sweep_detects_unreferenced_canonical(
    tmp_path, isolated_library,
):
    project = tmp_path / "proj"
    project.mkdir()
    # Empty project lock (no skills).
    (project / "skills-lock.json").write_text('{"version": 1, "skills": {}}')
    # An orphan canonical in the store with no lock entry.
    store = project_store_root(project)
    orphan = store / "ghost"
    orphan.mkdir(parents=True)
    (orphan / "SKILL.md").write_text("---\nname: ghost\n---\n")
    # A leftover migration backup.
    bak = store / "solo.bak-20260101T000000Z"
    bak.mkdir()

    findings = skill_doctor.diagnose(
        slugs=None, scope="project", home=None, project=project,
    )
    kinds = {(f.kind, f.slug) for f in findings}
    assert ("orphan_canonical", "ghost") in kinds
    assert any(f.kind == "orphan_canonical" and "bak-" in str(f.path) for f in findings)

    # Applying the fix removes both.
    for f in findings:
        if f.kind == "orphan_canonical":
            f.fix_action.apply()
    assert not orphan.exists()
    assert not bak.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_relocate_project_canonical.py::test_doctor_orphan_sweep_detects_unreferenced_canonical -v`
Expected: FAIL — no `orphan_canonical` findings (the sweep doesn't exist yet).

- [ ] **Step 3: Add `_scan_orphan_canonicals` and wire it in**

First, read `skill_doctor.py` lines 35-50 to confirm the `Finding` and `FixAction` dataclass field names, and the existing `_make_unlink_action` (~line referenced in `_scan_stray_symlinks`) for the action pattern. The action must expose a callable `.apply()` (the test calls `f.fix_action.apply()`); match whatever the existing `FixAction` uses (it has an `apply` method or a callable field — mirror it exactly).

Add this function (place it after `_scan_stray_symlinks`, ~line 160):

```python
def _scan_orphan_canonicals(
    *, scope: Scope, home: Path | None, project: Path | None, lock: LockFile,
) -> list[Finding]:
    """Find entries in the per-project external store with no lock entry.

    Project scope only. After a non-destructive uninstall the external canonical
    is left behind; over time the store accumulates unreferenced clones. Also
    sweeps `*.bak-*` dirs left by migration collisions. The fix removes them.
    """
    if scope != "project":
        return []
    assert project is not None
    from agent_toolkit_cli.skill_paths import project_store_root

    store = project_store_root(project)
    if not store.is_dir():
        return []
    known = set(lock.skills)
    findings: list[Finding] = []
    try:
        entries = sorted(store.iterdir())
    except OSError:
        return []
    for path in entries:
        name = path.name
        if name == "_parents":
            continue  # parent cache is managed by install, not an orphan
        is_bak = ".bak-" in name
        if name in known and not is_bak:
            continue  # referenced canonical — keep
        slug = name.split(".bak-")[0] if is_bak else name
        detail = (
            f"{path}: migration backup, safe to remove"
            if is_bak
            else f"{path}: '{name}' has no entry in the project lock "
                 f"(orphaned canonical from a prior uninstall)"
        )
        findings.append(Finding(
            kind="orphan_canonical", slug=slug, scope=scope,
            path=path, detail=detail,
            fix_action=_make_rmtree_action(path=path),
        ))
    return findings


def _make_rmtree_action(*, path: Path) -> FixAction:
    """A FixAction that removes a directory tree (or symlink) at `path`."""
    def _do() -> None:
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
    # Match the existing FixAction shape used by _make_unlink_action.
    return FixAction(description=f"remove {path}", apply=_do)
```

> The `FixAction(...)` constructor call above is a guess at the shape. Before writing, read the real `FixAction` definition (lines 35-50) and `_make_unlink_action`, then construct `_make_rmtree_action` to match exactly (same field names, same callable convention). Ensure `import shutil` is present in `skill_doctor.py`.

Wire into `diagnose` — replace lines 78-81:

```python
    if slugs is None:
        findings.extend(_scan_stray_symlinks(
            scope=scope, home=home, project=project, lock=lock,
        ))
```

with:

```python
    if slugs is None:
        findings.extend(_scan_stray_symlinks(
            scope=scope, home=home, project=project, lock=lock,
        ))
        findings.extend(_scan_orphan_canonicals(
            scope=scope, home=home, project=project, lock=lock,
        ))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_relocate_project_canonical.py::test_doctor_orphan_sweep_detects_unreferenced_canonical -v`
Expected: PASS.

- [ ] **Step 5: Run the doctor regression guard**

Run: `uv run pytest tests/test_cli/ -k doctor -v`
Expected: PASS — global doctor and stray-symlink detection unchanged.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/skill_doctor.py tests/test_cli/test_relocate_project_canonical.py
git commit -m "feat(skill doctor): orphan-canonical sweep for project store"
```

---

### Task 8: Fix `status -p` parent-clone path

**Files:**
- Modify: `src/agent_toolkit_cli/commands/skill/status_cmd.py:65-69`
- Test: `tests/test_cli/test_relocate_project_canonical.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli/test_relocate_project_canonical.py`:

```python
def test_status_p_monorepo_not_mislabeled_copy(
    tmp_path, isolated_library, monkeypatch,
):
    parent_url = _make_parent_repo(tmp_path)
    _seed_global_monorepo_entry(parent_url, "mkdocs", "mkdocs")
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.chdir(project)
    runner = CliRunner(env=scrub_git_env())
    assert runner.invoke(cli, ["skill", "install", "mkdocs",
                               "--agents", "claude-code", "-p"]).exit_code == 0

    result = runner.invoke(cli, ["skill", "status", "-p"])
    assert result.exit_code == 0, result.output
    # Must report clean/dirty (real git status of the parent clone), NOT 'copy'.
    line = next(l for l in result.output.splitlines() if l.startswith("mkdocs"))
    assert "\tcopy" not in line, f"monorepo skill mislabeled as copy: {line!r}"
    assert "\tclean" in line or "\tdirty" in line
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_relocate_project_canonical.py::test_status_p_monorepo_not_mislabeled_copy -v`
Expected: FAIL — status probes the global `_parents` path (no `root=`), finds no git repo, prints `mkdocs\tcopy`.

- [ ] **Step 3: Pass `root=` at project scope**

In `src/agent_toolkit_cli/commands/skill/status_cmd.py`, the monorepo branch calls (around line 67):

```python
            parent_dir = parent_clone_path(
                owner, repo, ref=entry.ref, env=None,
            )
```

Replace with:

```python
            parent_dir = parent_clone_path(
                owner, repo, ref=entry.ref, env=None,
                root=project_parents_root(project_root) if scope == "project" else None,
            )
```

Add `project_parents_root` to the existing `from agent_toolkit_cli.skill_paths import (...)` block at the top of the file (which already imports `parent_clone_path`). Confirm the in-scope variable holding the project path is named `project_root` (per `status_cmd.py:58`); if it's named differently in this function, use that name.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_relocate_project_canonical.py::test_status_p_monorepo_not_mislabeled_copy -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/skill/status_cmd.py tests/test_cli/test_relocate_project_canonical.py
git commit -m "fix(skill status): project monorepo probes project _parents, not global"
```

---

### Task 9: Full suite + lint, then renormalize ryanair_fares

**Files:** none (verification + manual repair re-run)

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest -q`
Expected: PASS, no regressions. If any pre-existing project-scope test asserts the OLD in-tree canonical path (`<project>/.agents/skills/<slug>` as a real dir), it now needs updating to the store path — update those assertions to use `canonical_skill_dir(scope="project", ...)` / `project_store_root(...)`. Do NOT weaken assertions; repoint them. Note in the commit which tests moved.

- [ ] **Step 2: Run the linter**

Run: `uv run ruff check src/ tests/`
Expected: clean. Fix any unused-import or import-ordering findings introduced by the edits (e.g. a now-unused `canonical_exists` local in `_current_linked_agents`).

- [ ] **Step 3: Install the fixed CLI locally**

From the worktree root:

```bash
uv tool install --reinstall --from . agent-toolkit-cli
```

- [ ] **Step 4: Renormalize ryanair_fares (auto-migration in action)**

```bash
cd /Users/ajanderson/GitHub/projects/ryanair_fares
agent-toolkit-cli skill doctor -p          # triggers auto-migration + reports orphans
agent-toolkit-cli skill install agent-browser --agents claude-code -p
agent-toolkit-cli skill install frontend-design --agents claude-code -p
```

- [ ] **Step 5: Verify ryanair_fares is fully on the new layout**

```bash
cd /Users/ajanderson/GitHub/projects/ryanair_fares
# Project tree holds ONLY symlinks, no real clones / _parents.
test ! -d .agents/skills/_parents && echo "no in-tree _parents OK"
test -L .claude/skills/agent-browser && test -f .claude/skills/agent-browser/SKILL.md && echo "agent-browser OK"
test -L .claude/skills/frontend-design && test -f .claude/skills/frontend-design/SKILL.md && echo "frontend-design OK"
# Canonical now lives in the external per-project store.
python3 -c "from agent_toolkit_cli.skill_paths import project_store_root; from pathlib import Path; print(project_store_root(Path.cwd()))"
```

Expected: no in-tree `_parents`, both SKILL.md resolve through `.claude/skills/`, canonical lives under `~/.agent-toolkit/projects/<id>/skills/`.

- [ ] **Step 6: Commit any test/lint fixes**

```bash
git add -A
git commit -m "chore: suite + lint green for relocated project canonical"
```

---

## Note on out-of-scope follow-ups

Project-scope `skill update` / `skill reset` remain global-only (they early-return with "only supported at global scope"). Enabling them against the relocated `_parents` is a separate follow-up. A dedicated `skill gc` / `skill migrate` command is deferred — auto-migration + the doctor orphan sweep cover the need.

---

## Self-Review

**Spec coverage:** §1 path model → Tasks 1+2 (`project_id`, `project_store_root`, repoint canonical/parents). §2 universal inversion → Task 3. Canonical relocation in install → Task 4. §3 migration → Task 5; uninstall semantics → Task 6; orphan sweep → Task 7; status fix → Task 8. Verification + renormalize → Task 9. All spec sections covered.

**Placeholder scan:** No TBD/TODO. Every code step shows full code. Three steps carry explicit "confirm against real code" notes (Task 3 `apply` universal-token branch, Task 6 uninstall CLI arg names, Task 7 `FixAction` shape) — these are honest verify-then-match instructions with the exact lines to read, not placeholders, because the exact `FixAction`/CLI surface wasn't fully read during planning.

**Type consistency:** `project_id(project)`, `project_store_root(project, *, env=None)`, `canonical_skill_dir(slug, scope=, project=)`, `project_parents_root(project)`, `migrate_project_canonical(*, project, slug)`, `Finding(kind=, slug=, scope=, path=, detail=, fix_action=)`, `parent_clone_path(..., root=)` — consistent across tasks. The `FixAction` constructor in Task 7 is explicitly flagged to match the real definition before use.
