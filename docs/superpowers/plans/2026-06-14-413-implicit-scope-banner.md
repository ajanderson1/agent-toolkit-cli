# Implicit-Scope Banner (#413) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a `skill` read-only verb resolves scope implicitly (no `-g`/`-p`) and lands on **project**, print a one-line stderr reminder of which lock was picked; and reword `update`'s monorepo-at-project-scope refusal to explain what `-g` actually does.

**Architecture:** `scope_and_roots` gains a 4th return element `implicit` (True iff no scope flag was passed). A new `scope_banner` helper in `commands/skill/_common.py` emits the reminder to **stderr** only on implicit-project. All six read verbs (`list`, `status`, `update`, `reset`, `push`, `doctor`) unpack the 4-tuple and call the helper before their main output. The `update` monorepo refusal string is reworded. `skill` only — agent/mcp/pi_extension are follow-ups.

**Tech Stack:** Python 3.9+, Click, pytest, `uv run`. Tests are CLI-level via `click.testing.CliRunner`.

**Spec:** `docs/superpowers/specs/2026-06-14-413-implicit-scope-banner-design.md`

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `src/agent_toolkit_cli/commands/skill/_common.py` | scope resolution + new banner helper | 4-tuple return; add `scope_banner` |
| `.../commands/skill/list_cmd.py` | `skill list` | unpack 4th elt; call banner before emit |
| `.../commands/skill/status_cmd.py` | `skill status` | unpack 4th elt; call banner |
| `.../commands/skill/update_cmd.py` | `skill update` | unpack 4th elt; call banner; reword refusal |
| `.../commands/skill/reset_cmd.py` | `skill reset` | unpack 4th elt; call banner |
| `.../commands/skill/push_cmd.py` | `skill push` | unpack 4th elt; call banner |
| `.../commands/skill/doctor_cmd.py` | `skill doctor` | unpack 4th elt; call banner |
| `tests/test_cli/test_cli_skill_scope_banner.py` | NEW — banner unit/CLI tests | create |
| `tests/test_cli/test_cli_skill_update.py` | reword-refusal e2e | add test |

> **Note on the 4-tuple change:** every call site currently does
> `scope, home, project_root = scope_and_roots(...)`. After Task 1 these become
> 4-element unpacks. **Tasks 1–7 must land in one working sequence** — between
> Task 1 (changes the return arity) and the last verb update, the unpatched
> verbs will fail. Run the targeted verb test after each task, and the **full
> suite only after Task 7**. Each task still commits independently.

---

## Task 1: `scope_and_roots` returns `implicit`

**Files:**
- Modify: `src/agent_toolkit_cli/commands/skill/_common.py`
- Test: `tests/test_cli/test_cli_skill_scope_banner.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli/test_cli_skill_scope_banner.py`:

```python
"""Tests for #413 — implicit-scope reminder banner + 4-tuple resolution."""
from __future__ import annotations

from pathlib import Path

from agent_toolkit_cli.commands.skill._common import scope_and_roots


def test_scope_and_roots_explicit_flags_are_not_implicit(tmp_path: Path):
    g = scope_and_roots(True, False, None, read_only=True)
    p = scope_and_roots(False, True, tmp_path, read_only=True)
    assert g == ("global", Path.home(), None, False)
    assert p == ("project", None, tmp_path, False)


def test_scope_and_roots_implicit_project_when_cwd_lock(tmp_path: Path):
    (tmp_path / "skills-lock.json").write_text("{}")
    scope, home, root, implicit = scope_and_roots(
        False, False, tmp_path, read_only=True,
    )
    assert (scope, home, root, implicit) == ("project", None, tmp_path, True)


def test_scope_and_roots_implicit_global_when_no_cwd_lock(tmp_path: Path):
    scope, home, root, implicit = scope_and_roots(
        False, False, tmp_path, read_only=True,
    )
    assert (scope, home, root, implicit) == ("global", Path.home(), None, True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_cli_skill_scope_banner.py -v`
Expected: FAIL — `scope_and_roots` returns a 3-tuple, so the 4-element comparisons fail (`ValueError: not enough values to unpack` / tuple inequality).

- [ ] **Step 3: Implement the 4-tuple**

In `_common.py`, update the function body so every `return` carries a 4th element. Replace the existing body of `scope_and_roots`:

