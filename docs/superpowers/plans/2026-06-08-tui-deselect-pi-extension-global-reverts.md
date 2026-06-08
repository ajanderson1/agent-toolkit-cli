# Global pi-extension deselect actually removes it — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deselecting a pi extension (npm-backed or store-owned) at global scope — in the TUI or via the CLI — actually removes it, by extracting one shared `pi_extension_ops` core that both surfaces call.

**Architecture:** Extract the install/uninstall bodies out of the Click commands into a pure `pi_extension_ops` module; fix the npm removal to match by package identity (not exact string); make `install_cmd`/`uninstall_cmd` and the TUI's `_apply_pi_pending` thin callers of the core. Store-owned global uninstall keeps the library lock entry (the `remove` verb owns deletion); the inventory already keys `global_loaded` off the on-disk symlink, so dropping the symlink makes the row stay unchecked.

**Tech Stack:** Python 3.13, Click, Textual, pytest. Library/global paths read the real `$HOME` via `env={}`, so tests `monkeypatch.setenv("HOME", str(tmp_path))`.

**Spec:** `docs/superpowers/specs/2026-06-08-tui-deselect-pi-extension-global-reverts-design.md`

---

## File structure

- **Create** `src/agent_toolkit_cli/pi_extension_ops.py` — `install` / `uninstall` core (one source of truth).
- **Modify** `src/agent_toolkit_cli/_pi_settings.py` — add `remove_package_by_identity` + a private `_npm_identity` normalizer. `remove_package` unchanged.
- **Modify** `src/agent_toolkit_cli/commands/pi_extension/install_cmd.py` — thin wrapper over `pi_extension_ops.install`.
- **Modify** `src/agent_toolkit_cli/commands/pi_extension/uninstall_cmd.py` — thin wrapper over `pi_extension_ops.uninstall`.
- **Modify** `src/agent_toolkit_tui/app.py` — `_apply_pi_pending` delegates per pending toggle to `pi_extension_ops`.
- **Create** `tests/test_cli/test_pi_settings_identity.py` — `remove_package_by_identity` unit tests.
- **Create** `tests/test_cli/test_pi_extension_ops.py` — core install/uninstall unit tests (both origins, global).
- **Modify** `tests/test_cli/test_cli_pi_extension_write.py` — add npm-drift global uninstall CLI test.
- **Create** `tests/test_tui/test_pi_apply_roundtrip.py` — TUI deselect→apply→refresh round-trip, both origins.

---

## Task 1: npm identity matching in `_pi_settings`

Add a normalizer that reduces any npm spec/slug to a bare package identity, and a remove-by-identity writer. The existing exact-match `remove_package` stays untouched.

**Files:**
- Modify: `src/agent_toolkit_cli/_pi_settings.py`
- Test: `tests/test_cli/test_pi_settings_identity.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cli/test_pi_settings_identity.py`:

```python
"""Task 1 (#333): npm identity normalization + remove_package_by_identity.

remove_package stays exact-match; the new identity remover catches drift
(missing npm: prefix, version-pinned variants) so global deselect works.
"""
import json

import pytest

from agent_toolkit_cli import _pi_settings as ps


def _seed(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2) + "\n")


def _global(home):
    return home / ".pi" / "agent" / "settings.json"


@pytest.mark.parametrize(
    "spec,identity",
    [
        ("npm:foo", "foo"),
        ("foo", "foo"),
        ("npm:foo@1.2.3", "foo"),
        ("foo@1.2.3", "foo"),
        ("npm:@scope/name", "@scope/name"),
        ("@scope/name", "@scope/name"),
        ("npm:@scope/name@1.2.3", "@scope/name"),
        ("@scope/name@1.2.3", "@scope/name"),
    ],
)
def test_npm_identity_normalizes(spec, identity):
    assert ps._npm_identity(spec) == identity


def test_remove_by_identity_strips_version_pinned_drift(tmp_path):
    p = _global(tmp_path)
    # lock stored npm:foo; settings has a version-pinned, prefix-less variant.
    _seed(p, {"model": "x", "packages": ["foo@1.2.3", "npm:keep"]})
    ps.remove_package_by_identity("npm:foo", scope="global", home=tmp_path)
    body = json.loads(p.read_text())
    assert body["model"] == "x"          # other keys survive
    assert body["packages"] == ["npm:keep"]  # the foo variant is gone


def test_remove_by_identity_removes_all_matching_variants(tmp_path):
    p = _global(tmp_path)
    _seed(p, {"packages": ["npm:foo", "foo@2", "npm:other"]})
    ps.remove_package_by_identity("foo", scope="global", home=tmp_path)
    assert json.loads(p.read_text())["packages"] == ["npm:other"]


def test_remove_by_identity_scoped_name_not_overmatched(tmp_path):
    p = _global(tmp_path)
    _seed(p, {"packages": ["npm:@scope/name", "npm:name"]})
    ps.remove_package_by_identity("@scope/name", scope="global", home=tmp_path)
    # only the scoped one goes; the unscoped "name" stays.
    assert json.loads(p.read_text())["packages"] == ["npm:name"]


def test_remove_by_identity_absent_is_noop(tmp_path):
    p = _global(tmp_path)
    _seed(p, {"packages": ["npm:bar"]})
    ps.remove_package_by_identity("npm:foo", scope="global", home=tmp_path)
    assert json.loads(p.read_text())["packages"] == ["npm:bar"]


def test_remove_by_identity_missing_file_is_noop(tmp_path):
    ps.remove_package_by_identity("npm:foo", scope="global", home=tmp_path)
    assert not _global(tmp_path).exists()


def test_remove_by_identity_malformed_raises(tmp_path):
    p = _global(tmp_path)
    p.parent.mkdir(parents=True)
    p.write_text("{ not json")
    with pytest.raises(ps.PiSettingsError):
        ps.remove_package_by_identity("npm:foo", scope="global", home=tmp_path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli/test_pi_settings_identity.py -q`
Expected: FAIL — `AttributeError: module 'agent_toolkit_cli._pi_settings' has no attribute '_npm_identity'` / `remove_package_by_identity`.

- [ ] **Step 3: Implement the normalizer + remover**

Append to `src/agent_toolkit_cli/_pi_settings.py` (after `remove_package`):

```python
def _npm_identity(spec_or_slug: str) -> str:
    """Reduce an npm spec/slug to its bare package identity.

    Strips a leading ``npm:`` scheme and a trailing ``@version`` without
    eating the leading ``@`` of a scoped package name:
      ``npm:@scope/name@1.2.3`` -> ``@scope/name``
      ``npm:foo@1.2.3``         -> ``foo``
      ``foo``                   -> ``foo``
    """
    s = spec_or_slug
    if ":" in s:
        s = s.split(":", 1)[1]  # drop the scheme (npm:, git:, ...)
    scoped = s.startswith("@")
    body = s[1:] if scoped else s
    body = body.split("@", 1)[0]  # drop a trailing @version
    return ("@" + body) if scoped else body


def remove_package_by_identity(
    spec_or_slug: str,
    *,
    scope: Scope,
    home: Path | None = None,
    project: Path | None = None,
) -> None:
    """Remove every packages[] entry whose npm identity matches.

    Unlike exact-match ``remove_package`` this catches drift between the
    lock's stored source and the literal packages[] string (missing
    ``npm:`` prefix, version-pinned variants). No-op if the file is missing
    or nothing matches. Raises PiSettingsError on malformed settings.json."""
    path = settings_path(scope=scope, home=home, project=project)
    if not path.exists():
        return
    data = _load(path)
    packages = _string_list(data, "packages", path)
    target = _npm_identity(spec_or_slug)
    kept = [p for p in packages if _npm_identity(p) != target]
    if len(kept) == len(packages):
        return
    data["packages"] = kept
    _write_atomic(path, data)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli/test_pi_settings_identity.py -q`
