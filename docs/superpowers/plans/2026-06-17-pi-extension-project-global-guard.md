# Pi-extension Project/Global Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent CLI and TUI project-scope pi-extension installs when the same extension slug is already globally loaded.

**Architecture:** Put the invariant in `pi_extension_ops.install(...)`, the shared path used by Click and TUI apply, then add a TUI pre-queue guard for better UX. Add a small npm package-identity reader helper so the guard handles version-pinned/package-prefix drift consistently with existing uninstall behavior.

**Tech Stack:** Python 3.13+, Click, Textual, pytest, existing pi-extension lock/settings helpers.

---

## File structure

- Modify `src/agent_toolkit_cli/_pi_settings.py`: expose `has_package_identity(...)` using existing `_npm_identity(...)`.
- Modify `src/agent_toolkit_cli/pi_extension_ops.py`: add shared project-install guard.
- Modify `src/agent_toolkit_tui/widgets/pi_grid.py`: block project install queue for global-loaded rows and explain blocked state.
- Modify `tests/test_cli/test_pi_extension_ops.py`: shared operation tests for store-owned/npm guard and allowed cleanup path.
- Modify `tests/test_cli/test_cli_pi_extension_write.py`: Click-level regression tests for user-facing command failure.
- Modify `tests/test_tui/test_pi_grid.py`: widget/app tests for queue prevention, info text, and stale apply failure.

## Task 1: Shared ops failing tests

**Files:**
- Modify: `tests/test_cli/test_pi_extension_ops.py`

- [ ] **Step 1: Add pytest import**

Change top imports from:

```python
import json
```

to:

```python
import json

import pytest
```

- [ ] **Step 2: Add failing tests**

Append these tests to `tests/test_cli/test_pi_extension_ops.py`:

```python
def test_project_install_store_owned_fails_when_global_loaded(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    canonical = _seed_store_owned(tmp_path, "demo")

    ops.install(slug="demo", scope="global", home=tmp_path, project=None)
    project = tmp_path / "proj"
    project.mkdir()

    with pytest.raises(ops.pi_extension_install.InstallError) as exc:
        ops.install(slug="demo", scope="project", home=tmp_path, project=project)

    assert "already installed at global scope" in str(exc.value)
    project_link = pep.pi_extension_dir("demo", scope="project", project=project)
    assert not project_link.exists()
    assert canonical.exists()


def test_project_install_npm_fails_when_global_loaded(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_npm_lock("foo", "npm:foo")

    ops.install(slug="foo", scope="global", home=tmp_path, project=None)
    project = tmp_path / "proj"
    project.mkdir()

    with pytest.raises(ops.pi_extension_install.InstallError) as exc:
        ops.install(slug="foo", scope="project", home=tmp_path, project=project)

    assert "already installed at global scope" in str(exc.value)
    project_settings = project / ".pi" / "settings.json"
    assert not project_settings.exists()


def test_project_install_npm_fails_when_global_package_identity_loaded(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_npm_lock("foo", "npm:foo")
    _seed_settings(tmp_path, {"packages": ["foo@1.2.3"]})
    project = tmp_path / "proj"
    project.mkdir()

    with pytest.raises(ops.pi_extension_install.InstallError) as exc:
        ops.install(slug="foo", scope="project", home=tmp_path, project=project)

    assert "already installed at global scope" in str(exc.value)


def test_project_install_succeeds_after_global_uninstall(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_store_owned(tmp_path, "demo")
    project = tmp_path / "proj"
    project.mkdir()

    ops.install(slug="demo", scope="global", home=tmp_path, project=None)
    ops.uninstall(slug="demo", scope="global", home=tmp_path, project=None)
    ops.install(slug="demo", scope="project", home=tmp_path, project=project)

    project_link = pep.pi_extension_dir("demo", scope="project", project=project)
    assert project_link.is_symlink()


def test_project_uninstall_still_allowed_when_global_loaded(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    canonical = _seed_store_owned(tmp_path, "demo")
    project = tmp_path / "proj"
    project.mkdir()

    global_link = pep.pi_extension_dir("demo", scope="global", home=tmp_path)
    global_link.parent.mkdir(parents=True, exist_ok=True)
    global_link.symlink_to(canonical, target_is_directory=True)
    project_link = pep.pi_extension_dir("demo", scope="project", project=project)
    project_link.parent.mkdir(parents=True, exist_ok=True)
    project_link.symlink_to(canonical, target_is_directory=True)

    ops.uninstall(slug="demo", scope="project", home=tmp_path, project=project)

    assert global_link.is_symlink()
    assert not project_link.exists()
```

