# `skill doctor` + TUI cell-info modal — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** `docs/superpowers/specs/2026-05-22-skill-doctor-design.md`

**Goal:** Add a `skill doctor` CLI command that diagnoses seven kinds of skill-installation drift and offers per-issue confirmation to repair, plus a TUI `i` keybinding that opens a state-aware info modal — on drifted cells the modal shows the exact `skill doctor` command to run.

**Architecture:** New pure module `skill_doctor.py` computes `Finding` objects (each carrying an idempotent `fix_action.apply` closure) by reading lock + filesystem; a thin Click command in `commands/skill/doctor_cmd.py` formats findings and drives a per-issue y/N/q prompt loop; a new `CellInfoScreen` modal + `i` binding on `SkillGrid` surfaces the doctor command (and other state-specific context) from the TUI.

**Tech Stack:** Python 3.12, Click 8 (CLI), Textual (TUI), pytest + Click `CliRunner` + Textual `App.run_test()` (tests). Existing helpers: `skill_lock`, `skill_git`, `skill_paths`, `skill_agents`, `skill_install`.

---

## File Structure

**New files**

- `src/agent_toolkit_cli/skill_doctor.py` — Pure-ish engine: `Finding`, `FixAction`, `diagnose()`. Reads filesystem + lock; emits findings; each finding's `apply` closure mutates the filesystem to repair.
- `src/agent_toolkit_cli/commands/skill/doctor_cmd.py` — Click command. Formats findings; runs the y/N/q prompt loop; computes exit code.
- `src/agent_toolkit_tui/screens/__init__.py` — empty package marker.
- `src/agent_toolkit_tui/screens/cell_info.py` — `CellInfoScreen(ModalScreen)`. State-aware body text computed by the caller; modal just renders + dismisses.
- `tests/test_cli/test_skill_doctor.py` — unit tests for `diagnose()` + fix closures.
- `tests/test_cli/test_cli_skill_doctor.py` — integration tests via `CliRunner`.
- `tests/test_tui/test_cell_info.py` — pilot tests for the `i` modal.

**Modified files**

- `src/agent_toolkit_cli/commands/skill/__init__.py` — wire `doctor_cmd` via `skill.add_command(doctor_cmd)`.
- `src/agent_toolkit_cli/cli.py` — update root help string (removes "doctor" from the list of removed pre-v2 commands).
- `src/agent_toolkit_tui/widgets/skill_grid.py` — add `i` binding and `action_info()` that pushes `CellInfoScreen` with state-derived body markup.
- `src/agent_toolkit_tui/app.py` — register the `i Info` keybinding in the app's `BINDINGS` so the Footer hints at it.

---

## Task 1: Scaffold `skill_doctor` module with `FixAction` and `Finding` dataclasses

Both downstream tasks (CLI + diagnose checks) depend on these dataclasses existing. Start with frames + a smoke test that imports them.

**Files:**
- Create: `src/agent_toolkit_cli/skill_doctor.py`
- Create: `tests/test_cli/test_skill_doctor.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli/test_skill_doctor.py
"""Tests for skill_doctor diagnose + fix engine."""
from __future__ import annotations

from pathlib import Path

from agent_toolkit_cli.skill_doctor import FixAction, Finding


def test_finding_has_expected_fields():
    fa = FixAction(
        description="noop", shell_preview="true", apply=lambda: None,
    )
    f = Finding(
        kind="drifted_symlink", slug="demo", scope="global",
        path=Path("/tmp/x"), detail="example", fix_action=fa,
    )
    assert f.kind == "drifted_symlink"
    assert f.slug == "demo"
    assert f.scope == "global"
    assert f.path == Path("/tmp/x")
    assert f.detail == "example"
    assert f.fix_action is fa


def test_fix_action_apply_is_callable():
    calls: list[int] = []
    fa = FixAction(
        description="touch", shell_preview="touch x",
        apply=lambda: calls.append(1),
    )
    fa.apply()
    fa.apply()
    assert calls == [1, 1]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_cli/test_skill_doctor.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'agent_toolkit_cli.skill_doctor'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/agent_toolkit_cli/skill_doctor.py
"""Diagnose + repair skill-installation drift.

Pure-ish engine: diagnose() reads lock + filesystem and returns Findings.
Each Finding carries an idempotent fix_action.apply() closure that the
CLI calls after the user confirms. No mutation happens here; that's the
caller's responsibility (via fix_action.apply).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

from agent_toolkit_cli.skill_paths import Scope

FindingKind = Literal[
    "missing_canonical", "drifted_symlink",
    "wrong_type_bundle", "orphan_symlink", "foreign_symlink",
    "dirty_tree", "lock_source_mismatch",
]


@dataclass(frozen=True)
class FixAction:
    description: str
    shell_preview: str
    apply: Callable[[], None]


@dataclass(frozen=True)
class Finding:
    kind: FindingKind
    slug: str
    scope: Scope
    path: Path
    detail: str
    fix_action: FixAction | None
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_cli/test_skill_doctor.py -v
```

Expected: PASS — both tests green.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/skill_doctor.py tests/test_cli/test_skill_doctor.py
git commit -m "feat(doctor): scaffold Finding + FixAction dataclasses"
```

---

## Task 2: Implement `diagnose()` shell — empty findings on clean tree

Add the `diagnose()` entry point. Just the signature + a return of `[]` for an empty lock. Subsequent tasks fill in each detector.

**Files:**
- Modify: `src/agent_toolkit_cli/skill_doctor.py`
- Modify: `tests/test_cli/test_skill_doctor.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli/test_skill_doctor.py`:

```python
def test_diagnose_empty_lock_returns_no_findings(tmp_path: Path, monkeypatch):
    library_root = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    from agent_toolkit_cli.skill_doctor import diagnose
    findings = diagnose(
        slugs=None, scope="global",
        home=tmp_path / "home", project=None,
    )
    assert findings == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_cli/test_skill_doctor.py::test_diagnose_empty_lock_returns_no_findings -v
```

Expected: FAIL — `ImportError: cannot import name 'diagnose'`.

- [ ] **Step 3: Write minimal implementation**

Append to `src/agent_toolkit_cli/skill_doctor.py`:

```python
from agent_toolkit_cli.skill_lock import read_lock
from agent_toolkit_cli.skill_paths import (
    library_lock_path, lock_file_path,
)


def diagnose(
    *,
    slugs: tuple[str, ...] | None,
    scope: Scope,
    home: Path | None,
    project: Path | None,
    repair_foreign: bool = False,
) -> list[Finding]:
    """Return all findings for the requested scope.

    slugs=None scans every slug in the lock. Otherwise scans only those slugs.
    """
    lock = read_lock(lock_file_path(scope=scope, home=home, project=project))
    targets = (
        tuple(sorted(lock.skills))
        if slugs is None
        else tuple(s for s in slugs if s in lock.skills)
    )
    findings: list[Finding] = []
    for slug in targets:
        findings.extend(_check_slug(
            slug=slug, scope=scope, home=home, project=project,
            entry=lock.skills[slug], lock=lock,
            repair_foreign=repair_foreign,
        ))
    return findings


def _check_slug(
    *, slug: str, scope: Scope, home: Path | None, project: Path | None,
    entry, lock, repair_foreign: bool,
) -> list[Finding]:
    return []
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_cli/test_skill_doctor.py -v
```

Expected: PASS — all three tests green.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/skill_doctor.py tests/test_cli/test_skill_doctor.py
git commit -m "feat(doctor): add diagnose() entry point (empty findings stub)"
```

---

## Task 3: Detect `missing_canonical` + fix (re-clone OR remove lock entry)

A `missing_canonical` is emitted when the lock has a slug but the canonical directory is absent. The fix offers two paths via the CLI prompt loop (re-clone, then remove-entry); in the engine we emit **two `FixAction` candidates on one Finding** — represented by the CLI sequentially trying re-clone then remove if the re-clone is refused. To keep the engine API tight, the Finding's `fix_action` re-clones; a sibling helper `make_remove_entry_action(slug, scope, home, project)` lets the CLI offer the secondary "just remove the lock entry" fix when the user declines re-clone.

**Files:**
- Modify: `src/agent_toolkit_cli/skill_doctor.py`
- Modify: `tests/test_cli/test_skill_doctor.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli/test_skill_doctor.py`:

