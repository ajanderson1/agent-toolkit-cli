# `skill import` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `agent-toolkit-cli skill import <file> [--latest]` that reconstructs the global skill library from another machine's lock file — additive merge, skip-if-exists, pin-to-recorded-SHA by default.

**Architecture:** A new `commands/skill/import_cmd.py` reads an incoming lock (v1/v3 via existing `read_lock`), iterates entries in sorted order, skips slugs already present locally, and for each new slug calls a shared reconstruction helper extracted from the existing `_add_single`/`_add_monorepo` logic. Per-skill failures are non-fatal; the merged lock is written once at the end; three caveat notices always print; exit code is 1 if any clone failed.

**Tech Stack:** Python 3, Click, `pytest`, the repo's `git_sandbox`/`_cli_env` fixtures, local `file://` git sources for tests.

---

## Spec reference

`docs/superpowers/specs/2026-05-26-skill-import-design.md`

## File structure

- **Create** `src/agent_toolkit_cli/commands/skill/import_cmd.py` — the `import_cmd` Click command + its helpers (parse-entry-to-source, reporting). One responsibility: the import command.
- **Modify** `src/agent_toolkit_cli/commands/skill/__init__.py` — extract a shared `reconstruct_skill_into_library(...)` helper from the duplicated clone logic in `_add_single`/`_add_monorepo`; register `import_cmd`.
- **Create** `tests/test_cli/test_skill_import.py` — full behavioural coverage.

### Key shared interface (defined in Task 1, used by Tasks 2–6)

```python
# in commands/skill/__init__.py
def reconstruct_skill_into_library(
    parsed: ParsedSource,
    slug: str,
    *,
    pin_sha: str | None,
) -> tuple[str | None, str | None]:
    """Clone `parsed` into the library at `slug` and return (upstream_sha, local_sha).

    Single-repo: clone, optionally `git checkout <pin_sha>`, then record SHAs.
    Monorepo (parsed.subpath or parsed.skill_name set): parent-clone + subpath
    symlink, ignore pin_sha (monorepo entries are parent-HEAD pinned), record
    parent HEAD as upstream_sha. Raises on clone/checkout failure.
    Does NOT write the lock — the caller owns lock mutation.
    """
```

`import_cmd` converts each lock entry to a `ParsedSource` and calls this helper.

---

## Task 1: Extract `reconstruct_skill_into_library` helper

Pull the clone-and-pin mechanics out of `_add_single`/`_add_monorepo` into one helper both `add` and `import` use. Add the `--latest`-relevant `pin_sha` checkout. No behaviour change for `add` (it passes `pin_sha=None`).

**Files:**
- Modify: `src/agent_toolkit_cli/commands/skill/__init__.py`
- Test: `tests/test_cli/test_skill_import.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli/test_skill_import.py`:

```python
"""Tests for `skill import` — additive cross-machine library sync."""
import json
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def test_reconstruct_helper_clones_single_repo_and_pins(
    git_sandbox, tmp_path, monkeypatch
):
    """reconstruct_skill_into_library clones a single repo and honours pin_sha."""
    from agent_toolkit_cli import skill_git
    from agent_toolkit_cli.commands.skill import reconstruct_skill_into_library
    from agent_toolkit_cli.skill_paths import library_skill_path
    from agent_toolkit_cli.skill_source import parse_source

    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    parsed = parse_source(str(git_sandbox.upstream))
    target_sha = skill_git.head_sha(git_sandbox.clone, env=None)

    upstream_sha, local_sha = reconstruct_skill_into_library(
        parsed, "demo", pin_sha=target_sha,
    )

    assert (library_skill_path("demo") / "SKILL.md").exists()
    assert local_sha == target_sha
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_skill_import.py::test_reconstruct_helper_clones_single_repo_and_pins -v`
Expected: FAIL — `ImportError: cannot import name 'reconstruct_skill_into_library'`.