- [ ] **Step 3: Run failing shared tests**

Run:

```bash
uv run pytest tests/test_cli/test_pi_extension_ops.py -q
```

Expected before implementation: new project-install guard tests fail because project install still succeeds.

## Task 2: Shared guard implementation

**Files:**
- Modify: `src/agent_toolkit_cli/_pi_settings.py`
- Modify: `src/agent_toolkit_cli/pi_extension_ops.py`

- [ ] **Step 1: Add package identity reader helper**

In `src/agent_toolkit_cli/_pi_settings.py`, after `read_packages(...)`, add:

```python
def has_package_identity(
    spec_or_slug: str,
    *,
    scope: Scope,
    home: Path | None = None,
    project: Path | None = None,
) -> bool:
    """Return true when packages[] contains the same npm package identity.

    Mirrors remove_package_by_identity() matching: `npm:foo`, `foo`, and
    `foo@1.2.3` all match identity `foo`; scoped package names keep their
    leading `@`.
    """
    target = _npm_identity(spec_or_slug)
    return any(
        _npm_identity(package) == target
        for package in read_packages(scope=scope, home=home, project=project)
    )
```

- [ ] **Step 2: Add shared guard helpers**

In `src/agent_toolkit_cli/pi_extension_ops.py`, update imports:

```python
from agent_toolkit_cli.pi_extension_paths import (
    Scope, library_lock_path, lock_file_path,
)
```

becomes:

```python
from agent_toolkit_cli.pi_extension_paths import (
    Scope, library_lock_path, lock_file_path,
)
```

No import change needed if `pi_extension_install` already imported. Then add helpers after `_global_entry(...)`:

```python
def _store_owned_global_loaded(slug: str, *, home: Path | None) -> bool:
    p = pi_extension_install.plan(
        slug=slug, scope="global", action="install", home=home, project=None
    )
    return not p.create


def _globally_loaded(slug: str, entry: LockEntry, *, home: Path | None) -> bool:
    if entry.source_type == "npm":
        return _pi_settings.has_package_identity(
            entry.source, scope="global", home=home, project=None
        )
    return _store_owned_global_loaded(slug, home=home)


def _reject_project_install_if_global_loaded(
    *, slug: str, entry: LockEntry, scope: Scope, home: Path | None
) -> None:
    if scope != "project":
        return
    if not _globally_loaded(slug, entry, home=home):
        return
    raise pi_extension_install.InstallError(
        f"{slug}: already installed at global scope; "
        f"uninstall globally before installing at project scope"
    )
```

- [ ] **Step 3: Call guard before origin branch**

In `install(...)`, after global lock entry missing check and before `if entry.source_type == "npm":`, add:

```python
    _reject_project_install_if_global_loaded(
        slug=slug, entry=entry, scope=scope, home=home
    )
```

Resulting start of `install(...)` should be:

```python
def install(
    *,
    slug: str,
    scope: Scope,
    home: Path | None = None,
    project: Path | None = None,
) -> None:
    """Project `slug` into `scope`. Raises InstallError / PiSettingsError."""
    entry = _global_entry(slug)
    if entry is None:
        raise pi_extension_install.InstallError(
            f"{slug}: not in the global library; run `pi-extension add` first"
        )

    _reject_project_install_if_global_loaded(
        slug=slug, entry=entry, scope=scope, home=home
    )

    if entry.source_type == "npm":
        _pi_settings.add_package(entry.source, scope=scope, home=home, project=project)
        return
```