```python
def scope_and_roots(
    global_: bool,
    project: bool,
    ctx_project: Path | None,
    *,
    read_only: bool = False,
):
    """Resolve (scope, home, project_root, implicit) from flags + context.

    ``implicit`` is True iff neither ``-g`` nor ``-p`` was passed — i.e. the
    scope was inferred from the presence of ``<cwd>/skills-lock.json`` (or its
    absence). Verbs use it to decide whether to print a scope reminder (#413).

    With ``read_only=True`` and neither flag set, fall back to global when no
    ``<cwd>/skills-lock.json`` exists. This matches ``skill add``'s
    global-by-default mental model for the read-only verbs. See issue #210.
    """
    if global_ and project:
        raise click.UsageError("use either -g/--global or -p/--project, not both")
    if global_:
        return "global", Path.home(), None, False
    if project:
        project_root = ctx_project or Path.cwd()
        return "project", None, project_root, False
    project_root = ctx_project or Path.cwd()
    if read_only and not (project_root / "skills-lock.json").exists():
        return "global", Path.home(), None, True
    return "project", None, project_root, True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_cli_skill_scope_banner.py -v`
Expected: PASS (3 tests).

> Do NOT run the full suite yet — the six verbs still do 3-element unpacks and will break until Tasks 2–7 land.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/skill/_common.py tests/test_cli/test_cli_skill_scope_banner.py
git commit -m "feat(skill): scope_and_roots returns implicit flag (#413)" --trailer "Device: $(hostname -s)"
```

---

## Task 2: `scope_banner` helper

**Files:**
- Modify: `src/agent_toolkit_cli/commands/skill/_common.py`
- Test: `tests/test_cli/test_cli_skill_scope_banner.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli/test_cli_skill_scope_banner.py`:

```python
import click
from click.testing import CliRunner

from agent_toolkit_cli.commands.skill._common import scope_banner


def _run_banner(**kwargs) -> tuple[str, str]:
    """Invoke scope_banner inside a tiny Click command; return (stdout, stderr)."""
    @click.command()
    def cmd():
        scope_banner(**kwargs)

    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(cmd, [])
    assert result.exit_code == 0
    return result.stdout, result.stderr


def test_banner_prints_on_implicit_project_to_stderr():
    stdout, stderr = _run_banner(
        scope="project", implicit=True,
        lock_path="/x/skills-lock.json", count=6,
    )
    assert stdout == ""                       # nothing on stdout
    assert "project scope" in stderr
    assert "/x/skills-lock.json" in stderr
    assert "6 skills" in stderr
    assert "-g" in stderr


def test_banner_singular_noun_for_one_skill():
    _, stderr = _run_banner(
        scope="project", implicit=True,
        lock_path="/x/skills-lock.json", count=1,
    )
    assert "1 skill." in stderr
    assert "1 skills" not in stderr


def test_banner_prints_on_empty_project_lock():
    _, stderr = _run_banner(
        scope="project", implicit=True,
        lock_path="/x/skills-lock.json", count=0,
    )
    assert "0 skills" in stderr


def test_banner_silent_on_implicit_global():
    _, stderr = _run_banner(
        scope="global", implicit=True, lock_path=None, count=12,
    )
    assert stderr == ""


