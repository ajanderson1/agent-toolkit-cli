# `skill migrate-to-monorepo` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `skill migrate-to-monorepo ajanderson1/agent-toolkit [--dry-run]` command that re-homes owned per-skill lock entries into the monorepo — rewriting each entry to owned-monorepo-subpath shape, replacing its clone dir with a symlink into the shared `_parents/` clone, and re-projecting harness symlinks — refusing on any unreconciled local work.

**Architecture:** A new `migrate_cmd.py` subcommand registered on the `skill` group. Pure-function core (`eligibility`, `refusal-check`, `entry-rewrite`) kept testable in isolation; the command orchestrates per-skill with isolated failures and a summary report. Safety is three layers: SHA+clean-tree refusal, cross-history content-diff, and destructive-delete-last ordering. Reuses PR1's data model (`LockEntry`/`write_lock`), git helpers (`skill_git.head_sha`/`status`/`is_git_repo`), paths (`parent_clone_path`/`library_skill_path`/`library_lock_path`), the `_symlink_or_copy` materialization primitive, and the `engine_apply(InstallPlan)` projection path.

**Tech Stack:** Python 3.13, click, pytest, `CliRunner`, `uv`, `ruff`, `mypy --strict`. Spec: `docs/superpowers/specs/2026-05-27-migrate-to-monorepo-design.md`.

---

## File Structure

- **Create:** `src/agent_toolkit_cli/skill_migrate.py` — pure-function core: `monorepo_subpath_for(slug)`, `is_migratable(entry)`, `RefusalReason`/`check_refusal(...)`, `migrated_entry(...)`. No click, no I/O beyond git reads passed in. One responsibility: the migration decision + entry transform.
- **Create:** `src/agent_toolkit_cli/commands/skill/migrate_cmd.py` — the click command. Orchestrates: load lock, ensure parent clone, per-skill (refusal → rewrite → symlink-swap → reproject), summary report, `--dry-run`.
- **Modify:** `src/agent_toolkit_cli/commands/skill/__init__.py` — import + `skill.add_command(migrate_cmd)`.
- **Create:** `tests/test_cli/test_skill_migrate.py` — full behavior matrix from the spec's Testing section.
- **Modify:** `docs/agent-toolkit/skill-lock.md` — document the migration (own-repo → owned-monorepo-subpath transform), if that doc enumerates entry shapes.

Helper shared by tests, defined once at the top of `test_skill_migrate.py` (DRY): `_setup(tmp_path, monkeypatch)` builds (a) a monorepo parent git repo with `skills/<slug>/SKILL.md` for the chosen skills, (b) per-skill clone dirs + own-repo-shape lock entries, and (c) sets `AGENT_TOOLKIT_SKILLS_ROOT`.

---

## Task 1: Pure core — subpath + migratability

**Files:**
- Create: `src/agent_toolkit_cli/skill_migrate.py`
- Test: `tests/test_cli/test_skill_migrate.py`

- [ ] **Step 1: Write the failing test**

```python
"""skill migrate-to-monorepo: re-home owned per-skill entries into a monorepo."""
import json
import subprocess
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main as cli
from agent_toolkit_cli.skill_lock import LockEntry, LockFile, write_lock
from agent_toolkit_cli.skill_migrate import is_migratable, monorepo_subpath_for
from agent_toolkit_cli.skill_paths import library_lock_path, library_skill_path
from tests.conftest import scrub_git_env


def test_monorepo_subpath_for_uses_bare_slug():
    assert monorepo_subpath_for("journal") == "skills/journal"


def test_is_migratable_true_for_own_repo_shape():
    e = LockEntry(source="ajanderson1/journal-skill", source_type="github",
                  skill_path="SKILL.md", upstream_sha="a", local_sha="a")
    assert is_migratable(e) is True


def test_is_migratable_true_for_renamed_source():
    # Track A may have renamed the repo; a bare source must still migrate.
    e = LockEntry(source="ajanderson1/journal", source_type="github",
                  skill_path="SKILL.md", upstream_sha="a", local_sha="a")
    assert is_migratable(e) is True


def test_is_migratable_false_when_already_monorepo():
    e = LockEntry(source="ajanderson1/agent-toolkit", source_type="github",
                  skill_path="skills/journal", upstream_sha="a",
                  parent_url="https://github.com/ajanderson1/agent-toolkit")
    assert is_migratable(e) is False


def test_is_migratable_false_for_third_party_readonly():
    e = LockEntry(source="anthropics/skills", source_type="github",
                  skill_path="skills/pdf", upstream_sha="a",
                  parent_url="https://github.com/anthropics/skills",
                  read_only=True)
    assert is_migratable(e) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd .worktrees/feat-258-migrate-to-monorepo && uv run pytest tests/test_cli/test_skill_migrate.py -k "subpath or migratable" -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_toolkit_cli.skill_migrate'`

- [ ] **Step 3: Write minimal implementation**