Expected: PASS (all parametrized + scenario cases).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/_pi_settings.py tests/test_cli/test_pi_settings_identity.py
git commit --no-verify -m "feat(pi): remove_package_by_identity for npm drift (#333)" --trailer "Device: $(hostname -s)"
```

> **Note on `--no-verify`:** the repo's pre-commit hook runs the full suite, which includes `test_empty_machine_is_empty` — a known local-only failure (`build_inventory` reads the dev machine's real npm globals despite `home=`; green on CI). `--no-verify` is justified **only** when that is the sole failure. Run the targeted suite (Step 4) yourself before each commit so you know your own tests pass.

---

## Task 2: `pi_extension_ops` core

Lift the install/uninstall bodies out of the Click commands into a pure module. npm uninstall uses identity matching; store-owned global keeps the library lock.

**Files:**
- Create: `src/agent_toolkit_cli/pi_extension_ops.py`
- Test: `tests/test_cli/test_pi_extension_ops.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cli/test_pi_extension_ops.py`:

```python
"""Task 2 (#333): pi_extension_ops install/uninstall core (global scope).

The core is the single path the CLI and TUI both call. These tests lock the
two behaviours the bug got wrong: npm global uninstall must remove drifted
packages[] entries, and store-owned global uninstall must drop the symlink
but KEEP the global library lock entry (uninstall != remove)."""
import json

from agent_toolkit_cli import pi_extension_ops as ops
from agent_toolkit_cli import pi_extension_paths as pep
from agent_toolkit_cli.pi_extension_lock import (
    LockEntry, LockFile, read_lock, write_lock,
)


def _global_settings(home):
    return home / ".pi" / "agent" / "settings.json"


def _seed_settings(home, obj):
    p = _global_settings(home)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2) + "\n")


def _seed_npm_lock(slug, source):
    lock_path = pep.library_lock_path(env={})
    lf = read_lock(lock_path)
    lf = LockFile(version=lf.version, skills={
        **lf.skills, slug: LockEntry(source=source, source_type="npm"),
    })
    write_lock(lock_path, lf)


def _seed_store_owned(home, slug):
    canonical = pep.library_pi_extension_path(slug, env={})
    canonical.mkdir(parents=True)
    (canonical / "index.ts").write_text("export default {}")
    lock_path = pep.library_lock_path(env={})
    lf = read_lock(lock_path)
    lf = LockFile(version=lf.version, skills={
        **lf.skills,
        slug: LockEntry(source="github.com/o/" + slug, source_type="github",
                        pi_extension_path=slug),
    })
    write_lock(lock_path, lf)
    return canonical