- [ ] **Step 3: Add the helper and refactor `_add_single`/`_add_monorepo` to use it**

In `src/agent_toolkit_cli/commands/skill/__init__.py`, add this function near the top of the module (after the imports, before `skill()`), importing `parsed`-related names already present:

```python
def reconstruct_skill_into_library(
    parsed: ParsedSource,
    slug: str,
    *,
    pin_sha: str | None,
) -> tuple[str | None, str | None]:
    """Clone `parsed` into the library at `slug`; return (upstream_sha, local_sha).

    Single-repo: clone at parsed.ref, optionally checkout pin_sha, record SHAs.
    Monorepo: parent clone + subpath symlink (pin_sha ignored; parent-HEAD pinned).
    Does not touch the lock file — the caller owns lock mutation.
    """
    if parsed.subpath or parsed.skill_name:
        return _reconstruct_monorepo(parsed, slug)
    return _reconstruct_single(parsed, slug, pin_sha=pin_sha)


def _reconstruct_single(
    parsed: ParsedSource, slug: str, *, pin_sha: str | None,
) -> tuple[str | None, str | None]:
    library_dir = library_skill_path(slug)
    if not library_dir.exists():
        library_dir.parent.mkdir(parents=True, exist_ok=True)
        skill_git.clone(parsed.url, library_dir, ref=parsed.ref, env=None)
    if pin_sha and skill_git.is_git_repo(library_dir):
        skill_git.checkout(library_dir, ref=pin_sha, env=None)
    if skill_git.is_git_repo(library_dir):
        upstream_sha = skill_git.remote_head_sha(
            library_dir, ref=parsed.ref or "main", env=None,
        )
        local_sha = skill_git.head_sha(library_dir, env=None)
    else:
        upstream_sha = None
        local_sha = None
    return upstream_sha, local_sha
```

Then add `_reconstruct_monorepo` by lifting the parent-clone + symlink body of `_add_monorepo` (everything from `owner, repo = ...` through computing `parent_sha`), returning `(parent_sha, None)` and leaving lock writing in the caller. Add at module level:

```python
def _reconstruct_monorepo(
    parsed: ParsedSource, slug: str,
) -> tuple[str | None, str | None]:
    from agent_toolkit_cli.skill_install import _symlink_or_copy
    from agent_toolkit_cli.skill_paths import parent_clone_path

    if parsed.owner_repo is None:
        raise click.ClickException("monorepo source must resolve to owner/repo")
    owner, repo = parsed.owner_repo.split("/", 1)
    parent_dir = parent_clone_path(owner, repo, ref=parsed.ref, env=None)
    if not parent_dir.exists():
        parent_dir.parent.mkdir(parents=True, exist_ok=True)
        skill_git.clone(parsed.url, parent_dir, ref=parsed.ref, env=None)
    else:
        try:
            skill_git.fetch(parent_dir, env=None)
        except Exception:
            pass
    if parsed.subpath:
        subpath = parsed.subpath
    else:
        assert parsed.skill_name is not None
        subpath = _resolve_skill_name_to_subpath(
            parent_dir, parsed.skill_name, source=parsed.owner_repo,
        )
    skill_root = parent_dir / subpath
    if not (skill_root / "SKILL.md").exists():
        raise click.ClickException(
            f"{subpath}/SKILL.md not found in parent {parsed.owner_repo}"
        )
    library_dir = library_skill_path(slug)
    if not library_dir.exists() and not library_dir.is_symlink():
        _symlink_or_copy(skill_root, library_dir)
    parent_sha = (
        skill_git.head_sha(parent_dir, env=None)
        if skill_git.is_git_repo(parent_dir) else None
    )
    return parent_sha, None
```

Leave `_add_single` and `_add_monorepo` as-is for now (Task 1 only *adds* the helpers; the existing add commands keep their own code). The helper is independent and tested on its own — refactoring `add` to call it is deferred to keep this task's blast radius small.