```python
"""Pure core for `skill migrate-to-monorepo`.

Decides which owned per-skill lock entries can be re-homed into a monorepo
and computes the rewritten entry. No I/O beyond values passed in.
"""
from __future__ import annotations

from agent_toolkit_cli.skill_lock import LockEntry


def monorepo_subpath_for(slug: str) -> str:
    """Subpath a slug occupies in the owned monorepo: bare `skills/<slug>`.

    The standalone repos carried a `-skill` suffix; the monorepo dropped it,
    so the subpath is the slug verbatim.
    """
    return f"skills/{slug}"


def is_migratable(entry: LockEntry) -> bool:
    """True for an own-repo per-skill entry not yet re-homed.

    Own-repo shape: a per-skill clone (has `local_sha`, no `parent_url`).
    Tolerant of pre- or post-Track-A rename of `source`. Already-migrated
    monorepo entries and read-only third-party entries are excluded by the
    `parent_url is None` test.
    """
    return entry.local_sha is not None and entry.parent_url is None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd .worktrees/feat-258-migrate-to-monorepo && uv run pytest tests/test_cli/test_skill_migrate.py -k "subpath or migratable" -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/skill_migrate.py tests/test_cli/test_skill_migrate.py
git commit -m "feat(migrate): pure core for subpath + migratability (#258)"
```

---

## Task 2: Pure core — refusal check

**Files:**
- Modify: `src/agent_toolkit_cli/skill_migrate.py`
- Test: `tests/test_cli/test_skill_migrate.py`

The refusal check answers: "is this skill's work fully reflected in the monorepo?" It takes already-computed facts (so it stays pure and trivially testable) and returns `None` (proceed) or a `RefusalReason`. The orchestrator (Task 4) computes the facts via git and the content-diff.

- [ ] **Step 1: Write the failing test**

```python
from agent_toolkit_cli.skill_migrate import RefusalReason, check_refusal


def test_check_refusal_none_when_all_clean():
    assert check_refusal(sha_match=True, tree_clean=True,
                          content_matches=True, in_monorepo=True) is None


def test_check_refusal_not_in_monorepo():
    assert check_refusal(sha_match=True, tree_clean=True,
                         content_matches=True,
                         in_monorepo=False) is RefusalReason.NOT_IN_MONOREPO


def test_check_refusal_sha_divergence():
    assert check_refusal(sha_match=False, tree_clean=True,
                         content_matches=True,
                         in_monorepo=True) is RefusalReason.SHA_DIVERGED


def test_check_refusal_dirty_tree():
    assert check_refusal(sha_match=True, tree_clean=False,
                         content_matches=True,
                         in_monorepo=True) is RefusalReason.DIRTY_TREE


def test_check_refusal_content_drift():
    assert check_refusal(sha_match=True, tree_clean=True,
                         content_matches=False,
                         in_monorepo=True) is RefusalReason.CONTENT_DRIFT


def test_refusal_reason_has_hint():
    # Every reason carries a human reconcile hint.
    for r in RefusalReason:
        assert r.hint  # non-empty string
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd .worktrees/feat-258-migrate-to-monorepo && uv run pytest tests/test_cli/test_skill_migrate.py -k "refusal" -v`
Expected: FAIL — `ImportError: cannot import name 'RefusalReason'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/agent_toolkit_cli/skill_migrate.py`:

```python
import enum


class RefusalReason(enum.Enum):
    """Why a skill was skipped during migration. `.hint` is shown to the user.

    Ordering matters: `check_refusal` returns the FIRST reason that applies,
    most-fundamental first (absent from monorepo → can't migrate at all).
    """
    NOT_IN_MONOREPO = "not yet in monorepo (fold it in first, then re-run)"
    SHA_DIVERGED = "local commits not in monorepo (reconcile, then re-run)"
    DIRTY_TREE = "uncommitted edits in clone (commit/push, then re-run)"
    CONTENT_DRIFT = (
        "monorepo copy differs from local (re-fold or push, then re-run)"
    )

    @property
    def hint(self) -> str:
        return self.value


def check_refusal(
    *, sha_match: bool, tree_clean: bool,
    content_matches: bool, in_monorepo: bool,
) -> RefusalReason | None:
    """Return the first refusal that applies, or None to proceed.

    Checks run most-fundamental first so the user sees the root blocker:
    a skill absent from the monorepo can't be evaluated for drift at all.
    """
    if not in_monorepo:
        return RefusalReason.NOT_IN_MONOREPO
    if not sha_match:
        return RefusalReason.SHA_DIVERGED
    if not tree_clean:
        return RefusalReason.DIRTY_TREE
    if not content_matches:
        return RefusalReason.CONTENT_DRIFT
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd .worktrees/feat-258-migrate-to-monorepo && uv run pytest tests/test_cli/test_skill_migrate.py -k "refusal" -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/skill_migrate.py tests/test_cli/test_skill_migrate.py
git commit -m "feat(migrate): refusal-reason core (#258)"
```

---

## Task 3: Pure core — rewritten entry

**Files:**
- Modify: `src/agent_toolkit_cli/skill_migrate.py`
- Test: `tests/test_cli/test_skill_migrate.py`

- [ ] **Step 1: Write the failing test**