```python
import shutil
from click.testing import CliRunner
from agent_toolkit_cli.cli import main


def _seed_library(runner, upstream_path) -> None:
    """Add 'demo' to the global library lock."""
    r = runner.invoke(main, ["skill", "add", str(upstream_path), "--slug", "demo"])
    assert r.exit_code == 0, r.output


def test_diagnose_missing_canonical(git_sandbox, tmp_path: Path, monkeypatch):
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))

    runner = CliRunner()
    _seed_library(runner, git_sandbox.upstream)

    # Delete the library canonical behind the lock's back.
    shutil.rmtree(library_root / "demo")

    from agent_toolkit_cli.skill_doctor import diagnose
    findings = diagnose(
        slugs=None, scope="global", home=fake_home, project=None,
    )
    kinds = [f.kind for f in findings]
    assert "missing_canonical" in kinds


def test_missing_canonical_fix_reclones(git_sandbox, tmp_path: Path, monkeypatch):
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))

    runner = CliRunner()
    _seed_library(runner, git_sandbox.upstream)
    shutil.rmtree(library_root / "demo")

    from agent_toolkit_cli.skill_doctor import diagnose
    findings = diagnose(
        slugs=None, scope="global", home=fake_home, project=None,
    )
    f = next(f for f in findings if f.kind == "missing_canonical")
    assert f.fix_action is not None
    f.fix_action.apply()
    assert (library_root / "demo" / "SKILL.md").exists()
    # Idempotent: second apply is a no-op.
    f.fix_action.apply()
    assert (library_root / "demo" / "SKILL.md").exists()


def test_make_remove_entry_action_drops_lock_row(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))

    runner = CliRunner()
    _seed_library(runner, git_sandbox.upstream)

    from agent_toolkit_cli.skill_doctor import make_remove_entry_action
    from agent_toolkit_cli.skill_lock import read_lock
    from agent_toolkit_cli.skill_paths import library_lock_path

    action = make_remove_entry_action(
        slug="demo", scope="global", home=fake_home, project=None,
    )
    action.apply()

    lock = read_lock(library_lock_path())
    assert "demo" not in lock.skills
    # Idempotent.
    action.apply()
    lock = read_lock(library_lock_path())
    assert "demo" not in lock.skills
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_cli/test_skill_doctor.py -v
```

Expected: FAIL — `ImportError: cannot import name 'make_remove_entry_action'`, plus the diagnose test asserts `missing_canonical` in an empty list.

- [ ] **Step 3: Write minimal implementation**

Append to `src/agent_toolkit_cli/skill_doctor.py`:

```python
from agent_toolkit_cli import skill_git
from agent_toolkit_cli.skill_lock import (
    LockEntry, clone_url_from_entry, remove_entry, write_lock,
)
from agent_toolkit_cli.skill_paths import canonical_skill_dir


def _make_reclone_action(
    *, slug: str, scope: Scope, home: Path | None, project: Path | None,
    entry: LockEntry,
) -> FixAction:
    canonical = canonical_skill_dir(slug, scope=scope, home=home, project=project)
    url = clone_url_from_entry(entry)
    ref = entry.ref or "main"

    def _apply() -> None:
        if canonical.exists():
            return  # idempotent
        canonical.parent.mkdir(parents=True, exist_ok=True)
        skill_git.clone(url, canonical, ref=entry.ref, env=None)

    return FixAction(
        description=f"Re-clone {slug} from {url}",
        shell_preview=f"git clone --branch {ref} {url} {canonical}",
        apply=_apply,
    )


def make_remove_entry_action(
    *, slug: str, scope: Scope, home: Path | None, project: Path | None,
) -> FixAction:
    """Return a FixAction that drops `slug` from the lock for the given scope.

    Idempotent: removing a missing entry is a no-op.
    """
    lock_path = lock_file_path(scope=scope, home=home, project=project)

    def _apply() -> None:
        lock = read_lock(lock_path)
        if slug not in lock.skills:
            return  # idempotent
        write_lock(lock_path, remove_entry(lock, slug))

    return FixAction(
        description=f"Remove {slug} from lock at {lock_path}",
        shell_preview=(
            f"# Edit {lock_path} and delete the \"{slug}\" entry under \"skills\""
        ),
        apply=_apply,
    )
```

Replace the `_check_slug` stub with a real body that includes the `missing_canonical` check:

```python
def _check_slug(
    *, slug: str, scope: Scope, home: Path | None, project: Path | None,
    entry: LockEntry, lock, repair_foreign: bool,
) -> list[Finding]:
    findings: list[Finding] = []
    canonical = canonical_skill_dir(slug, scope=scope, home=home, project=project)
    if not canonical.exists():
        findings.append(Finding(
            kind="missing_canonical", slug=slug, scope=scope,
            path=canonical,
            detail=(
                f"lock has {slug} but canonical directory is gone. "
                f"Source: {entry.source}"
            ),
            fix_action=_make_reclone_action(
                slug=slug, scope=scope, home=home, project=project, entry=entry,
            ),
        ))
        return findings  # other checks all assume canonical exists
    return findings
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_cli/test_skill_doctor.py -v
```

Expected: PASS — all six tests green (3 new + 3 from earlier tasks).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/skill_doctor.py tests/test_cli/test_skill_doctor.py
git commit -m "feat(doctor): detect missing canonical; offer re-clone or remove-entry"
```

---

## Task 4: Detect `drifted_symlink` + fix (unlink + relink)

The main case that motivated this work. Walks every interactive agent's projection path at the requested scope; emits a `drifted_symlink` when the link exists but doesn't resolve to the canonical. The fix is unlink + symlink_to(canonical).

**Files:**
- Modify: `src/agent_toolkit_cli/skill_doctor.py`
- Modify: `tests/test_cli/test_skill_doctor.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli/test_skill_doctor.py`:

```python
def test_diagnose_drifted_symlink_global(git_sandbox, tmp_path: Path, monkeypatch):
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
    # claude-code's global_skills_dir is computed at import time from
    # CLAUDE_CONFIG_DIR / HOME. Patch the AgentConfig directly.
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(fake_home / ".claude"))
    from agent_toolkit_cli import skill_agents
    monkeypatch.setattr(
        skill_agents.AGENTS["claude-code"],
        "global_skills_dir",
        fake_home / ".claude" / "skills",
    )

    runner = CliRunner()
    _seed_library(runner, git_sandbox.upstream)

    # Stale symlink → some other path.
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    claude_skills = fake_home / ".claude" / "skills"
    claude_skills.mkdir(parents=True)
    stale = claude_skills / "demo"
    stale.symlink_to(elsewhere)

    from agent_toolkit_cli.skill_doctor import diagnose
    findings = diagnose(
        slugs=None, scope="global", home=fake_home, project=None,
    )
    drift = [f for f in findings if f.kind == "drifted_symlink"]
    assert len(drift) == 1
    assert drift[0].path == stale


def test_drifted_symlink_fix_relinks(git_sandbox, tmp_path: Path, monkeypatch):
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(fake_home / ".claude"))
    from agent_toolkit_cli import skill_agents
    monkeypatch.setattr(
        skill_agents.AGENTS["claude-code"],
        "global_skills_dir",
        fake_home / ".claude" / "skills",
    )

    runner = CliRunner()
    _seed_library(runner, git_sandbox.upstream)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    claude_skills = fake_home / ".claude" / "skills"
    claude_skills.mkdir(parents=True)
    stale = claude_skills / "demo"
    stale.symlink_to(elsewhere)

    from agent_toolkit_cli.skill_doctor import diagnose
    f = next(
        f for f in diagnose(
            slugs=None, scope="global", home=fake_home, project=None,
        )
        if f.kind == "drifted_symlink"
    )
    f.fix_action.apply()
    assert stale.is_symlink()
    assert stale.resolve() == (library_root / "demo").resolve()
    # Idempotent.
    f.fix_action.apply()
    assert stale.resolve() == (library_root / "demo").resolve()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_cli/test_skill_doctor.py::test_diagnose_drifted_symlink_global -v
```

Expected: FAIL — assertion error (empty findings list).

- [ ] **Step 3: Write minimal implementation**

Add to `src/agent_toolkit_cli/skill_doctor.py`:

```python
from agent_toolkit_cli.skill_agents import AGENTS, get_agent
from agent_toolkit_cli.skill_install import _should_skip_symlink
from agent_toolkit_cli.skill_paths import agent_projection_dir


