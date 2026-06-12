# push not-in-lock cross-scope hint + exit 1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When `skill|agent|pi-extension push <slug>` can't find the slug in the resolved scope's lock, hint if it lives in the other scope's lock and exit 1 (issue #371).

**Architecture:** Each of the three push command modules gets one private helper `_missing_slug_message(slug, scope, ctx_project)` that probes the other scope's lock (read-only, crash-proof — `read_lock` returns an empty lock for missing files) and returns the message. The `not in lock` branch echoes it and sets the existing `rejected = True` flag, feeding the existing `ctx.exit(1)` tail. The three modules are deliberate near-clones; the change is cloned, not extracted.

**Tech Stack:** Python 3.13, Click, pytest + CliRunner. Spec: `docs/superpowers/specs/2026-06-12-push-not-in-lock-cross-scope-design.md`.

**Verification baseline:** main @ dba6d20. Run tests with `uv run pytest`. Two pre-existing environment failures are whitelisted: `test_empty_machine_is_empty`, `test_build_instruction_rows_empty_lock_no_canonical` (HOME-isolation, fail locally on any branch).

**Commit discipline (parallel-checkout rule):** this checkout is shared with sibling issue-preps/runs. Always commit with `git add <file>... && git commit --only <file>...` — never `git add -A` / `commit -a`. Leave pre-existing `skills-lock.json` / `uv.lock` modifications untouched. (At /aj-run time this lands in its own worktree and the rule is just good hygiene.)

---

## File structure

| File | Change |
|---|---|
| `src/agent_toolkit_cli/commands/skill/push_cmd.py` | helper + branch change (lines 65-67) |
| `src/agent_toolkit_cli/commands/agent/push_cmd.py` | helper + branch change (lines 63-65) |
| `src/agent_toolkit_cli/commands/pi_extension/push_cmd.py` | helper + branch change (lines 62-64) |
| `tests/test_cli/test_cli_skill_push.py` | 4 new tests + `_seed_lock` helper |
| `tests/test_cli/test_cli_agent_group.py` | 4 new tests + local seed helper |
| `tests/test_cli/test_cli_pi_extension_write.py` | 4 new tests + local seed helper |

Lock-path facts the tests rely on (verified):

- A minimal valid v1 lock is `{"version": 1, "skills": {"<slug>": {"source": "acme/x", "sourceType": "github"}}}`; `read_lock` on a missing path returns an empty `LockFile` (never raises).
- Skill global lock: `$AGENT_TOOLKIT_SKILLS_ROOT/../skills-lock.json` (the env override applies to skills only). Agent/pi-extension global locks: `$HOME/.agent-toolkit/agents-lock.json` / `$HOME/.agent-toolkit/pi-extensions-lock.json` (isolate via `monkeypatch.setenv("HOME", ...)`).
- Project locks: `<project>/skills-lock.json`, `<project>/agents-lock.json`, `<project>/pi-extensions-lock.json`.
- The top-level CLI option `--project <dir>` sets `ctx.obj["project_root"]`; push resolves to project scope (no flags) only when the project lock file exists — so seed an (empty) project lock to pin project scope, exactly the real trap.

---

### Task 1: skill push

**Files:**
- Modify: `src/agent_toolkit_cli/commands/skill/push_cmd.py`
- Test: `tests/test_cli/test_cli_skill_push.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli/test_cli_skill_push.py`:

```python
def _seed_lock(path: Path, slugs: list[str]) -> None:
    """Write a minimal v1 lock with bare github entries for `slugs`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "version": 1,
        "skills": {
            s: {"source": "acme/skills", "sourceType": "github"} for s in slugs
        },
    }))


def test_push_project_scope_hints_global_lock(tmp_path, monkeypatch):
    """Slug only in the GLOBAL lock, resolved scope project → hint + exit 1 (#371)."""
    library_root = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    project = tmp_path / "proj"
    project.mkdir()
    _seed_lock(tmp_path / "lib" / "skills-lock.json", ["demo"])
    _seed_lock(project / "skills-lock.json", [])
    result = CliRunner().invoke(
        main, ["--project", str(project), "skill", "push", "demo"],
    )
    assert result.exit_code == 1, result.output
    assert "demo: not in the project lock" in result.output
    assert "found in the global lock — re-run with -g" in result.output


def test_push_global_scope_hints_project_lock(tmp_path, monkeypatch):
    """Slug only in the PROJECT lock, -g forces global → inverse hint + exit 1."""
    library_root = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    project = tmp_path / "proj"
    project.mkdir()
    _seed_lock(tmp_path / "lib" / "skills-lock.json", [])
    _seed_lock(project / "skills-lock.json", ["demo"])
    result = CliRunner().invoke(
        main, ["--project", str(project), "skill", "push", "-g", "demo"],
    )
    assert result.exit_code == 1, result.output
    assert "demo: not in the global lock" in result.output
    assert "found in the project lock — re-run with -p" in result.output


def test_push_slug_in_neither_lock_exits_nonzero(tmp_path, monkeypatch):
    """Slug nowhere → scope-naming message, no hint, exit 1."""
    library_root = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    project = tmp_path / "proj"
    project.mkdir()
    _seed_lock(tmp_path / "lib" / "skills-lock.json", [])
    _seed_lock(project / "skills-lock.json", [])
    result = CliRunner().invoke(
        main, ["--project", str(project), "skill", "push", "ghost"],
    )
    assert result.exit_code == 1, result.output
    assert "ghost: not in the project lock" in result.output
    assert "found in" not in result.output


def test_bare_push_empty_lock_unchanged(tmp_path, monkeypatch):
    """Bare push takes targets from the lock — never hits the branch; exit 0."""
    library_root = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    project = tmp_path / "proj"
    project.mkdir()
    _seed_lock(project / "skills-lock.json", [])
    result = CliRunner().invoke(
        main, ["--project", str(project), "skill", "push"],
    )
    assert result.exit_code == 0, result.output
    assert "not in the" not in result.output
```