```python
from agent_toolkit_cli.skill_migrate import migrated_entry


def test_migrated_entry_has_owned_monorepo_shape():
    old = LockEntry(source="ajanderson1/journal-skill", source_type="github",
                    skill_path="SKILL.md", upstream_sha="old", local_sha="old")
    new = migrated_entry(
        old, slug="journal",
        parent_source="ajanderson1/agent-toolkit",
        parent_url="https://github.com/ajanderson1/agent-toolkit",
        parent_sha="PARENTHEAD",
    )
    assert new.source == "ajanderson1/agent-toolkit"
    assert new.skill_path == "skills/journal"
    assert new.parent_url == "https://github.com/ajanderson1/agent-toolkit"
    assert new.upstream_sha == "PARENTHEAD"
    assert new.local_sha is None          # dropped — no longer a per-skill clone
    assert new.read_only is False         # owned → writable
    assert new.source_type == "github"    # preserved
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd .worktrees/feat-258-migrate-to-monorepo && uv run pytest tests/test_cli/test_skill_migrate.py -k "migrated_entry" -v`
Expected: FAIL — `ImportError: cannot import name 'migrated_entry'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/agent_toolkit_cli/skill_migrate.py`:

```python
def migrated_entry(
    old: LockEntry, *, slug: str, parent_source: str,
    parent_url: str, parent_sha: str | None,
) -> LockEntry:
    """Rewrite an own-repo entry to owned-monorepo-subpath shape.

    Mirrors what `_add_monorepo(..., owned=True)` writes: monorepo source,
    `skills/<slug>` subpath, parent_url set, upstream pinned to parent HEAD,
    `local_sha` dropped, `read_only=False` (owned). source_type preserved.
    """
    return LockEntry(
        source=parent_source,
        source_type=old.source_type,
        ref=old.ref,
        skill_path=monorepo_subpath_for(slug),
        upstream_sha=parent_sha,
        local_sha=None,
        parent_url=parent_url,
        read_only=False,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd .worktrees/feat-258-migrate-to-monorepo && uv run pytest tests/test_cli/test_skill_migrate.py -k "migrated_entry" -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/skill_migrate.py tests/test_cli/test_skill_migrate.py
git commit -m "feat(migrate): entry-rewrite core (#258)"
```

---

## Task 4: The command — happy path (one clean skill migrates)

**Files:**
- Create: `src/agent_toolkit_cli/commands/skill/migrate_cmd.py`
- Modify: `src/agent_toolkit_cli/commands/skill/__init__.py` (import + register)
- Test: `tests/test_cli/test_skill_migrate.py`

- [ ] **Step 1: Write the failing test**

Add the shared `_setup` helper and the happy-path test at the top of the test file's CLI section:

```python
def _git(args, cwd, env):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, env=env,
                   capture_output=True)


def _commit_all(cwd, env, msg="init"):
    _git(["add", "."], cwd, env)
    _git(["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q",
          "-m", msg], cwd, env)


def _setup(tmp_path, monkeypatch, slugs=("journal",)):
    """Build a monorepo parent + per-skill clones + own-repo lock entries.

    Returns (parent_url, parent_path, library_root, env).
    Each <slug> gets skills/<slug>/SKILL.md in the monorepo AND an identical
    standalone clone dir at <library>/skills/<slug> with its own git history,
    plus an own-repo-shape lock entry (localSha == upstreamSha, no parentUrl).
    """
    env = scrub_git_env()
    # --- monorepo parent ---
    parent = tmp_path / "parent"
    for slug in slugs:
        d = parent / "skills" / slug
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"# {slug}\n")
    _git(["init", "-q", "-b", "main"], parent, env)
    _commit_all(parent, env)
    parent_url = f"file://{parent}"
    # --- library root ---
    library = tmp_path / "library"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library / "skills"))
    # --- per-skill standalone clones + lock entries ---
    skills = {}
    for slug in slugs:
        clone = library_skill_path(slug)
        clone.mkdir(parents=True)
        (clone / "SKILL.md").write_text(f"# {slug}\n")  # identical content
        _git(["init", "-q", "-b", "main"], clone, env)
        _commit_all(clone, env)
        sha = subprocess.run(
            ["git", "-C", str(clone), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True, env=env,
        ).stdout.strip()
        skills[slug] = LockEntry(
            source=f"ajanderson1/{slug}-skill", source_type="github",
            skill_path="SKILL.md", upstream_sha=sha, local_sha=sha,
        )
    write_lock(library_lock_path(), LockFile(version=1, skills=skills))
    return parent_url, parent, library, env


def _lock():
    return json.loads(library_lock_path().read_text())


def test_migrate_happy_path_rewrites_entry_and_symlinks(tmp_path, monkeypatch):
    parent_url, _, _, _ = _setup(tmp_path, monkeypatch, slugs=("journal",))
    r = CliRunner().invoke(
        cli, ["skill", "migrate-to-monorepo", parent_url],
    )
    assert r.exit_code == 0, r.output
    entry = _lock()["skills"]["journal"]
    assert entry["source"] == parent_url or entry["source"].endswith(
        "agent-toolkit")
    assert entry["skillPath"] == "skills/journal"
    assert "parentUrl" in entry
    assert "readOnly" not in entry          # owned → writable
    assert "localSha" not in entry          # dropped
    # clone dir is now a symlink into the shared parent clone
    clone = library_skill_path("journal")
    assert clone.is_symlink()
    assert (clone / "SKILL.md").read_text() == "# journal\n"
    assert "Migrated 1" in r.output
```

