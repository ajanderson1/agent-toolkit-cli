# #419 — mcp implicit-scope banner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the #413 implicit-scope transparency banner to the `mcp` asset type — `scope_and_roots` returns a 4th `implicit` element and the mcp read verbs (`list`, `status`, `doctor`) print a one-line reminder when scope was resolved implicitly to project.

**Architecture:** Mirror PR #417 / #424 inside `commands/mcp/`, adapting two mcp specifics: the lock is a plain `dict` (count = `len(lock)`, not `len(lock.skills)`), and there is **no `--json` read verb** (banner is always stdout; no `err=True` caller). `mcp update` is NOT wired — it doesn't use `scope_and_roots`.

**Tech Stack:** Python, Click 8.2+, pytest, `CliRunner` (`from agent_toolkit_cli.cli import main`).

---

## File structure

- `src/agent_toolkit_cli/commands/mcp/_common.py` — `scope_and_roots` → 4-tuple; add `scope_banner` (noun "MCP server(s)").
- `src/agent_toolkit_cli/commands/mcp/{list,status,doctor}_cmd.py` — unpack 4th element, call `scope_banner` pre-output.
- `src/agent_toolkit_cli/commands/mcp/{install,uninstall,remove}_cmd.py` — absorb the 4th element as `_implicit`.
- `tests/test_cli/test_mcp_scope_banner.py` — new test file.

---

### Task 1: `scope_and_roots` returns the `implicit` 4-tuple

**Files:**
- Modify: `src/agent_toolkit_cli/commands/mcp/_common.py`
- Test: `tests/test_cli/test_mcp_scope_banner.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from agent_toolkit_cli.commands.mcp._common import scope_and_roots


def test_scope_and_roots_explicit_global_is_not_implicit():
    assert scope_and_roots(True, False, None) == ("global", Path.home(), None, False)


def test_scope_and_roots_explicit_project_is_not_implicit(tmp_path):
    assert scope_and_roots(False, True, tmp_path) == ("project", None, tmp_path, False)


def test_scope_and_roots_implicit_global_when_read_only_and_no_lock(tmp_path):
    assert scope_and_roots(False, False, tmp_path, read_only=True) == (
        "global", Path.home(), None, True,
    )


def test_scope_and_roots_implicit_project_when_lock_present(tmp_path):
    (tmp_path / "mcps-lock.json").write_text('{"mcps": {}}')
    assert scope_and_roots(False, False, tmp_path, read_only=True) == (
        "project", None, tmp_path, True,
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_mcp_scope_banner.py -q`
Expected: FAIL — current `scope_and_roots` returns a 3-tuple.

- [ ] **Step 3: Add the `implicit` element**

In `mcp/_common.py`, widen the return annotation to
`tuple[Scope, Path | None, Path | None, bool]`, update the docstring to mention
`implicit` (True iff no -g/-p, inferred from `<cwd>/mcps-lock.json`), and append
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

