# #418 — agent implicit-scope banner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the #413 implicit-scope transparency banner to the `agent` asset type — `scope_and_roots` returns a 4th `implicit` element and the agent read verbs print a one-line reminder when scope was resolved implicitly to project.

**Architecture:** Mirror PR #417 (commit `4d0eed1`) inside `commands/agent/`: extend `scope_and_roots` to a 4-tuple, add a `scope_banner` helper (noun "agent(s)"), and wire it into the six agent read verbs (`list`, `status`, `update`, `reset`, `push`, `doctor`). Read-path only; no behaviour change.

**Tech Stack:** Python, Click 8.2+, pytest, `CliRunner` (Click 8.2 splits `result.stdout`/`result.stderr`; no `mix_stderr`).

---

## File structure

- `src/agent_toolkit_cli/commands/agent/_common.py` — extend `scope_and_roots` return to 4-tuple; add `scope_banner`.
- `src/agent_toolkit_cli/commands/agent/{list,status,update,reset,push,doctor}_cmd.py` — unpack 4th element, call `scope_banner` pre-output.
- `tests/test_cli/test_agent_scope_banner.py` — new test file for the helper + wiring.

The agent `scope_and_roots` is typed (`Scope = Literal[...]`, explicit tuple annotation) and parametrised on `_LOCK_FILENAME = AGENT_BINDING.lock_filename`. Keep both; only widen the annotation and add the `implicit` element.

---

### Task 1: `scope_and_roots` returns the `implicit` 4-tuple

**Files:**
- Modify: `src/agent_toolkit_cli/commands/agent/_common.py`
- Test: `tests/test_cli/test_agent_scope_banner.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from agent_toolkit_cli.commands.agent._common import scope_and_roots


def test_scope_and_roots_explicit_global_is_not_implicit():
    assert scope_and_roots(True, False, None) == ("global", Path.home(), None, False)


def test_scope_and_roots_explicit_project_is_not_implicit(tmp_path):
    assert scope_and_roots(False, True, tmp_path) == ("project", None, tmp_path, False)


def test_scope_and_roots_implicit_global_when_read_only_and_no_lock(tmp_path):
    # read_only + no agents-lock.json in cwd → global fallback, implicit=True
    assert scope_and_roots(
        False, False, tmp_path, read_only=True
    ) == ("global", Path.home(), None, True)


def test_scope_and_roots_implicit_project_when_lock_present(tmp_path):
    (tmp_path / "agents-lock.json").write_text("{}")
    assert scope_and_roots(
        False, False, tmp_path, read_only=True
    ) == ("project", None, tmp_path, True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_agent_scope_banner.py -q`
Expected: FAIL — current `scope_and_roots` returns a 3-tuple, so each equality fails.

- [ ] **Step 3: Add the `implicit` element**

In `_common.py`, change the signature annotation and each return:

```python
def scope_and_roots(
    global_: bool,
    project: bool,
    ctx_project: Path | None,
    *,
    read_only: bool = False,
) -> tuple[Scope, Path | None, Path | None, bool]:
    """Resolve (scope, home, project_root, implicit) from CLI flags + context.

    ``implicit`` is True iff neither -g nor -p was passed (scope inferred from
    the presence/absence of <cwd>/agents-lock.json). Read verbs use it to
    decide whether to print a scope reminder (#418, mirrors #413).

    Convention (cross-cutting, verified):
      - READ verbs pass read_only=True so they default to global outside a
        project (no agents-lock.json in cwd).
      - WRITE verbs do NOT pass read_only; they default to project scope.
    """
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

Run: `uv run pytest tests/test_cli/test_agent_scope_banner.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Update the call sites that unpack the 3-tuple**

Every call site listed below unpacks 3 names; add the 4th. For read verbs that will use it, name it `implicit`; for write verbs that ignore it, name it `_implicit` to satisfy the linter:

- `agent/list_cmd.py:84` → `scope, home, project_root, implicit = scope_and_roots(`
- `agent/status_cmd.py:67` → `scope, home, project_root, implicit = scope_and_roots(`
- `agent/update_cmd.py:34` → `scope, home, project_root, implicit = scope_and_roots(`
- `agent/reset_cmd.py:41` → `scope, home, project_root, implicit = scope_and_roots(`
- `agent/push_cmd.py:47` → `scope, home, project_root, implicit = scope_and_roots(`
- `agent/doctor_cmd.py:420` → `scope, home, project_root, implicit = scope_and_roots(`
- `agent/install_cmd.py:94` → `scope, home, project, _implicit = scope_and_roots(`
- `agent/uninstall_cmd.py:78` → `scope, home, project, _implicit = scope_and_roots(`

(The read verbs get `scope_banner` wired in later tasks; install/uninstall just absorb the 4th element.)

- [ ] **Step 6: Run the full agent CLI test slice to verify nothing else broke**

Run: `uv run pytest tests/test_cli -k agent -q`
Expected: PASS (no unpack errors).

- [ ] **Step 7: Commit**

```bash
git add src/agent_toolkit_cli/commands/agent/_common.py \
        src/agent_toolkit_cli/commands/agent/*_cmd.py \
        tests/test_cli/test_agent_scope_banner.py
git commit -m "feat(agent): scope_and_roots returns implicit flag (#418)"
```

---

### Task 2: `scope_banner` helper

**Files:**
- Modify: `src/agent_toolkit_cli/commands/agent/_common.py`
- Test: `tests/test_cli/test_agent_scope_banner.py`

- [ ] **Step 1: Write the failing test**

```python
import click
from click.testing import CliRunner

from agent_toolkit_cli.commands.agent._common import scope_banner


def _run(**kwargs):
    @click.command()
    def cmd():
        scope_banner(**kwargs)
    return CliRunner().invoke(cmd, [])


def test_banner_prints_on_implicit_project_plural():
    r = _run(scope="project", implicit=True, lock_path="/p/agents-lock.json", count=3)
    assert "Operating on project scope — /p/agents-lock.json (3 agents)." in r.stdout
    assert "Pass -g for the global library." in r.stdout


def test_banner_singular_noun():
    r = _run(scope="project", implicit=True, lock_path="/p/agents-lock.json", count=1)
    assert "(1 agent)." in r.stdout


def test_banner_count_zero_still_prints():
    r = _run(scope="project", implicit=True, lock_path="/p/agents-lock.json", count=0)
    assert "(0 agents)." in r.stdout


def test_banner_silent_on_implicit_global():
    r = _run(scope="global", implicit=True, lock_path="/x", count=5)
    assert r.stdout == ""


def test_banner_silent_on_explicit_project():
    r = _run(scope="project", implicit=False, lock_path="/x", count=5)
    assert r.stdout == ""


def test_banner_err_routes_to_stderr():
    r = _run(scope="project", implicit=True, lock_path="/p", count=2, err=True)
    assert r.stdout == ""
    assert "Operating on project scope" in r.stderr
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_agent_scope_banner.py -k banner -q`
Expected: FAIL — `scope_banner` not defined (ImportError).

- [ ] **Step 3: Add the helper**

In `_common.py`, after `scope_and_roots`:

```python
def scope_banner(scope, *, implicit, lock_path, count, err=False) -> None:
    """Print a one-line scope reminder on implicit-project resolution.

    Best-effort and informational: never raises, never affects exit codes.
    Silent unless scope was resolved implicitly (no -g/-p) AND landed on
    project — the one case (#418, mirrors #413) where the user got no signal
    about which lock was picked. Goes to stdout by default (so a human sees it
    inline with the verb output); callers emitting a machine stream pass
    ``err=True`` to route it to stderr instead (today only ``list --json``).
    """
    if not (implicit and scope == "project"):
        return
    noun = "agent" if count == 1 else "agents"
    click.echo(
        f"Operating on project scope — {lock_path} ({count} {noun}). "
        f"Pass -g for the global library.",
        err=err,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_agent_scope_banner.py -k banner -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/agent/_common.py \
        tests/test_cli/test_agent_scope_banner.py
git commit -m "feat(agent): scope_banner helper, stdout/stderr-aware (#418)"
```

---

### Task 3: Wire `list` (human stdout + `--json` stderr)

**Files:**
- Modify: `src/agent_toolkit_cli/commands/agent/list_cmd.py`
- Test: `tests/test_cli/test_agent_scope_banner.py`

- [ ] **Step 1: Write the failing test**