> **Note on `source`:** the command stores the monorepo's owner/repo (`ajanderson1/agent-toolkit`) as `source` when the parent arg is an `owner/repo`; with a `file://` test URL it stores the URL. The assertion accepts either so the test is transport-agnostic.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd .worktrees/feat-258-migrate-to-monorepo && uv run pytest tests/test_cli/test_skill_migrate.py -k "happy_path" -v`
Expected: FAIL — `Error: No such command 'migrate-to-monorepo'`

- [ ] **Step 3: Write minimal implementation**

Create `src/agent_toolkit_cli/commands/skill/migrate_cmd.py`:

```python
"""skill migrate-to-monorepo subcommand.

Re-homes owned per-skill lock entries into an owned monorepo: rewrites the
entry to owned-monorepo-subpath shape, replaces the per-skill clone dir with
a symlink into the shared `_parents/` clone, and re-projects harness symlinks.
Refuses (skips) any skill whose local work is not reflected in the monorepo.
See docs/superpowers/specs/2026-05-27-migrate-to-monorepo-design.md.
"""
from __future__ import annotations

import filecmp
import shutil
from pathlib import Path

import click

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.skill_install import (
    InstallError,
    InstallPlan,
    apply as engine_apply,
)
from agent_toolkit_cli.skill_lock import read_lock, write_lock
from agent_toolkit_cli.skill_migrate import (
    check_refusal,
    is_migratable,
    migrated_entry,
    monorepo_subpath_for,
)
from agent_toolkit_cli.skill_paths import (
    library_lock_path,
    library_skill_path,
    parent_clone_path,
)
from agent_toolkit_cli.skill_source import parse_source


def _trees_equal(a: Path, b: Path) -> bool:
    """Recursive content comparison ignoring `.git` (independent histories)."""
    cmp = filecmp.dircmp(a, b, ignore=[".git"])
    if cmp.left_only or cmp.right_only or cmp.diff_files or cmp.funny_files:
        return False
    return all(
        _trees_equal(a / sub, b / sub) for sub in cmp.common_dirs
    )


@click.command("migrate-to-monorepo", epilog="""\
One-shot, idempotent, per-machine. Re-homes owned per-skill skills into the
monorepo. Skips any skill with local work not yet in the monorepo.

\b
  agent-toolkit-cli skill migrate-to-monorepo ajanderson1/agent-toolkit
  agent-toolkit-cli skill migrate-to-monorepo ajanderson1/agent-toolkit --dry-run
""")
@click.argument("parent")
@click.option("--dry-run", is_flag=True,
              help="Print the per-skill plan; write nothing.")
def migrate_cmd(parent: str, dry_run: bool) -> None:
    """Re-home owned per-skill skills into an owned monorepo."""
    parsed = parse_source(parent)
    if parsed.owner_repo is None:
        raise click.UsageError("parent must resolve to owner/repo")
    owner, repo = parsed.owner_repo.split("/", 1)
    parent_source = parsed.owner_repo
    parent_url = parsed.url

    parent_dir = parent_clone_path(owner, repo, ref=parsed.ref, env=None)
    if not parent_dir.exists():
        parent_dir.parent.mkdir(parents=True, exist_ok=True)
        try:
            skill_git.clone(parent_url, parent_dir, ref=parsed.ref, env=None)
        except Exception as exc:
            raise click.ClickException(f"parent clone failed: {exc}") from exc
    else:
        try:
            skill_git.fetch(parent_dir, env=None)
        except Exception as exc:
            click.echo(f"warning: parent fetch failed: {exc}", err=True)

    parent_sha = (
        skill_git.head_sha(parent_dir, env=None)
        if skill_git.is_git_repo(parent_dir) else None
    )

    lock_path = library_lock_path()
    lock = read_lock(lock_path)

    migrated: list[str] = []
    skipped: list[tuple[str, str]] = []

    for slug in sorted(lock.skills):
        entry = lock.skills[slug]
        if not is_migratable(entry):
            continue
        subpath = monorepo_subpath_for(slug)
        mono_skill = parent_dir / subpath
        in_monorepo = (mono_skill / "SKILL.md").exists()

        clone = library_skill_path(slug)
        sha_match = (
            skill_git.is_git_repo(clone)
            and entry.upstream_sha is not None
            and skill_git.head_sha(clone, env=None) == entry.upstream_sha
        )
        tree_clean = (
            not skill_git.is_git_repo(clone)
            or skill_git.status(clone, env=None)
            == skill_git.GitWorkingTreeStatus.CLEAN
        )
        content_matches = in_monorepo and _trees_equal(clone, mono_skill)

        reason = check_refusal(
            sha_match=sha_match, tree_clean=tree_clean,
            content_matches=content_matches, in_monorepo=in_monorepo,
        )
        if reason is not None:
            skipped.append((slug, reason.hint))
            continue

        if dry_run:
            migrated.append(slug)
            continue

        # Layer 3: rewrite lock, verify symlink, delete clone LAST.
        new_entry = migrated_entry(
            entry, slug=slug, parent_source=parent_source,
            parent_url=parent_url, parent_sha=parent_sha,
        )
        tmp_link = clone.parent / f".{slug}.migrating"
        if tmp_link.exists() or tmp_link.is_symlink():
            tmp_link.unlink()
        tmp_link.symlink_to(mono_skill, target_is_directory=True)
        if not (tmp_link / "SKILL.md").exists():
            tmp_link.unlink()
            skipped.append((slug, "symlink verification failed"))
            continue
        # clone is a real dir here; swap it for the verified symlink.
        shutil.rmtree(clone)
        tmp_link.rename(clone)

        lock = lock.__class__(
            version=lock.version,
            skills={**lock.skills, slug: new_entry},
            wrapper_extras=dict(lock.wrapper_extras),
        )
        write_lock(lock_path, lock)

        try:
            engine_apply(
                InstallPlan(slug=slug, scope="global", source=None, ref=None,
                            add_agents=(), remove_agents=()),
                home=None, project=None, env=None,
            )
        except InstallError as exc:
            click.echo(f"warning: reproject {slug} failed: {exc}", err=True)

        migrated.append(slug)

    _report(migrated, skipped, dry_run)


def _report(
    migrated: list[str], skipped: list[tuple[str, str]], dry_run: bool,
) -> None:
    prefix = "Would migrate" if dry_run else "Migrated"
    if migrated:
        click.echo(f"{prefix} {len(migrated)}: {', '.join(migrated)}")
    if skipped:
        click.echo(f"Skipped {len(skipped)}:")
        for slug, hint in skipped:
            click.echo(f"  {slug} — {hint}")
    if not migrated and not skipped:
        click.echo("Nothing to migrate (no owned per-skill entries).")
```