def _projection_paths(
    slug: str, *, scope: Scope, home: Path | None, project: Path | None,
) -> list[tuple[str, Path]]:
    """Return (agent_name, projection_path) tuples for every non-universal
    real agent at the given scope. Universal bundle handled separately.
    """
    out: list[tuple[str, Path]] = []
    for name in AGENTS:
        if name == "universal":
            continue
        if get_agent(name).is_universal:
            # Skip rule fires at both scopes; no per-agent symlink expected.
            continue
        skip, _ = _should_skip_symlink(
            agent_name=name, scope=scope, project=project,
        )
        if skip:
            continue
        out.append((name, agent_projection_dir(
            name, slug, scope=scope, home=home, project=project,
        )))
    return out


def _make_relink_action(*, link: Path, canonical: Path) -> FixAction:
    def _apply() -> None:
        if link.is_symlink() and link.resolve() == canonical.resolve():
            return  # idempotent
        if link.is_symlink() or link.exists():
            link.unlink()
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(canonical)

    return FixAction(
        description=f"Re-link {link} → {canonical}",
        shell_preview=f"rm {link} && ln -s {canonical} {link}",
        apply=_apply,
    )
```

Extend `_check_slug` (replace the trailing `return findings`) with the drift walk:

```python
    canonical_real = canonical.resolve()
    for agent_name, link in _projection_paths(
        slug, scope=scope, home=home, project=project,
    ):
        if not link.is_symlink():
            continue
        try:
            target = link.resolve()
        except OSError:
            continue
        if target == canonical_real:
            continue
        findings.append(Finding(
            kind="drifted_symlink", slug=slug, scope=scope,
            path=link,
            detail=(
                f"{agent_name} symlink at {link} points to {target}, "
                f"expected {canonical}"
            ),
            fix_action=_make_relink_action(link=link, canonical=canonical),
        ))
    return findings
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_cli/test_skill_doctor.py -v
```

Expected: PASS — all eight tests green.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/skill_doctor.py tests/test_cli/test_skill_doctor.py
git commit -m "feat(doctor): detect drifted symlinks; fix re-links to canonical"
```

---

## Task 5: Detect `wrong_type_bundle` + fix (move + relink)

Global scope only. `~/.agents/skills/<slug>` should be a symlink to the library canonical; if it's a real directory (the user's v2.1→v2.2 migration case), back it up and replace with a symlink.

**Files:**
- Modify: `src/agent_toolkit_cli/skill_doctor.py`
- Modify: `tests/test_cli/test_skill_doctor.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli/test_skill_doctor.py`:

```python
def test_diagnose_wrong_type_bundle_global(git_sandbox, tmp_path: Path, monkeypatch):
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))

    runner = CliRunner()
    _seed_library(runner, git_sandbox.upstream)

    # Create a REAL directory at the bundle path (the v2.1-era layout).
    bundle = fake_home / ".agents" / "skills" / "demo"
    bundle.mkdir(parents=True)
    (bundle / "SKILL.md").write_text("v2.1 leftover\n")

    from agent_toolkit_cli.skill_doctor import diagnose
    findings = diagnose(
        slugs=None, scope="global", home=fake_home, project=None,
    )
    wrong = [f for f in findings if f.kind == "wrong_type_bundle"]
    assert len(wrong) == 1
    assert wrong[0].path == bundle


def test_wrong_type_bundle_fix_moves_and_relinks(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))

    runner = CliRunner()
    _seed_library(runner, git_sandbox.upstream)
    bundle = fake_home / ".agents" / "skills" / "demo"
    bundle.mkdir(parents=True)
    (bundle / "SKILL.md").write_text("v2.1 leftover\n")

    from agent_toolkit_cli.skill_doctor import diagnose
    f = next(
        f for f in diagnose(
            slugs=None, scope="global", home=fake_home, project=None,
        )
        if f.kind == "wrong_type_bundle"
    )
    f.fix_action.apply()

    assert bundle.is_symlink()
    assert bundle.resolve() == (library_root / "demo").resolve()
    # Backup directory was created with a .bak-doctor- prefix.
    backups = list(bundle.parent.glob("demo.bak-doctor-*"))
    assert len(backups) == 1
    # Idempotent: applying again does nothing destructive.
    f.fix_action.apply()
    assert bundle.is_symlink()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_cli/test_skill_doctor.py::test_diagnose_wrong_type_bundle_global -v
```

Expected: FAIL — `len(wrong) == 1` against an empty list.

- [ ] **Step 3: Write minimal implementation**

Add to `src/agent_toolkit_cli/skill_doctor.py`:

```python
import datetime as _dt

from agent_toolkit_cli.skill_install import _universal_bundle_link


def _make_bundle_repair_action(*, bundle: Path, canonical: Path) -> FixAction:
    def _apply() -> None:
        # Idempotent: if it's already a correct symlink, no-op.
        if bundle.is_symlink() and bundle.resolve() == canonical.resolve():
            return
        if bundle.is_dir() and not bundle.is_symlink():
            stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = bundle.with_name(f"{bundle.name}.bak-doctor-{stamp}")
            bundle.rename(backup)
        if bundle.is_symlink():
            bundle.unlink()
        bundle.parent.mkdir(parents=True, exist_ok=True)
        bundle.symlink_to(canonical)

    return FixAction(
        description=(
            f"Back up real directory at {bundle} and replace with symlink to "
            f"{canonical}"
        ),
        shell_preview=(
            f"mv {bundle} {bundle}.bak-doctor-$(date +%Y%m%d-%H%M%S) && "
            f"ln -s {canonical} {bundle}"
        ),
        apply=_apply,
    )
```

Extend `_check_slug` — add this block immediately after the drift walk and before `return findings`:

```python
    if scope == "global":
        bundle = _universal_bundle_link(slug)
        if bundle.exists() and not bundle.is_symlink():
            findings.append(Finding(
                kind="wrong_type_bundle", slug=slug, scope=scope,
                path=bundle,
                detail=(
                    f"{bundle} is a real directory; expected symlink to "
                    f"{canonical}"
                ),
                fix_action=_make_bundle_repair_action(
                    bundle=bundle, canonical=canonical,
                ),
            ))
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_cli/test_skill_doctor.py -v
```

Expected: PASS — all ten tests green.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/skill_doctor.py tests/test_cli/test_skill_doctor.py
git commit -m "feat(doctor): detect wrong-type bundle dir; back up + relink"
```

---

## Task 6: Detect `orphan_symlink` + fix (unlink)

Projection symlink exists but resolves to a path that doesn't exist on disk (broken link). Fix is to unlink it.

**Files:**
- Modify: `src/agent_toolkit_cli/skill_doctor.py`
- Modify: `tests/test_cli/test_skill_doctor.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli/test_skill_doctor.py`:

```python
def test_diagnose_orphan_symlink(git_sandbox, tmp_path: Path, monkeypatch):
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(fake_home / ".claude"))
    from agent_toolkit_cli import skill_agents
    monkeypatch.setattr(
        skill_agents.AGENTS["claude-code"],
        "global_skills_dir",
        fake_home / ".claude" / "skills",
    )

    runner = CliRunner()
    _seed_library(runner, git_sandbox.upstream)
    # Symlink to a path that doesn't exist.
    claude_skills = fake_home / ".claude" / "skills"
    claude_skills.mkdir(parents=True)
    broken = claude_skills / "demo"
    broken.symlink_to(tmp_path / "does-not-exist")

    from agent_toolkit_cli.skill_doctor import diagnose
    findings = diagnose(
        slugs=None, scope="global", home=fake_home, project=None,
    )
    orphans = [f for f in findings if f.kind == "orphan_symlink"]
    assert len(orphans) == 1


def test_orphan_symlink_fix_unlinks(git_sandbox, tmp_path: Path, monkeypatch):
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(fake_home / ".claude"))
    from agent_toolkit_cli import skill_agents
    monkeypatch.setattr(
        skill_agents.AGENTS["claude-code"],
        "global_skills_dir",
        fake_home / ".claude" / "skills",
    )

    runner = CliRunner()
    _seed_library(runner, git_sandbox.upstream)
    claude_skills = fake_home / ".claude" / "skills"
    claude_skills.mkdir(parents=True)
    broken = claude_skills / "demo"
    broken.symlink_to(tmp_path / "does-not-exist")

    from agent_toolkit_cli.skill_doctor import diagnose
    f = next(
        f for f in diagnose(
            slugs=None, scope="global", home=fake_home, project=None,
        )
        if f.kind == "orphan_symlink"
    )
    f.fix_action.apply()
    assert not broken.is_symlink()
    assert not broken.exists()
    # Idempotent.
    f.fix_action.apply()
    assert not broken.exists()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_cli/test_skill_doctor.py::test_diagnose_orphan_symlink -v