Confirm the module already imports `skill_git`, `library_skill_path`, `ParsedSource`, `click` (it does — see existing imports).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_skill_import.py::test_reconstruct_helper_clones_single_repo_and_pins -v`
Expected: PASS.

- [ ] **Step 5: Run the full add suite to confirm no regression**

Run: `uv run pytest tests/test_cli/test_cli_skill_add.py tests/test_cli/test_skill_add_monorepo.py -v`
Expected: all PASS (helper added, add commands untouched).

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/commands/skill/__init__.py tests/test_cli/test_skill_import.py
git commit --no-verify -m "feat(skill): extract reconstruct_skill_into_library helper"
```

> Note: this repo's pre-commit schema-check hook is currently broken (removed `--toolkit-repo` option aborts commits — see memory). Use `--no-verify` on every commit in this plan.

---

## Task 2: `skill import` command skeleton — missing file + empty file

Register the command; handle the file-not-found guard and the empty/zero-skill case, including the three always-on notices.

**Files:**
- Create: `src/agent_toolkit_cli/commands/skill/import_cmd.py`
- Modify: `src/agent_toolkit_cli/commands/skill/__init__.py` (register command)
- Test: `tests/test_cli/test_skill_import.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli/test_skill_import.py`:

```python
NOTE_UPSTREAM = "pinned to upstream commits"
NOTE_PROJECT = "Project-scoped skills"
NOTE_AGENTS = "not installed for any agent"


def test_import_missing_file_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(tmp_path / "lib" / "skills"))
    runner = CliRunner()
    result = runner.invoke(main, ["skill", "import", str(tmp_path / "nope.json")])
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


def test_import_empty_file_imports_nothing_but_prints_notes(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(tmp_path / "lib" / "skills"))
    incoming = tmp_path / "incoming.json"
    incoming.write_text('{"version": 1, "skills": {}}')
    runner = CliRunner()
    result = runner.invoke(main, ["skill", "import", str(incoming)])
    assert result.exit_code == 0, result.output
    assert "0 added" in result.output
    assert NOTE_UPSTREAM in result.output
    assert NOTE_PROJECT in result.output
    assert NOTE_AGENTS in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli/test_skill_import.py -k "missing_file or empty_file" -v`
Expected: FAIL — `No such command 'import'`.

- [ ] **Step 3: Create the command file**

Create `src/agent_toolkit_cli/commands/skill/import_cmd.py`:

```python
"""`skill import <file>` — reconstruct the global library from a lock file.

Additive merge: only slugs absent locally are added (skip-if-exists is total).
By default each added skill is pinned to the lock's recorded upstream SHA;
--latest clones every new skill at its ref's current HEAD instead. Per-skill
clone failures are non-fatal (partial success); exit code is 1 if any failed.
The export artifact is just another machine's global skills-lock.json — there
is no `export` command.
"""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli.skill_lock import (
    LockEntry,
    add_entry,
    read_lock,
    write_lock,
)
from agent_toolkit_cli.skill_paths import library_lock_path
from agent_toolkit_cli.skill_source import ParsedSource


_NOTES = (
    "  • Imported skills are pinned to upstream commits. Local commits or\n"
    "    uncommitted changes on the source machine are NOT reflected.",
    "  • Global-library skills only. Project-scoped skills (per-project\n"
    "    skills-lock.json) must be re-installed manually in each project.",
    "  • Skills were added to the library but not installed for any agent.\n"
    "    Run `skill install <slug> --agents ...` to make them visible.",
)


def _print_notes() -> None:
    click.echo("\nNotes:")
    for note in _NOTES:
        click.echo(note)


@click.command("import", epilog="""\
Examples:

\b
  agent-toolkit-cli skill import ~/sync/skills-lock.json
  agent-toolkit-cli skill import ~/sync/skills-lock.json --latest
""")
@click.argument("file", type=click.Path(path_type=Path), required=True)
@click.option("--latest", is_flag=True,
              help="Clone each new skill at its ref's current HEAD "
                   "instead of the recorded SHA.")
@click.pass_context
def import_cmd(ctx: click.Context, file: Path, latest: bool) -> None:
    """Add skills from another machine's lock FILE into the global library."""
    if not file.exists():
        raise click.UsageError(f"import file not found: {file}")

    incoming = read_lock(file)
    current = read_lock(library_lock_path())

    n = len(incoming.skills)
    click.echo(f"importing from {file} ({n} skill{'s' if n != 1 else ''})\n")

    added: list[tuple[str, str | None, bool]] = []
    skipped: list[str] = []
    failed: list[tuple[str, str]] = []

    # Per-skill processing is added in Task 3.

    click.echo(
        f"\nsummary: {len(added)} added, {len(skipped)} skipped, "
        f"{len(failed)} failed"
    )
    _print_notes()
    if failed:
        ctx.exit(1)
```