Then register it in `src/agent_toolkit_cli/commands/skill/__init__.py`. Add the import alongside the other subcommand imports (near line 34-39):

```python
from .migrate_cmd import migrate_cmd
```

And add the registration alongside the others (near line 808-814):

```python
skill.add_command(migrate_cmd)
```

> **Verify before coding:** confirm `apply` is exported from `skill_install` (the projection engine entrypoint `install_cmd` uses as `engine_apply`). Check the import line in `__init__.py` (`from agent_toolkit_cli.skill_install import (...)`). If the symbol is named differently (e.g. `apply_plan`), use that name in the `import ... as engine_apply` line. Confirm `InstallPlan`'s field names (`slug`, `scope`, `source`, `ref`, `add_agents`, `remove_agents`) match the dataclass in `skill_install.py` (shown in the plan's research).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd .worktrees/feat-258-migrate-to-monorepo && uv run pytest tests/test_cli/test_skill_migrate.py -k "happy_path" -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/skill/migrate_cmd.py src/agent_toolkit_cli/commands/skill/__init__.py tests/test_cli/test_skill_migrate.py
git commit -m "feat(migrate): migrate-to-monorepo command, happy path (#258)"
```

---

## Task 5: Refusal — SHA divergence is skipped, untouched

**Files:**
- Test: `tests/test_cli/test_skill_migrate.py`

- [ ] **Step 1: Write the failing test**

```python
def test_migrate_skips_sha_diverged(tmp_path, monkeypatch):
    parent_url, _, _, env = _setup(tmp_path, monkeypatch, slugs=("journal",))
    # Add a local commit to the clone so head != recorded upstream_sha.
    clone = library_skill_path("journal")
    (clone / "SKILL.md").write_text("# journal\nlocal edit\n")
    _commit_all(clone, env, msg="local improvement")
    r = CliRunner().invoke(cli, ["skill", "migrate-to-monorepo", parent_url])
    assert r.exit_code == 0, r.output
    entry = _lock()["skills"]["journal"]
    assert entry["source"] == "ajanderson1/journal-skill"  # untouched
    assert "parentUrl" not in entry
    assert not library_skill_path("journal").is_symlink()  # clone preserved
    assert "Skipped 1" in r.output
    assert "journal" in r.output
```

- [ ] **Step 2: Run test to verify it fails (or passes immediately)**

Run: `cd .worktrees/feat-258-migrate-to-monorepo && uv run pytest tests/test_cli/test_skill_migrate.py -k "sha_diverged" -v`
Expected: PASS immediately — Task 4's refusal logic already handles this. If it FAILS, the refusal wiring is wrong; fix `migrate_cmd.py` until green. (This task is a guard test; no new implementation expected.)

- [ ] **Step 3: (only if Step 2 failed) Fix the refusal wiring**

If the test fails, the most likely cause is `sha_match` computed wrong. Verify the clone's `head_sha` is compared against `entry.upstream_sha`, not `local_sha`, and that a fresh local commit makes them differ.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd .worktrees/feat-258-migrate-to-monorepo && uv run pytest tests/test_cli/test_skill_migrate.py -k "sha_diverged" -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add tests/test_cli/test_skill_migrate.py
git commit -m "test(migrate): SHA-divergence refusal leaves entry untouched (#258)"
```

---

## Task 6: Refusal — dirty working tree is skipped

**Files:**
- Test: `tests/test_cli/test_skill_migrate.py`

- [ ] **Step 1: Write the failing test**