- [ ] **Step 4: Run shared tests**

Run:

```bash
uv run pytest tests/test_cli/test_pi_extension_ops.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit shared guard**

```bash
git add src/agent_toolkit_cli/_pi_settings.py src/agent_toolkit_cli/pi_extension_ops.py tests/test_cli/test_pi_extension_ops.py
git commit -m "fix(pi-extension): block project install when global loaded" -m "Device: $(hostname -s)"
```

## Task 3: CLI regression tests

**Files:**
- Modify: `tests/test_cli/test_cli_pi_extension_write.py`

- [ ] **Step 1: Add store-owned CLI regression**

After `test_store_owned_install_uninstall_project_round_trip(...)`, add:

```python
def test_store_owned_project_install_fails_when_global_loaded(tmp_path, monkeypatch, git_sandbox):
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path))
    _add_store_owned(tmp_path, git_sandbox.env, git_sandbox.upstream)

    proj = tmp_path / "proj"
    proj.mkdir()
    monkeypatch.chdir(proj)

    r_global = CliRunner().invoke(main, ["pi-extension", "install", "demo", "-g"])
    assert r_global.exit_code == 0, r_global.output

    r_project = CliRunner().invoke(main, ["pi-extension", "install", "demo", "-p"])
    assert r_project.exit_code != 0
    assert "already installed at global scope" in r_project.output
    assert not pep.pi_extension_dir("demo", scope="project", project=proj).exists()