```

Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

Add to `src/agent_toolkit_cli/skill_doctor.py`:

```python
def _make_unlink_action(*, link: Path) -> FixAction:
    def _apply() -> None:
        if not link.is_symlink():
            return  # idempotent
        link.unlink()

    return FixAction(
        description=f"Unlink {link}",
        shell_preview=f"rm {link}",
        apply=_apply,
    )
```

Modify the drift walk in `_check_slug` to dispatch on resolve state. Replace this block:

```python
        if not link.is_symlink():
            continue
        try:
            target = link.resolve()
        except OSError:
            continue
        if target == canonical_real:
            continue
        findings.append(Finding(
            kind="drifted_symlink", slug=slug, scope=scope,
            path=link,
            detail=(
                f"{agent_name} symlink at {link} points to {target}, "
                f"expected {canonical}"
            ),
            fix_action=_make_relink_action(link=link, canonical=canonical),
        ))
```

with this:

```python
        if not link.is_symlink():
            continue
        target_path = Path(link.readlink())
        if not target_path.is_absolute():
            target_path = (link.parent / target_path).resolve()
        target_exists = target_path.exists()
        if not target_exists:
            findings.append(Finding(
                kind="orphan_symlink", slug=slug, scope=scope,
                path=link,
                detail=(
                    f"{agent_name} symlink at {link} points to {target_path} "
                    f"which does not exist"
                ),
                fix_action=_make_unlink_action(link=link),
            ))
            continue
        target = link.resolve()
        if target == canonical_real:
            continue
        findings.append(Finding(
            kind="drifted_symlink", slug=slug, scope=scope,
            path=link,
            detail=(
                f"{agent_name} symlink at {link} points to {target}, "
                f"expected {canonical}"
            ),
            fix_action=_make_relink_action(link=link, canonical=canonical),
        ))
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_cli/test_skill_doctor.py -v
```

Expected: PASS — all twelve tests green.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/skill_doctor.py tests/test_cli/test_skill_doctor.py
git commit -m "feat(doctor): detect orphan symlinks; fix unlinks"
```

---

## Task 7: Detect `foreign_symlink` (report-only; `--repair-foreign` makes it fixable)

A symlink whose target is outside `library_root()` (global) or outside `<project>/.agents/skills/` (project). Even if it resolves to something that exists. Report-only by default; with `repair_foreign=True` the Finding gets an unlink `fix_action`.

**Files:**
- Modify: `src/agent_toolkit_cli/skill_doctor.py`
- Modify: `tests/test_cli/test_skill_doctor.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli/test_skill_doctor.py`:

```python
def test_diagnose_foreign_symlink_report_only(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(fake_home / ".claude"))
    from agent_toolkit_cli import skill_agents
    monkeypatch.setattr(
        skill_agents.AGENTS["claude-code"],
        "global_skills_dir",
        fake_home / ".claude" / "skills",
    )

    runner = CliRunner()
    _seed_library(runner, git_sandbox.upstream)

    # Foreign target outside the library root — but the path EXISTS so it's
    # not orphan; and it's NOT inside library_root so it's foreign rather
    # than drifted.
    foreign = tmp_path / "user-handrolled-skill"
    foreign.mkdir()
    claude_skills = fake_home / ".claude" / "skills"
    claude_skills.mkdir(parents=True)
    link = claude_skills / "demo"
    link.symlink_to(foreign)

    from agent_toolkit_cli.skill_doctor import diagnose
    findings = diagnose(
        slugs=None, scope="global", home=fake_home, project=None,
    )
    foreign_findings = [f for f in findings if f.kind == "foreign_symlink"]
    assert len(foreign_findings) == 1
    # Report-only by default.
    assert foreign_findings[0].fix_action is None


def test_diagnose_foreign_symlink_repair_foreign(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(fake_home / ".claude"))
    from agent_toolkit_cli import skill_agents
    monkeypatch.setattr(
        skill_agents.AGENTS["claude-code"],
        "global_skills_dir",
        fake_home / ".claude" / "skills",
    )

    runner = CliRunner()
    _seed_library(runner, git_sandbox.upstream)

    foreign = tmp_path / "user-handrolled-skill"
    foreign.mkdir()
    claude_skills = fake_home / ".claude" / "skills"
    claude_skills.mkdir(parents=True)
    link = claude_skills / "demo"
    link.symlink_to(foreign)

    from agent_toolkit_cli.skill_doctor import diagnose
    findings = diagnose(
        slugs=None, scope="global", home=fake_home, project=None,
        repair_foreign=True,
    )
    f = next(f for f in findings if f.kind == "foreign_symlink")
    assert f.fix_action is not None
    f.fix_action.apply()
    assert not link.is_symlink()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_cli/test_skill_doctor.py::test_diagnose_foreign_symlink_report_only -v
```

Expected: FAIL — drift walk currently emits `drifted_symlink` for the foreign target.

- [ ] **Step 3: Write minimal implementation**

Add a helper:

```python
from agent_toolkit_cli.skill_paths import library_root as _library_root_fn


def _is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _expected_target_root(
    *, scope: Scope, project: Path | None,
) -> Path:
    if scope == "global":
        return _library_root_fn()
    assert project is not None
    return project / ".agents" / "skills"
```

Update the drift walk in `_check_slug` to dispatch foreign vs drift. Replace the drifted-symlink branch (the `target != canonical_real` case) with:

```python
        target = link.resolve()
        if target == canonical_real:
            continue
        expected_root = _expected_target_root(scope=scope, project=project)
        if not _is_inside(target, expected_root):
            findings.append(Finding(
                kind="foreign_symlink", slug=slug, scope=scope,
                path=link,
                detail=(
                    f"{agent_name} symlink at {link} points to {target}, "
                    f"which is outside {expected_root}"
                ),
                fix_action=(
                    _make_unlink_action(link=link) if repair_foreign else None
                ),
            ))
            continue
        findings.append(Finding(
            kind="drifted_symlink", slug=slug, scope=scope,
            path=link,
            detail=(
                f"{agent_name} symlink at {link} points to {target}, "
                f"expected {canonical}"
            ),
            fix_action=_make_relink_action(link=link, canonical=canonical),
        ))
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_cli/test_skill_doctor.py -v
```

Expected: PASS — all fourteen tests green. The earlier `test_diagnose_drifted_symlink_global` continues to pass because its `elsewhere = tmp_path / "elsewhere"` is also outside the library root, so it would now be classified as `foreign_symlink`, not `drifted_symlink`. **Update that test** to put `elsewhere` *inside* the library root so the drift branch is exercised:

In `test_diagnose_drifted_symlink_global` AND `test_drifted_symlink_fix_relinks`, change:

```python
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
```

to:

```python
    elsewhere = library_root / "elsewhere-slug"
    elsewhere.mkdir(parents=True)
```

Re-run:

```bash
uv run pytest tests/test_cli/test_skill_doctor.py -v
```

Expected: PASS — all fourteen tests green.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/skill_doctor.py tests/test_cli/test_skill_doctor.py
git commit -m "feat(doctor): detect foreign symlinks; report-only unless --repair-foreign"
```

---

## Task 8: Detect `dirty_tree` (report-only)

Canonical is a git repo with uncommitted changes. Already surfaced by `skill status`; doctor includes it for completeness. No fix action.

**Files:**
- Modify: `src/agent_toolkit_cli/skill_doctor.py`
- Modify: `tests/test_cli/test_skill_doctor.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli/test_skill_doctor.py`:

```python
def test_diagnose_dirty_tree(git_sandbox, tmp_path: Path, monkeypatch):
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))

    runner = CliRunner()
    _seed_library(runner, git_sandbox.upstream)
    # Dirty the canonical.
    (library_root / "demo" / "SKILL.md").write_text("edited\n")

    from agent_toolkit_cli.skill_doctor import diagnose
    findings = diagnose(
        slugs=None, scope="global", home=fake_home, project=None,
    )
    dirty = [f for f in findings if f.kind == "dirty_tree"]
    assert len(dirty) == 1
    # Report-only.
    assert dirty[0].fix_action is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_cli/test_skill_doctor.py::test_diagnose_dirty_tree -v