```python
def test_migrate_skips_dirty_tree(tmp_path, monkeypatch):
    parent_url, _, _, _ = _setup(tmp_path, monkeypatch, slugs=("journal",))
    # Uncommitted edit on disk: head == upstream_sha, but tree is dirty.
    (library_skill_path("journal") / "SKILL.md").write_text("# journal\nWIP\n")
    r = CliRunner().invoke(cli, ["skill", "migrate-to-monorepo", parent_url])
    assert r.exit_code == 0, r.output
    assert "parentUrl" not in _lock()["skills"]["journal"]
    assert not library_skill_path("journal").is_symlink()
    assert "Skipped 1" in r.output
```

- [ ] **Step 2: Run test to verify it fails (or passes immediately)**

Run: `cd .worktrees/feat-258-migrate-to-monorepo && uv run pytest tests/test_cli/test_skill_migrate.py -k "dirty_tree" -v`
Expected: PASS immediately (Task 4 already wired `tree_clean`). If FAIL, fix `migrate_cmd.py`.

- [ ] **Step 3: (only if Step 2 failed) Fix**

Ensure `tree_clean` uses `skill_git.status(clone) == GitWorkingTreeStatus.CLEAN`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd .worktrees/feat-258-migrate-to-monorepo && uv run pytest tests/test_cli/test_skill_migrate.py -k "dirty_tree" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_cli/test_skill_migrate.py
git commit -m "test(migrate): dirty-tree refusal (#258)"
```

---

## Task 7: Refusal — content drift (Layer 2, load-bearing)

**Files:**
- Test: `tests/test_cli/test_skill_migrate.py`

This is the test that proves migrate verifies reality, not metadata: SHAs match and the tree is clean, but the monorepo's copy of the skill differs from the local clone. Must skip.

- [ ] **Step 1: Write the failing test**

```python
def test_migrate_skips_content_drift(tmp_path, monkeypatch):
    parent_url, parent, _, env = _setup(tmp_path, monkeypatch,
                                        slugs=("journal",))
    # Diverge the MONOREPO copy so it differs from the (clean, in-sync) clone.
    (parent / "skills" / "journal" / "SKILL.md").write_text("# journal\nDRIFT\n")
    _commit_all(parent, env, msg="monorepo drift")
    r = CliRunner().invoke(cli, ["skill", "migrate-to-monorepo", parent_url])
    assert r.exit_code == 0, r.output
    assert "parentUrl" not in _lock()["skills"]["journal"]   # untouched
    assert not library_skill_path("journal").is_symlink()    # clone preserved
    assert "Skipped 1" in r.output
```

- [ ] **Step 2: Run test to verify it fails (or passes immediately)**

Run: `cd .worktrees/feat-258-migrate-to-monorepo && uv run pytest tests/test_cli/test_skill_migrate.py -k "content_drift" -v`
Expected: PASS if `_trees_equal` + `content_matches` are correctly wired in Task 4. If FAIL — `content_matches` likely always True; fix `_trees_equal` to actually diff file contents.

- [ ] **Step 3: (only if Step 2 failed) Fix `_trees_equal`**

`filecmp.dircmp` by default compares by os.stat signature, which can miss same-size edits. If the test is flaky, force shallow=False content comparison:

```python
def _trees_equal(a: Path, b: Path) -> bool:
    cmp = filecmp.dircmp(a, b, ignore=[".git"])
    if cmp.left_only or cmp.right_only or cmp.funny_files:
        return False
    match, mismatch, errors = filecmp.cmpfiles(
        a, b, cmp.common_files, shallow=False)
    if mismatch or errors:
        return False
    return all(_trees_equal(a / sub, b / sub) for sub in cmp.common_dirs)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd .worktrees/feat-258-migrate-to-monorepo && uv run pytest tests/test_cli/test_skill_migrate.py -k "content_drift" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_cli/test_skill_migrate.py src/agent_toolkit_cli/commands/skill/migrate_cmd.py
git commit -m "test(migrate): content-drift refusal (Layer 2) (#258)"
```

---

## Task 8: Skip — owned skill not in monorepo; regression — third-party untouched

**Files:**
- Test: `tests/test_cli/test_skill_migrate.py`

- [ ] **Step 1: Write the failing test**

```python
def test_migrate_skips_owned_not_in_monorepo(tmp_path, monkeypatch):
    # Monorepo has only journal; repo_recon owned entry exists but isn't folded.
    parent_url, parent, _, env = _setup(tmp_path, monkeypatch,
                                        slugs=("journal",))
    # Add an owned per-skill entry whose skill is absent from the monorepo.
    clone = library_skill_path("repo-recon")
    clone.mkdir(parents=True)
    (clone / "SKILL.md").write_text("# repo-recon\n")
    _git(["init", "-q", "-b", "main"], clone, env)
    _commit_all(clone, env)
    sha = subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"],
                         check=True, capture_output=True, text=True,
                         env=env).stdout.strip()
    from agent_toolkit_cli.skill_lock import LockEntry as LE
    lock = read_lock_local()
    lock["skills"]["repo-recon"] = {
        "source": "ajanderson1/repo-recon-skill", "sourceType": "github",
        "skillPath": "SKILL.md", "upstreamSha": sha, "localSha": sha,
    }
    library_lock_path().write_text(json.dumps({"version": 1,
                                               "skills": lock["skills"]},
                                              indent=2) + "\n")
    r = CliRunner().invoke(cli, ["skill", "migrate-to-monorepo", parent_url])
    assert r.exit_code == 0, r.output
    # journal migrates, repo-recon is skipped (not in monorepo)
    assert "parentUrl" in _lock()["skills"]["journal"]
    assert "parentUrl" not in _lock()["skills"]["repo-recon"]
    assert not library_skill_path("repo-recon").is_symlink()
    assert "Migrated 1" in r.output
    assert "Skipped 1" in r.output