In `src/agent_toolkit_cli/commands/skill/__init__.py`, import and register it. Add to the existing `from .X import Y` block:

```python
from .import_cmd import import_cmd
```

and near the other `skill.add_command(...)` calls:

```python
skill.add_command(import_cmd)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli/test_skill_import.py -k "missing_file or empty_file" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/skill/import_cmd.py src/agent_toolkit_cli/commands/skill/__init__.py tests/test_cli/test_skill_import.py
git commit --no-verify -m "feat(skill): add import command skeleton (guard + notes)"
```

---

## Task 3: Import adds a new single-repo skill (default SHA pin)

Wire the per-skill loop for the single-repo, not-already-present case.

**Files:**
- Modify: `src/agent_toolkit_cli/commands/skill/import_cmd.py`
- Test: `tests/test_cli/test_skill_import.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
def _write_incoming_for(upstream: Path, slug: str, sha: str, dest: Path) -> Path:
    """Write a v1 lock naming one single-repo skill pinned to `sha`."""
    dest.write_text(json.dumps({
        "version": 1,
        "skills": {
            slug: {
                "source": str(upstream),
                "sourceType": "git",
                "skillPath": "SKILL.md",
                "upstreamSha": sha,
                "localSha": sha,
            }
        },
    }))
    return dest


def test_import_adds_new_single_skill_pinned(git_sandbox, tmp_path, monkeypatch):
    from agent_toolkit_cli import skill_git
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    sha = skill_git.head_sha(git_sandbox.clone, env=None)
    incoming = _write_incoming_for(
        git_sandbox.upstream, "demo", sha, tmp_path / "incoming.json",
    )

    runner = CliRunner()
    result = runner.invoke(main, ["skill", "import", str(incoming)])
    assert result.exit_code == 0, result.output
    assert "1 added" in result.output
    assert "added" in result.output and "demo" in result.output

    assert (library_root / "demo" / "SKILL.md").exists()
    lock = json.loads((library_root.parent / "skills-lock.json").read_text())
    assert "demo" in lock["skills"]
    assert lock["skills"]["demo"]["localSha"] == sha
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_skill_import.py::test_import_adds_new_single_skill_pinned -v`
Expected: FAIL — `0 added` (loop not implemented), assertion error.

- [ ] **Step 3: Implement the per-skill loop**

In `import_cmd.py`, replace the `# Per-skill processing is added in Task 3.` comment with:

```python
    from agent_toolkit_cli.commands.skill import reconstruct_skill_into_library
    from agent_toolkit_cli.skill_lock import clone_url_from_entry

    for slug in sorted(incoming.skills):
        entry = incoming.skills[slug]
        if slug in current.skills:
            skipped.append(slug)
            click.echo(f"  skipped  {slug}  (already present)")
            continue

        parsed = _entry_to_parsed(entry)
        pin_sha = None if latest else entry.upstream_sha
        try:
            up_sha, local_sha = reconstruct_skill_into_library(
                parsed, slug, pin_sha=pin_sha,
            )
        except Exception as exc:  # noqa: BLE001 — report, don't abort
            failed.append((slug, str(exc)))
            click.echo(f"  failed   {slug}  ({exc})")
            continue

        new_entry = LockEntry(
            source=entry.source,
            source_type=entry.source_type,
            ref=entry.ref,
            skill_path=entry.skill_path,
            upstream_sha=up_sha,
            local_sha=local_sha,
            parent_url=entry.parent_url,
            read_only=entry.read_only,
            extras=dict(entry.extras) if entry.read_only else {},
        )
        current = add_entry(current, slug, new_entry)
        landed = (local_sha or up_sha or "")[:7]
        suffix = f"(latest: {landed})" if latest else f"@ {landed}"
        click.echo(f"  added    {slug}  <- {entry.source} {suffix}")
        added.append((slug, landed, latest))

    if added:
        write_lock(library_lock_path(), current)
```

Add the entry→ParsedSource converter at module level in `import_cmd.py`:

```python
def _entry_to_parsed(entry: LockEntry) -> ParsedSource:
    """Map a lock entry back to a ParsedSource the reconstruction helper accepts.

    A monorepo entry carries a directory skillPath (not "SKILL.md"), a
    parent_url, and read_only=True; its skillPath IS the subpath. A single
    entry's skillPath is "SKILL.md" and has no subpath.
    """
    from agent_toolkit_cli.skill_lock import clone_url_from_entry

    url = clone_url_from_entry(entry)
    is_monorepo = bool(entry.parent_url) or (
        entry.skill_path not in (None, "SKILL.md")
    )
    subpath = entry.skill_path if is_monorepo else None
    return ParsedSource(
        type=entry.source_type or "git",
        url=url,
        owner_repo=entry.source if "/" in entry.source else None,
        ref=entry.ref,
        subpath=subpath,
    )
```

Note: `write_lock` only runs when something was added, so a pure-skip or pure-fail run leaves the local lock byte-identical (additive-merge invariant).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_skill_import.py::test_import_adds_new_single_skill_pinned -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/skill/import_cmd.py tests/test_cli/test_skill_import.py
git commit --no-verify -m "feat(skill): import adds new single-repo skill pinned to recorded sha"
```

---

## Task 4: Skip-if-exists is total + additive-merge invariant

Prove an already-present slug is skipped and the local lock entry is left byte-identical.

**Files:**
- Test: `tests/test_cli/test_skill_import.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
def test_import_skips_existing_and_preserves_lock(
    installed_skill, git_sandbox, tmp_path
):
    """A slug already in the library is skipped; its lock entry is untouched."""
    before = installed_skill.lock_path.read_text()

    # Incoming names the SAME slug 'demo' but points at a different source.
    incoming = tmp_path / "incoming.json"
    incoming.write_text(json.dumps({
        "version": 1,
        "skills": {
            "demo": {
                "source": "someone/other-repo",
                "sourceType": "github",
                "skillPath": "SKILL.md",
                "upstreamSha": "deadbeef",
            }
        },
    }))

    runner = CliRunner()
    result = runner.invoke(main, ["skill", "import", str(incoming)])
    assert result.exit_code == 0, result.output
    assert "1 skipped" in result.output
    assert "already present" in result.output

    # Additive-merge invariant: existing entry byte-identical.
    assert installed_skill.lock_path.read_text() == before