```

- [ ] **Step 2: Add npm CLI regression**

After `test_npm_install_project_scope(...)`, add:

```python
def test_npm_project_install_fails_when_global_loaded(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    CliRunner().invoke(main, ["pi-extension", "add", "npm:bar"])
    proj = tmp_path / "proj"
    proj.mkdir()
    monkeypatch.chdir(proj)

    r_global = CliRunner().invoke(main, ["pi-extension", "install", "bar", "-g"])
    assert r_global.exit_code == 0, r_global.output

    r_project = CliRunner().invoke(main, ["pi-extension", "install", "bar", "-p"])
    assert r_project.exit_code != 0
    assert "already installed at global scope" in r_project.output
    assert "npm:bar" not in _pi_settings.read_packages(scope="project", project=proj)
```

- [ ] **Step 3: Run CLI write tests**

Run:

```bash
uv run pytest tests/test_cli/test_cli_pi_extension_write.py -q
```

Expected: all tests pass.

- [ ] **Step 4: Commit CLI tests**

```bash
git add tests/test_cli/test_cli_pi_extension_write.py
git commit -m "test(pi-extension): cover CLI global project guard" -m "Device: $(hostname -s)"
```

## Task 4: TUI grid guard tests

**Files:**
- Modify: `tests/test_tui/test_pi_grid.py`

- [ ] **Step 1: Add widget queue prevention test**

After `test_untracked_row_is_non_interactive(...)`, add:

```python
@pytest.mark.asyncio
async def test_project_install_global_loaded_row_is_non_interactive():
    """Project-scope unloaded cell with global-loaded marker cannot queue install."""

    class _A(App):
        def compose(self) -> ComposeResult:
            grid = PiGrid([_store_row("alpha", global_loaded=True, project_loaded=False)], id="g")
            grid.set_scope("project")
            yield grid

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", PiGrid)
        table = app.query_one("#pi-table", DataTable)
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()

    assert g.pending_entries() == {}
```

- [ ] **Step 2: Add project uninstall remains queueable test**

Append after previous test:

```python
@pytest.mark.asyncio
async def test_project_uninstall_global_loaded_row_still_queues_unlink():
    """Existing duplicate state can still be cleaned up from project scope."""

    class _A(App):
        def compose(self) -> ComposeResult:
            grid = PiGrid([_store_row("alpha", global_loaded=True, project_loaded=True)], id="g")
            grid.set_scope("project")
            yield grid

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", PiGrid)
        table = app.query_one("#pi-table", DataTable)
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()

    assert g.pending_entries() == {("project", "alpha"): "unlink"}
```

- [ ] **Step 3: Add info text test**

Append after previous test:

```python
def test_project_info_explains_global_loaded_install_block():
    grid = PiGrid([_store_row("alpha", global_loaded=True, project_loaded=False)])
    row = grid._rows[0]

    body = grid._info_body(row=row, scope="project")

    assert "Already loaded globally" in body
    assert "uninstall globally" in body
    assert "queue install" not in body
```

- [ ] **Step 4: Run TUI grid tests before implementation**

Run:

```bash
uv run pytest tests/test_tui/test_pi_grid.py::test_project_install_global_loaded_row_is_non_interactive tests/test_tui/test_pi_grid.py::test_project_uninstall_global_loaded_row_still_queues_unlink tests/test_tui/test_pi_grid.py::test_project_info_explains_global_loaded_install_block -q
```

Expected before implementation: queue-prevention and info-text tests fail.

## Task 5: TUI grid implementation

**Files:**
- Modify: `src/agent_toolkit_tui/widgets/pi_grid.py`

- [ ] **Step 1: Add helper method**

Inside `PiGrid`, after `restore_pending(...)`, add:

```python
    def _project_install_blocked(self, *, row: PiExtensionRow, loaded: bool) -> bool:
        return self._scope == "project" and row.global_cell.global_loaded and not loaded
```

- [ ] **Step 2: Use helper in `_toggle_at(...)`**

Change this block:

```python
            loaded = (
                row.global_cell.global_loaded
                if scope == "global"
                else row.project_cell.project_loaded
            )
            self._pending[key] = "unlink" if loaded else "link"
```

to:

```python
            loaded = (
                row.global_cell.global_loaded
                if scope == "global"
                else row.project_cell.project_loaded
            )
            if self._project_install_blocked(row=row, loaded=loaded):
                return
            self._pending[key] = "unlink" if loaded else "link"
```

- [ ] **Step 3: Explain npm blocked state**

In `_info_body(...)`, inside `if row.origin == "npm":`, before final `return (f"Not loaded (npm)...`)`, add:

```python
            if scope == "project" and row.global_cell.global_loaded:
                return (
                    f"Not loaded in project (npm).\n"
                    f"Already loaded globally as {row.source}.\n"
                    f"Project install is unavailable; uninstall globally first "
                    f"if this extension must be project-scoped."
                )
```

- [ ] **Step 4: Explain store-owned blocked state**

In store-owned project branch, before final `return (f"Not loaded...`)`, add:

```python
        if scope == "project" and row.global_cell.global_loaded:
            return (
                f"Not loaded in project.\n"
                f"Already loaded globally.\n"
                f"Project install is unavailable; uninstall globally first "
                f"if this extension must be project-scoped.\n"
                f"{link} → {canonical}"
            )
```

- [ ] **Step 5: Run TUI grid tests**

Run:

```bash
uv run pytest tests/test_tui/test_pi_grid.py::test_project_install_global_loaded_row_is_non_interactive tests/test_tui/test_pi_grid.py::test_project_uninstall_global_loaded_row_still_queues_unlink tests/test_tui/test_pi_grid.py::test_project_info_explains_global_loaded_install_block -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit TUI grid guard**

```bash
git add src/agent_toolkit_tui/widgets/pi_grid.py tests/test_tui/test_pi_grid.py
git commit -m "fix(tui): block pi-extension project queue when global loaded" -m "Device: $(hostname -s)"
```

## Task 6: TUI stale apply regression

**Files:**
- Modify: `tests/test_tui/test_pi_grid.py`

- [ ] **Step 1: Add stale apply failure test**

After `test_apply_install_error_surfaces_notify_and_footer(...)`, add:

```python
@pytest.mark.asyncio
async def test_apply_project_link_fails_when_global_loaded(monkeypatch):
    """Stale queued project link still fails through shared pi_extension_ops guard."""
    from agent_toolkit_tui.app import TUIApp
    import agent_toolkit_cli.pi_extension_install as _pi_install
    import agent_toolkit_cli.pi_extension_lock as _lock
    import agent_toolkit_cli.pi_extension_ops as _ops

    notify_calls: list[Any] = []

    entry = MagicMock()
    entry.source_type = "git"
    entry.source = "git@github.com:x/alpha"
    entry.ref = "main"
    entry.pi_extension_path = None

    def fake_read_lock(path):
        lf = MagicMock()
        lf.skills = {"alpha": entry}
        return lf

    def fake_install(*, slug, scope, home=None, project=None):
        raise _pi_install.InstallError(
            "alpha: already installed at global scope; uninstall globally before installing at project scope"
        )

    monkeypatch.setattr(_lock, "read_lock", fake_read_lock)
    monkeypatch.setattr(_ops, "install", fake_install)
    monkeypatch.setattr("agent_toolkit_cli.pi_extension_paths.library_lock_path", lambda env=None: Path("/fake/lock"))

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        orig_notify = app.notify

        def spy_notify(*a, **k):
            notify_calls.append(k)
            return orig_notify(*a, **k)

        monkeypatch.setattr(app, "notify", spy_notify)
        app._active_asset_type = "pi-extension"
        grid = app.query_one("#pi-grid", PiGrid)
        grid.set_rows([_store_row("alpha", global_loaded=True, project_loaded=False)])
        grid.restore_pending({("project", "alpha"): "link"})
        await pilot.pause()

        app._apply_pi_pending()
        footer = str(app.query_one("#footer-pending", Static).render())

    assert "apply failed" in footer
    assert "already installed at global scope" in footer
    assert notify_calls
    assert notify_calls[-1].get("severity") == "error"
```

- [ ] **Step 2: Run stale apply test**

Run:

```bash
uv run pytest tests/test_tui/test_pi_grid.py::test_apply_project_link_fails_when_global_loaded -q
```

Expected: test passes after Task 2 shared guard and monkeypatch path are correct.

- [ ] **Step 3: Commit stale apply test**

```bash
git add tests/test_tui/test_pi_grid.py
git commit -m "test(tui): cover stale pi-extension project apply guard" -m "Device: $(hostname -s)"
```

## Task 7: Full verification and issue update

**Files:**
- Modify: `docs/superpowers/plans/2026-06-17-pi-extension-project-global-guard.md` only if execution discoveries require plan correction.
- Modify: GitHub issue #449 body.

- [ ] **Step 1: Run focused regression suite**

```bash
uv run pytest tests/test_cli/test_pi_extension_ops.py tests/test_cli/test_cli_pi_extension_write.py tests/test_tui/test_pi_grid.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run full suite**

```bash
uv run pytest -q
```

Expected: full suite passes.

- [ ] **Step 3: Update issue #449 sections**

Set issue sections:

- `## 4. Plan` link to `docs/superpowers/plans/2026-06-17-pi-extension-project-global-guard.md` and commit SHA.
- `## 5. Approvals front-loaded` = spec approved in `/aj-issue` flow; no additional approvals required.
- `## 6. Skills/tools required` = `superpowers:test-driven-development`, `superpowers:subagent-driven-development` or `superpowers:executing-plans`, `superpowers:verification-before-completion`.
- `## 7. Test surface` = focused CLI ops/write tests, TUI grid tests, full `uv run pytest -q`.
- `## 8. Autonomy-level recommendation` = L3 Conditional.
- `## Critical review` = add review findings if M review produces any.

- [ ] **Step 4: Apply build-ready only after review gate**

Only after M critical review findings are resolved or waived:

```bash
gh issue edit 449 --add-label build-ready
```