def test_migrate_never_touches_third_party_readonly(tmp_path, monkeypatch):
    parent_url, _, _, _ = _setup(tmp_path, monkeypatch, slugs=("journal",))
    # Inject a read-only third-party monorepo entry.
    cur = _lock()
    cur["skills"]["pdf"] = {
        "source": "anthropics/skills", "sourceType": "github",
        "skillPath": "skills/pdf", "upstreamSha": "x",
        "parentUrl": "https://github.com/anthropics/skills", "readOnly": True,
    }
    library_lock_path().write_text(json.dumps(cur, indent=2) + "\n")
    r = CliRunner().invoke(cli, ["skill", "migrate-to-monorepo", parent_url])
    assert r.exit_code == 0, r.output
    pdf = _lock()["skills"]["pdf"]
    assert pdf["source"] == "anthropics/skills"   # untouched
    assert pdf["readOnly"] is True
```

Add this small helper near `_lock` (used by the first test):

```python
def read_lock_local():
    return json.loads(library_lock_path().read_text())
```

- [ ] **Step 2: Run test to verify it fails (or passes)**

Run: `cd .worktrees/feat-258-migrate-to-monorepo && uv run pytest tests/test_cli/test_skill_migrate.py -k "not_in_monorepo or third_party" -v`
Expected: PASS if eligibility (`is_migratable` excludes `parent_url`-bearing entries) + NOT_IN_MONOREPO refusal are correct. Fix `migrate_cmd.py`/`skill_migrate.py` if not.

- [ ] **Step 3: (only if Step 2 failed) Fix**

Ensure the third-party entry is excluded by `is_migratable` (has `parent_url`), and the not-in-monorepo owned entry hits `RefusalReason.NOT_IN_MONOREPO`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd .worktrees/feat-258-migrate-to-monorepo && uv run pytest tests/test_cli/test_skill_migrate.py -k "not_in_monorepo or third_party" -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add tests/test_cli/test_skill_migrate.py
git commit -m "test(migrate): skip absent-from-monorepo + third-party guard (#258)"
```

---

## Task 9: Idempotency + `--dry-run`

**Files:**
- Test: `tests/test_cli/test_skill_migrate.py`

- [ ] **Step 1: Write the failing test**

```python
def test_migrate_is_idempotent(tmp_path, monkeypatch):
    parent_url, _, _, _ = _setup(tmp_path, monkeypatch, slugs=("journal",))
    r1 = CliRunner().invoke(cli, ["skill", "migrate-to-monorepo", parent_url])
    assert r1.exit_code == 0, r1.output
    assert "Migrated 1" in r1.output
    # Second run: journal now has parentUrl → ineligible → no-op.
    r2 = CliRunner().invoke(cli, ["skill", "migrate-to-monorepo", parent_url])
    assert r2.exit_code == 0, r2.output
    assert "Migrated 1" not in r2.output
    assert library_skill_path("journal").is_symlink()  # still a symlink
    assert "parentUrl" in _lock()["skills"]["journal"]


def test_migrate_dry_run_writes_nothing(tmp_path, monkeypatch):
    parent_url, _, _, _ = _setup(tmp_path, monkeypatch, slugs=("journal",))
    r = CliRunner().invoke(
        cli, ["skill", "migrate-to-monorepo", parent_url, "--dry-run"])
    assert r.exit_code == 0, r.output
    assert "Would migrate 1" in r.output
    entry = _lock()["skills"]["journal"]
    assert "parentUrl" not in entry                       # nothing written
    assert not library_skill_path("journal").is_symlink()  # clone intact
```

- [ ] **Step 2: Run test to verify it fails (or passes)**

Run: `cd .worktrees/feat-258-migrate-to-monorepo && uv run pytest tests/test_cli/test_skill_migrate.py -k "idempotent or dry_run" -v`
Expected: PASS if Task 4's `--dry-run` short-circuit and idempotency (via `is_migratable`) are correct.

- [ ] **Step 3: (only if Step 2 failed) Fix**

