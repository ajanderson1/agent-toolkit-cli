# #420 — pi-extension implicit-scope banner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the #413 implicit-scope transparency banner to the `pi-extension` asset type — `scope_and_roots` returns a 4th `implicit` element and the pi read verbs (`list`, `status`, `update`, `reset`, `push`, `doctor`) print a one-line reminder when scope was resolved implicitly to project.

**Architecture:** Mirror PR #417 / #424 / #426 inside `commands/pi_extension/`. pi delta: `list`/`status`/`doctor` are inventory- or diagnose-based (no body-level lock read), so they get an **introduced** `read_lock` for the banner count; `update`/`reset`/`push` already read the lock. `list` has `--json` (banner → stderr there); `status` does not. Count is `len(lock.skills)` (pi's `read_lock` is the lenient `LockFile`-returning re-export). The four `scope_and_roots` copies are NOT unified here — see the spec's cross-cutting decision; a follow-up issue is filed.

**Tech Stack:** Python, Click 8.2+, pytest, `CliRunner` (`from agent_toolkit_cli.cli import main`).

---

## File structure

- `src/agent_toolkit_cli/commands/pi_extension/_common.py` — `scope_and_roots` → 4-tuple; add `scope_banner` (noun "pi extension(s)").
- `src/agent_toolkit_cli/commands/pi_extension/{list,status,update,reset,push,doctor}_cmd.py` — unpack 4th element, call `scope_banner` pre-output.
- `src/agent_toolkit_cli/commands/pi_extension/{install,uninstall}_cmd.py` — absorb the 4th element as `_implicit`.
- `tests/test_cli/test_pi_extension_scope_banner.py` — new test file.

---

### Task 1: `scope_and_roots` returns the `implicit` 4-tuple

**Files:**
- Modify: `src/agent_toolkit_cli/commands/pi_extension/_common.py`
- Test: `tests/test_cli/test_pi_extension_scope_banner.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from agent_toolkit_cli.commands.pi_extension._common import scope_and_roots


def test_scope_and_roots_explicit_global_is_not_implicit():
    assert scope_and_roots(True, False, None) == ("global", Path.home(), None, False)


def test_scope_and_roots_explicit_project_is_not_implicit(tmp_path):
    assert scope_and_roots(False, True, tmp_path) == ("project", None, tmp_path, False)


def test_scope_and_roots_implicit_global_when_read_only_and_no_lock(tmp_path):
    assert scope_and_roots(False, False, tmp_path, read_only=True) == (
        "global", Path.home(), None, True,
    )


def test_scope_and_roots_implicit_project_when_lock_present(tmp_path):
    (tmp_path / "pi-extensions-lock.json").write_text('{"version": 1, "skills": {}}')
    assert scope_and_roots(False, False, tmp_path, read_only=True) == (
        "project", None, tmp_path, True,
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_pi_extension_scope_banner.py -q`
Expected: FAIL — current `scope_and_roots` returns a 3-tuple.

- [ ] **Step 3: Add the `implicit` element**

In `pi_extension/_common.py`, widen the return annotation to
`tuple[Scope, Path | None, Path | None, bool]`, add a docstring noting `implicit`
(True iff no -g/-p, inferred from `<cwd>/pi-extensions-lock.json`), and append
the bool to each return:

```python
    if global_ and project:
        raise click.UsageError("use either -g/--global or -p/--project, not both")
    if global_:
        return "global", Path.home(), None, False
    if project:
        project_root = ctx_project or Path.cwd()
        return "project", None, project_root, False
    project_root = ctx_project or Path.cwd()
    if read_only and not (project_root / _LOCK_FILENAME).exists():
        return "global", Path.home(), None, True
    return "project", None, project_root, True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_pi_extension_scope_banner.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Update the call sites that unpack the 3-tuple**

Read verbs → name the 4th `implicit`; write verbs → `_implicit`:

- `pi_extension/list_cmd.py:25` → `scope, home, project_root, implicit = scope_and_roots(`
- `pi_extension/status_cmd.py:22` → `scope, home, project_root, implicit = scope_and_roots(`
- `pi_extension/update_cmd.py:38` → `scope, home, project_root, implicit = scope_and_roots(`
- `pi_extension/reset_cmd.py:44` → `scope, home, project_root, implicit = scope_and_roots(`
- `pi_extension/push_cmd.py:51` → `scope, home, project_root, implicit = scope_and_roots(`
- `pi_extension/doctor_cmd.py:44` → `scope, home, project_root, implicit = scope_and_roots(`
- `pi_extension/install_cmd.py:26` → `scope, home, project, _implicit = scope_and_roots(`
- `pi_extension/uninstall_cmd.py:25` → `scope, home, project, _implicit = scope_and_roots(`

- [ ] **Step 6: Run the pi CLI slice to verify no unpack errors**

Run: `uv run pytest tests/test_cli -k pi_extension -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/agent_toolkit_cli/commands/pi_extension/_common.py \
        src/agent_toolkit_cli/commands/pi_extension/*_cmd.py \
        tests/test_cli/test_pi_extension_scope_banner.py
git commit -m "feat(pi-extension): scope_and_roots returns implicit flag (#420)"
```

---

### Task 2: `scope_banner` helper

**Files:**
- Modify: `src/agent_toolkit_cli/commands/pi_extension/_common.py`
- Test: `tests/test_cli/test_pi_extension_scope_banner.py`

- [ ] **Step 1: Write the failing test**

```python
import click
from click.testing import CliRunner

from agent_toolkit_cli.commands.pi_extension._common import scope_banner


def _run_banner(**kwargs):
    @click.command()
    def cmd():
        scope_banner(**kwargs)
    return CliRunner().invoke(cmd, [])


def test_banner_prints_on_implicit_project_plural():
    r = _run_banner(scope="project", implicit=True, lock_path="/p/pi-extensions-lock.json", count=3)
    assert "Operating on project scope — /p/pi-extensions-lock.json (3 pi extensions)." in r.stdout
    assert "Pass -g for the global library." in r.stdout


def test_banner_singular_noun():
    r = _run_banner(scope="project", implicit=True, lock_path="/p/pi-extensions-lock.json", count=1)
    assert "(1 pi extension)." in r.stdout


def test_banner_count_zero_still_prints():
    r = _run_banner(scope="project", implicit=True, lock_path="/p/pi-extensions-lock.json", count=0)
    assert "(0 pi extensions)." in r.stdout


def test_banner_silent_on_implicit_global():
    r = _run_banner(scope="global", implicit=True, lock_path="/x", count=5)
    assert r.stdout == ""


def test_banner_silent_on_explicit_project():
    r = _run_banner(scope="project", implicit=False, lock_path="/x", count=5)
    assert r.stdout == ""


def test_banner_silent_on_explicit_global():
    r = _run_banner(scope="global", implicit=False, lock_path="/x", count=5)
    assert r.stdout == ""


def test_banner_err_routes_to_stderr():
    r = _run_banner(scope="project", implicit=True, lock_path="/p", count=2, err=True)
    assert r.stdout == ""
    assert "Operating on project scope" in r.stderr
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_pi_extension_scope_banner.py -k banner -q`
Expected: FAIL — `scope_banner` not defined.

- [ ] **Step 3: Add the helper**

In `pi_extension/_common.py`, after `scope_and_roots`:

```python
def scope_banner(scope, *, implicit, lock_path, count, err=False) -> None:
    """Print a one-line scope reminder on implicit-project resolution.

    Best-effort and informational: never raises, never affects exit codes.
    Silent unless scope was resolved implicitly (no -g/-p) AND landed on
    project — the one case (#420, mirrors #413) where the user got no signal
    about which lock was picked. Goes to stdout by default; callers emitting a
    machine stream (``list --json``) pass ``err=True`` to route it to stderr.
    """
    if not (implicit and scope == "project"):
        return
    noun = "pi extension" if count == 1 else "pi extensions"
    click.echo(
        f"Operating on project scope — {lock_path} ({count} {noun}). "
        f"Pass -g for the global library.",
        err=err,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_pi_extension_scope_banner.py -k banner -q`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/pi_extension/_common.py \
        tests/test_cli/test_pi_extension_scope_banner.py
git commit -m "feat(pi-extension): scope_banner helper, pi-extension noun (#420)"
```

---

### Task 3: Wire `list` (stdout + `--json` stderr) and `status` (introduced lock read)

**Files:**
- Modify: `src/agent_toolkit_cli/commands/pi_extension/{list,status}_cmd.py`
- Test: `tests/test_cli/test_pi_extension_scope_banner.py`

- [ ] **Step 1: Write the failing test**

```python
import json

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main as cli  # entrypoint symbol is `main`
from agent_toolkit_cli.pi_extension_lock import LockEntry, LockFile, write_lock


def _seed_project_lock(tmp_path):
    """A minimal valid pi-extensions-lock.json with one entry, in tmp_path."""
    write_lock(
        tmp_path / "pi-extensions-lock.json",
        LockFile(version=1, skills={
            "demo-ext": LockEntry(source="https://example.com/demo-ext",
                                  source_type="git", ref="main"),
        }),
    )


def test_pi_list_human_banner_on_stdout(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    monkeypatch.chdir(tmp_path)
    _seed_project_lock(tmp_path)
    r = CliRunner().invoke(cli, ["pi-extension", "list"])
    assert "Operating on project scope" in r.stdout
    assert "(1 pi extension)." in r.stdout


def test_pi_list_json_banner_on_stderr_stdout_is_json(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    monkeypatch.chdir(tmp_path)
    _seed_project_lock(tmp_path)
    r = CliRunner().invoke(cli, ["pi-extension", "list", "--json"])
    json.loads(r.stdout)  # stdout parses clean
    assert "Operating on project scope" in r.stderr


def test_pi_status_banner_on_stdout(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    monkeypatch.chdir(tmp_path)
    _seed_project_lock(tmp_path)
    r = CliRunner().invoke(cli, ["pi-extension", "status"])
    assert "Operating on project scope" in r.stdout


def test_pi_list_no_banner_when_global_fallback(tmp_path, monkeypatch):
    # Isolate HOME: the global path reads ~/.agent-toolkit via build_inventory.
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    monkeypatch.chdir(tmp_path)  # no pi-extensions-lock.json → global fallback
    r = CliRunner().invoke(cli, ["pi-extension", "list"])
    assert "Operating on project scope" not in r.stdout
    assert "Operating on project scope" not in r.stderr
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_pi_extension_scope_banner.py -k "list or status" -q`
Expected: FAIL — banners not wired.

- [ ] **Step 3: Wire `list`**

`list_cmd.py` is inventory-based (no lock read). Import `read_lock` and
`lock_file_path`, plus `scope_banner`. After `scope_and_roots`, before
`build_inventory`, introduce the lock read for the count, routing to stderr on
`--json`:

```python
from agent_toolkit_cli.commands.pi_extension._common import scope_and_roots, scope_banner
from agent_toolkit_cli.pi_extension_lock import read_lock
from agent_toolkit_cli.pi_extension_paths import lock_file_path
# ...
    lock_path = lock_file_path(scope=scope, home=home, project=project_root)
    scope_banner(
        scope, implicit=implicit, lock_path=lock_path,
        count=len(read_lock(lock_path).skills), err=as_json,
    )
    records = build_inventory(home=home, project=project_root)
```

- [ ] **Step 4: Wire `status`**

`status_cmd.py` is inventory-based, no `--json`. Same introduced read, default
`err` (stdout), after `scope_and_roots`, before `build_inventory`:

```python
from agent_toolkit_cli.commands.pi_extension._common import scope_and_roots, scope_banner
from agent_toolkit_cli.pi_extension_lock import read_lock
from agent_toolkit_cli.pi_extension_paths import lock_file_path
# ...
    lock_path = lock_file_path(scope=scope, home=home, project=project_root)
    scope_banner(
        scope, implicit=implicit, lock_path=lock_path,
        count=len(read_lock(lock_path).skills),
    )
    records = build_inventory(home=home, project=project_root)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_pi_extension_scope_banner.py -k "list or status" -q`
Expected: PASS (4 passed).

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/commands/pi_extension/{list,status}_cmd.py \
        tests/test_cli/test_pi_extension_scope_banner.py
git commit -m "feat(pi-extension): list/status emit scope banner (#420)"
```

---

### Task 4: Wire `update`, `reset`, `push` (lock already read) and `doctor` (introduced read)

**Files:**
- Modify: `src/agent_toolkit_cli/commands/pi_extension/{update,reset,push,doctor}_cmd.py`
- Test: `tests/test_cli/test_pi_extension_scope_banner.py`

- [ ] **Step 1: Write the failing test**

```python
# reset rejects a bare invocation with UsageError BEFORE scope_and_roots, so it
# must be given a slug (the seeded "demo-ext"). update/push reach the banner over
# the no-slug one-entry lock; doctor introduces its own read.
_ARGV = {
    "update": ["pi-extension", "update"],
    "reset": ["pi-extension", "reset", "demo-ext"],
    "push": ["pi-extension", "push"],
    "doctor": ["pi-extension", "doctor"],
}


@pytest.mark.parametrize("verb", ["update", "reset", "push", "doctor"])
def test_pi_read_verb_banner_on_stdout(verb, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    monkeypatch.chdir(tmp_path)
    _seed_project_lock(tmp_path)  # defined in Task 3
    r = CliRunner().invoke(cli, _ARGV[verb])
    assert "Operating on project scope" in r.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_pi_extension_scope_banner.py -k read_verb -q`
Expected: FAIL — banners not wired into these four.

- [ ] **Step 3: Wire `update`, `reset`, `push`**

Each already reads `lock = read_lock(lock_path)` with `lock_path` local. Import
`scope_banner` and, after the read and before the per-slug loop, add:

```python
scope_banner(scope, implicit=implicit, lock_path=lock_path, count=len(lock.skills))
```

- [ ] **Step 4: Wire `doctor`**

`doctor_cmd.py` calls `diagnose(...)` with no body-level lock read. Import
`scope_banner`, `read_lock`, `lock_file_path`, and after `scope_and_roots`,
before `diagnose`, introduce the count read:

```python
from agent_toolkit_cli.commands.pi_extension._common import scope_and_roots, scope_banner
from agent_toolkit_cli.pi_extension_lock import read_lock
from agent_toolkit_cli.pi_extension_paths import lock_file_path
# ...
    lock_path = lock_file_path(scope=scope, home=home, project=project_root)
    scope_banner(
        scope, implicit=implicit, lock_path=lock_path,
        count=len(read_lock(lock_path).skills),
    )
    findings = diagnose(
        slugs=slugs or None,
        scope=scope, home=home, project=project_root,
    )
```

(`pi_extension_lock.read_lock` is the lenient `skill_lock.read_lock` re-export —
empty `LockFile` on a missing file, so safe at implicit-global.)

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_pi_extension_scope_banner.py -k read_verb -q`
Expected: PASS (4 passed).

- [ ] **Step 6: Run the whole pi slice + banner file**

Run: `uv run pytest tests/test_cli -k pi_extension -q && uv run pytest tests/test_cli/test_pi_extension_scope_banner.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/agent_toolkit_cli/commands/pi_extension/{update,reset,push,doctor}_cmd.py \
        tests/test_cli/test_pi_extension_scope_banner.py
git commit -m "feat(pi-extension): update/reset/push/doctor emit scope banner (#420)"
```

---

### Task 5: Full suite + lint/type gates

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest -q`
Expected: PASS (all green; no regressions). Record the count.

- [ ] **Step 2: Lint + type check**

Run: `uv run ruff check src tests && uv run mypy src/agent_toolkit_cli/commands/pi_extension/`
Expected: no *new* ruff/mypy errors vs base.

- [ ] **Step 3: Final commit if cleanup was needed** (skip if clean)

```bash
git add -A && git commit -m "chore(pi-extension): scope-banner lint/type cleanup (#420)"
```

---

## Self-review notes

- **Spec coverage:** 4-tuple (Task 1), `scope_banner` noun/err/zero (Task 2), `list` stdout+`--json` stderr + `status` stdout (Task 3), update/reset/push/doctor stdout (Task 4), suite+gates (Task 5).
- **pi delta — `list`/`status`/`doctor` introduce a lock read** for the count (they're inventory/diagnose-based, not lock-based). update/reset/push already read the lock. Verified against the source.
- **Count is `len(lock.skills)`** (pi lock is a `LockFile`). Verified `read_lock` is the lenient skill re-export.
- **`reset` needs a slug** (UsageError fires pre-`scope_and_roots`). update/push reach the banner bare.
- **`list` has `--json`** (`err=as_json`); `status` does not (always stdout).
- **HOME isolation** in every CLI test (build_inventory's global path reads real `~/.agent-toolkit`).
- **Test import is `main`** (`from agent_toolkit_cli.cli import main`).
- **Unify decision:** copy, not unify; follow-up filed (see spec).