```python
import json

from click.testing import CliRunner

from agent_toolkit_cli.cli import main as cli  # entrypoint symbol is `main`


def _seed_project_lock(tmp_path):
    """A minimal valid agents-lock.json with one entry, in tmp_path."""
    (tmp_path / "agents-lock.json").write_text(
        json.dumps({
            "version": 1,
            "skills": {
                "demo-agent": {
                    "source": "https://example.com/demo-agent",
                    "sourceType": "git",
                    "ref": "main",
                }
            },
        })
    )


def test_agent_list_human_banner_on_stdout(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_project_lock(tmp_path)
    r = CliRunner().invoke(cli, ["agent", "list"])
    assert r.exit_code == 0
    assert "Operating on project scope" in r.stdout
    assert "(1 agent)." in r.stdout


def test_agent_list_json_banner_on_stderr_stdout_is_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_project_lock(tmp_path)
    r = CliRunner().invoke(cli, ["agent", "list", "--json"])
    assert r.exit_code == 0
    json.loads(r.stdout)  # stdout parses clean
    assert "Operating on project scope" in r.stderr


def test_agent_list_no_banner_when_global_fallback(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # no agents-lock.json → global fallback
    r = CliRunner().invoke(cli, ["agent", "list"])
    assert "Operating on project scope" not in r.stdout
    assert "Operating on project scope" not in r.stderr
```

> Verify the lock JSON schema against `agent_lock.read_lock` before running — adjust keys (`sourceType`/`ref`) to whatever `read_lock` requires. If `read_lock` rejects the hand-written file, build it via the existing `agent add` flow or an existing fixture (`installed_agent`/`git_sandbox`) instead.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_agent_scope_banner.py -k list -q`
Expected: FAIL — no banner emitted yet.

- [ ] **Step 3: Wire the banner into `list_cmd`**

Import the helper and call it after a successful `read_lock`, before emitting. The agent `list` JSON path bails on `FileNotFoundError`; place the banner after the successful lock read on both the JSON and human branches. Pass `err=as_json` (stderr for JSON, stdout for human), mirroring skill's `list`:

```python
from agent_toolkit_cli.commands.agent._common import scope_and_roots, scope_banner
# ...
    try:
        lock = read_lock(lock_file_path(scope=scope, home=home, project=project_root))
    except FileNotFoundError:
        # (unchanged early-return)
        ...
        return

    scope_banner(
        scope, implicit=implicit, lock_path=lock_path,
        count=len(lock.skills), err=as_json,
    )
```

Where `lock_path = lock_file_path(scope=scope, home=home, project=project_root)` — compute it once and reuse for both `read_lock` and `scope_banner` (skill's `list` does exactly this).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_agent_scope_banner.py -k list -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/agent/list_cmd.py \
        tests/test_cli/test_agent_scope_banner.py
git commit -m "feat(agent): list emits scope banner (stdout; stderr for --json) (#418)"
```

---

### Task 4: Wire `status`, `update`, `reset`, `push`, `doctor` (human stdout)

**Files:**
- Modify: `src/agent_toolkit_cli/commands/agent/{status,update,reset,push,doctor}_cmd.py`
- Test: `tests/test_cli/test_agent_scope_banner.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main as cli  # entrypoint symbol is `main`


# reset (and push) iterate over targets and reject a bare invocation with a
# UsageError that fires BEFORE scope_and_roots — so they must be given a slug,
# else the banner never reaches stdout. The slug-bearing entry is the one seeded
# by _seed_project_lock ("demo-agent"). status/update/push/doctor reach the
# banner over a no-slug one-entry lock; reset needs the explicit slug.
_ARGV = {
    "status": ["agent", "status"],
    "update": ["agent", "update"],
    "reset": ["agent", "reset", "demo-agent"],
    "push": ["agent", "push"],
    "doctor": ["agent", "doctor"],
}


@pytest.mark.parametrize("verb", ["status", "update", "reset", "push", "doctor"])
def test_agent_read_verb_banner_on_stdout(verb, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_project_lock(tmp_path)  # defined in Task 3
    r = CliRunner().invoke(cli, _ARGV[verb])
    # Banner is advisory; the verb may still exit non-zero for other reasons
    # (e.g. nothing to update). We only assert the banner appears on stdout.
    assert "Operating on project scope" in r.stdout
```