def test_banner_silent_on_explicit_project():
    _, stderr = _run_banner(
        scope="project", implicit=False,
        lock_path="/x/skills-lock.json", count=6,
    )
    assert stderr == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_cli_skill_scope_banner.py -k banner -v`
Expected: FAIL — `ImportError: cannot import name 'scope_banner'`.

- [ ] **Step 3: Implement `scope_banner`**

Add to `_common.py` (after `scope_and_roots`):

```python
def scope_banner(scope, *, implicit, lock_path, count) -> None:
    """Print a one-line scope reminder to stderr on implicit-project resolution.

    Best-effort and informational: never raises, never affects exit codes.
    Silent unless scope was resolved implicitly (no -g/-p) AND landed on
    project — the one case (#413) where the user got no signal about which
    lock was picked. Routed to stderr so it never contaminates stdout (e.g.
    `skill list --json`).
    """
    if not (implicit and scope == "project"):
        return
    noun = "skill" if count == 1 else "skills"
    click.echo(
        f"Operating on project scope — {lock_path} ({count} {noun}). "
        f"Pass -g to target the global library.",
        err=True,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_cli_skill_scope_banner.py -k banner -v`
Expected: PASS (5 banner tests).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/skill/_common.py tests/test_cli/test_cli_skill_scope_banner.py
git commit -m "feat(skill): scope_banner helper for implicit-project reminder (#413)" --trailer "Device: $(hostname -s)"
```

---

## Task 3: Wire `list` (with JSON-pristine proof)

**Files:**
- Modify: `src/agent_toolkit_cli/commands/skill/list_cmd.py`
- Test: `tests/test_cli/test_cli_skill_scope_banner.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli/test_cli_skill_scope_banner.py`:

```python
import json

from agent_toolkit_cli.cli import main


def _seed_project_lock(runner, tmp_path, monkeypatch, git_sandbox, slug="demo"):
    """Add a skill to the library and install it into a project, so the
    project gets a non-empty skills-lock.json. Returns the project path."""
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".claude").mkdir()
    assert runner.invoke(main, [
        "skill", "add", str(git_sandbox.upstream), "--slug", slug,
    ]).exit_code == 0
    assert runner.invoke(main, [
        "--project", str(project), "skill", "install", slug,
        "--scope", "project", "--agents", "claude-code",
    ]).exit_code == 0
    return project


def test_list_implicit_project_banner_on_stderr_json_clean(
    git_sandbox, tmp_path, monkeypatch,
):
    runner = CliRunner(mix_stderr=False)
    project = _seed_project_lock(runner, tmp_path, monkeypatch, git_sandbox)
    # No -g/-p: implicit project (cwd has skills-lock.json via --project root).
    result = runner.invoke(main, [
        "--project", str(project), "skill", "list", "--json",
    ])
    assert result.exit_code == 0, result.stderr
    # stdout is pristine JSON; banner is on stderr.
    assert json.loads(result.stdout)
    assert "project scope" in result.stderr


def test_list_explicit_global_no_banner(
    git_sandbox, tmp_path, monkeypatch,
):
    runner = CliRunner(mix_stderr=False)
    _seed_project_lock(runner, tmp_path, monkeypatch, git_sandbox)
    result = runner.invoke(main, ["skill", "list", "-g"])
    assert result.exit_code == 0, result.stderr
    assert "project scope" not in result.stderr
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_cli_skill_scope_banner.py -k list -v`
Expected: FAIL — `list_cmd` still unpacks 3 values (`ValueError: too many values to unpack`) after Task 1, and emits no banner.

- [ ] **Step 3: Implement**

In `list_cmd.py`, update the unpack and add the banner call. Change the `scope_and_roots` call (line ~46) and import:

```python
from ._common import scope_and_roots, scope_banner
```

```python
    scope, home, project_root, implicit = scope_and_roots(
        global_,
        project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
        read_only=True,
    )
```

After the lock is read (after line ~60 `lock = read_lock(...)`), before the JSON/table dispatch:

```python
    lock = read_lock(lock_file_path(scope=scope, home=home, project=project_root))
    scope_banner(
        scope, implicit=implicit,
        lock_path=lock_file_path(scope=scope, home=home, project=project_root),
        count=len(lock.skills),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_cli_skill_scope_banner.py -k list -v`
Expected: PASS.

Also confirm existing list/json tests still pass (they use `-g`, so no banner; default runner mixes stderr but the banner won't fire):
Run: `uv run pytest tests/test_cli/test_cli_skill_list_json.py tests/test_cli/test_cli_skill_list.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/skill/list_cmd.py tests/test_cli/test_cli_skill_scope_banner.py
git commit -m "feat(skill): list prints implicit-project scope banner (#413)" --trailer "Device: $(hostname -s)"
```

---

## Task 4: Wire `status`

**Files:**
- Modify: `src/agent_toolkit_cli/commands/skill/status_cmd.py`
- Test: existing `tests/test_cli/test_cli_skill_status.py` must stay green.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli/test_cli_skill_scope_banner.py` (reuses `_seed_project_lock`):

```python
def test_status_implicit_project_banner(git_sandbox, tmp_path, monkeypatch):
    runner = CliRunner(mix_stderr=False)
    project = _seed_project_lock(runner, tmp_path, monkeypatch, git_sandbox)
    result = runner.invoke(main, ["--project", str(project), "skill", "status"])
    assert result.exit_code == 0, result.stderr
    assert "project scope" in result.stderr


def test_status_explicit_project_no_banner(git_sandbox, tmp_path, monkeypatch):
    runner = CliRunner(mix_stderr=False)
    project = _seed_project_lock(runner, tmp_path, monkeypatch, git_sandbox)
    result = runner.invoke(main, ["--project", str(project), "skill", "status", "-p"])
    assert result.exit_code == 0, result.stderr
    assert "project scope" not in result.stderr  # explicit -p → no reminder
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_cli_skill_scope_banner.py -k status -v`
Expected: FAIL — 3-value unpack error / no banner.

- [ ] **Step 3: Implement**

In `status_cmd.py`, import `scope_banner`, unpack the 4th value, and add the banner after the lock read (before the empty-lock hint at line ~68):

```python
from ._common import scope_and_roots, scope_banner
```

```python
    scope, home, project_root, implicit = scope_and_roots(
        global_,
        project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
        read_only=True,
    )
    lock_path = lock_file_path(scope=scope, home=home, project=project_root)
    lock = read_lock(lock_path)
    scope_banner(scope, implicit=implicit, lock_path=lock_path, count=len(lock.skills))
    if not lock.skills and project_flag and scope == "project":
        ...
```

> The existing `lock = read_lock(lock_file_path(...))` on line 67 is replaced by the two-line `lock_path = ...` / `lock = read_lock(lock_path)` form so the path can be reused by the banner.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_cli_skill_scope_banner.py -k status tests/test_cli/test_cli_skill_status.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/skill/status_cmd.py tests/test_cli/test_cli_skill_scope_banner.py
git commit -m "feat(skill): status prints implicit-project scope banner (#413)" --trailer "Device: $(hostname -s)"
```

---

## Task 5: Wire `update` + reword monorepo refusal

**Files:**
- Modify: `src/agent_toolkit_cli/commands/skill/update_cmd.py`
- Test: `tests/test_cli/test_cli_skill_scope_banner.py`, `tests/test_cli/test_cli_skill_update.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli/test_cli_skill_scope_banner.py`:

```python
def test_update_implicit_project_banner(git_sandbox, tmp_path, monkeypatch):
    runner = CliRunner(mix_stderr=False)
    project = _seed_project_lock(runner, tmp_path, monkeypatch, git_sandbox)
    result = runner.invoke(main, ["--project", str(project), "skill", "update"])
    # Exit code may be 0 (clean) — we only assert the banner is on stderr.
    assert "project scope" in result.stderr
```

Add to `tests/test_cli/test_cli_skill_update.py` a reworded-refusal assertion. Find `test_update_*monorepo*` setup or add a focused test. Minimal new test:

```python
def test_update_monorepo_refusal_explains_global(
    monorepo_project,  # fixture: project lock with a monorepo-backed entry
):
    """Project-scope monorepo update is refused with a message that explains
    -g switches to the global *set*, not a re-scope of this entry (#413)."""
    runner = CliRunner()
    result = runner.invoke(main, [
        "--project", str(monorepo_project), "skill", "update", "-p",
    ])
    assert result.exit_code == 1
    out = result.output.lower()
    assert "global scope" in out
    assert "different set" in out  # the new clarifying clause
```

> **Fixture note:** if no `monorepo_project` fixture exists, reuse the
> monorepo-install helper from `tests/test_cli/test_skill_update_monorepo.py`
> (read it first) to build a project whose lock has a `parent_url` entry, then
> invoke `skill update -p`. Match that file's existing fixture/helper names
> rather than inventing new ones.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli/test_cli_skill_scope_banner.py -k update tests/test_cli/test_cli_skill_update.py -k refusal -v`
Expected: FAIL — 3-value unpack error (banner test) and old refusal string lacks "different set".

- [ ] **Step 3: Implement**

In `update_cmd.py`:

Import and unpack:
```python
from ._common import scope_and_roots, scope_banner
```
```python
    scope, home, project_root, implicit = scope_and_roots(
        global_,
        project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
        read_only=True,
    )
    lock_path = lock_file_path(scope=scope, home=home, project=project_root)
    lock = read_lock(lock_path)
    scope_banner(scope, implicit=implicit, lock_path=lock_path, count=len(lock.skills))
```

Reword the monorepo refusal (lines ~77-79):
```python
            if scope != "global":
                click.echo(
                    f"{slug}: monorepo skill — update it at global scope. "
                    f"Note: -g switches to the global library (a different "
                    f"set), it does not update this project entry."
                )
                had_conflict = True
                continue
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli/test_cli_skill_scope_banner.py -k update tests/test_cli/test_cli_skill_update.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/skill/update_cmd.py tests/test_cli/test_cli_skill_scope_banner.py tests/test_cli/test_cli_skill_update.py
git commit -m "feat(skill): update scope banner + clearer monorepo refusal (#413)" --trailer "Device: $(hostname -s)"
```

---

## Task 6: Wire `reset` and `push`

**Files:**
- Modify: `src/agent_toolkit_cli/commands/skill/reset_cmd.py`, `push_cmd.py`
- Test: `tests/test_cli/test_cli_skill_scope_banner.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli/test_cli_skill_scope_banner.py`:

```python
def test_reset_implicit_project_banner(git_sandbox, tmp_path, monkeypatch):
    runner = CliRunner(mix_stderr=False)
    project = _seed_project_lock(runner, tmp_path, monkeypatch, git_sandbox)
    result = runner.invoke(main, ["--project", str(project), "skill", "reset", "demo"])
    assert "project scope" in result.stderr


def test_push_implicit_project_banner(git_sandbox, tmp_path, monkeypatch):
    runner = CliRunner(mix_stderr=False)
    project = _seed_project_lock(runner, tmp_path, monkeypatch, git_sandbox)
    result = runner.invoke(main, ["--project", str(project), "skill", "push", "demo"])
    assert "project scope" in result.stderr
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_cli_skill_scope_banner.py -k "reset or push" -v`
Expected: FAIL — 3-value unpack error.

- [ ] **Step 3: Implement**

In **`reset_cmd.py`**: import `scope_banner`, unpack 4th value, banner after lock read (lines ~51-58):
```python
from ._common import scope_and_roots, scope_banner
```
```python
    scope, home, project_root, implicit = scope_and_roots(
        global_,
        project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
        read_only=True,
    )
    lock_path = lock_file_path(scope=scope, home=home, project=project_root)
    lock = read_lock(lock_path)
    scope_banner(scope, implicit=implicit, lock_path=lock_path, count=len(lock.skills))
```

In **`push_cmd.py`**: import `scope_banner`, unpack 4th value (lines ~55-62). Note `push` re-derives the project root later (`scope_and_roots` returns None home in project scope) — leave that logic intact; only add the banner after the lock read:
```python
from ._common import scope_and_roots, scope_banner
```
```python
    scope, home, project_root, implicit = scope_and_roots(
        global_,
        project_flag,
        ctx_project,
        read_only=True,
    )
    lock_path = lock_file_path(scope=scope, home=home, project=project_root)
    lock = read_lock(lock_path)
    scope_banner(scope, implicit=implicit, lock_path=lock_path, count=len(lock.skills))
```

> `reset_cmd` and `push_cmd` already assign `lock_path` then `lock = read_lock(lock_path)` — reuse those existing variables; only add the unpack 4th element, the import, and the one `scope_banner(...)` line.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_cli_skill_scope_banner.py -k "reset or push" tests/test_cli/test_cli_skill_reset.py tests/test_cli/test_cli_skill_push.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/skill/reset_cmd.py src/agent_toolkit_cli/commands/skill/push_cmd.py tests/test_cli/test_cli_skill_scope_banner.py
git commit -m "feat(skill): reset + push print implicit-project scope banner (#413)" --trailer "Device: $(hostname -s)"
```

---

## Task 7: Wire `doctor` + full-suite gate

**Files:**
- Modify: `src/agent_toolkit_cli/commands/skill/doctor_cmd.py`
- Test: `tests/test_cli/test_cli_skill_scope_banner.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli/test_cli_skill_scope_banner.py`:

```python
def test_doctor_implicit_project_banner(git_sandbox, tmp_path, monkeypatch):
    runner = CliRunner(mix_stderr=False)
    project = _seed_project_lock(runner, tmp_path, monkeypatch, git_sandbox)
    result = runner.invoke(main, ["--project", str(project), "skill", "doctor"])
    assert "project scope" in result.stderr
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_cli_skill_scope_banner.py -k doctor -v`
Expected: FAIL — 3-value unpack error.

- [ ] **Step 3: Implement**

In `doctor_cmd.py`: import `scope_banner`, unpack 4th value (lines ~26-30). `doctor` builds findings rather than reading the lock directly; read the lock for the count. After the `scope_and_roots` call:

```python
from ._common import scope_and_roots, scope_banner
from agent_toolkit_cli.skill_lock import read_lock
from agent_toolkit_cli.skill_paths import lock_file_path
```
```python
    scope, home, project_root, implicit = scope_and_roots(
        global_, project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
        read_only=True,
    )
    _lock = read_lock(lock_file_path(scope=scope, home=home, project=project_root))
    scope_banner(
        scope, implicit=implicit,
        lock_path=lock_file_path(scope=scope, home=home, project=project_root),
        count=len(_lock.skills),
    )
```

> Check `doctor_cmd.py`'s existing imports first — `read_lock`/`lock_file_path` may already be imported; if so, do not duplicate. If `diagnose()` already reads the lock, you may pass its count instead of re-reading — prefer not adding a second read if one is already in scope.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_cli_skill_scope_banner.py -k doctor tests/test_cli/test_cli_skill_doctor.py tests/test_cli/test_skill_doctor.py -q`
Expected: PASS.

- [ ] **Step 5: Full-suite gate**

Now that all six verbs unpack the 4-tuple, run the whole suite:

Run: `uv run pytest -q`
Expected: PASS (baseline was 1650 passed, 2 skipped — expect 1650 + the new scope-banner tests passing, 2 skipped).

If any pre-existing test asserted exact stdout that now also caught the banner: confirm it used the default `CliRunner()` AND an implicit-project invocation. Most existing verb tests pass `-g`/`-p` explicitly (no banner) — if one regresses, it is a real find; fix the test to assert against `result.stdout` with `mix_stderr=False`, or note it.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/commands/skill/doctor_cmd.py tests/test_cli/test_cli_skill_scope_banner.py
git commit -m "feat(skill): doctor prints implicit-project scope banner (#413)" --trailer "Device: $(hostname -s)"
```

---

## Task 8: Follow-up issues for the other asset types

**Files:** none (GitHub only).

- [ ] **Step 1: File three follow-up issues** for the same implicit-scope opacity in the sibling asset types, each pointing back at this fix as the template:

```bash
gh issue create --title "feat(agent): surface implicitly-resolved scope (mirror #413)" \
  --body "Same implicit-scope opacity as #413, in \`commands/agent/_common.py\` \`scope_and_roots\` + its read verbs. Apply the #413 pattern: 4-tuple \`implicit\` return + stderr scope banner on implicit-project. See spec docs/superpowers/specs/2026-06-14-413-implicit-scope-banner-design.md." \
  --label enhancement
gh issue create --title "feat(mcp): surface implicitly-resolved scope (mirror #413)" \
  --body "Same as #413 for \`commands/mcp/_common.py\` (\`mcps-lock.json\`). Apply the 4-tuple \`implicit\` + stderr banner pattern." \
  --label enhancement
gh issue create --title "feat(pi-extension): surface implicitly-resolved scope (mirror #413)" \
  --body "Same as #413 for \`commands/pi_extension/_common.py\`. Apply the 4-tuple \`implicit\` + stderr banner pattern." \
  --label enhancement
```

- [ ] **Step 2: Note the follow-up numbers** in the #413 PR description so the relationship is traceable.

---

## Verification checklist (end of run)

- [ ] `uv run pytest -q` green (1650 + new scope-banner tests, 2 skipped).
- [ ] `uv run ruff check src/agent_toolkit_cli/commands/skill/ tests/test_cli/test_cli_skill_scope_banner.py` — no new errors.
- [ ] `uv run mypy src/agent_toolkit_cli/commands/skill/` — no new errors (the 4-tuple return is untyped today; do not add a return annotation that the other call sites would break — `scope_and_roots` has no annotation, keep it that way).
- [ ] Manual: `agent-toolkit-cli skill list` from a dir with a `skills-lock.json` → banner on stderr; `skill list 2>/dev/null` → no banner in stdout; `skill list --json | jq .` → valid JSON.
```