Run: `uv run pytest tests/test_cli/test_mcp_scope_banner.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Update the call sites that unpack the 3-tuple**

Read verbs → name the 4th `implicit`; write verbs → `_implicit`:

- `mcp/list_cmd.py:78` → `scope, home, project_root, implicit = scope_and_roots(`
- `mcp/status_cmd.py:29` → `scope, home, project_root, implicit = scope_and_roots(`
- `mcp/doctor_cmd.py:213` → `scope, home, project_root, implicit = scope_and_roots(`
- `mcp/install_cmd.py:57` → `scope, home, project, _implicit = scope_and_roots(`
- `mcp/uninstall_cmd.py:56` → `scope, home, project, _implicit = scope_and_roots(`
- `mcp/remove_cmd.py:46` → `scope, home, project, _implicit = scope_and_roots(`

(`mcp update` does NOT call `scope_and_roots`, so it is untouched.)

- [ ] **Step 6: Run the mcp CLI slice to verify no unpack errors**

Run: `uv run pytest tests/test_cli tests/test_cli_mcp.py -k mcp -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/agent_toolkit_cli/commands/mcp/_common.py \
        src/agent_toolkit_cli/commands/mcp/*_cmd.py \
        tests/test_cli/test_mcp_scope_banner.py
git commit -m "feat(mcp): scope_and_roots returns implicit flag (#419)"
```

---

### Task 2: `scope_banner` helper

**Files:**
- Modify: `src/agent_toolkit_cli/commands/mcp/_common.py`
- Test: `tests/test_cli/test_mcp_scope_banner.py`

- [ ] **Step 1: Write the failing test**

```python
import click
from click.testing import CliRunner

from agent_toolkit_cli.commands.mcp._common import scope_banner


def _run_banner(**kwargs):
    @click.command()
    def cmd():
        scope_banner(**kwargs)
    return CliRunner().invoke(cmd, [])


def test_banner_prints_on_implicit_project_plural():
    r = _run_banner(scope="project", implicit=True, lock_path="/p/mcps-lock.json", count=3)
    assert "Operating on project scope — /p/mcps-lock.json (3 MCP servers)." in r.stdout
    assert "Pass -g for the global library." in r.stdout


def test_banner_singular_noun():
    r = _run_banner(scope="project", implicit=True, lock_path="/p/mcps-lock.json", count=1)
    assert "(1 MCP server)." in r.stdout


def test_banner_count_zero_still_prints():
    r = _run_banner(scope="project", implicit=True, lock_path="/p/mcps-lock.json", count=0)
    assert "(0 MCP servers)." in r.stdout


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

Run: `uv run pytest tests/test_cli/test_mcp_scope_banner.py -k banner -q`
Expected: FAIL — `scope_banner` not defined.

- [ ] **Step 3: Add the helper**

In `mcp/_common.py`, after `scope_and_roots`:

```python
def scope_banner(scope, *, implicit, lock_path, count, err=False) -> None:
    """Print a one-line scope reminder on implicit-project resolution.

    Best-effort and informational: never raises, never affects exit codes.
    Silent unless scope was resolved implicitly (no -g/-p) AND landed on
    project — the one case (#419, mirrors #413) where the user got no signal
    about which lock was picked. Goes to stdout by default; the ``err``
    argument exists for cross-type parity but mcp has no --json read verb, so
    no caller passes ``err=True``.
    """
    if not (implicit and scope == "project"):
        return
    noun = "MCP server" if count == 1 else "MCP servers"
    click.echo(
        f"Operating on project scope — {lock_path} ({count} {noun}). "
        f"Pass -g for the global library.",
        err=err,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_mcp_scope_banner.py -k banner -q`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/mcp/_common.py \
        tests/test_cli/test_mcp_scope_banner.py
git commit -m "feat(mcp): scope_banner helper, MCP-server noun (#419)"
```

---

### Task 3: Wire `list`, `status`, `doctor`

**Files:**
- Modify: `src/agent_toolkit_cli/commands/mcp/{list,status,doctor}_cmd.py`
- Test: `tests/test_cli/test_mcp_scope_banner.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main as cli  # entrypoint symbol is `main`
from agent_toolkit_cli.mcp_lock import McpLockEntry, write_lock


def _seed_project_lock(tmp_path):
    """A minimal valid mcps-lock.json with one tracked slug, in tmp_path."""
    write_lock(
        tmp_path / "mcps-lock.json",
        {"demo-mcp": [McpLockEntry(slug="demo-mcp", harness="claude-code", source="npx")]},
    )


@pytest.mark.parametrize("verb", ["list", "status", "doctor"])
def test_mcp_read_verb_banner_on_stdout(verb, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_project_lock(tmp_path)
    r = CliRunner().invoke(cli, ["mcp", verb])
    # Banner is advisory; the verb may exit non-zero for other reasons.
    assert "Operating on project scope" in r.stdout
    assert "(1 MCP server)." in r.stdout


def test_mcp_list_no_banner_when_global_fallback(tmp_path, monkeypatch):
    # Isolate HOME: the global-fallback path reads ~/.agent-toolkit via
    # library_root(Path.home()) and read_lock against the real global lock. A
    # malformed real global lock would raise (mcp read_lock is fail-loud), and
    # real global state makes the test environment-dependent. Point HOME at an
    # empty tmp dir so the global path reads nothing.
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)  # no mcps-lock.json in cwd → global fallback
    r = CliRunner().invoke(cli, ["mcp", "list"])
    assert "Operating on project scope" not in r.stdout
    assert "Operating on project scope" not in r.stderr
```

> `list_library`/`load_mcp_asset` read the global library at `~/.agent-toolkit/mcps`; the seeded project lock has a slug with no library asset, but the banner fires off the lock read, before the library loop, so the assertion holds regardless of library state. If `doctor` errors before the banner over this lock, seed an installed mcp via the `mcp install` flow instead — but the introduced banner read sits immediately after `scope_and_roots`, before `_diagnose`, so it fires first.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_mcp_scope_banner.py -k read_verb -q`
Expected: FAIL — banners not wired.

- [ ] **Step 3: Wire `list`**

`list_cmd.py` reads `lock = read_lock(lock_path_for_scope(scope, home=effective_home, project=project_root))`. Hoist `lock_path` into a local and call the banner after the read, before the `for slug in slugs:` loop. Import `scope_banner` alongside `scope_and_roots`:

```python
from agent_toolkit_cli.commands.mcp._common import scope_and_roots, scope_banner
# ...
    effective_home = home if home is not None else Path.home()
    library = library_root(Path.home())
    lock_path = lock_path_for_scope(scope, home=effective_home, project=project_root)
    lock = read_lock(lock_path)
    scope_banner(scope, implicit=implicit, lock_path=lock_path, count=len(lock))

    slugs = list_library(library)
```

- [ ] **Step 4: Wire `status`**

`status_cmd.py` reads the lock the same way and then has `if not lock: … return`. Place the banner **before** that early-return so `count == 0` still banners:

```python
from agent_toolkit_cli.commands.mcp._common import scope_and_roots, scope_banner
# ...
    lock_path = lock_path_for_scope(scope, home=effective_home, project=project_root)
    lock = read_lock(lock_path)
    scope_banner(scope, implicit=implicit, lock_path=lock_path, count=len(lock))

    if not lock:
        click.echo(f"no MCP servers in the {scope} lock")
        return
```

(Check `status_cmd`'s actual `home`/`effective_home` local name and reuse it; if it inlines `lock_path_for_scope(...)` inside `read_lock(...)`, hoist it into `lock_path` first.)

- [ ] **Step 5: Wire `doctor`**

`doctor_cmd.py` has no body-level lock read. After `scope_and_roots`, before `_diagnose`, introduce the count read (it already imports `read_lock` and `lock_path_for_scope`; add `scope_banner` to the `_common` import):

```python
from agent_toolkit_cli.commands.mcp._common import scope_and_roots, scope_banner
# ...
    effective_home = home if home is not None else Path.home()
    lock_path = lock_path_for_scope(scope, home=effective_home, project=project_root)
    scope_banner(scope, implicit=implicit, lock_path=lock_path, count=len(read_lock(lock_path)))
    findings, env_warnings = _diagnose(
        scope=scope, home=effective_home, project=project_root,
    )
```

`mcp_lock.read_lock` returns `{}` on a missing file (safe at implicit-global) and raises only on a *malformed* lock; on the implicit-project path the lock is toolkit-written and well-formed.

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_mcp_scope_banner.py -q`
Expected: PASS (all).

- [ ] **Step 7: Commit**

```bash
git add src/agent_toolkit_cli/commands/mcp/{list,status,doctor}_cmd.py \
        tests/test_cli/test_mcp_scope_banner.py
git commit -m "feat(mcp): list/status/doctor emit scope banner (#419)"
```

---

### Task 4: Full suite + lint/type gates

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest -q`
Expected: PASS (all green; no regressions). Record the count.

- [ ] **Step 2: Lint + type check**

Run: `uv run ruff check src tests && uv run mypy src/agent_toolkit_cli/commands/mcp/`
Expected: no *new* ruff/mypy errors vs base (record base count first if unsure).

- [ ] **Step 3: Final commit if cleanup was needed** (skip if clean)

```bash
git add -A && git commit -m "chore(mcp): scope-banner lint/type cleanup (#419)"
```

---

## Self-review notes

- **Spec coverage:** 4-tuple (Task 1), `scope_banner` noun/err/zero (Task 2), three read verbs on stdout + global-fallback silence (Task 3), suite+gates (Task 4).
- **mcp lock is a `dict`** → `count=len(lock)` everywhere (NOT `.skills`). Verified against `mcp_lock.read_lock`.
- **No `--json` read verb** → banner always stdout; the `err=True` test is helper-level only (mcp never passes it).
- **`mcp update` excluded** — it does not call `scope_and_roots` (hard-codes home, required slug, iterates scopes). Confirmed in `update_cmd.py`.
- **doctor introduced read** is safe (`read_lock` empty-on-missing; raises only on malformed, which can't happen on the implicit-project well-formed path).
- **Test import is `main`** (`from agent_toolkit_cli.cli import main`), matching every existing CLI test.
