"""#333: deselecting a pi extension at global scope, applying, and refreshing
must leave it removed — the row stays unchecked. Drives the real TUIApp's
_apply_pi_pending against a seeded tmp HOME for both origins.

This is the round-trip regression: it exercises the actual delegated path
(_apply_pi_pending -> pi_extension_ops.uninstall) against on-disk state, then
asserts the extension is genuinely gone via build_inventory. The npm case is
the proven RED: the pre-fix inline exact-match remove_package("npm:foo") missed
the drifted "foo@1.2.3" entry, so it survived the apply.
"""
from __future__ import annotations

import json

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
    """Build the real app on a seeded HOME, queue a global unlink for slug via
    the grid's pending store, run the real _apply_pi_pending, then read back the
    post-refresh global_loaded for slug from a fresh inventory."""
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        # Match the proven apply-test idiom (test_pi_grid.py): activate the pi
        # kind, grab the always-present #pi-grid, and seed the pending unlink via
        # restore_pending (updates the backing _pending dict that
        # _apply_pi_pending reads through pending_entries()).
        app._active_kind = "pi-extension"
        grid = app.query_one("#pi-grid", PiGrid)
        grid.restore_pending({("global", slug): "unlink"})
        await pilot.pause()
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
