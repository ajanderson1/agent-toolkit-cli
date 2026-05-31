"""End-to-end CLI tests for pi-extension write verbs (Tasks 4-8).

Tasks in this file:
  Task 4: add_cmd (global-only, npm + store-owned)
  Task 5: install/uninstall round-trips at both scopes + idempotency + npm toggle
  Task 6: remove verb
  Task 7: full write-path loop + inventory state reflection
  Task 8: Pi-only matrix-parity guard (in test_pi_extension_pi_only.py)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli import _pi_settings
from agent_toolkit_cli import pi_extension_paths as pep
from agent_toolkit_cli.cli import main
from agent_toolkit_cli.pi_extension_lock import read_lock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _add_store_owned(tmp_path: Path, env: dict[str, str], upstream: Path) -> None:
    """Add a store-owned ext named 'demo' to the global library via CLI."""
    r = CliRunner().invoke(main, ["pi-extension", "add", str(upstream), "--slug", "demo"])
    assert r.exit_code == 0, r.output


# ---------------------------------------------------------------------------
# Task 4: add_cmd
# ---------------------------------------------------------------------------


def test_add_npm_via_cli(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    r = CliRunner().invoke(main, ["pi-extension", "add", "npm:@scope/foo"])
    assert r.exit_code == 0, r.output
    lock = read_lock(pep.library_lock_path(env={}))
    assert lock.skills["@scope/foo"].source_type == "npm"


def test_add_has_no_project_flag(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    r = CliRunner().invoke(main, ["pi-extension", "add", "npm:x", "-p"])
    assert r.exit_code != 0  # global-only: -p is not a valid option


# ---------------------------------------------------------------------------
# Task 5: install / uninstall round-trips
# ---------------------------------------------------------------------------


def test_store_owned_install_uninstall_global_round_trip(tmp_path, monkeypatch, git_sandbox):
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path))  # keep HOME as tmp, not overridden
    _add_store_owned(tmp_path, git_sandbox.env, git_sandbox.upstream)

    link = pep.pi_extension_dir("demo", scope="global", home=tmp_path)
    canonical = pep.library_pi_extension_path("demo", env={})

    r = CliRunner().invoke(main, ["pi-extension", "install", "demo", "-g"])
    assert r.exit_code == 0, r.output
    assert link.is_symlink() and link.resolve() == canonical.resolve()

    r = CliRunner().invoke(main, ["pi-extension", "uninstall", "demo", "-g"])
    assert r.exit_code == 0, r.output
    assert not link.exists() and not link.is_symlink()   # ASSERT GONE
    assert canonical.exists()                            # store copy preserved


def test_store_owned_install_uninstall_project_round_trip(tmp_path, monkeypatch, git_sandbox):
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path))
    _add_store_owned(tmp_path, git_sandbox.env, git_sandbox.upstream)

    proj = tmp_path / "proj"
    proj.mkdir()
    link = pep.pi_extension_dir("demo", scope="project", project=proj)
    canonical = pep.library_pi_extension_path("demo", env={})

    r = CliRunner().invoke(main, ["pi-extension", "install", "demo", "-p"],
                           obj={"project_root": proj})
    assert r.exit_code == 0, r.output
    assert link.is_symlink() and link.resolve() == canonical.resolve()
    # project lock entry written AFTER projection
    proj_lock = read_lock(proj / "pi-extensions-lock.json")
    assert "demo" in proj_lock.skills

    r = CliRunner().invoke(main, ["pi-extension", "uninstall", "demo", "-p"],
                           obj={"project_root": proj})
    assert r.exit_code == 0, r.output
    assert not link.exists() and not link.is_symlink()   # ASSERT GONE
    assert canonical.exists()                            # global store preserved
    proj_lock = read_lock(proj / "pi-extensions-lock.json")
    assert "demo" not in proj_lock.skills                # lock entry cleared


def test_double_install_is_idempotent(tmp_path, monkeypatch, git_sandbox):
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path))
    _add_store_owned(tmp_path, git_sandbox.env, git_sandbox.upstream)
    r1 = CliRunner().invoke(main, ["pi-extension", "install", "demo", "-g"])
    r2 = CliRunner().invoke(main, ["pi-extension", "install", "demo", "-g"])
    assert r1.exit_code == 0 and r2.exit_code == 0, (r1.output, r2.output)
    link = pep.pi_extension_dir("demo", scope="global", home=tmp_path)
    assert link.is_symlink()


def test_double_uninstall_is_safe(tmp_path, monkeypatch, git_sandbox):
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path))
    _add_store_owned(tmp_path, git_sandbox.env, git_sandbox.upstream)
    CliRunner().invoke(main, ["pi-extension", "install", "demo", "-g"])
    r1 = CliRunner().invoke(main, ["pi-extension", "uninstall", "demo", "-g"])
    r2 = CliRunner().invoke(main, ["pi-extension", "uninstall", "demo", "-g"])
    assert r1.exit_code == 0 and r2.exit_code == 0, (r1.output, r2.output)


def test_npm_install_uninstall_global_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    CliRunner().invoke(main, ["pi-extension", "add", "npm:@scope/foo"])

    r = CliRunner().invoke(main, ["pi-extension", "install", "@scope/foo", "-g"])
    assert r.exit_code == 0, r.output
    assert "npm:@scope/foo" in _pi_settings.read_packages(scope="global", home=tmp_path)

    r = CliRunner().invoke(main, ["pi-extension", "uninstall", "@scope/foo", "-g"])
    assert r.exit_code == 0, r.output
    assert "npm:@scope/foo" not in _pi_settings.read_packages(scope="global", home=tmp_path)


def test_npm_install_project_scope(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    CliRunner().invoke(main, ["pi-extension", "add", "npm:bar"])
    proj = tmp_path / "proj"
    proj.mkdir()
    r = CliRunner().invoke(main, ["pi-extension", "install", "bar", "-p"],
                           obj={"project_root": proj})
    assert r.exit_code == 0, r.output
    assert "npm:bar" in _pi_settings.read_packages(scope="project", project=proj)
    # global settings untouched
    assert "npm:bar" not in _pi_settings.read_packages(scope="global", home=tmp_path)


def test_install_refuses_foreign_dir_at_cli(tmp_path, monkeypatch, git_sandbox):
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path))
    _add_store_owned(tmp_path, git_sandbox.env, git_sandbox.upstream)
    link = pep.pi_extension_dir("demo", scope="global", home=tmp_path)
    link.parent.mkdir(parents=True, exist_ok=True)
    link.mkdir()
    (link / "index.ts").write_text("user ext")
    r = CliRunner().invoke(main, ["pi-extension", "install", "demo", "-g"])
    assert r.exit_code != 0
    assert "doctor" in r.output.lower() or "conflict" in r.output.lower()
    assert (link / "index.ts").read_text() == "user ext"  # untouched


# ---------------------------------------------------------------------------
# Task 6: remove verb
# ---------------------------------------------------------------------------


def test_remove_drops_store_and_lock(tmp_path, monkeypatch, git_sandbox):
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path))
    _add_store_owned(tmp_path, git_sandbox.env, git_sandbox.upstream)
    canonical = pep.library_pi_extension_path("demo", env={})
    assert canonical.exists()

    r = CliRunner().invoke(main, ["pi-extension", "remove", "demo"])
    assert r.exit_code == 0, r.output
    assert not canonical.exists()
    lock = read_lock(pep.library_lock_path(env={}))
    assert "demo" not in lock.skills


def test_remove_npm_drops_lock_no_store(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    CliRunner().invoke(main, ["pi-extension", "add", "npm:foo"])
    r = CliRunner().invoke(main, ["pi-extension", "remove", "foo"])
    assert r.exit_code == 0, r.output
    assert "foo" not in read_lock(pep.library_lock_path(env={})).skills


def test_remove_dirty_store_refused_without_force(tmp_path, monkeypatch, git_sandbox):
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path))
    _add_store_owned(tmp_path, git_sandbox.env, git_sandbox.upstream)
    canonical = pep.library_pi_extension_path("demo", env={})
    (canonical / "DIRTY.txt").write_text("uncommitted")
    r = CliRunner().invoke(main, ["pi-extension", "remove", "demo"])
    assert r.exit_code != 0
    assert canonical.exists()  # not deleted
    # --force overrides
    r2 = CliRunner().invoke(main, ["pi-extension", "remove", "demo", "--force"])
    assert r2.exit_code == 0, r2.output
    assert not canonical.exists()


def test_remove_unknown_slug_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    r = CliRunner().invoke(main, ["pi-extension", "remove", "nope"])
    assert r.exit_code != 0


# ---------------------------------------------------------------------------
# Task 7: full write-path loop + inventory state reflection
# ---------------------------------------------------------------------------


def test_full_loop_store_owned_then_inventory(tmp_path, monkeypatch, git_sandbox):
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path))
    runner = CliRunner()

    # add -> not yet projected
    assert runner.invoke(main, ["pi-extension", "add", str(git_sandbox.upstream),
                                "--slug", "demo"]).exit_code == 0
    out = runner.invoke(main, ["pi-extension", "list", "-g", "--json"])
    rows = {r["slug"]: r for r in json.loads(out.output)}
    assert rows["demo"]["origin"] == "store-owned"
    assert rows["demo"]["globalLoaded"] is False  # added, not installed

    # Write index.ts into the cloned canonical so _discover_loose flags it loaded.
    canonical = pep.library_pi_extension_path("demo", env={})
    (canonical / "index.ts").write_text("export default {}")

    # install -> projected, inventory shows loaded
    assert runner.invoke(main, ["pi-extension", "install", "demo", "-g"]).exit_code == 0
    out = runner.invoke(main, ["pi-extension", "list", "-g", "--json"])
    rows = {r["slug"]: r for r in json.loads(out.output)}
    assert rows["demo"]["globalLoaded"] is True

    # uninstall -> gone from projection, still store-owned
    assert runner.invoke(main, ["pi-extension", "uninstall", "demo", "-g"]).exit_code == 0
    out = runner.invoke(main, ["pi-extension", "list", "-g", "--json"])
    rows = {r["slug"]: r for r in json.loads(out.output)}
    assert rows["demo"]["origin"] == "store-owned"
    assert rows["demo"]["globalLoaded"] is False

    # remove -> gone entirely
    assert runner.invoke(main, ["pi-extension", "remove", "demo"]).exit_code == 0
    out = runner.invoke(main, ["pi-extension", "list", "-g", "--json"])
    slugs = {r["slug"] for r in json.loads(out.output)}
    assert "demo" not in slugs


def test_full_loop_npm_then_inventory(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    runner = CliRunner()
    assert runner.invoke(main, ["pi-extension", "add", "npm:@scope/foo"]).exit_code == 0
    assert runner.invoke(main, ["pi-extension", "install", "@scope/foo", "-g"]).exit_code == 0
    out = runner.invoke(main, ["pi-extension", "list", "-g", "--json"])
    rows = {r["slug"]: r for r in json.loads(out.output)}
    assert rows["@scope/foo"]["origin"] == "npm"
    assert rows["@scope/foo"]["globalLoaded"] is True