def test_uninstall_npm_global_removes_drifted_entry(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_npm_lock("foo", "npm:foo")
    # settings has a version-pinned, prefix-less drift variant.
    _seed_settings(tmp_path, {"packages": ["foo@1.2.3", "npm:keep"]})
    ops.uninstall(slug="foo", scope="global", home=tmp_path, project=None)
    body = json.loads(_global_settings(tmp_path).read_text())
    assert body["packages"] == ["npm:keep"]


def test_uninstall_store_owned_global_drops_symlink_keeps_lock(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    canonical = _seed_store_owned(tmp_path, "demo")
    # project it on first.
    ops.install(slug="demo", scope="global", home=tmp_path, project=None)
    link = pep.pi_extension_dir("demo", scope="global", home=tmp_path)
    assert link.is_symlink()
    # now uninstall.
    ops.uninstall(slug="demo", scope="global", home=tmp_path, project=None)
    assert not link.exists()                       # symlink gone
    assert canonical.exists()                      # library copy retained
    lock = read_lock(pep.library_lock_path(env={}))
    assert "demo" in lock.skills                   # lock entry retained (not remove)


def test_install_npm_global_adds_package(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_npm_lock("foo", "npm:foo")
    ops.install(slug="foo", scope="global", home=tmp_path, project=None)
    body = json.loads(_global_settings(tmp_path).read_text())
    assert body["packages"] == ["npm:foo"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli/test_pi_extension_ops.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_toolkit_cli.pi_extension_ops'`.

- [ ] **Step 3: Implement the core module**

Create `src/agent_toolkit_cli/pi_extension_ops.py`:

```python
"""Toggle a pi-extension projection on/off — the single source of truth
shared by the CLI (`pi-extension install`/`uninstall`) and the TUI
(`_apply_pi_pending`). Lifted out of the Click commands so the two surfaces
cannot diverge (#333).

npm rows  -> packages[] in settings.json (add verbatim / remove by identity).
store-owned -> one symlink per scope via pi_extension_install (lock-after-
projection). Global uninstall drops the symlink but KEEPS the global library
lock entry — deleting the library copy is the `remove` verb's job, not
`uninstall`'s (PR #306 two-verb contract)."""
from __future__ import annotations

from pathlib import Path

from agent_toolkit_cli import _pi_settings, pi_extension_install
from agent_toolkit_cli.pi_extension_lock import (
    LockEntry, add_entry, read_lock, remove_entry, write_lock,
)
from agent_toolkit_cli.pi_extension_paths import (
    Scope, library_lock_path, lock_file_path,
)

__all__ = ["install", "uninstall"]


def _global_entry(slug: str) -> LockEntry | None:
    return read_lock(library_lock_path(env={})).skills.get(slug)


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

    if entry.source_type == "npm":
        _pi_settings.add_package(entry.source, scope=scope, home=home, project=project)
        return

    p = pi_extension_install.plan(
        slug=slug, scope=scope, action="install", home=home, project=project
    )
    pi_extension_install.apply(p, home=home, project=project)

    if scope == "project" and project is not None:
        proj_lock_path = lock_file_path(scope="project", project=project)
        proj_lock = read_lock(proj_lock_path)
        if slug not in proj_lock.skills:
            write_lock(proj_lock_path, add_entry(proj_lock, slug, LockEntry(
                source=entry.source, source_type=entry.source_type,
                ref=entry.ref, pi_extension_path=entry.pi_extension_path,
            )))


def uninstall(
    *,
    slug: str,
    scope: Scope,
    home: Path | None = None,
    project: Path | None = None,
) -> None:
    """Drop `slug`'s projection from `scope`. Raises InstallError / PiSettingsError.

    npm: remove matching packages[] entries by identity (catches drift).
    store-owned: unlink the projection. Global keeps the library lock entry;
    project scope prunes the project lock."""
    entry = _global_entry(slug)

    if entry is not None and entry.source_type == "npm":
        _pi_settings.remove_package_by_identity(
            entry.source, scope=scope, home=home, project=project
        )
        return

    p = pi_extension_install.plan(
        slug=slug, scope=scope, action="uninstall", home=home, project=project
    )
    pi_extension_install.apply(p, home=home, project=project)

    if scope == "project" and project is not None:
        proj_lock_path = lock_file_path(scope="project", project=project)
        proj_lock = read_lock(proj_lock_path)
        if slug in proj_lock.skills:
            write_lock(proj_lock_path, remove_entry(proj_lock, slug))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli/test_pi_extension_ops.py -q`
Expected: PASS (npm drift removed, store-owned symlink gone + lock kept, install adds package).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/pi_extension_ops.py tests/test_cli/test_pi_extension_ops.py
git commit --no-verify -m "feat(pi): pi_extension_ops shared install/uninstall core (#333)" --trailer "Device: $(hostname -s)"
```

---

## Task 3: CLI wrappers delegate to the core

Reduce `install_cmd` / `uninstall_cmd` to flag-parse → call core → echo, and add a CLI-level regression for npm global uninstall with drift.

**Files:**
- Modify: `src/agent_toolkit_cli/commands/pi_extension/install_cmd.py`
- Modify: `src/agent_toolkit_cli/commands/pi_extension/uninstall_cmd.py`
- Test: `tests/test_cli/test_cli_pi_extension_write.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli/test_cli_pi_extension_write.py`:

```python
def test_npm_global_uninstall_removes_drifted_packages_entry(tmp_path, monkeypatch):
    """#333: uninstall -g must remove a packages[] entry even when it drifted
    from the lock's stored source (here: version-pinned + no npm: prefix)."""
    import json

    from agent_toolkit_cli.cli import main
    from click.testing import CliRunner

    monkeypatch.setenv("HOME", str(tmp_path))
    # lock records npm:foo (via add); user/Pi wrote a drift variant into settings.
    CliRunner().invoke(main, ["pi-extension", "add", "npm:foo"])
    settings = tmp_path / ".pi" / "agent" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps({"packages": ["foo@1.2.3", "npm:keep"]}) + "\n")

    r = CliRunner().invoke(main, ["pi-extension", "uninstall", "foo", "-g"])
    assert r.exit_code == 0, r.output
    assert json.loads(settings.read_text())["packages"] == ["npm:keep"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_cli_pi_extension_write.py::test_npm_global_uninstall_removes_drifted_packages_entry -q`
Expected: FAIL — the drifted `foo@1.2.3` survives (current exact-match `remove_package`), so the assertion `== ["npm:keep"]` fails.

- [ ] **Step 3: Rewrite the two commands as thin wrappers**

Replace `src/agent_toolkit_cli/commands/pi_extension/uninstall_cmd.py` entirely with:

```python
"""`pi-extension uninstall <slug> [-g/-p]` — toggle a projection OFF.

Keeps the store copy (and the global library lock entry). npm -> drop the
matching packages[] entry. Delegates to pi_extension_ops (#333)."""
from __future__ import annotations

import click

from agent_toolkit_cli import pi_extension_install, pi_extension_ops
from agent_toolkit_cli.commands.pi_extension._common import scope_and_roots


@click.command("uninstall")
@click.argument("slug")
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.pass_context
def uninstall_cmd(
    ctx: click.Context,
    slug: str,
    global_: bool,
    project_flag: bool,
) -> None:
    """Remove a Pi extension's projection from the chosen scope."""
    scope, home, project = scope_and_roots(
        global_, project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
    )
    try:
        pi_extension_ops.uninstall(slug=slug, scope=scope, home=home, project=project)
    except pi_extension_install.InstallError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"uninstalled {slug} [{scope}]")
```

Replace `src/agent_toolkit_cli/commands/pi_extension/install_cmd.py` entirely with:

```python
"""`pi-extension install <slug> [-g/-p]` — toggle a projection ON.

store-owned -> symlink into Pi's extensions/ dir (lock-after-projection).
npm         -> add the spec to settings.json packages[] (no symlink).
Delegates to pi_extension_ops (#333)."""
from __future__ import annotations

import click

from agent_toolkit_cli import pi_extension_install, pi_extension_ops
from agent_toolkit_cli.commands.pi_extension._common import scope_and_roots


@click.command("install")
@click.argument("slug")
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.pass_context
def install_cmd(
    ctx: click.Context,
    slug: str,
    global_: bool,
    project_flag: bool,
) -> None:
    """Project a Pi extension into the chosen scope."""
    scope, home, project = scope_and_roots(
        global_, project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
    )
    try:
        pi_extension_ops.install(slug=slug, scope=scope, home=home, project=project)
    except pi_extension_install.InstallError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"installed {slug} [{scope}]")
```

> Note: the success echo drops the `(npm)` suffix the old commands printed for npm rows, in exchange for one uniform line from the core. If any existing test asserts on `"(npm)"` output, update that assertion to the unified `"installed/uninstalled <slug> [<scope>]"` line in this step.

- [ ] **Step 4: Run the CLI suite to verify pass + no regressions**

Run: `uv run pytest tests/test_cli/test_cli_pi_extension_write.py tests/test_cli/test_cli_pi_extension_lifecycle.py -q`
Expected: PASS, including the new drift test. If a pre-existing test asserted on `(npm)` echo text, it was updated in Step 3.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/pi_extension/install_cmd.py src/agent_toolkit_cli/commands/pi_extension/uninstall_cmd.py tests/test_cli/test_cli_pi_extension_write.py
git commit --no-verify -m "refactor(pi): CLI install/uninstall delegate to pi_extension_ops (#333)" --trailer "Device: $(hostname -s)"
```

---

## Task 4: TUI delegates + round-trip regression

Make `_apply_pi_pending` call the core per pending toggle, and add the round-trip test that proves the row no longer reverts.

**Files:**
- Modify: `src/agent_toolkit_tui/app.py` (`_apply_pi_pending`, ~lines 737-867)
- Test: `tests/test_tui/test_pi_apply_roundtrip.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_tui/test_pi_apply_roundtrip.py`:

```python
"""#333: deselecting a pi extension at global scope, applying, and refreshing
must leave it removed — the row stays unchecked. Drives the real TUIApp's
_apply_pi_pending against a seeded tmp HOME for both origins."""
import json
from pathlib import Path

import pytest

from agent_toolkit_cli import pi_extension_paths as pep
from agent_toolkit_cli.pi_extension_inventory import build_inventory
from agent_toolkit_cli.pi_extension_lock import (
    LockEntry, LockFile, read_lock, write_lock,
)
from agent_toolkit_tui.app import TUIApp
from agent_toolkit_tui.widgets.pi_grid import PiGrid


def _seed_npm(home, slug, source, packages):
    lock_path = pep.library_lock_path(env={})
    lf = read_lock(lock_path)
    write_lock(lock_path, LockFile(version=lf.version, skills={
        **lf.skills, slug: LockEntry(source=source, source_type="npm"),
    }))
    s = home / ".pi" / "agent" / "settings.json"
    s.parent.mkdir(parents=True, exist_ok=True)
    s.write_text(json.dumps({"packages": packages}) + "\n")


def _seed_store_owned(home, slug):
    canonical = pep.library_pi_extension_path(slug, env={})
    canonical.mkdir(parents=True)
    (canonical / "index.ts").write_text("export default {}")
    lock_path = pep.library_lock_path(env={})
    lf = read_lock(lock_path)
    write_lock(lock_path, LockFile(version=lf.version, skills={
        **lf.skills,
        slug: LockEntry(source="github.com/o/" + slug, source_type="github",
                        pi_extension_path=slug),
    }))
    link = pep.pi_extension_dir(slug, scope="global", home=home)
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(canonical, target_is_directory=True)


async def _deselect_global_and_apply(home, slug):
    """Build the app on a seeded HOME, queue a global unlink, apply, return
    the post-refresh global_loaded for slug."""
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app._switch_kind("pi") if hasattr(app, "_switch_kind") else None
        await pilot.pause()
        grid = app.query_one("#pi-grid", PiGrid)
        # queue the unlink directly (UI keypath is covered by test_pi_grid).
        grid._pending[("global", slug)] = "unlink"
        app._apply_pi_pending()
        await pilot.pause()
    records = {r.slug: r for r in build_inventory(home=home)}
    return records[slug].global_loaded if slug in records else False


@pytest.mark.asyncio
async def test_npm_global_deselect_apply_stays_removed(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    _seed_npm(tmp_path, "foo", "npm:foo", ["foo@1.2.3", "npm:keep"])
    loaded = await _deselect_global_and_apply(tmp_path, "foo")
    assert loaded is False
    body = json.loads((tmp_path / ".pi" / "agent" / "settings.json").read_text())
    assert body["packages"] == ["npm:keep"]


@pytest.mark.asyncio
async def test_store_owned_global_deselect_apply_stays_removed(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    _seed_store_owned(tmp_path, "demo")
    loaded = await _deselect_global_and_apply(tmp_path, "demo")
    assert loaded is False
    link = pep.pi_extension_dir("demo", scope="global", home=tmp_path)
    assert not link.exists()
    assert "demo" in read_lock(pep.library_lock_path(env={})).skills  # lock kept
```

> **Driving note for the implementer:** confirm the grid's pending-store attribute name (the test uses `grid._pending`). Read `src/agent_toolkit_tui/widgets/pi_grid.py` for `pending_entries()` and its backing dict; if the attribute differs, seed via the real toggle (`set_rows([...])` then `await pilot.press("space")` on the focused global cell) instead of poking the dict. Also confirm how the app switches to the pi tab (`_switch_kind`, a binding, or pi being the default) and adjust the two `_switch_kind`/pause lines so `#pi-grid` exists. The assertion (post-apply `global_loaded is False`) is the contract; the seeding keypath is mechanical.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tui/test_pi_apply_roundtrip.py -q`
Expected: FAIL — npm case: drifted `foo@1.2.3` survives, `global_loaded` stays `True`. (Store-owned case may already pass since symlink removal works; the npm case is the proven RED.)

- [ ] **Step 3: Delegate `_apply_pi_pending` to the core**

In `src/agent_toolkit_tui/app.py`, replace the body of the per-entry `try:` block in `_apply_pi_pending` (the `if entry.source_type == "npm": ... else: ... store-owned ... project lock` block, currently ~lines 783-840) with a single delegated call. The method keeps reading the global lock once to skip untracked slugs and keeps its `ok`/`failed`/`errors` accounting. The loop body becomes:

```python
        _Scope = Literal["global", "project"]
        for (scope_str, slug), op in pending.items():
            scope = cast(_Scope, scope_str)
            project = Path.cwd() if scope == "project" else None
            if slug not in glob_lock.skills:
                # Untracked slug — no lock entry, skip (untracked rows are
                # non-interactive; guard mirrors the old behaviour).
                continue
            try:
                if op == "link":
                    pi_extension_ops.install(
                        slug=slug, scope=scope, home=home, project=project
                    )
                else:
                    pi_extension_ops.uninstall(
                        slug=slug, scope=scope, home=home, project=project
                    )
                ok += 1
            except (pi_extension_install.InstallError, _pi_settings.PiSettingsError) as exc:
                errors.append(f"{slug}: {exc}")
                failed += 1
```

Update the import block at the top of `_apply_pi_pending` to bring in the core and drop now-unused names. It should read:

```python
        from agent_toolkit_cli import (
            _pi_settings, pi_extension_install, pi_extension_ops,
        )
        from agent_toolkit_cli.pi_extension_lock import read_lock
        from agent_toolkit_cli.pi_extension_paths import library_lock_path
```

(Remove the now-unused `LockEntry, add_entry, remove_entry, write_lock` and `lock_file_path` imports from this method. `pi_extension_install` is still needed for the `except` clause. Leave the global-lock read, the `pending`/`grid` setup, the `clear_pending()`, the three `_refresh_*` calls, and the footer/notify code below the loop unchanged.)

- [ ] **Step 4: Run the round-trip test + the existing pi-grid tests**

Run: `uv run pytest tests/test_tui/test_pi_apply_roundtrip.py tests/test_tui/test_pi_grid.py -q`
Expected: PASS — both origins stay removed after apply; existing grid behaviour (toggle queueing) unchanged.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/app.py tests/test_tui/test_pi_apply_roundtrip.py
git commit --no-verify -m "fix(tui): _apply_pi_pending delegates to pi_extension_ops (#333)" --trailer "Device: $(hostname -s)"
```

---

## Task 5: Full-suite sanity + lint

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest -q`
Expected: PASS except the known `tests/test_cli/test_pi_extension_inventory.py::test_empty_machine_is_empty` local-only flake (reads the dev machine's real npm globals; green on CI). Every other test — including all four new files — passes. If anything *else* fails, fix it before continuing.

- [ ] **Step 2: Lint / type-check**

Run: `uv run ruff check src tests && uv run mypy src`
Expected: clean. Fix any findings (e.g. unused imports left in `app.py`).

- [ ] **Step 3: Commit any lint fixes**

```bash
git add -A
git commit --no-verify -m "chore(pi): lint/type fixups for #333" --trailer "Device: $(hostname -s)"
```

(Skip this commit if Steps 1-2 were already clean.)

---

## Self-review notes

- **Spec coverage:** npm identity fix → Task 1; shared core + store-owned-keeps-lock → Task 2; CLI delegation + CLI regression → Task 3; TUI delegation + round-trip (both origins) → Task 4; full DoD (CLI global removal correct, TUI delegates, row stays unchecked, RED-first tests both surfaces/origins) → Tasks 1-4, verified in Task 5.
- **Out of scope respected:** project-scope deselect untouched (core preserves the `if scope == "project"` project-lock branch verbatim); `remove` verb and exact-match `remove_package` unchanged; inventory derivation unchanged.
- **Type/name consistency:** `_npm_identity` / `remove_package_by_identity` (Task 1) used identically in Tasks 2-4; `pi_extension_ops.install` / `.uninstall` signatures match across core, CLI wrappers, and TUI caller; `Scope` imported from `pi_extension_paths` in the core (same `Literal["project","global"]` as `_common.Scope`).
- **Known flake** called out at each `--no-verify` commit so the implementer never mistakes it for their own breakage.
