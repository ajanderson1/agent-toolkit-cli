# TUI Row-Universe Union Implementation Plan (#360)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make project-installed-but-not-in-library assets visible (`unlisted` state) and actionable in the TUI, align row-inclusion semantics (union of library lock + scope lock) across the skill and agent tabs, and add a doctor `unlisted` finding with a re-add-to-library fix-action.

**Architecture:** Row builders in `agent_toolkit_tui/{skill_state,agent_state}.py` compute union(library lock, scope lock) inline (no shared helper — the lock modules differ). `skill_state` gains state `"unlisted"`; `agent_state` gains a `state` field (`installed`/`library`/`unlisted`). Exactly two Apply-path fixes make unlisted rows actionable: Task 3 (`ensure_project_canonical` early-return) and Task 4 (drop the project lock entry on full uninstall). `skill_doctor.diagnose` and agent `_diagnose` gain an `unlisted` finding whose fix-action re-materialises the library canonical and lock entry from the project entry's recorded source+ref.

**Tech Stack:** Python 3.13, Click, Textual, pytest (headless `run_test()` pilots).

**Spec:** `docs/superpowers/specs/2026-06-10-tui-row-universe-union-design.md`

**Known local-only test failure:** `tests/test_cli/test_pi_extension_inventory.py::test_empty_machine_is_empty` fails on this machine only (global pi inventory ignores `home=`; green on CI). If it is the ONLY pre-commit failure, commit with `--no-verify`.

**#362 dependency (do NOT fix here):** `agent install -p` writes no project lock entry today, so agent-tab `unlisted` rows and the agent-doctor finding cannot occur in the wild until #362 lands. Both ship now and are exercised in tests via locks written programmatically with `agent_lock.write_lock`.

---

### Task 1: `skill_state` — union universe + `unlisted` state

**Files:**
- Modify: `src/agent_toolkit_tui/skill_state.py`
- Test: `tests/test_tui/test_skill_state.py`

- [ ] **Step 1: Write the failing tests** — append to `tests/test_tui/test_skill_state.py` (reuse the existing `_add_demo_project` helper and fixture style in that file):

```python
def test_unlisted_row_after_global_remove(git_sandbox, tmp_path: Path, monkeypatch):
    """#360: project-lock-only slug renders as an `unlisted` row at project scope."""
    project = tmp_path / "proj"
    project.mkdir()
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    r = _add_demo_project(runner, git_sandbox.upstream, project, library_root)
    assert r.exit_code == 0, r.output
    # Remove from the library (destructive, global) — the project install survives.
    r = runner.invoke(main, ["skill", "remove", "demo", "--force"])
    assert r.exit_code == 0, r.output

    rows = build_skill_rows(scope="project", home=None, project=project)
    demo = [row for row in rows if row.slug == "demo"]
    assert len(demo) == 1
    assert demo[0].state == "unlisted"
    # source/ref come from the project lock entry
    assert demo[0].source  # non-empty
    # cells still probed (canonical exists at project scope)
    assert demo[0].cells

    # Global scope: slug is gone from the universe entirely.
    rows_g = build_skill_rows(scope="global", home=tmp_path, project=None)
    assert not any(row.slug == "demo" for row in rows_g)


def test_library_state_preserved_for_uninstalled(git_sandbox, tmp_path: Path, monkeypatch):
    """#360 AC5 regression: library-but-not-in-project keeps the dim `library` state."""
    project = tmp_path / "proj"
    project.mkdir()
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    r = runner.invoke(main, ["skill", "add", str(git_sandbox.upstream), "--slug", "demo"])
    assert r.exit_code == 0, r.output

    rows = build_skill_rows(scope="project", home=None, project=project)
    assert any(row.slug == "demo" and row.state == "library" for row in rows)
```

- [ ] **Step 2: Run tests to verify the new one fails**