```

Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

In `_check_slug`, add after the drift walk and bundle-check block, before `return findings`:

```python
    if skill_git.is_git_repo(canonical):
        if skill_git.status(canonical, env=None) == skill_git.GitWorkingTreeStatus.DIRTY:
            findings.append(Finding(
                kind="dirty_tree", slug=slug, scope=scope,
                path=canonical,
                detail=f"working tree at {canonical} has uncommitted changes",
                fix_action=None,
            ))
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_cli/test_skill_doctor.py -v
```

Expected: PASS — all fifteen tests green.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/skill_doctor.py tests/test_cli/test_skill_doctor.py
git commit -m "feat(doctor): detect dirty working tree (report-only)"
```

---

## Task 9: Detect `lock_source_mismatch` (report-only)

Canonical is a git repo, but `git remote get-url origin` differs from the lock's recorded source (after normalisation via `clone_url_from_entry`). Report-only — the remediation is `skill remove && skill add <new-source>`, which doctor doesn't perform automatically.

**Files:**
- Modify: `src/agent_toolkit_cli/skill_doctor.py`
- Modify: `tests/test_cli/test_skill_doctor.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli/test_skill_doctor.py`:

```python
import subprocess


def test_diagnose_lock_source_mismatch(git_sandbox, tmp_path: Path, monkeypatch):
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))

    runner = CliRunner()
    _seed_library(runner, git_sandbox.upstream)

    # Point origin at a different URL on disk.
    other = tmp_path / "other-remote.git"
    subprocess.run(
        ["git", "init", "--bare", str(other)],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(library_root / "demo"),
         "remote", "set-url", "origin", str(other)],
        check=True, env=git_sandbox.env, capture_output=True,
    )

    from agent_toolkit_cli.skill_doctor import diagnose
    findings = diagnose(
        slugs=None, scope="global", home=fake_home, project=None,
    )
    mismatch = [f for f in findings if f.kind == "lock_source_mismatch"]
    assert len(mismatch) == 1
    assert mismatch[0].fix_action is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_cli/test_skill_doctor.py::test_diagnose_lock_source_mismatch -v
```

Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

Add a helper in `skill_doctor.py`:

```python
def _remote_origin_url(canonical: Path) -> str | None:
    """Return `git remote get-url origin` for canonical, or None on failure."""
    try:
        proc = skill_git._run(
            ["git", "-C", str(canonical), "remote", "get-url", "origin"],
            env=None,
        )
    except skill_git.GitError:
        return None
    return proc.stdout.strip() or None


def _normalise_git_url(url: str) -> str:
    """Lowercase + strip a trailing .git so `foo` and `foo.git` compare equal."""
    u = url.strip().lower()
    if u.endswith(".git"):
        u = u[:-4]
    return u
```

Add to `_check_slug` after the dirty-tree block, before `return findings`:

```python
    if skill_git.is_git_repo(canonical):
        observed = _remote_origin_url(canonical)
        expected = clone_url_from_entry(entry)
        if observed is not None and _normalise_git_url(observed) != _normalise_git_url(expected):
            findings.append(Finding(
                kind="lock_source_mismatch", slug=slug, scope=scope,
                path=canonical,
                detail=(
                    f"lock source {expected!r} != git remote origin "
                    f"{observed!r}"
                ),
                fix_action=None,
            ))
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_cli/test_skill_doctor.py -v
```

Expected: PASS — all sixteen tests green.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/skill_doctor.py tests/test_cli/test_skill_doctor.py
git commit -m "feat(doctor): detect lock-vs-git-remote source mismatch (report-only)"
```

---

## Task 10: Add `skill doctor` CLI command

Thin Click wrapper that calls `diagnose()`, renders findings, runs the y/N/q prompt loop, and returns the right exit code.

**Files:**
- Create: `src/agent_toolkit_cli/commands/skill/doctor_cmd.py`
- Modify: `src/agent_toolkit_cli/commands/skill/__init__.py`
- Create: `tests/test_cli/test_cli_skill_doctor.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli/test_cli_skill_doctor.py
"""Integration tests for `agent-toolkit-cli skill doctor`."""
from __future__ import annotations

import shutil
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def _seed(runner, upstream, monkeypatch, tmp_path):
    library_root = tmp_path / "lib" / "skills"
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
    r = runner.invoke(main, ["skill", "add", str(upstream), "--slug", "demo"])
    assert r.exit_code == 0, r.output
    return library_root, fake_home


def test_doctor_clean_tree_exit0(git_sandbox, tmp_path: Path, monkeypatch):
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    runner = CliRunner()
    _seed(runner, git_sandbox.upstream, monkeypatch, tmp_path)
    r = runner.invoke(main, ["skill", "doctor", "-g"])
    assert r.exit_code == 0, r.output
    assert "all clean" in r.output


def test_doctor_no_fix_exits_nonzero_with_findings(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    runner = CliRunner()
    library_root, fake_home = _seed(
        runner, git_sandbox.upstream, monkeypatch, tmp_path,
    )
    shutil.rmtree(library_root / "demo")
    r = runner.invoke(main, ["skill", "doctor", "-g", "--no-fix"])
    assert r.exit_code == 1, r.output
    assert "missing_canonical" in r.output


def test_doctor_yes_fixes_drift(git_sandbox, tmp_path: Path, monkeypatch):
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "home" / ".claude"))
    from agent_toolkit_cli import skill_agents
    monkeypatch.setattr(
        skill_agents.AGENTS["claude-code"],
        "global_skills_dir",
        tmp_path / "home" / ".claude" / "skills",
    )
    runner = CliRunner()
    library_root, fake_home = _seed(
        runner, git_sandbox.upstream, monkeypatch, tmp_path,
    )
    # Plant a drifted symlink within library_root so it's drift, not foreign.
    elsewhere = library_root / "elsewhere"
    elsewhere.mkdir(parents=True)
    claude_skills = fake_home / ".claude" / "skills"
    claude_skills.mkdir(parents=True)
    stale = claude_skills / "demo"
    stale.symlink_to(elsewhere)
    # 'y' to apply the fix.
    r = runner.invoke(main, ["skill", "doctor", "-g"], input="y\n")
    assert r.exit_code == 0, r.output
    assert stale.resolve() == (library_root / "demo").resolve()


def test_doctor_no_response_skips_and_exits_nonzero(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "home" / ".claude"))
    from agent_toolkit_cli import skill_agents
    monkeypatch.setattr(
        skill_agents.AGENTS["claude-code"],
        "global_skills_dir",
        tmp_path / "home" / ".claude" / "skills",
    )
    runner = CliRunner()
    library_root, fake_home = _seed(
        runner, git_sandbox.upstream, monkeypatch, tmp_path,
    )
    elsewhere = library_root / "elsewhere"
    elsewhere.mkdir(parents=True)
    claude_skills = fake_home / ".claude" / "skills"
    claude_skills.mkdir(parents=True)
    stale = claude_skills / "demo"
    stale.symlink_to(elsewhere)
    r = runner.invoke(main, ["skill", "doctor", "-g"], input="N\n")
    assert r.exit_code == 1, r.output
    assert stale.resolve() == elsewhere.resolve()  # untouched


def test_doctor_q_breaks_loop(git_sandbox, tmp_path: Path, monkeypatch):
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    runner = CliRunner()
    library_root, fake_home = _seed(
        runner, git_sandbox.upstream, monkeypatch, tmp_path,
    )
    shutil.rmtree(library_root / "demo")
    r = runner.invoke(main, ["skill", "doctor", "-g"], input="q\n")
    assert r.exit_code == 1, r.output
    # Library still missing (we quit before applying).
    assert not (library_root / "demo").exists()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_cli/test_cli_skill_doctor.py -v
```

Expected: FAIL — `Error: No such command 'doctor'`.

- [ ] **Step 3: Write minimal implementation**

Create the command file:

```python
# src/agent_toolkit_cli/commands/skill/doctor_cmd.py
"""skill doctor subcommand."""
from __future__ import annotations

import click

from agent_toolkit_cli.skill_doctor import diagnose

from ._common import scope_and_roots


@click.command("doctor")
@click.argument("slugs", nargs=-1)
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.option("--no-fix", is_flag=True,
              help="Report only; do not prompt or mutate.")
@click.option("--repair-foreign", is_flag=True,
              help="Allow fixing foreign symlinks (off by default).")