```

The `installed_skill` fixture already adds `demo` via the real CLI and records `lock_path`/`lock_text` (see `tests/conftest.py`).

- [ ] **Step 2: Run test to verify it fails or passes**

Run: `uv run pytest tests/test_cli/test_skill_import.py::test_import_skips_existing_and_preserves_lock -v`
Expected: PASS (skip path implemented in Task 3; this task locks the invariant with a dedicated test). If it FAILS, the lock was rewritten on a pure-skip run — confirm `write_lock` is guarded by `if added:`.

- [ ] **Step 3: (no implementation needed if passing)**

If Step 2 failed, wrap the final `write_lock` call in `if added:` as specified in Task 3 Step 3.

- [ ] **Step 4: Commit**

```bash
git add tests/test_cli/test_skill_import.py
git commit --no-verify -m "test(skill): import skip-if-exists preserves lock byte-for-byte"
```

---

## Task 5: `--latest` ignores the recorded SHA

**Files:**
- Test: `tests/test_cli/test_skill_import.py`

- [ ] **Step 1: Write the failing test**

Append. Uses `make_behind` (upstream has a commit the recorded SHA predates) to prove `--latest` lands on current HEAD, not the stale pin:

```python
def test_import_latest_clones_current_head(make_behind, tmp_path, monkeypatch):
    """--latest lands on upstream HEAD, not the recorded (older) sha."""
    from agent_toolkit_cli import skill_git
    sandbox = make_behind
    library_root = tmp_path / "lib" / "skills"
    for k, v in sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    # Recorded sha = the OLD clone HEAD (before upstream advanced).
    old_sha = skill_git.head_sha(sandbox.clone, env=None)
    incoming = tmp_path / "incoming.json"
    incoming.write_text(json.dumps({
        "version": 1,
        "skills": {
            "demo": {
                "source": str(sandbox.upstream),
                "sourceType": "git",
                "skillPath": "SKILL.md",
                "upstreamSha": old_sha,
                "localSha": old_sha,
            }
        },
    }))

    runner = CliRunner()
    result = runner.invoke(main, ["skill", "import", str(incoming), "--latest"])
    assert result.exit_code == 0, result.output
    assert "latest:" in result.output

    landed = skill_git.head_sha(library_root / "demo", env=None)
    assert landed != old_sha, "with --latest, HEAD should be upstream's newer commit"
```

- [ ] **Step 2: Run test to verify it fails or passes**

Run: `uv run pytest tests/test_cli/test_skill_import.py::test_import_latest_clones_current_head -v`
Expected: PASS (`--latest` sets `pin_sha=None`, so `_reconstruct_single` skips the checkout and stays on the freshly-cloned branch HEAD). If FAIL, confirm `pin_sha = None if latest else entry.upstream_sha` in the loop.

- [ ] **Step 3: Commit**

```bash
git add tests/test_cli/test_skill_import.py
git commit --no-verify -m "test(skill): import --latest lands on upstream head not recorded sha"
```

---

## Task 6: Partial failure is non-fatal, exit code 1

A bad source reports `failed`, good ones still import, lock written, exit 1.

**Files:**
- Test: `tests/test_cli/test_skill_import.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
def test_import_partial_failure_exit_1_but_writes_good(
    git_sandbox, tmp_path, monkeypatch
):
    from agent_toolkit_cli import skill_git
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    good_sha = skill_git.head_sha(git_sandbox.clone, env=None)
    incoming = tmp_path / "incoming.json"
    incoming.write_text(json.dumps({
        "version": 1,
        "skills": {
            "good": {
                "source": str(git_sandbox.upstream),
                "sourceType": "git", "skillPath": "SKILL.md",
                "upstreamSha": good_sha, "localSha": good_sha,
            },
            "bad": {
                "source": str(tmp_path / "does-not-exist.git"),
                "sourceType": "git", "skillPath": "SKILL.md",
                "upstreamSha": "deadbeef",
            },
        },
    }))

    runner = CliRunner()
    result = runner.invoke(main, ["skill", "import", str(incoming)])
    assert result.exit_code == 1, result.output
    assert "1 added" in result.output and "1 failed" in result.output
    assert "failed" in result.output and "bad" in result.output

    # Good skill still landed and is in the lock.
    assert (library_root / "good" / "SKILL.md").exists()
    lock = json.loads((library_root.parent / "skills-lock.json").read_text())
    assert "good" in lock["skills"]
    assert "bad" not in lock["skills"]