> Verified against the reference: #413's reset/push test cases invoke the verb
> *with* a slug for exactly this reason. If a verb's behaviour over the one-entry
> lock still makes the assertion flaky (e.g. it errors before output), seed
> whatever that verb needs, or assert against a no-op invocation. Keep the
> banner-before-output ordering the real requirement.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_agent_scope_banner.py -k read_verb -q`
Expected: FAIL — banners not wired into these five verbs.

- [ ] **Step 3: Wire each verb**

For `status_cmd.py`, `update_cmd.py`, `reset_cmd.py`, `push_cmd.py`: import
`scope_banner` alongside `scope_and_roots`, then after the successful `read_lock`
and before the verb's main output add:

```python
scope_banner(scope, implicit=implicit, lock_path=lock_path, count=len(lock.skills))
```

Compute `lock_path` once (reuse the path passed to `read_lock`). For verbs that
currently inline `read_lock(lock_file_path(...))`, hoist the path into a local
`lock_path` first so the banner can reuse it. Place the call after any
early-return (`FileNotFoundError`, empty-lock) guard so it only fires when there
is a real project lock — matching skill's wiring. (`update`/`reset`/`push` each
already read the lock via `read_lock(lock_path)` near the top with `lock_path`
local; the banner slots in right after the `try/except`, before the per-slug
loop.)

**`doctor_cmd.py` is different — it has NO body-level lock read.** Its command
body calls `scope_and_roots` (line 420) then `_diagnose(...)` (line ~425), which
returns a findings list, not a lock — the lock is read *inside* `_diagnose` and
never surfaced. So introduce a standalone lock read purely for the banner count,
mirroring `skill/doctor_cmd.py:33-37` exactly. `agent/doctor_cmd.py` already
imports `read_lock` and `lock_file_path`, so only `scope_banner` needs importing.
Between the `scope_and_roots` unpack and the `_diagnose(...)` call, add:

```python
lock_path = lock_file_path(scope=scope, home=home, project=project_root)
scope_banner(
    scope, implicit=implicit, lock_path=lock_path,
    count=len(read_lock(lock_path).skills),
)
```

`read_lock` returns an empty `LockFile` on a missing file (it is the same lenient
`skill_lock.read_lock`, re-exported), so this is safe at implicit-global too
(`scope_banner` stays silent there regardless).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_agent_scope_banner.py -k read_verb -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Run the whole agent slice + banner file**

Run: `uv run pytest tests/test_cli -k agent -q && uv run pytest tests/test_cli/test_agent_scope_banner.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/commands/agent/{status,update,reset,push,doctor}_cmd.py \
        tests/test_cli/test_agent_scope_banner.py
git commit -m "feat(agent): status/update/reset/push/doctor emit scope banner (#418)"
```

---

### Task 5: Full suite + lint/type gates

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest -q`
Expected: PASS (all green; no regressions vs base). Record the count.

- [ ] **Step 2: Lint + type check**

Run: `uv run ruff check src tests && uv run mypy src` (record counts vs base — no *new* errors introduced).
Expected: no new ruff/mypy errors attributable to this change. The agent
`scope_and_roots` annotation is already explicit, so the 4-tuple is fully typed.

- [ ] **Step 3: Final commit if any cleanup was needed**

```bash
git add -A && git commit -m "chore(agent): scope-banner lint/type cleanup (#418)"
```

(Skip if Steps 1–2 were clean with nothing to commit.)

---

## Self-review notes

- **Spec coverage:** 4-tuple (Task 1), `scope_banner` noun/err/zero-count (Task 2), `list` stdout+`--json` stderr (Task 3), five read verbs stdout (Task 4), suite+gates (Task 5). All spec § Test surface bullets map to a task.
- **No monorepo refusal** in agent (skill-specific) — correctly absent.
- **Lock object:** agent uses the shared `Lock` with `.skills`; `count=len(lock.skills)` is correct (verified against `list_cmd`/`status_cmd`).
- **Click 8.2 stderr split:** tests use bare `CliRunner()`; assert on `result.stdout`/`result.stderr` separately — no `mix_stderr`.