@click.pass_context
def doctor_cmd(
    ctx: click.Context, slugs: tuple[str, ...],
    global_: bool, project_flag: bool,
    no_fix: bool, repair_foreign: bool,
) -> None:
    """Diagnose and (optionally) repair skill-installation drift."""
    scope, home, project_root = scope_and_roots(
        global_, project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
    )
    findings = diagnose(
        slugs=slugs or None,
        scope=scope, home=home, project=project_root,
        repair_foreign=repair_foreign,
    )
    if not findings:
        click.echo("✓ all clean")
        return

    fixed = skipped = 0
    quit_loop = False
    for f in findings:
        click.echo("")
        click.echo(f"{f.slug} · {f.kind} ({f.scope})")
        click.echo(f"  path:   {f.path}")
        click.echo(f"  detail: {f.detail}")
        if f.fix_action is None or no_fix or quit_loop:
            skipped += 1
            if f.fix_action is None:
                click.echo("  (report-only — no automatic fix)")
            continue
        click.echo(f"  fix:    {f.fix_action.shell_preview}")
        ans = click.prompt(
            "  apply?", default="N", show_default=False,
            type=click.Choice(["y", "N", "q"], case_sensitive=False),
        )
        ans = ans.lower()
        if ans == "y":
            try:
                f.fix_action.apply()
                click.echo("  fixed.")
                fixed += 1
            except Exception as exc:
                click.echo(f"  fix failed: {exc}")
                skipped += 1
        elif ans == "q":
            quit_loop = True
            skipped += 1
        else:
            skipped += 1

    click.echo("")
    click.echo(
        f"summary: {len(findings)} findings, {fixed} fixed, {skipped} skipped"
    )
    if skipped > 0:
        ctx.exit(1)
```

Wire into `__init__.py`. Open `src/agent_toolkit_cli/commands/skill/__init__.py` and:

Add the import near the other subcommand imports (after `from .update_cmd import update_cmd`):

```python
from .doctor_cmd import doctor_cmd
```

Add the registration near the existing `skill.add_command(...)` block at the bottom:

```python
skill.add_command(doctor_cmd)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_cli/test_cli_skill_doctor.py -v
```

Expected: PASS — all five tests green.

Also re-run the full suite to confirm nothing else broke:

```bash
uv run pytest -q
```

Expected: full suite green (existing tests + 5 new).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/skill/doctor_cmd.py \
        src/agent_toolkit_cli/commands/skill/__init__.py \
        tests/test_cli/test_cli_skill_doctor.py
git commit -m "feat(doctor): add skill doctor CLI command with y/N/q prompt loop"
```

---

## Task 11: Update root CLI help string (remove "doctor" from removed-pre-v2 list)

The root help text in `cli.py` claims `doctor` was removed in v2.3.0; that's now inaccurate.

**Files:**
- Modify: `src/agent_toolkit_cli/cli.py:21-25`
- Modify: `tests/test_cli_help.py`

- [ ] **Step 1: Write the failing test**

Inspect the existing help test first to match the assertion pattern:

```bash
uv run pytest tests/test_cli_help.py -v
```

Then append to `tests/test_cli_help.py`:

```python
def test_root_help_does_not_call_doctor_removed():
    """v2.3.0 help string listed 'doctor' as removed; v2.3.x reintroduces it.

    Guard against the stale claim by asserting doctor is not in the removed
    list. (skill doctor itself is registered via `skill.add_command`.)"""
    from click.testing import CliRunner
    from agent_toolkit_cli.cli import main
    r = CliRunner().invoke(main, ["--help"])
    assert r.exit_code == 0
    # The "Pre-v2 commands ... were removed" sentence must not mention doctor.
    removed_line = next(
        (line for line in r.output.splitlines() if "were removed" in line),
        "",
    )
    assert "doctor" not in removed_line, removed_line
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_cli_help.py::test_root_help_does_not_call_doctor_removed -v
```

Expected: FAIL — current help mentions `doctor` in the removed list.

- [ ] **Step 3: Write minimal implementation**

In `src/agent_toolkit_cli/cli.py`, replace the help block (lines 19-25):

```python
        "agent-toolkit-cli — manage skills via per-skill upstream git repos + "
        "lockfile. Run `agent-toolkit-cli skill --help` for subcommands.\n\n"
        "Pre-v2 commands (check, link, doctor, etc.) were removed in v2.3.0. "
        "The frozen v1 surface lives at the v1.0.0 tag; install it via "
        "`uv tool install --from git+https://github.com/ajanderson1/agent-toolkit-cli@v1.0.0 agent-toolkit`."
```

with:

```python
        "agent-toolkit-cli — manage skills via per-skill upstream git repos + "
        "lockfile. Run `agent-toolkit-cli skill --help` for subcommands.\n\n"
        "Pre-v2 commands (check, link, etc.) were removed in v2.3.0. "
        "The frozen v1 surface lives at the v1.0.0 tag; install it via "
        "`uv tool install --from git+https://github.com/ajanderson1/agent-toolkit-cli@v1.0.0 agent-toolkit`."
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_cli_help.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/cli.py tests/test_cli_help.py
git commit -m "docs(cli): drop 'doctor' from removed-pre-v2 list (reintroduced in v2.4)"
```

---

## Task 12: Scaffold `CellInfoScreen` modal

A standalone Textual `ModalScreen` that takes a title + body markup string and dismisses on Escape. No state-aware content yet — that's Task 13.

**Files:**
- Create: `src/agent_toolkit_tui/screens/__init__.py` (empty)
- Create: `src/agent_toolkit_tui/screens/cell_info.py`
- Create: `tests/test_tui/test_cell_info.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tui/test_cell_info.py
"""Pilot tests for the CellInfoScreen modal."""
from __future__ import annotations

import pytest

from agent_toolkit_tui.screens.cell_info import CellInfoScreen


@pytest.mark.asyncio
async def test_modal_renders_title_and_body():
    from textual.app import App
    pushed: list[CellInfoScreen] = []

    class _A(App):
        def on_mount(self):
            screen = CellInfoScreen(
                title="demo · claude-code @ global",
                body_markup="Linked.\nPath: /tmp/x",
            )
            pushed.append(screen)
            self.push_screen(screen)

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        assert pushed
        text = pushed[0].query_one("#cell-info-body").renderable
        # Rich Text or str — coerce both.
        rendered = str(text)
        assert "Linked." in rendered
        assert "/tmp/x" in rendered


@pytest.mark.asyncio
async def test_modal_dismisses_on_escape():
    from textual.app import App

    class _A(App):
        def on_mount(self):
            self.push_screen(CellInfoScreen(title="t", body_markup="b"))

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        assert isinstance(a.screen, CellInfoScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(a.screen, CellInfoScreen)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_tui/test_cell_info.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'agent_toolkit_tui.screens'`.

- [ ] **Step 3: Write minimal implementation**

Create the empty package marker:

```python
# src/agent_toolkit_tui/screens/__init__.py
"""Modal screens for the agent-toolkit TUI."""
```

Create the modal:

```python
# src/agent_toolkit_tui/screens/cell_info.py
"""CellInfoScreen — modal that renders state-specific info for a SkillGrid cell."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, Static


class CellInfoScreen(ModalScreen[None]):
    """Read-only info modal for a single SkillGrid cell."""

    DEFAULT_CSS = """
    CellInfoScreen {
        align: center middle;
    }
    CellInfoScreen > Vertical {
        background: $panel;
        border: round $primary;
        padding: 1 2;
        width: 80;
        height: auto;
    }
    CellInfoScreen #cell-info-title {
        width: 100%;
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }
    CellInfoScreen #cell-info-body {
        width: 100%;
    }
    CellInfoScreen #cell-info-footer {
        margin-top: 1;
        color: $secondary;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss_modal", "Close"),
        Binding("q", "dismiss_modal", "Close"),
        Binding("i", "dismiss_modal", "Close"),
    ]

    def __init__(self, *, title: str, body_markup: str) -> None:
        super().__init__()
        self._title = title
        self._body_markup = body_markup

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self._title, id="cell-info-title")
            yield Static(self._body_markup, id="cell-info-body", markup=True)
            yield Static("Esc / q / i  close", id="cell-info-footer")

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_tui/test_cell_info.py -v
```

Expected: PASS — both modal tests green.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/screens/__init__.py \
        src/agent_toolkit_tui/screens/cell_info.py \
        tests/test_tui/test_cell_info.py
git commit -m "feat(tui): add CellInfoScreen modal scaffolding"
```

---

## Task 13: Wire `i` keybinding on `SkillGrid` with state-aware content

Add the binding + `action_info()` that derives title + body from the cursor's row/column and the current cell state. The drift body includes the doctor command for copy-paste.