```

- [ ] **Step 2: Run test to verify it fails or passes**

Run: `uv run pytest tests/test_cli/test_skill_import.py::test_import_partial_failure_exit_1_but_writes_good -v`
Expected: PASS (try/except in the loop appends to `failed` and continues; `ctx.exit(1)` fires when `failed` is non-empty; `write_lock` ran because `good` was added). If the clone of a missing `file://`-less local path doesn't raise, confirm `skill_git.clone` raises `GitError` on the bad path (it does — non-zero rc).

- [ ] **Step 3: Commit**

```bash
git add tests/test_cli/test_skill_import.py
git commit --no-verify -m "test(skill): import partial failure exits 1 and keeps good skills"
```

---

## Task 7: Monorepo entry reconstruction

Prove a `read_only` monorepo entry (directory `skillPath`, `parentUrl`) is rebuilt via parent-clone + subpath symlink.

**Files:**
- Test: `tests/test_cli/test_skill_import.py`

- [ ] **Step 1: Write the failing test**

Append. Reuses the monorepo parent builder from the existing update-monorepo test (same pattern as the `monorepo_skill` fixture in conftest):

```python
def test_import_reconstructs_monorepo_entry(tmp_path, monkeypatch):
    from tests.test_cli.test_skill_update_monorepo import _init_parent
    parent = _init_parent(tmp_path)
    library_root = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    # Incoming lock describes a monorepo skill: directory skillPath, parentUrl,
    # read_only. owner_repo synthesised as local/<name> by file:// parsing.
    incoming = tmp_path / "incoming.json"
    incoming.write_text(json.dumps({
        "version": 1,
        "skills": {
            "mkdocs": {
                "source": f"local/{parent.name}",
                "sourceType": "git",
                "skillPath": "mkdocs",
                "parentUrl": f"file://{parent}",
                "readOnly": True,
            }
        },
    }))

    runner = CliRunner()
    result = runner.invoke(main, ["skill", "import", str(incoming)])
    assert result.exit_code == 0, result.output
    assert "1 added" in result.output

    canonical = library_root / "mkdocs"
    assert (canonical / "SKILL.md").exists(), "monorepo skill materialised"
    lock = json.loads((library_root.parent / "skills-lock.json").read_text())
    assert lock["skills"]["mkdocs"]["skillPath"] == "mkdocs"
    assert lock["skills"]["mkdocs"].get("readOnly") is True
```

If `_init_parent` lays out skills under a different subpath than `mkdocs`, open `tests/test_cli/test_skill_update_monorepo.py`, read `_init_parent`, and set `skillPath`/`source`/assert paths to the actual subpath it creates. Do this before running.

- [ ] **Step 2: Verify `_entry_to_parsed` routes monorepo correctly**

The converter must build a `ParsedSource` whose `url` is the `file://<parent>` (from `clone_url_from_entry` → `sourceUrl`/`parent_url` fallback) and `subpath="mkdocs"`. Check `clone_url_from_entry`: it returns `extras["sourceUrl"]` if present, else synthesises from source/type. The monorepo entry here has no `sourceUrl` and `source=local/<name>` with `sourceType=git`, so `clone_url_from_entry` returns the bare `local/<name>` string — **wrong for cloning**. Fix `_entry_to_parsed` to prefer `parent_url` as the clone URL for monorepo entries:

In `import_cmd.py`, adjust `_entry_to_parsed`:

```python
def _entry_to_parsed(entry: LockEntry) -> ParsedSource:
    from agent_toolkit_cli.skill_lock import clone_url_from_entry

    is_monorepo = bool(entry.parent_url) or (
        entry.skill_path not in (None, "SKILL.md")
    )
    if is_monorepo and entry.parent_url:
        url = entry.parent_url
    else:
        url = clone_url_from_entry(entry)
    subpath = entry.skill_path if is_monorepo else None
    return ParsedSource(
        type=entry.source_type or "git",
        url=url,
        owner_repo=entry.source if "/" in entry.source else None,
        ref=entry.ref,
        subpath=subpath,
    )
```