(`json`, `Path`, `CliRunner`, `main` are already imported at the top of this module.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli/test_cli_skill_push.py -k "hints or neither or bare_push_empty" -v`
Expected: the three new assertion-bearing tests FAIL (exit code 0 instead of 1 / old `not in lock` wording); `test_bare_push_empty_lock_unchanged` may already PASS (it is a regression guard).

- [ ] **Step 3: Implement**

In `src/agent_toolkit_cli/commands/skill/push_cmd.py`:

3a. Hoist the ctx-project expression into a local (it is needed twice now). Replace lines 54-59:

```python
    ctx_project = ctx.obj.get("project_root") if ctx.obj else None
    scope, home, project_root = scope_and_roots(
        global_,
        project_flag,
        ctx_project,
        read_only=True,
    )
```

3b. Replace the not-in-lock branch (`if slug not in lock.skills: click.echo(f"{slug}: not in lock"); continue`):

```python
        if slug not in lock.skills:
            click.echo(_missing_slug_message(slug, scope, ctx_project))
            rejected = True
            continue
```

3c. Add the helper (place it directly after `push_cmd`, before `_push_direct`):

```python
def _missing_slug_message(
    slug: str, scope: str, ctx_project: Path | None,
) -> str:
    """Message for an explicitly named slug missing from the resolved scope's
    lock (#371). Probes the OTHER scope's lock so a slug that lives there gets
    a re-run hint instead of a bare "not in lock". `read_lock` returns an
    empty lock for a missing/corrupt file, so the probe never raises. The
    project root is re-derived here because `scope_and_roots` returns
    `project_root=None` at global scope even when the cwd is a project."""
    if scope == "project":
        other = read_lock(lock_file_path(scope="global", home=Path.home()))
        if slug in other.skills:
            return (
                f"{slug}: not in the project lock "
                f"(found in the global lock — re-run with -g)"
            )
        return f"{slug}: not in the project lock"
    other_root = ctx_project or Path.cwd()
    other = read_lock(lock_file_path(scope="project", project=other_root))
    if slug in other.skills:
        return (
            f"{slug}: not in the global lock "
            f"(found in the project lock — re-run with -p)"
        )
    return f"{slug}: not in the global lock"
```

(`read_lock`, `lock_file_path`, `Path` are already imported in this module.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli/test_cli_skill_push.py -v`
Expected: ALL tests in the module PASS (the 4 new ones plus all pre-existing — notably `test_push_*` global-fallback tests, which exercise the slug-found path and are unaffected).

- [ ] **Step 5: Commit**

```bash
git add tests/test_cli/test_cli_skill_push.py src/agent_toolkit_cli/commands/skill/push_cmd.py
git commit --only tests/test_cli/test_cli_skill_push.py --only src/agent_toolkit_cli/commands/skill/push_cmd.py -m "fix(skill): push not-in-lock hints the other scope's lock and exits 1 (#371)"
```

(If pre-commit fails ONLY on the 2 whitelisted HOME-isolation tests, `--no-verify` is approved.)

---

### Task 2: agent push

**Files:**
- Modify: `src/agent_toolkit_cli/commands/agent/push_cmd.py`
- Test: `tests/test_cli/test_cli_agent_group.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli/test_cli_agent_group.py`:

```python
def _seed_agent_lock(path, slugs):
    """Minimal v1 agents lock with bare github entries for `slugs`."""
    import json as _json
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json.dumps({
        "version": 1,
        "skills": {
            s: {"source": "acme/agents", "sourceType": "github"} for s in slugs
        },
    }))


def test_agent_push_project_scope_hints_global_lock(tmp_path, monkeypatch):
    """Slug only in the GLOBAL agents lock, resolved scope project → hint + exit 1 (#371)."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    project = tmp_path / "proj"
    project.mkdir()
    _seed_agent_lock(home / ".agent-toolkit" / "agents-lock.json", ["my-agent"])
    _seed_agent_lock(project / "agents-lock.json", [])
    result = CliRunner().invoke(
        main, ["--project", str(project), "agent", "push", "my-agent"],
    )
    assert result.exit_code == 1, result.output
    assert "my-agent: not in the project lock" in result.output
    assert "found in the global lock — re-run with -g" in result.output


def test_agent_push_global_scope_hints_project_lock(tmp_path, monkeypatch):
    """Slug only in the PROJECT agents lock, -g forces global → inverse hint + exit 1."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    project = tmp_path / "proj"
    project.mkdir()
    _seed_agent_lock(home / ".agent-toolkit" / "agents-lock.json", [])
    _seed_agent_lock(project / "agents-lock.json", ["my-agent"])
    result = CliRunner().invoke(
        main, ["--project", str(project), "agent", "push", "-g", "my-agent"],
    )
    assert result.exit_code == 1, result.output
    assert "my-agent: not in the global lock" in result.output
    assert "found in the project lock — re-run with -p" in result.output


def test_agent_push_slug_in_neither_lock_exits_nonzero(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    project = tmp_path / "proj"
    project.mkdir()
    _seed_agent_lock(home / ".agent-toolkit" / "agents-lock.json", [])
    _seed_agent_lock(project / "agents-lock.json", [])
    result = CliRunner().invoke(
        main, ["--project", str(project), "agent", "push", "ghost"],
    )
    assert result.exit_code == 1, result.output
    assert "ghost: not in the project lock" in result.output
    assert "found in" not in result.output


def test_agent_bare_push_empty_lock_unchanged(tmp_path, monkeypatch):
    """Bare push takes targets from the lock — never hits the branch; exit 0."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    project = tmp_path / "proj"
    project.mkdir()
    _seed_agent_lock(project / "agents-lock.json", [])
    result = CliRunner().invoke(
        main, ["--project", str(project), "agent", "push"],
    )
    assert result.exit_code == 0, result.output
    assert "not in the" not in result.output
```

(Match this module's existing imports: it already has `CliRunner` and `main`; keep the local `import json as _json` inside the helper if `json` is not module-level.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli/test_cli_agent_group.py -k "push_project_scope_hints or push_global_scope_hints or push_slug_in_neither" -v`
Expected: all three FAIL (exit code 0, old `not in lock` wording).

- [ ] **Step 3: Implement**

In `src/agent_toolkit_cli/commands/agent/push_cmd.py`:

3a. Hoist the ctx-project local (replace lines 46-51):

```python
    ctx_project = ctx.obj.get("project_root") if ctx.obj else None
    scope, home, project_root = scope_and_roots(
        global_,
        project_flag,
        ctx_project,
        read_only=True,
    )
```

3b. Replace the not-in-lock branch:

```python
        if slug not in lock.skills:
            click.echo(_missing_slug_message(slug, scope, ctx_project))
            rejected = True
            continue
```

3c. Add the helper after `push_cmd` (same docstring rationale as the skill clone):

```python
def _missing_slug_message(
    slug: str, scope: str, ctx_project: Path | None,
) -> str:
    """Message for an explicitly named slug missing from the resolved scope's
    lock (#371). Probes the OTHER scope's lock so a slug that lives there gets
    a re-run hint instead of a bare "not in lock". `read_lock` returns an
    empty lock for a missing/corrupt file, so the probe never raises. The
    project root is re-derived here because `scope_and_roots` returns
    `project_root=None` at global scope even when the cwd is a project."""
    if scope == "project":
        other = read_lock(lock_file_path(scope="global", home=Path.home()))
        if slug in other.skills:
            return (
                f"{slug}: not in the project lock "
                f"(found in the global lock — re-run with -g)"
            )
        return f"{slug}: not in the project lock"
    other_root = ctx_project or Path.cwd()
    other = read_lock(lock_file_path(scope="project", project=other_root))
    if slug in other.skills:
        return (
            f"{slug}: not in the global lock "
            f"(found in the project lock — re-run with -p)"
        )
    return f"{slug}: not in the global lock"
```

Note: this module wraps its scope-resolved `read_lock` in `try/except FileNotFoundError` ("no agents lock found"). That except is dead code (`read_lock` returns an empty lock instead of raising) — leave it as-is; out of scope per the spec.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli/test_cli_agent_group.py -v`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_cli/test_cli_agent_group.py src/agent_toolkit_cli/commands/agent/push_cmd.py
git commit --only tests/test_cli/test_cli_agent_group.py --only src/agent_toolkit_cli/commands/agent/push_cmd.py -m "fix(agent): push not-in-lock hints the other scope's lock and exits 1 (#371)"
```

---

### Task 3: pi-extension push

**Files:**
- Modify: `src/agent_toolkit_cli/commands/pi_extension/push_cmd.py`
- Test: `tests/test_cli/test_cli_pi_extension_write.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli/test_cli_pi_extension_write.py`:

```python
def _seed_pi_lock(path, slugs):
    """Minimal v1 pi-extensions lock with bare github entries for `slugs`."""
    import json as _json
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json.dumps({
        "version": 1,
        "skills": {
            s: {"source": "acme/pi-extensions", "sourceType": "github"}
            for s in slugs
        },
    }))


def test_push_project_scope_hints_global_lock(tmp_path, monkeypatch):
    """Slug only in the GLOBAL pi-extensions lock, resolved scope project → hint + exit 1 (#371)."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    project = tmp_path / "proj"
    project.mkdir()
    _seed_pi_lock(home / ".agent-toolkit" / "pi-extensions-lock.json", ["my-ext"])
    _seed_pi_lock(project / "pi-extensions-lock.json", [])
    result = CliRunner().invoke(
        main, ["--project", str(project), "pi-extension", "push", "my-ext"],
    )
    assert result.exit_code == 1, result.output
    assert "my-ext: not in the project lock" in result.output
    assert "found in the global lock — re-run with -g" in result.output


def test_push_global_scope_hints_project_lock(tmp_path, monkeypatch):
    """Slug only in the PROJECT pi-extensions lock, -g forces global → inverse hint + exit 1."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    project = tmp_path / "proj"
    project.mkdir()
    _seed_pi_lock(home / ".agent-toolkit" / "pi-extensions-lock.json", [])
    _seed_pi_lock(project / "pi-extensions-lock.json", ["my-ext"])
    result = CliRunner().invoke(
        main, ["--project", str(project), "pi-extension", "push", "-g", "my-ext"],
    )
    assert result.exit_code == 1, result.output
    assert "my-ext: not in the global lock" in result.output
    assert "found in the project lock — re-run with -p" in result.output


def test_push_slug_in_neither_lock_exits_nonzero(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    project = tmp_path / "proj"
    project.mkdir()
    _seed_pi_lock(home / ".agent-toolkit" / "pi-extensions-lock.json", [])
    _seed_pi_lock(project / "pi-extensions-lock.json", [])
    result = CliRunner().invoke(
        main, ["--project", str(project), "pi-extension", "push", "ghost"],
    )
    assert result.exit_code == 1, result.output
    assert "ghost: not in the project lock" in result.output
    assert "found in" not in result.output


def test_bare_push_empty_lock_unchanged(tmp_path, monkeypatch):
    """Bare push takes targets from the lock — never hits the branch; exit 0."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    project = tmp_path / "proj"
    project.mkdir()
    _seed_pi_lock(project / "pi-extensions-lock.json", [])
    result = CliRunner().invoke(
        main, ["--project", str(project), "pi-extension", "push"],
    )
    assert result.exit_code == 0, result.output
    assert "not in the" not in result.output
```

(Match this module's existing imports; it already has `CliRunner` and `main`.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli/test_cli_pi_extension_write.py -k "push_project_scope_hints or push_global_scope_hints or push_slug_in_neither" -v`
Expected: all three FAIL (exit code 0, old wording).

- [ ] **Step 3: Implement**

In `src/agent_toolkit_cli/commands/pi_extension/push_cmd.py`:

3a. Hoist the ctx-project local (replace lines 50-55):

```python
    ctx_project = ctx.obj.get("project_root") if ctx.obj else None
    scope, home, project_root = scope_and_roots(
        global_,
        project_flag,
        ctx_project,
        read_only=True,
    )
```

3b. Replace the not-in-lock branch:

```python
        if slug not in lock.skills:
            click.echo(_missing_slug_message(slug, scope, ctx_project))
            rejected = True
            continue
```

3c. Add the helper after `push_cmd`:

```python
def _missing_slug_message(
    slug: str, scope: str, ctx_project: Path | None,
) -> str:
    """Message for an explicitly named slug missing from the resolved scope's
    lock (#371). Probes the OTHER scope's lock so a slug that lives there gets
    a re-run hint instead of a bare "not in lock". `read_lock` returns an
    empty lock for a missing/corrupt file, so the probe never raises. The
    project root is re-derived here because `scope_and_roots` returns
    `project_root=None` at global scope even when the cwd is a project."""
    if scope == "project":
        other = read_lock(lock_file_path(scope="global", home=Path.home()))
        if slug in other.skills:
            return (
                f"{slug}: not in the project lock "
                f"(found in the global lock — re-run with -g)"
            )
        return f"{slug}: not in the project lock"
    other_root = ctx_project or Path.cwd()
    other = read_lock(lock_file_path(scope="project", project=other_root))
    if slug in other.skills:
        return (
            f"{slug}: not in the global lock "
            f"(found in the project lock — re-run with -p)"
        )
    return f"{slug}: not in the global lock"
```

(`read_lock`, `lock_file_path`, `Path` are already imported in this module.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli/test_cli_pi_extension_write.py -v`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_cli/test_cli_pi_extension_write.py src/agent_toolkit_cli/commands/pi_extension/push_cmd.py
git commit --only tests/test_cli/test_cli_pi_extension_write.py --only src/agent_toolkit_cli/commands/pi_extension/push_cmd.py -m "fix(pi-extension): push not-in-lock hints the other scope's lock and exits 1 (#371)"
```

---

### Task 4: full-suite verification

- [ ] **Step 1: Run the full suite**

Run: `uv run pytest`
Expected: green, except (possibly) the 2 whitelisted HOME-isolation environment failures (`test_empty_machine_is_empty`, `test_build_instruction_rows_empty_lock_no_canonical`) — both reproduce on clean main and are NOT caused by this change.

- [ ] **Step 2: Lint + types**

Run: `uv run ruff check src/agent_toolkit_cli/commands/skill/push_cmd.py src/agent_toolkit_cli/commands/agent/push_cmd.py src/agent_toolkit_cli/commands/pi_extension/push_cmd.py tests/test_cli/test_cli_skill_push.py tests/test_cli/test_cli_agent_group.py tests/test_cli/test_cli_pi_extension_write.py && uv run mypy src/agent_toolkit_cli/commands/skill/push_cmd.py src/agent_toolkit_cli/commands/agent/push_cmd.py src/agent_toolkit_cli/commands/pi_extension/push_cmd.py`
Expected: no NEW findings vs main on these files (main carries pre-existing repo-wide ruff/mypy counts — the bar is no-new-errors, not zero).

- [ ] **Step 3: Manual smoke (optional, sandbox HOME)**

```bash
HOME=$(mktemp -d) uv run agent-toolkit-cli skill push ghost -g; echo "exit=$?"
```
Expected: `ghost: not in the global lock` and `exit=1`.