**Files:**
- Modify: `src/agent_toolkit_tui/widgets/skill_grid.py`
- Modify: `src/agent_toolkit_tui/app.py`
- Modify: `tests/test_tui/test_cell_info.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_tui/test_cell_info.py`:

```python
from pathlib import Path

from agent_toolkit_tui.skill_state import INTERACTIVE_AGENTS, SkillCell, SkillRow
from agent_toolkit_tui.widgets.skill_grid import SkillGrid


def _row(slug: str, *, scope="global",
         linked: tuple[str, ...] = (),
         drifted: tuple[str, ...] = (),
         skipped: tuple[str, ...] = ()) -> SkillRow:
    cells = {}
    for a in INTERACTIVE_AGENTS:
        cells[(a, scope)] = SkillCell(
            linked=(a in linked),
            drift=(a in drifted),
            skipped=(a in skipped),
        )
    return SkillRow(
        slug=slug, source=f"x/{slug}", ref="main",
        state="clean", cells=cells,
    )


@pytest.mark.asyncio
async def test_info_on_drift_cell_shows_doctor_command():
    from textual.app import App

    class _A(App):
        def compose(self):
            yield SkillGrid([_row("journal", drifted=("claude-code",))], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        g = a.query_one("#g", SkillGrid)
        g.cursor_to_cell(row_slug="journal", agent_name="claude-code")
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        from agent_toolkit_tui.screens.cell_info import CellInfoScreen
        assert isinstance(a.screen, CellInfoScreen)
        body = str(a.screen.query_one("#cell-info-body").renderable)
        assert "skill doctor journal -g" in body
        assert "drift" in body.lower()


@pytest.mark.asyncio
async def test_info_on_unlinked_cell_explains_space():
    from textual.app import App

    class _A(App):
        def compose(self):
            yield SkillGrid([_row("journal")], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        g = a.query_one("#g", SkillGrid)
        g.cursor_to_cell(row_slug="journal", agent_name="claude-code")
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        from agent_toolkit_tui.screens.cell_info import CellInfoScreen
        assert isinstance(a.screen, CellInfoScreen)
        body = str(a.screen.query_one("#cell-info-body").renderable)
        assert "space" in body.lower()


@pytest.mark.asyncio
async def test_info_on_slug_column_shows_source():
    from textual.app import App

    class _A(App):
        def compose(self):
            yield SkillGrid([_row("journal")], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        g = a.query_one("#g", SkillGrid)
        from textual.coordinate import Coordinate
        from textual.widgets import DataTable
        t = g.query_one("#skill-table", DataTable)
        t.cursor_coordinate = Coordinate(row=0, column=0)  # slug col
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        from agent_toolkit_tui.screens.cell_info import CellInfoScreen
        assert isinstance(a.screen, CellInfoScreen)
        body = str(a.screen.query_one("#cell-info-body").renderable)
        assert "x/journal" in body  # the source string from _row
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_tui/test_cell_info.py -v
```

Expected: FAIL — `i` binding not on `SkillGrid`; `action_info` undefined.

- [ ] **Step 3: Write minimal implementation**

In `src/agent_toolkit_tui/widgets/skill_grid.py`, extend `BINDINGS`:

```python
    BINDINGS = [
        Binding("space", "toggle_cell", "Toggle", priority=True),
        Binding("a", "toggle_column", "All/None", priority=True),
        Binding("i", "info", "Info", priority=True),
    ]
```

Add an `action_info` method to the class (place it just before `action_toggle_column`):

```python
    def action_info(self) -> None:
        from agent_toolkit_cli.skill_paths import (
            agent_projection_dir, canonical_skill_dir,
        )
        from agent_toolkit_tui.screens.cell_info import CellInfoScreen

        try:
            table = self.query_one("#skill-table", DataTable)
        except Exception:
            return
        coord = table.cursor_coordinate
        if coord.row >= len(self._rows):
            return
        row = self._rows[coord.row]
        scope = self._scope
        scope_flag = "-g" if scope == "global" else "-p"

        # Column 0 = slug; last column = state; middle = INTERACTIVE_AGENTS.
        if coord.column == 0:
            title = f"{row.slug} · slug"
            body = (
                f"Skill [b]{row.slug}[/]\n"
                f"Source: {row.source}\n"
                f"Ref:    {row.ref}\n"
                f"State:  {row.state}"
            )
        elif coord.column == 1 + len(INTERACTIVE_AGENTS):
            title = f"{row.slug} · state"
            body = f"State: [b]{row.state}[/]"
            if row.state == "missing":
                body += (
                    f"\n\nLibrary entry exists but the directory is gone.\n"
                    f"Run [b]agent-toolkit-cli skill doctor {row.slug} "
                    f"{scope_flag}[/] to repair."
                )
        else:
            agent = self._agent_for_column(coord.column)
            if agent is None:
                return
            cell = row.cells.get((agent, scope))
            if cell is None:
                return
            title = f"{row.slug} · {agent} @ {scope}"
            pending = self._pending.get((scope, agent, row.slug))
            body = self._info_body_for_cell(
                row=row, agent=agent, cell=cell, pending=pending,
                scope=scope, scope_flag=scope_flag,
            )
        self.app.push_screen(CellInfoScreen(title=title, body_markup=body))

    def _info_body_for_cell(
        self, *, row: "SkillRow", agent: str, cell, pending,
        scope: str, scope_flag: str,
    ) -> str:
        from agent_toolkit_cli.skill_paths import (
            agent_projection_dir, canonical_skill_dir,
        )
        from pathlib import Path

        canonical = canonical_skill_dir(
            row.slug, scope=scope,
            home=Path.home() if scope == "global" else None,
            project=None if scope == "global" else Path.cwd(),
        )
        if agent == "universal":
            if scope == "global":
                bundle = Path.home() / ".agents" / "skills" / row.slug
                if cell.drift:
                    return (
                        f"[red]Drift detected.[/]\n\n"
                        f"Bundle path: {bundle}\n"
                        f"Expected:    symlink → {canonical}\n\n"
                        f"Fix with:\n"
                        f"  [b]agent-toolkit-cli skill doctor {row.slug} "
                        f"{scope_flag}[/]"
                    )
                if cell.linked:
                    return f"Linked.\nBundle: {bundle} → {canonical}"
                return (
                    f"Not linked.\nPress [b]space[/] to queue link "
                    f"({bundle} → {canonical})."
                )
            # project scope: canonical IS the install
            if cell.linked:
                return f"Project canonical exists at {canonical}."
            return (
                f"Not installed in project.\nPress [b]space[/] to queue "
                f"install (clones into {canonical})."
            )

        link = agent_projection_dir(
            agent, row.slug, scope=scope,
            home=Path.home() if scope == "global" else None,
            project=None if scope == "global" else Path.cwd(),
        )
        if cell.skipped:
            return (
                f"Universal agent — no symlink needed.\n"
                f"Skill lives at {canonical}."
            )
        if pending == "link":
            return (
                f"[yellow]Pending: link.[/]\n"
                f"{link} → {canonical}\n\n"
                f"Press [b]^s[/] to apply."
            )
        if pending == "unlink":
            return (
                f"[yellow]Pending: unlink.[/]\n"
                f"{link}\n\n"
                f"Press [b]^s[/] to apply."
            )
        if cell.drift:
            try:
                target = link.resolve()
            except OSError:
                target = "(unreadable)"
            return (
                f"[red]Drift detected.[/]\n\n"
                f"Symlink: {link}\n"
                f"Points to: {target}\n"
                f"Expected:  {canonical}\n\n"
                f"Fix with:\n"
                f"  [b]agent-toolkit-cli skill doctor {row.slug} {scope_flag}[/]"
            )
        if cell.linked:
            return f"Linked.\n{link} → {canonical}"
        return (
            f"Not linked.\nPress [b]space[/] to queue link "
            f"({link} → {canonical})."
        )
```

Wire the binding into the Footer via the app. Open `src/agent_toolkit_tui/app.py` and add to `TUIApp.BINDINGS`:

```python
    BINDINGS = [
        Binding("ctrl+s", "apply", "Apply", priority=True),
        Binding("ctrl+d", "diff", "Diff", priority=True),
        Binding("ctrl+r", "refresh", "Refresh", priority=True),
        Binding("ctrl+z", "revert", "Revert", priority=True),
        Binding("s", "scope_toggle", "toggle scope"),
        Binding("i", "info_pass", "Info"),
        Binding("q", "quit", "Quit"),
    ]
```