For idempotency: confirm a migrated entry (has `parent_url`) returns False from `is_migratable`. For dry-run: confirm the `if dry_run: migrated.append(slug); continue` branch runs before any mutation.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd .worktrees/feat-258-migrate-to-monorepo && uv run pytest tests/test_cli/test_skill_migrate.py -k "idempotent or dry_run" -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add tests/test_cli/test_skill_migrate.py
git commit -m "test(migrate): idempotency + dry-run (#258)"
```

---

## Task 10: Full suite, lint, types, docs

**Files:**
- Modify: `docs/agent-toolkit/skill-lock.md` (if it enumerates entry shapes)

- [ ] **Step 1: Run the full test suite**

Run: `cd .worktrees/feat-258-migrate-to-monorepo && uv run pytest -q`
Expected: all green (486 prior + the new migrate tests, 0 failures).

- [ ] **Step 2: Lint + type-check**

Run: `cd .worktrees/feat-258-migrate-to-monorepo && uv run ruff check src tests && uv run mypy --strict src/agent_toolkit_cli/skill_migrate.py src/agent_toolkit_cli/commands/skill/migrate_cmd.py`
Expected: no errors. Fix any reported issue inline (e.g. add return-type annotations).

- [ ] **Step 3: Update skill-lock doc**

Read `docs/agent-toolkit/skill-lock.md`. If it documents lock-entry shapes, add a short note that `skill migrate-to-monorepo` transforms an own-repo per-skill entry (`source: ajanderson1/<slug>-skill`, `skillPath: SKILL.md`, has `localSha`) into an owned-monorepo-subpath entry (`source: ajanderson1/agent-toolkit`, `skillPath: skills/<slug>`, `parentUrl` set, no `readOnly`, `localSha` dropped). If the doc has no entry-shape section, skip this step.

- [ ] **Step 4: Update the CLI help reference doc if one exists**

Run: `cd .worktrees/feat-258-migrate-to-monorepo && grep -rl "skill push\|skill update" docs/ | head`
If a generated/maintained command reference lists subcommands, add `migrate-to-monorepo` there mirroring the existing entries' style. Otherwise skip.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "docs(migrate): document migrate-to-monorepo entry transform (#258)"
```

---

## Task 11: Push + open PR

- [ ] **Step 1: Push the branch**

```bash
cd .worktrees/feat-258-migrate-to-monorepo
git push -u origin feat/258-migrate-to-monorepo
```

- [ ] **Step 2: Open the PR**

```bash
gh pr create --title "feat: skill migrate-to-monorepo (#258 PR2)" \
  --body "$(cat <<'EOF'
## Summary
Adds `skill migrate-to-monorepo ajanderson1/agent-toolkit [--dry-run]` — PR2 of #258.
Re-homes owned per-skill lock entries into the monorepo: rewrites each entry to
owned-monorepo-subpath shape, replaces the clone dir with a symlink into the
shared `_parents/` clone, re-projects harness symlinks. Idempotent, per-machine.

## Safety (never drops local work)
- Refuses (skips) any skill with `localSha != upstreamSha` or a dirty tree.
- Layer 2: cross-history **content-diff** against the monorepo subpath — skips on drift.
- Layer 3: destructive clone-dir delete happens **last**, only after the symlink verifies.

## Scope
- Ships the migrate command + tests only. The 9 currently-foldable skills migrate;
  the 8 not yet in the monorepo are reported as skipped.
- Standalone-repo renames (drop `-skill`) and orphan-source fixes are a separate
  one-time operational fix, not in this PR.

## Test plan
Spec: docs/superpowers/specs/2026-05-27-migrate-to-monorepo-design.md
Automated: happy path, SHA/dirty/content-drift/not-in-monorepo refusals, third-party
guard, idempotency, dry-run. Manual end-to-end testing by AJ after merge-ready.

Closes the migrate-command acceptance criteria of #258.
EOF
)"
```

- [ ] **Step 3: Report PR URL to the user**

Print the PR URL and hand off for AJ's thorough manual testing.

---

## Self-Review

**Spec coverage:** command signature + global-only + required parent ✓ (Task 4); eligibility ✓ (Task 1); refusal Layer 1 SHA+clean ✓ (Tasks 5,6); Layer 2 content-diff ✓ (Task 7); Layer 3 delete-last ordering ✓ (Task 4 impl); entry rewrite shape ✓ (Task 3); symlink materialization ✓ (Task 4); reprojection ✓ (Task 4); idempotency ✓ (Task 9); dry-run ✓ (Task 9); reporting ✓ (Task 4 `_report`); not-in-monorepo skip ✓ (Task 8); third-party regression guard ✓ (Task 8). All spec Testing-section cases mapped.

**Placeholder scan:** no TBD/TODO; every code step shows complete code. Two "verify before coding" notes (Task 4) name exact symbols to confirm (`apply` export name, `InstallPlan` fields) — these are real interface checks, not placeholders, because the engine entrypoint name must be confirmed against `skill_install.py` at implementation time.

**Type consistency:** `monorepo_subpath_for`, `is_migratable`, `check_refusal`, `RefusalReason`, `migrated_entry` signatures are identical across Tasks 1-4 and their call site in `migrate_cmd.py`. `LockEntry` fields match `skill_lock.py`. `GitWorkingTreeStatus.CLEAN`, `skill_git.head_sha/status/is_git_repo/clone/fetch` match the helpers in `skill_git.py`.

**Known risk to confirm during execution:** the projection engine entrypoint is imported in `install_cmd` — Task 4 imports it as `apply as engine_apply`. If `skill_install` exports it under a different name, adjust the import (flagged inline). `filecmp.dircmp` shallow-compare caveat is pre-empted by the Task 7 fallback using `cmpfiles(shallow=False)`.