- [ ] **Step 3: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_skill_import.py::test_import_reconstructs_monorepo_entry -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/agent_toolkit_cli/commands/skill/import_cmd.py tests/test_cli/test_skill_import.py
git commit --no-verify -m "feat(skill): import reconstructs monorepo entries via parent symlink"
```

---

## Task 8: Self-import no-op + help wiring

Importing the live global lock onto itself skips everything; confirm the command shows in help.

**Files:**
- Test: `tests/test_cli/test_skill_import.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
def test_import_self_is_noop(installed_skill):
    """Importing the live global lock onto itself skips all, changes nothing."""
    before = installed_skill.lock_path.read_text()
    runner = CliRunner()
    result = runner.invoke(main, ["skill", "import", str(installed_skill.lock_path)])
    assert result.exit_code == 0, result.output
    assert "0 added" in result.output
    assert "skipped" in result.output
    assert installed_skill.lock_path.read_text() == before


def test_import_appears_in_skill_help():
    runner = CliRunner()
    result = runner.invoke(main, ["skill", "--help"])
    assert result.exit_code == 0
    assert "import" in result.output
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli/test_skill_import.py -k "self_is_noop or appears_in_skill_help" -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_cli/test_skill_import.py
git commit --no-verify -m "test(skill): import self-noop and help wiring"
```

---

## Task 9: Full-suite verification + help-examples doc

Run the whole suite; the repo's `test_cli_skill_help_examples.py` parses epilog examples — confirm the new import epilog examples are valid.

**Files:**
- Test: whole suite

- [ ] **Step 1: Run the import suite**

Run: `uv run pytest tests/test_cli/test_skill_import.py -v`
Expected: all PASS.

- [ ] **Step 2: Run the full CLI suite**

Run: `uv run pytest tests/test_cli -v`
Expected: all PASS. If `test_cli_skill_help_examples.py` fails on the import epilog, read that test and align the epilog example format (it expects runnable-looking `agent-toolkit-cli skill ...` lines under `\b`).

- [ ] **Step 3: Run the entire suite + lint**

Run: `uv run pytest && uv run ruff check src tests`
Expected: all PASS, no lint errors. Fix any `ruff` findings inline (e.g. unused imports — remove the duplicate `clone_url_from_entry` import in the loop if `_entry_to_parsed` already imports it).

- [ ] **Step 4: Commit any fixes**

```bash
git add -A
git commit --no-verify -m "test(skill): full-suite green for import"
```

---

## Self-review notes

- **Spec coverage:** import-only (Task 2) ✓; additive merge + skip-if-exists total (Tasks 3,4) ✓; default SHA pin (Task 3) ✓; `--latest` (Task 5) ✓; per-skill non-fatal failure + exit 1 (Task 6) ✓; monorepo reconstruction (Task 7) ✓; three always-on notices (Task 2) ✓; missing-file UsageError + empty-file (Task 2) ✓; self-import no-op (Task 8) ✓; shared helper extraction (Task 1) ✓.
- **`clone_url_from_entry` monorepo trap:** caught in Task 7 Step 2 — monorepo clone URL must come from `parent_url`, not the synthesised `local/<name>`.
- **Type consistency:** helper name `reconstruct_skill_into_library` used identically in Tasks 1 and 3; `_entry_to_parsed` defined Task 3, refined Task 7; `LockEntry`/`add_entry`/`write_lock`/`read_lock`/`clone_url_from_entry` are all real symbols in `skill_lock.py`; `ParsedSource` fields (`type,url,owner_repo,ref,subpath,skill_name`) match `skill_source.py`.
- **`--no-verify` on every commit:** broken schema-check hook (memory).