And add a passthrough action immediately after `action_scope_toggle`:

```python
    def action_info_pass(self) -> None:
        """Delegate `i` to the SkillGrid widget (visible in Footer hints)."""
        try:
            grid = self.query_one("#skill-grid", SkillGrid)
        except NoMatches:
            return
        grid.action_info()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_tui/test_cell_info.py -v
```

Expected: PASS — all five tests in this file green.

Re-run the whole suite to make sure nothing else broke (the new `i` binding shouldn't collide with anything in existing tests):

```bash
uv run pytest -q
```

Expected: full suite green.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/widgets/skill_grid.py \
        src/agent_toolkit_tui/app.py \
        tests/test_tui/test_cell_info.py
git commit -m "feat(tui): add i Info keybinding with state-aware modal content"
```

---

## Task 14: Smoke-test the full feature against the real journal-skill drift

Drive the doctor command against a controlled reproduction of the user's actual on-disk problem to make sure the cross-component flow works.

**Files:**
- Modify: `tests/test_cli/test_cli_skill_doctor.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli/test_cli_skill_doctor.py`:

```python
def test_doctor_journal_v21_to_v22_repro(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    """End-to-end repro of the v2.1->v2.2 layout the user hit on `journal`.

    Setup:
      ~/.agent-toolkit/skills/journal/  - library canonical (v2.2)
      ~/.agents/skills/journal/         - real directory (v2.1 leftover)
      ~/.claude/skills/journal          - symlink to ~/.agents/skills/journal

    Expected: doctor with 'y' to all prompts ends with bundle as a symlink to
    library, claude-code link re-pointed at library, and exit code 0.
    """
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "home" / ".claude"))
    from agent_toolkit_cli import skill_agents
    monkeypatch.setattr(
        skill_agents.AGENTS["claude-code"],
        "global_skills_dir",
        tmp_path / "home" / ".claude" / "skills",
    )

    runner = CliRunner()
    library_root, fake_home = _seed(
        runner, git_sandbox.upstream, monkeypatch, tmp_path,
    )

    # Mirror the user's actual filesystem:
    # 1. Real dir at the bundle path.
    bundle = fake_home / ".agents" / "skills" / "journal"
    bundle.mkdir(parents=True)
    (bundle / "SKILL.md").write_text("v2.1 leftover\n")
    # 2. Claude link pointing at the bundle (not library).
    claude_skills = fake_home / ".claude" / "skills"
    claude_skills.mkdir(parents=True)
    claude_link = claude_skills / "journal"
    claude_link.symlink_to(bundle)
    # 3. Add a 'journal' entry to the library by reusing the demo upstream
    #    under a journal slug.
    r = runner.invoke(main, [
        "skill", "add", str(git_sandbox.upstream), "--slug", "journal",
    ])
    assert r.exit_code == 0, r.output
    library_journal = library_root / "journal"
    assert library_journal.exists()

    # Two fixable findings (wrong_type_bundle + drifted_symlink). Answer y/y.
    r = runner.invoke(main, ["skill", "doctor", "journal", "-g"], input="y\ny\n")
    assert r.exit_code == 0, r.output

    # Bundle is now a symlink to library.
    assert bundle.is_symlink()
    assert bundle.resolve() == library_journal.resolve()
    # Claude link now resolves to library (not the backup).
    assert claude_link.resolve() == library_journal.resolve()
    # Backup of the original bundle dir was created.
    assert any(bundle.parent.glob("journal.bak-doctor-*"))
```

- [ ] **Step 2: Run test to verify it fails (or passes)**

```bash
uv run pytest tests/test_cli/test_cli_skill_doctor.py::test_doctor_journal_v21_to_v22_repro -v
```

If everything wired correctly in Tasks 1-13, this should already PASS — it's a verification test more than a TDD test. If it fails, the failure points to either ordering of findings (wrong_type_bundle vs drifted_symlink) or a missing case in the diagnose walk. Fix in `skill_doctor.py`.

- [ ] **Step 3: Re-run full suite**

```bash
uv run pytest -q
```

Expected: full suite green.

- [ ] **Step 4: Commit**

```bash
git add tests/test_cli/test_cli_skill_doctor.py
git commit -m "test(doctor): end-to-end repro of journal v2.1->v2.2 drift"
```

---

## Task 15: Run doctor against the actual on-disk state

Verify the change against the user's real machine (the original issue reproducer).

- [ ] **Step 1: Confirm we're outside the worktree's test sandbox**

```bash
pwd
```

Expected: `/Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/skill-doctor`.

- [ ] **Step 2: Run doctor in --no-fix mode against the user's real ~/.agent-toolkit/skills lock**

```bash
uv run agent-toolkit-cli skill doctor -g --no-fix
```

Expected output (with the user's real on-disk state at session start): findings of kind `wrong_type_bundle` for `journal` (and possibly `aj-workflow`, `cmux`, `cmux-browser` if those are also v2.1-shaped) and `drifted_symlink` for the Claude Code symlinks pointing at the bundle dirs.

- [ ] **Step 3: Show the user the findings and let them decide whether to apply**

Do NOT auto-apply against the user's real filesystem. Present the `--no-fix` output and ask whether to run the full `skill doctor -g` interactively.

- [ ] **Step 4: No commit needed**

This task is observational. The change is already committed in Task 14.

---

## Self-Review

Run through the spec section by section against the plan:

| Spec section | Implementing task(s) |
| --- | --- |
| `missing_canonical` detection + re-clone OR remove-entry fix | Task 3 |
| `drifted_symlink` detection + relink fix | Task 4 |
| `wrong_type_bundle` detection + backup-and-relink fix (global only) | Task 5 |
| `orphan_symlink` detection + unlink fix | Task 6 |
| `foreign_symlink` detection (report-only; `--repair-foreign` opens fix) | Task 7 |
| `dirty_tree` detection (report-only) | Task 8 |
| `lock_source_mismatch` detection (report-only) | Task 9 |
| `--no-fix` flag | Task 10 |
| `--repair-foreign` flag | Task 10 |
| Per-issue y/N/q prompt loop | Task 10 |
| Exit-code semantics (1 if any skipped) | Task 10 (asserted in tests 10c/10d/10e) |
| `-g/--global` / `-p/--project` flags, default project | Task 10 |
| Optional slug arg (no slug = scan all) | Task 10 (asserted in test_doctor_clean_tree_exit0 + test_doctor_journal_v21_to_v22_repro) |
| `i` keybinding on `SkillGrid` | Task 13 |
| `CellInfoScreen` modal with state-aware body | Tasks 12 + 13 |
| Drift cell shows doctor command | Task 13 (test_info_on_drift_cell_shows_doctor_command) |
| Other cell states (linked, unlinked, pending link/unlink, skipped, slug, state) | Task 13 (`_info_body_for_cell`) |
| Footer hint for `i Info` | Task 13 (app-level binding pass-through) |
| Update root CLI help string | Task 11 |

**Placeholder check:** scanned the plan for TBD/TODO/"fill in later" — none found. Every step has actual code, exact commands, expected output.

**Type-consistency check:**
- `Finding.fix_action: FixAction | None` — used consistently in Tasks 3, 8, 9 (None for report-only).
- `FixAction.apply: Callable[[], None]` — invoked as `f.fix_action.apply()` everywhere.
- `make_remove_entry_action` — public symbol in Task 3, referenced in the test of the same task. CLI flow in Task 10 uses only the primary `fix_action` field; sibling action is reserved for a follow-up if the CLI needs to offer the secondary "just remove the lock entry" prompt. The spec describes a sequential two-prompt path for `missing_canonical`; this plan ships the simpler single-prompt re-clone fix and exposes `make_remove_entry_action` for a follow-up to layer the second prompt without a new engine API. (Noted as a deliberate scope reduction here.)
- `diagnose(slugs=..., scope=..., home=..., project=..., repair_foreign=...)` signature matches across all tests.
- `CellInfoScreen(title=..., body_markup=...)` constructor signature consistent in Tasks 12 and 13.

**Deliberate spec deviation:** the spec proposed a sequential two-prompt UX for `missing_canonical` (re-clone? then if N: remove lock entry?). This plan ships only the re-clone prompt as the `fix_action`, plus a `make_remove_entry_action` helper for a follow-up to layer the second prompt. This trades a small UX gap for a tighter first cut; the helper is in place and tested so the follow-up is small.

---