Run: `uv run pytest tests/test_tui/test_skill_state.py -k "unlisted or preserved" -v`
Expected: `test_unlisted_row_after_global_remove` FAILS (no `demo` row at project scope — `len(demo) == 1` assertion); `test_library_state_preserved_for_uninstalled` PASSES (it pins today's behaviour).

- [ ] **Step 3: Implement the union in `build_skill_rows`**

In `src/agent_toolkit_tui/skill_state.py`:

(a) Extend the `State` literal (line 27):

```python
# "library" means the skill exists in the library but is not installed in this
# project (no project canonical at <project>/.agents/skills/<slug>/). This is
# the normal pre-install state and is rendered in dim/gray — not alarming.
# "unlisted" means the inverse: installed at project scope (project lock entry
# + working canonical) but the slug is missing from the library lock — e.g.
# after `skill remove <slug>` at global scope. Functional, rendered with a
# warning tint. See the module docstring for the row-universe contract.
State = Literal["clean", "dirty", "missing", "copy", "library", "unlisted"]
```

(b) Add `lock_file_path` to the existing `skill_paths` import block:

```python
from agent_toolkit_cli.skill_paths import (
    agent_projection_dir, canonical_skill_dir, library_lock_path,
    library_skill_path, lock_file_path, parent_clone_path,
    project_parents_root,
)
```

(c) Replace the module docstring with the canonical row-universe statement:

```python
"""Data model for the TUI's skill tab.

Reads the lock + filesystem to produce SkillRow records with per-(agent, scope)
cell state plus a working-tree state badge.

Row-universe contract (#360 — canonical statement, cross-referenced by
agent_state.py, pi_extension_state.py and instruction_state.py):
the row universe is the UNION of the library lock and the scope lock. At
global scope the two are the same file, so the union is a no-op. At project
scope: library-only slugs render as `library` (dim, available), slugs in both
locks render their installed state, and project-lock-only slugs render as
`unlisted` (warning) — installed and functional, but no longer tracked by the
library.
"""
```

(d) In `build_skill_rows` (line 148), replace the universe construction:

```python
    # Row universe = union(library lock, scope lock) — see module docstring.
    # At global scope the library lock IS the scope lock, so the union is a
    # no-op. At project scope, project-lock-only slugs are `unlisted`.
    lib_lock = read_lock(library_lock_path())
    universe = dict(lib_lock.skills)
    unlisted: set[str] = set()
    if scope == "project":
        proj_lock = read_lock(
            lock_file_path(scope="project", home=home, project=project)
        )
        for slug, proj_entry in proj_lock.skills.items():
            if slug not in universe:
                universe[slug] = proj_entry
                unlisted.add(slug)
    rows: list[SkillRow] = []
    for slug in sorted(universe):
        entry = universe[slug]
```

(e) In the state derivation immediately below, make `unlisted` the first branch (it supersedes the git badge, exactly as `library` does):

```python
        if slug in unlisted:
            # Project-lock-only: functional install, library no longer tracks
            # it. Supersedes the git working-tree badge, like `library` does.
            state: State = "unlisted"
        elif not canonical.exists():
            # Project scope: slug is in the library but not yet installed here.
            # Global scope: library entry recorded but directory was deleted.
            state = "library" if scope == "project" else "missing"
        elif entry.parent_url is not None:
```

(`elif entry.parent_url ...` is the existing monorepo branch — unchanged, only re-chained.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tui/test_skill_state.py -v`
Expected: ALL PASS (including all pre-existing tests — global scope is behaviourally unchanged).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/skill_state.py tests/test_tui/test_skill_state.py
git commit -m "feat(tui): skill row universe = union(library, project lock); unlisted state (#360)" --trailer "Device: $(hostname -s)"
```

---

### Task 2: `skill_grid` — render `unlisted` with a warning tint

**Files:**
- Modify: `src/agent_toolkit_tui/widgets/skill_grid.py:39-41` (the `_STATE_MARKUP` dict) and its `action_info` slug-column branch
- Modify: `src/agent_toolkit_tui/column_info.py` (`_state_info` legend)
- Test: `tests/test_tui/test_skill_grid_new_columns.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_tui/test_skill_grid_new_columns.py` (mirror the row-construction helper style used by `tests/test_tui/test_skill_grid_apply.py::_row`):

```python
def test_unlisted_state_markup():
    """#360: unlisted rows render with a warning (yellow) tint, distinct from dim library."""
    from agent_toolkit_tui.widgets.skill_grid import _STATE_MARKUP
    assert "unlisted" in _STATE_MARKUP
    assert "yellow" in _STATE_MARKUP["unlisted"]
    # library stays dim — the two states must be visually distinct.
    assert "dim" in _STATE_MARKUP["library"]


def test_unlisted_in_state_legend():
    """#360: the State column's `i` legend explains the unlisted badge."""
    from agent_toolkit_tui.column_info import get_column_info
    info = get_column_info("state")
    assert any("unlisted" in line for line in info.lines)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tui/test_skill_grid_new_columns.py::test_unlisted_state_markup -v`
Expected: FAIL — `KeyError`/assert: `"unlisted" in _STATE_MARKUP`.

- [ ] **Step 3: Implement**

(a) In `skill_grid.py`, extend `_STATE_MARKUP`:

```python
    # "library" = in the library, not yet installed in this project. Normal
    # pre-install state. Rendered dim so it doesn't look alarming.
    "library": "[dim]library[/]",
    # "unlisted" = installed in this project but missing from the library
    # lock (#360). Functional; warning tint so it stands out from `library`.
    "unlisted": "[yellow]unlisted[/]",
```

(b) In `src/agent_toolkit_tui/column_info.py`, add an `unlisted` bullet to `_state_info`'s `lines`, immediately after the `library` bullet:

```python
            "• unlisted — installed in this project but no longer tracked by "
            "the library lock (re-add via `skill doctor -p`)",
```

(c) In `skill_grid.py`'s `action_info` slug-column branch, give `unlisted` an explanatory display alongside the existing `library` suppression:

```python
        if row.state == "library":
            state_display = "—"
        elif row.state == "unlisted":
            state_display = "unlisted — not in library (re-add via: skill doctor -p)"
        else:
            state_display = row.state
```

(replacing the current one-liner `state_display = "—" if row.state == "library" else row.state`).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_tui/test_skill_grid_new_columns.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/widgets/skill_grid.py tests/test_tui/test_skill_grid_new_columns.py
git commit -m "feat(tui): warning-tint markup for unlisted skill rows (#360)" --trailer "Device: $(hostname -s)"
```

---

### Task 3: `ensure_project_canonical` early-return for already-installed slugs

Today `skill_install.ensure_project_canonical` reads the GLOBAL lock first and raises `InstallError(f"{slug}: not in global library")` even when the project canonical and project lock entry both exist. The TUI Apply path calls it for EVERY project-scope mutation, so any Apply touching an unlisted row fails before reaching the engine. Fix: return early when the slug is already fully installed at project scope.

**Files:**
- Modify: `src/agent_toolkit_cli/skill_install.py:351-450` (`ensure_project_canonical`)
- Test: `tests/test_cli/test_skill_install_project_canonical.py` (Create — or append to the existing test file that covers `ensure_project_canonical` if one exists; check with `grep -rln ensure_project_canonical tests/`)

- [ ] **Step 1: Write the failing test**

```python
"""#360: ensure_project_canonical must not require a library entry when the
project install is already complete (canonical + project lock entry)."""
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from agent_toolkit_cli.skill_install import ensure_project_canonical
from agent_toolkit_cli.skill_paths import library_lock_path


def test_ensure_project_canonical_unlisted_is_noop(git_sandbox, tmp_path: Path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    r = runner.invoke(main, ["skill", "add", str(git_sandbox.upstream), "--slug", "demo"])
    assert r.exit_code == 0, r.output
    (project / ".claude").mkdir(exist_ok=True)
    r = runner.invoke(main, [
        "--project", str(project),
        "skill", "install", "demo", "--scope", "project",
        "--agents", "claude-code",
    ])
    assert r.exit_code == 0, r.output
    r = runner.invoke(main, ["skill", "remove", "demo", "--force"])
    assert r.exit_code == 0, r.output

    # Must NOT raise "not in global library": install is already complete.
    p = ensure_project_canonical(
        slug="demo", project=project, global_lock_path=library_lock_path(),
    )
    assert p.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_skill_install_project_canonical.py -v`
Expected: FAIL with `InstallError: demo: not in global library`.

- [ ] **Step 3: Implement** — in `ensure_project_canonical`, move the project-side checks BEFORE the global lock read. Replace the function body's opening (currently: imports → `read_lock(global_lock_path)` → entry-None raise → `migrate_project_canonical` → compute `project_canonical`) with:

```python
    from agent_toolkit_cli.skill_lock import (
        LockEntry, add_entry, clone_url_from_entry, read_lock, write_lock,
    )
    from agent_toolkit_cli.skill_paths import (
        lock_file_path, parent_clone_path, project_parents_root,
    )
    from agent_toolkit_cli.skill_paths import canonical_skill_dir

    migrate_project_canonical(project=project, slug=slug)
    project_canonical = canonical_skill_dir(slug, scope="project", project=project)

    # Already fully installed at project scope (canonical on disk + project
    # lock entry)? Nothing to ensure — return without consulting the global
    # lock. This keeps `unlisted` installs (project entry whose slug was
    # removed from the library, #360) operable: Apply must not fail on rows
    # that need no materialisation. A broken canonical symlink fails the
    # .exists() check and falls through to the normal (fail-loud) path.
    if project_canonical.exists():
        project_lock_path = lock_file_path(scope="project", project=project)
        if slug in read_lock(project_lock_path).skills:
            return project_canonical

    global_lock = read_lock(global_lock_path)
    entry = global_lock.skills.get(slug)
    if entry is None:
        raise InstallError(f"{slug}: not in global library")
```

(The rest of the function — monorepo branch, single-repo clone, project-lock backfill — is unchanged.)

- [ ] **Step 4: Run tests to verify pass + no regression**

Run: `uv run pytest tests/test_cli/test_skill_install_project_canonical.py tests/test_cli/ -k "ensure_project or install" -v`
Expected: PASS (new test) and no regressions in install tests.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/skill_install.py tests/test_cli/test_skill_install_project_canonical.py
git commit -m "fix(install): ensure_project_canonical early-returns for complete project installs (#360)" --trailer "Device: $(hostname -s)"
```

---

### Task 4: Apply drops the project lock entry on full uninstall of an unlisted row

`TUIApp._apply_skill_pending` (`src/agent_toolkit_tui/app.py:653`) calls `engine_apply` with `source=None`, which never touches the lock. For a LISTED row that's fine (the row stays visible via the library). For an UNLISTED row, leaving the entry would strand a fully-unlinked `unlisted` row forever (the TUI has no remove verb). After a successful apply at project scope for an unlisted slug, if no projection remains, drop the project lock entry — mirroring `skill_install.uninstall`'s non-destructive posture (canonical preserved; doctor's orphan sweep reclaims it).

**Files:**
- Modify: `src/agent_toolkit_tui/app.py` (inside `_apply_skill_pending`, after the successful `engine_apply` call)
- Test: `tests/test_tui/test_skill_apply_unlisted.py` (Create)

- [ ] **Step 1: Write the failing test**

```python
"""#360 AC2: TUI Apply fully uninstalls an unlisted row — projections detached
AND project lock entry dropped (non-destructive: canonical preserved)."""
from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from agent_toolkit_cli.skill_lock import read_lock
from agent_toolkit_cli.skill_paths import canonical_skill_dir, lock_file_path
from agent_toolkit_tui.app import TUIApp


@pytest.mark.asyncio
async def test_apply_full_uninstall_unlisted_drops_project_entry(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    project = tmp_path / "proj"
    project.mkdir()
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    r = runner.invoke(main, ["skill", "add", str(git_sandbox.upstream), "--slug", "demo"])
    assert r.exit_code == 0, r.output
    (project / ".claude").mkdir(exist_ok=True)
    r = runner.invoke(main, [
        "--project", str(project),
        "skill", "install", "demo", "--scope", "project",
        "--agents", "claude-code",
    ])
    assert r.exit_code == 0, r.output
    r = runner.invoke(main, ["skill", "remove", "demo", "--force"])
    assert r.exit_code == 0, r.output

    # The TUI apply path resolves the project as Path.cwd().
    monkeypatch.chdir(project)

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        from agent_toolkit_tui.widgets.skill_grid import SkillGrid
        grid = app.query_one("#skill-grid", SkillGrid)
        # Queue an unlink for every linked, non-skipped cell of the demo row
        # at project scope (full uninstall), then apply.
        pending = {}
        for row in grid._rows:  # SkillGrid stores rows in `_rows` (skill_grid.py:110)
            if row.slug != "demo":
                continue
            for (agent, scope), cell in row.cells.items():
                if scope == "project" and cell.linked and not cell.skipped:
                    pending[(scope, agent, "demo")] = "unlink"
        assert pending, "expected at least one linked project cell to unlink"
        grid.restore_pending(pending)
        app._apply_skill_pending()
        await pilot.pause()

    proj_lock = read_lock(lock_file_path(scope="project", project=project))
    assert "demo" not in proj_lock.skills          # entry dropped
    canonical = canonical_skill_dir("demo", scope="project", project=project)
    assert canonical.exists()                      # non-destructive: canonical preserved
    # The apply genuinely detached projections (it consulted the pending ops,
    # not the library — spec D4): the claude-code projection symlink is gone.
    from agent_toolkit_cli.skill_paths import agent_projection_dir
    link = agent_projection_dir("claude-code", "demo", scope="project", home=None, project=project)
    assert not link.is_symlink()


@pytest.mark.asyncio
async def test_apply_failure_keeps_project_entry(git_sandbox, tmp_path: Path, monkeypatch):
    """#360 AC2 failure path: if the engine apply errors, the project lock
    entry is NOT dropped (the drop only follows a successful apply)."""
    project = tmp_path / "proj"
    project.mkdir()
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    r = runner.invoke(main, ["skill", "add", str(git_sandbox.upstream), "--slug", "demo"])
    assert r.exit_code == 0, r.output
    (project / ".claude").mkdir(exist_ok=True)
    r = runner.invoke(main, [
        "--project", str(project),
        "skill", "install", "demo", "--scope", "project",
        "--agents", "claude-code",
    ])
    assert r.exit_code == 0, r.output
    r = runner.invoke(main, ["skill", "remove", "demo", "--force"])
    assert r.exit_code == 0, r.output
    monkeypatch.chdir(project)

    # Patch the SOURCE module (app.py imports inside the method, so the
    # call resolves through skill_install at apply time — same monkeypatch
    # trap as #337's doctor_cmd lesson).
    import agent_toolkit_cli.skill_install as skill_install

    def _boom(*args, **kwargs):
        raise skill_install.InstallError("boom")

    monkeypatch.setattr(skill_install, "apply", _boom)

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        from agent_toolkit_tui.widgets.skill_grid import SkillGrid
        grid = app.query_one("#skill-grid", SkillGrid)
        grid.restore_pending({("project", "claude-code", "demo"): "unlink"})
        app._apply_skill_pending()
        await pilot.pause()

    proj_lock = read_lock(lock_file_path(scope="project", project=project))
    assert "demo" in proj_lock.skills  # entry survives a failed apply
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tui/test_skill_apply_unlisted.py -v`
Expected: the full-uninstall test FAILS on `assert "demo" not in proj_lock.skills` (entry survives today); the failure-path test PASSES (it pins behaviour that must not change). If the first instead fails with `InstallError: demo: not in global library`, Task 3 has not been applied — do Task 3 first.

- [ ] **Step 3: Implement** — in `app.py` `_apply_skill_pending`, inside the per-`(scope, slug)` loop, after the successful `engine_apply` call (`ok += len(result.created) + len(result.removed)`), add:

```python
                if scope == "project" and not adds:
                    self._drop_project_entry_if_unlisted_and_unlinked(
                        slug=slug, project=project,
                    )
```

and add the helper method to `TUIApp`:

```python
    def _drop_project_entry_if_unlisted_and_unlinked(
        self, *, slug: str, project: Path,
    ) -> None:
        """#360 AC2: after a remove-only apply, drop the project lock entry of
        an UNLISTED slug once no projection symlink remains. Listed slugs keep
        today's behaviour (entry stays; the row remains visible via the
        library universe). Non-destructive: the external-store canonical is
        preserved; doctor's orphan sweep reclaims it if unreferenced."""
        from agent_toolkit_cli.skill_agents import AGENTS
        from agent_toolkit_cli.skill_lock import read_lock, remove_entry, write_lock
        from agent_toolkit_cli.skill_paths import library_lock_path, lock_file_path
        from agent_toolkit_tui.skill_state import _cell_for

        if slug in read_lock(library_lock_path()).skills:
            return  # listed — out of scope for the drop rule
        # Probe the FULL agent universe, not just the rendered columns: a
        # long-tail projection installed via the CLI must block the drop,
        # otherwise the entry vanishes while a live symlink remains and
        # doctor then offers destructive cleanup of a functional install.
        # Mirrors skill_doctor._scan_stray_symlinks' universe.
        probe = ("standard", *(a for a in AGENTS if not AGENTS[a].is_standard))
        for agent in probe:
            cell = _cell_for(slug, agent, scope="project", home=None, project=project)
            if cell.skipped:
                continue  # skipped cells report linked=canonical-exists, not a symlink
            if cell.linked or cell.drift:
                return  # a projection remains — not a full uninstall
        lpath = lock_file_path(scope="project", project=project)
        lock = read_lock(lpath)
        if slug in lock.skills:
            write_lock(lpath, remove_entry(lock, slug))
```

- [ ] **Step 4: Run tests to verify pass + apply-path regressions**

Run: `uv run pytest tests/test_tui/test_skill_apply_unlisted.py tests/test_tui/test_skill_grid_apply.py -v`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/app.py tests/test_tui/test_skill_apply_unlisted.py
git commit -m "feat(tui): full uninstall of an unlisted row drops the project lock entry (#360)" --trailer "Device: $(hostname -s)"
```

---

### Task 5: `agent_state` — union universe + `state` field

**Files:**
- Modify: `src/agent_toolkit_tui/agent_state.py`
- Test: `tests/test_tui/test_agent_state.py` (Create)

- [ ] **Step 1: Write the failing tests**

```python
"""#360: agent row universe = union(library lock, scope lock).

Pre-#362 the project lock is never written by the CLI, so project-lock cases
are exercised via locks written programmatically with agent_lock.write_lock.
"""
from __future__ import annotations

from pathlib import Path

from agent_toolkit_cli.agent_lock import LockEntry, LockFile, write_lock
from agent_toolkit_cli.agent_paths import library_lock_path, lock_file_path
from agent_toolkit_tui.agent_state import build_agent_rows


def _entry(source: str) -> LockEntry:
    return LockEntry(source=source, source_type="github", ref="main")


def _write_library(slugs: dict) -> None:
    path = library_lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    write_lock(path, LockFile(version=1, skills=slugs))


def test_library_only_slug_is_dim_available_at_project(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    _write_library({"reviewer": _entry("o/reviewer")})

    rows = build_agent_rows(scope="project", home=tmp_path, project=project)
    assert [r.slug for r in rows] == ["reviewer"]
    assert rows[0].state == "library"


def test_project_only_slug_is_unlisted(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    _write_library({})
    proj_path = lock_file_path(scope="project", project=project)
    write_lock(proj_path, LockFile(version=1, skills={"reviewer": _entry("o/reviewer")}))

    rows = build_agent_rows(scope="project", home=tmp_path, project=project)
    assert [r.slug for r in rows] == ["reviewer"]
    assert rows[0].state == "unlisted"
    assert rows[0].source == "o/reviewer"


def test_both_locks_slug_is_installed(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    _write_library({"reviewer": _entry("o/reviewer")})
    proj_path = lock_file_path(scope="project", project=project)
    write_lock(proj_path, LockFile(version=1, skills={"reviewer": _entry("o/reviewer")}))

    rows = build_agent_rows(scope="project", home=tmp_path, project=project)
    assert rows[0].state == "installed"


def test_global_scope_all_installed(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _write_library({"reviewer": _entry("o/reviewer")})
    rows = build_agent_rows(scope="global", home=tmp_path, project=None)
    assert [r.slug for r in rows] == ["reviewer"]
    assert rows[0].state == "installed"


def test_no_locks_no_rows(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    rows = build_agent_rows(scope="project", home=tmp_path, project=project)
    assert rows == []
```

Implementer note: `agent_lock.__all__` re-exports `LockEntry`, `LockFile`, `read_lock`, `write_lock`, `add_entry`, `remove_entry`, and `clone_url_from_entry` (verified — it is a facade over `skill_lock`), so the imports above are correct as written. If `library_lock_path()` does not honour `HOME` via monkeypatch in-process (it resolves through `_paths_core` bindings), mirror whatever isolation `tests/test_cli/test_agent_install.py` uses (it sets `HOME`) and resolve paths AFTER the `setenv`.

- [ ] **Step 2: Run tests to verify the union cases fail**

Run: `uv run pytest tests/test_tui/test_agent_state.py -v`
Expected: `test_library_only_slug_is_dim_available_at_project` FAILS (returns [] today — scope lock missing), `test_project_only_slug_is_unlisted` FAILS (`AgentRow` has no `state`), `test_no_locks_no_rows` PASSES.

- [ ] **Step 3: Implement** — in `src/agent_toolkit_tui/agent_state.py`:

(a) Module docstring — append the cross-reference:

```
Row-universe contract: union(library lock, scope lock) — canonical statement
in skill_state.py's module docstring (#360). Rows carry a `state`:
`installed` (in the scope lock), `library` (library-only, dim available),
`unlisted` (scope-lock-only, warning). Pre-#362 the CLI never writes a
project lock, so at project scope the union degenerates to library rows.
```

(b) Add the state literal and field:

```python
State = Literal["installed", "library", "unlisted"]


@dataclass
class AgentRow:
    """One row per slug in union(library lock, scope lock)."""

    slug: str
    source: str
    ref: str
    state: State = "installed"
    # Key: (scope, harness_name) → AgentCell
    cells: dict[tuple[str, str], AgentCell] = field(default_factory=dict)
```

(c) Rewrite `build_agent_rows`:

```python
def build_agent_rows(
    *,
    scope: Scope,
    home: Path | None,
    project: Path | None,
) -> list[AgentRow]:
    """Build AgentRow list from union(library lock, scope lock) + filesystem.

    See the module docstring for the row-universe contract (#360).
    """
    from agent_toolkit_cli.agent_paths import library_lock_path

    def _read(path: Path) -> dict:
        try:
            return dict(read_lock(path).skills)
        except FileNotFoundError:
            return {}

    lib_slugs = _read(library_lock_path())
    scope_slugs = _read(lock_file_path(scope=scope, home=home, project=project))
    # At global scope library_lock_path() IS the scope lock — same file.
    universe = {**lib_slugs, **scope_slugs}

    rows: list[AgentRow] = []
    for slug in sorted(universe):
        entry = universe[slug]
        if slug in scope_slugs:
            # At global scope the scope lock IS the library lock (same file),
            # so this branch covers every slug and yields "installed".
            state: State = "installed" if slug in lib_slugs else "unlisted"
        else:
            state = "library"
        cells: dict[tuple[str, str], AgentCell] = {}
        for harness in INTERACTIVE_HARNESSES:
            cell = _cell_for(slug, harness, scope=scope, home=home, project=project)
            if cell is not None:
                cells[(harness, scope)] = cell
        rows.append(AgentRow(
            slug=slug,
            source=entry.source,
            ref=entry.ref or "(default)",
            state=state,
            cells=cells,
        ))
    return rows
```

(Drop the old top-level `try/except FileNotFoundError: return []` — `_read` subsumes it. Remove the now-unused `lock_path` local if any.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tui/test_agent_state.py tests/test_tui/test_agent_grid.py -v`
Expected: new file ALL PASS; `test_agent_grid.py` ALL PASS (rows there are constructed directly; `state` has a default so existing constructors stay valid).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/agent_state.py tests/test_tui/test_agent_state.py
git commit -m "feat(tui): agent row universe = union(library, scope lock) with state field (#360)" --trailer "Device: $(hostname -s)"
```

---

### Task 6: `agent_grid` — State column

**Files:**
- Modify: `src/agent_toolkit_tui/widgets/agent_grid.py` (column layout: `[0]=slug, [1..N]=harnesses, [N+1]=state, [N+2]=source`)
- Test: `tests/test_tui/test_agent_grid.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_tui/test_agent_grid.py` (reuse its `_linked_row` helper):

```python
@pytest.mark.asyncio
async def test_state_column_rendered():
    """#360: agent grid renders a State column between harnesses and Source."""
    from textual.widgets import DataTable

    row = _linked_row("reviewer")
    row.state = "unlisted"
    app = _grid_app([row])  # reuse this file's existing app-harness helper
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one(DataTable)
        labels = [str(c.label) for c in table.columns.values()]
        assert any("State" in l for l in labels)
        # State column sits immediately before Source.
        state_i = next(i for i, l in enumerate(labels) if "State" in l)
        source_i = next(i for i, l in enumerate(labels) if "Source" in l)
        assert source_i == state_i + 1
```

(Adapt the app-construction line to this test file's existing pattern for mounting an `AgentGrid` — the file has several such tests; copy the harness of `columns renders correctly` test #1.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tui/test_agent_grid.py::test_state_column_rendered -v`
Expected: FAIL — no "State" column.

- [ ] **Step 3: Implement** — in `agent_grid.py`:

(a) Add the markup map near the top (mirror skill_grid's `_STATE_MARKUP`):

```python
# Row-state badges (#360). `installed` renders as an em-dash to keep the
# common case quiet; `library` mirrors skill_grid's dim available state;
# `unlisted` gets a warning tint.
_STATE_MARKUP = {
    "installed": "[dim]—[/]",
    "library": "[dim]library[/]",
    "unlisted": "[yellow]unlisted[/]",
}
```

(b) In the column-construction block (`agent_grid.py:284-291`), insert before the Source column:

```python
        table.add_column("State", width=10)
        table.add_column("Source", width=30)
```

(c) In the row-cell construction (`agent_grid.py:~297`), insert before `cells.append(row.source)`:

```python
            cells.append(_STATE_MARKUP.get(row.state, row.state))
```

(d) Update the two layout-comment/index helpers (`agent_grid.py:258` `_col_for_harness`-style and `:265` `_harness_for_col`-style): the harness range is unchanged (`[1..N]`), but any logic that treats "last column" or `N+1` as Source must now treat `N+1` as State and `N+2` as Source. Update the docstrings to `Layout: [0]=slug, [1..N]=harnesses, [N+1]=state, [N+2]=source.` There are THREE index sites, not two — the cursor clamp in `_rebuild` (`agent_grid.py:~303`) must change from `max_col = 1 + len(INTERACTIVE_HARNESSES)` to `max_col = 2 + len(INTERACTIVE_HARNESSES)` (and its layout comment updated), or the saved cursor can never reach the Source column after a rebuild.

(e) In `action_info`'s slug-column branch (`agent_grid.py:~153-158`), append a State line to the body, mirroring the skill grid's panel:

```python
        body = (
            f"Agent [b]{row.slug}[/]\n"
            f"Source: {row.source}\n"
            f"Ref:    {row.ref}\n"
            f"State:  {'—' if row.state == 'installed' else row.state}"
        )
```

- [ ] **Step 4: Run the full agent-grid suite**

Run: `uv run pytest tests/test_tui/test_agent_grid.py -v`
Expected: ALL PASS — if a pre-existing columns test pins the exact column list, update it to include State (that is an intended behaviour change, not a regression).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/widgets/agent_grid.py tests/test_tui/test_agent_grid.py
git commit -m "feat(tui): agent grid State column (installed/library/unlisted) (#360)" --trailer "Device: $(hostname -s)"
```

---

### Task 7: `skill doctor -p` — `unlisted` finding + re-add-to-library fix-action

**Files:**
- Modify: `src/agent_toolkit_cli/skill_doctor.py`
- Test: `tests/test_cli/test_skill_doctor.py`

- [ ] **Step 1: Write the failing tests** — append to `tests/test_cli/test_skill_doctor.py` (reuse that file's existing sandbox/fixture style for add+install+remove; the setup below mirrors Task 1's):

```python
def test_unlisted_finding_fires_at_project_scope(git_sandbox, tmp_path, monkeypatch):
    """#360 AC4: project lock entry whose slug is missing from the library lock."""
    project = tmp_path / "proj"
    project.mkdir()
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    r = runner.invoke(main, ["skill", "add", str(git_sandbox.upstream), "--slug", "demo"])
    assert r.exit_code == 0, r.output
    (project / ".claude").mkdir(exist_ok=True)
    r = runner.invoke(main, [
        "--project", str(project),
        "skill", "install", "demo", "--scope", "project",
        "--agents", "claude-code",
    ])
    assert r.exit_code == 0, r.output
    r = runner.invoke(main, ["skill", "remove", "demo", "--force"])
    assert r.exit_code == 0, r.output

    from agent_toolkit_cli.skill_doctor import diagnose
    findings = diagnose(slugs=None, scope="project", home=None, project=project)
    unlisted = [f for f in findings if f.kind == "unlisted"]
    assert len(unlisted) == 1
    assert unlisted[0].slug == "demo"
    assert unlisted[0].fix_action is not None


def test_unlisted_fix_action_readds_to_library(git_sandbox, tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    runner = CliRunner()
    r = runner.invoke(main, ["skill", "add", str(git_sandbox.upstream), "--slug", "demo"])
    assert r.exit_code == 0, r.output
    (project / ".claude").mkdir(exist_ok=True)
    r = runner.invoke(main, [
        "--project", str(project),
        "skill", "install", "demo", "--scope", "project",
        "--agents", "claude-code",
    ])
    assert r.exit_code == 0, r.output
    r = runner.invoke(main, ["skill", "remove", "demo", "--force"])
    assert r.exit_code == 0, r.output

    from agent_toolkit_cli.skill_doctor import diagnose
    from agent_toolkit_cli.skill_lock import read_lock
    from agent_toolkit_cli.skill_paths import library_lock_path, library_skill_path

    findings = diagnose(slugs=None, scope="project", home=None, project=project)
    fix = next(f for f in findings if f.kind == "unlisted").fix_action
    fix.apply()
    fix.apply()  # idempotent: second apply is a no-op, not an error

    assert "demo" in read_lock(library_lock_path()).skills   # lock entry restored
    assert library_skill_path("demo").exists()               # canonical re-materialised
    # Finding clears on the next run.
    findings2 = diagnose(slugs=None, scope="project", home=None, project=project)
    assert not [f for f in findings2 if f.kind == "unlisted"]


def test_unlisted_not_checked_at_global_scope(tmp_path, monkeypatch):
    library_root = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    from agent_toolkit_cli.skill_doctor import diagnose
    findings = diagnose(slugs=None, scope="global", home=tmp_path, project=None)
    assert not [f for f in findings if f.kind == "unlisted"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli/test_skill_doctor.py -k unlisted -v`
Expected: first two FAIL (no `unlisted` kind emitted); the global-scope test PASSES trivially.

- [ ] **Step 3: Implement** — in `src/agent_toolkit_cli/skill_doctor.py`:

(a) Add `"unlisted"` to the `FindingKind` literal list (line ~30). The Literal update must land in the same commit as the scan code and tests — `Finding` is a frozen dataclass typed `kind: FindingKind`, so `mypy --strict` rejects `kind="unlisted"` until the Literal carries it.

(b) Ensure `library_lock_path` and `library_skill_path` are imported from `skill_paths`, and `add_entry`/`write_lock` from `skill_lock` (extend existing import blocks; `dataclasses` may need importing).

(c) Add the scan + fix-action builder:

```python
def _scan_unlisted_entries(
    *, scope: Scope, home: Path | None, project: Path | None, lock,
) -> list[Finding]:
    """#360: project lock entries whose slug is missing from the library lock.

    The install is functional (project canonicals are independent of the
    library); the finding flags that the library no longer tracks the slug
    and offers to re-add it from the entry's recorded source+ref."""
    if scope != "project":
        return []
    lib_lock = read_lock(library_lock_path())
    findings: list[Finding] = []
    for slug, entry in sorted(lock.skills.items()):
        if slug in lib_lock.skills:
            continue
        findings.append(Finding(
            kind="unlisted", slug=slug, scope=scope,
            path=lock_file_path(scope=scope, home=home, project=project),
            detail=(
                "project lock entry's slug is missing from the library lock "
                "(install is functional; the library no longer tracks it)"
            ),
            fix_action=_make_readd_library_action(slug=slug, entry=entry),
        ))
    return findings


def _make_readd_library_action(*, slug: str, entry: LockEntry) -> FixAction:
    """Re-add an unlisted slug to the library from its recorded source+ref:
    materialise the library canonical (reusing the reclone machinery at
    global scope — monorepo entries take the parent-clone branch) and write
    the library lock entry. SHAs are reset to None; `skill update` re-resolves
    them."""
    reclone = _make_reclone_action(
        slug=slug, scope="global", home=None, project=None, entry=entry,
    )

    def _apply() -> None:
        reclone.apply()
        lib_path = library_lock_path()
        lib_lock = read_lock(lib_path)
        if slug not in lib_lock.skills:
            write_lock(lib_path, add_entry(
                lib_lock, slug,
                dataclasses.replace(entry, upstream_sha=None, local_sha=None),
            ))

    ref_arg = f" --ref {entry.ref}" if entry.ref else ""
    return FixAction(
        description=f"Re-add {slug} to the library from {entry.source}",
        shell_preview=f"agent-toolkit-cli skill add {entry.source}{ref_arg} --slug {slug}",
        apply=_apply,
    )
```

(d) Wire into `diagnose` — in the `if slugs is None:` block, after `_scan_stray_bundle_dirs`:

```python
        findings.extend(_scan_unlisted_entries(
            scope=scope, home=home, project=project, lock=lock,
        ))
```

- [ ] **Step 4: Run the doctor suites**

Run: `uv run pytest tests/test_cli/test_skill_doctor.py tests/test_cli/test_cli_skill_doctor.py -v`
Expected: ALL PASS (the CLI-level doctor loop needs no change — it already prints any Finding with a y/N/q prompt).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/skill_doctor.py tests/test_cli/test_skill_doctor.py
git commit -m "feat(doctor): unlisted finding for project entries missing from the library (#360)" --trailer "Device: $(hostname -s)"
```

---

### Task 8: `agent doctor -p` — same finding shape (inert until #362)

**Files:**
- Modify: `src/agent_toolkit_cli/commands/agent/doctor_cmd.py`
- Test: `tests/test_cli/test_agent_doctor_unlisted.py` (Create)

- [ ] **Step 1: Write the failing tests** (project lock written programmatically — the CLI cannot produce one until #362):

```python
"""#360: agent doctor `unlisted` finding — project lock entry missing from the
library lock. Inert in the wild until #362 (CLI writes no project lock);
exercised here via programmatically-written locks."""
from __future__ import annotations

from pathlib import Path

from agent_toolkit_cli.agent_lock import LockEntry, LockFile, read_lock, write_lock
from agent_toolkit_cli.agent_paths import library_lock_path, lock_file_path
from agent_toolkit_cli.commands.agent.doctor_cmd import _diagnose


def _entry(source: str) -> LockEntry:
    return LockEntry(source=source, source_type="github", ref="main")


def test_unlisted_finding_fires(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    proj_lock = lock_file_path(scope="project", project=project)
    write_lock(proj_lock, LockFile(version=1, skills={"reviewer": _entry("o/reviewer")}))

    findings = _diagnose(slugs=None, scope="project", home=tmp_path, project=project)
    unlisted = [f for f in findings if f.kind == "unlisted"]
    assert len(unlisted) == 1
    assert unlisted[0].slug == "reviewer"
    assert unlisted[0].fix_action is not None


def test_unlisted_fix_action_writes_library_entry(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    proj_lock = lock_file_path(scope="project", project=project)
    write_lock(proj_lock, LockFile(version=1, skills={"reviewer": _entry("o/reviewer")}))

    findings = _diagnose(slugs=None, scope="project", home=tmp_path, project=project)
    fix = next(f for f in findings if f.kind == "unlisted").fix_action
    # The clone leg may fail for a fake source; the lock leg is the contract
    # under test — monkeypatch the clone to a no-op that creates the dir.
    import agent_toolkit_cli.commands.agent.doctor_cmd as dc

    def _fake_clone(url, dest, *, ref=None, env=None):
        Path(dest).mkdir(parents=True, exist_ok=True)
        (Path(dest) / "reviewer.md").write_text("stub\n")

    monkeypatch.setattr(dc.skill_git, "clone", _fake_clone)
    fix.apply()
    fix.apply()  # idempotent: second apply is a no-op, not an error
    assert "reviewer" in read_lock(library_lock_path()).skills


def test_no_finding_when_library_tracks_slug(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    lib = library_lock_path()
    lib.parent.mkdir(parents=True, exist_ok=True)
    write_lock(lib, LockFile(version=1, skills={"reviewer": _entry("o/reviewer")}))
    proj_lock = lock_file_path(scope="project", project=project)
    write_lock(proj_lock, LockFile(version=1, skills={"reviewer": _entry("o/reviewer")}))

    findings = _diagnose(slugs=None, scope="project", home=tmp_path, project=project)
    assert not [f for f in findings if f.kind == "unlisted"]
```

(Implementer note: `agent_lock` re-exports all the lock primitives the tests import — verified against its `__all__`. `_diagnose` may return findings for missing canonicals for these stub entries — filter by `kind == "unlisted"` as the tests do.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli/test_agent_doctor_unlisted.py -v`
Expected: first two FAIL (no `unlisted` kind), third PASSES trivially.

- [ ] **Step 3: Implement** — in `commands/agent/doctor_cmd.py`:

(a) Extend imports:

```python
from agent_toolkit_cli.agent_lock import read_lock
from agent_toolkit_cli.agent_paths import (
    Scope, library_agent_path, library_lock_path, lock_file_path,
)
```

plus `import dataclasses` and `from agent_toolkit_cli.agent_lock import LockFile, add_entry, clone_url_from_entry, write_lock` — all four are confirmed in `agent_lock.__all__` (it is a facade re-exporting `skill_lock`'s primitives).

(b) Add the fix-action builder above `_diagnose`:

```python
def _make_readd_library_action(slug: str, entry) -> FixAction:
    """#360: re-add an unlisted agent to the library from its recorded
    source+ref — clone the canonical if missing, then write the library lock
    entry (SHAs reset; `agent update` re-resolves)."""
    canonical = library_agent_path(slug)
    url = clone_url_from_entry(entry)

    def _apply() -> None:
        if not canonical.exists():
            canonical.parent.mkdir(parents=True, exist_ok=True)
            skill_git.clone(url, canonical, ref=entry.ref, env=None)
        lib_path = library_lock_path()
        try:
            lib = read_lock(lib_path)
        except FileNotFoundError:
            lib = LockFile(version=1, skills={})
        if slug not in lib.skills:
            write_lock(lib_path, add_entry(
                lib, slug,
                dataclasses.replace(entry, upstream_sha=None, local_sha=None),
            ))

    ref_arg = f" --ref {entry.ref}" if entry.ref else ""
    return FixAction(
        shell_preview=f"agent-toolkit-cli agent add {entry.source}{ref_arg} --slug {slug}",
        apply=_apply,
    )
```

(c) In `_diagnose`, after the per-slug loop and before the orphan-canonical scan, add:

```python
    # 3.5: unlisted — project lock entry whose slug is missing from the
    # library lock (#360). Inert until #362 lands (the CLI writes no project
    # lock today); ships now for forward-compatibility.
    if scope == "project":
        try:
            lib_slugs = set(read_lock(library_lock_path()).skills)
        except FileNotFoundError:
            lib_slugs = set()
        for slug, entry in sorted(targets.items()):
            if slug in lib_slugs:
                continue
            findings.append(Finding(
                slug=slug, kind="unlisted", scope=scope, path=lock_path,
                detail=(
                    "project lock entry's slug is missing from the library "
                    "lock (install is functional; the library no longer "
                    "tracks it)"
                ),
                fix_action=_make_readd_library_action(slug, entry),
            ))
```

Caution: the existing per-slug loop checks `library_agent_path(slug)` for a missing canonical — for project-lock entries that check fires `missing-canonical` findings too. That is pre-existing behaviour of `_diagnose` for any project entry and is NOT in scope to change; the new tests filter by kind.

- [ ] **Step 4: Run the agent doctor suites**

Run: `uv run pytest tests/test_cli/test_agent_doctor_unlisted.py tests/test_cli/ -k "agent_doctor or agent and doctor" -v`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/agent/doctor_cmd.py tests/test_cli/test_agent_doctor_unlisted.py
git commit -m "feat(doctor): agent unlisted finding (inert until #362) (#360)" --trailer "Device: $(hostname -s)"
```

---

### Task 9: Documented exceptions + full-suite verification

**Files:**
- Modify: `src/agent_toolkit_tui/pi_extension_state.py:1-5` (module docstring)
- Modify: `src/agent_toolkit_tui/instruction_state.py:1-14` (module docstring)

- [ ] **Step 1: Add the cross-references**

`pi_extension_state.py` docstring — append (the union claim was verified against `pi_extension_inventory.build_inventory` in the 2026-06-10 audit: pass 1 reads both scope locks, pass 2 discovers loose extension dirs, pass 3 reads settings.json packages):

```
Row-universe contract (#360): this tab already implements the union semantic
— build_inventory merges both scope locks, loose extension dirs, and
settings.json packages. Canonical statement: skill_state.py docstring.
```

`instruction_state.py` docstring — append:

```
Row-universe contract (#360): instructions are the documented by-design
EXCEPTION to the union semantic (canonical statement: skill_state.py
docstring) — there is no library lock for this kind; the universe is the
scope lock plus the fresh-user canonical fallback below.
```

- [ ] **Step 2: Run the full suite**

Run: `uv run pytest`
Expected: everything green EXCEPT (possibly) the known local-only `test_empty_machine_is_empty` failure documented in the header. Any other failure is a regression — fix before proceeding.

- [ ] **Step 3: Commit**

```bash
git add src/agent_toolkit_tui/pi_extension_state.py src/agent_toolkit_tui/instruction_state.py
git commit -m "docs(tui): cross-reference the row-universe contract from pi/instruction state (#360)" --trailer "Device: $(hostname -s)"
```

---

## Verification checklist (maps to issue ACs)

- AC1 (unlisted rows render): Task 1 (skill), Task 5 (agent), Task 2/6 (distinct warning rendering).
- AC2 (actionable uninstall): Task 3 (Apply no longer hard-fails), Task 4 (full uninstall drops the project entry, canonical preserved, #319 rollback posture unchanged — Apply still surfaces errors and restores pending on failure).
- AC3 (documented identical semantics): Task 1c (canonical statement), Task 5a, Task 9 (pi precedent + instruction exception).
- AC4 (doctor finding + fix-action): Task 7 (live), Task 8 (inert until #362).
- AC5 (library state preserved): Task 1's regression test; agent tab gains it (Task 5).
