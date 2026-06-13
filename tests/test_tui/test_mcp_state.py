import json
from pathlib import Path

import yaml

import agent_toolkit_tui.mcp_state as mcp_state
from agent_toolkit_cli._install_core import InstallError
from agent_toolkit_cli.mcp_lock import McpLockEntry, lock_path_for_scope, write_lock
from agent_toolkit_tui.mcp_state import (
    _cell_for,
    build_mcp_rows,
    mcp_interactive_harnesses,
)


def test_interactive_harnesses_project_has_standard_first():
    # ("standard",) + mcp_nonstandard_main("project")
    assert mcp_interactive_harnesses("project") == (
        "standard", "codex", "opencode",
    )


def test_interactive_harnesses_global_no_standard():
    # No standard column at global (KeyError-guarded covered set).
    assert mcp_interactive_harnesses("global") == (
        "claude-code", "codex", "opencode", "pi",
    )


class _FakeAdapter:
    def __init__(self, installed: bool):
        self._installed = installed

    def is_installed(self, slug, *, scope, home, project):
        return self._installed


def test_cell_for_linked_true(monkeypatch):
    monkeypatch.setattr(mcp_state, "get_adapter", lambda h: _FakeAdapter(True))
    cell = _cell_for("ctx7", "codex", scope="project",
                     home=Path("/home"), project=Path("/proj"))
    assert cell is not None and cell.linked is True


def test_cell_for_linked_false(monkeypatch):
    monkeypatch.setattr(mcp_state, "get_adapter", lambda h: _FakeAdapter(False))
    cell = _cell_for("ctx7", "codex", scope="project",
                     home=Path("/home"), project=Path("/proj"))
    assert cell is not None and cell.linked is False


def test_cell_for_unknown_harness_none(monkeypatch):
    def _boom(h):
        raise InstallError(f"unknown harness {h}")  # real type: UnsupportedMcpHarnessError(InstallError)
    monkeypatch.setattr(mcp_state, "get_adapter", _boom)
    assert _cell_for("ctx7", "bogus", scope="project",
                     home=Path("/home"), project=Path("/proj")) is None


def test_cell_for_standard_at_global_none(monkeypatch):
    # The standard adapter raises InstallError for a global target (no global
    # .mcp.json). _cell_for must swallow it → None, never crash.
    class _GlobalRefuser:
        def is_installed(self, slug, *, scope, home, project):
            raise InstallError("no global standard target")
    monkeypatch.setattr(mcp_state, "get_adapter", lambda h: _GlobalRefuser())
    assert _cell_for("ctx7", "standard", scope="global",
                     home=Path("/home"), project=None) is None


def _seed_library(home: Path, slug: str, *, install_method="npx", version=None):
    """Write a library entry the way `mcp add` does: <root>/<slug>/config.json
    + <root>/<slug>.toolkit.yaml. NOT a lock write."""
    root = home / ".agent-toolkit" / "mcps"
    (root / slug).mkdir(parents=True, exist_ok=True)
    (root / slug / "config.json").write_text(
        json.dumps({"command": "npx", "args": ["-y", slug]}), encoding="utf-8")
    meta = {"install_method": install_method}
    if version:
        meta["resolved_version"] = version
    (root / f"{slug}.toolkit.yaml").write_text(yaml.safe_dump(meta), encoding="utf-8")


def test_build_rows_library_only_is_library_state(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    # A library MCP that was ADDED but never installed → no lock entry at all.
    _seed_library(home, "ctx7", install_method="npx", version="1.2.3")
    monkeypatch.setattr(mcp_state, "_cell_for", lambda *a, **k: None)
    rows = {r.slug: r for r in build_mcp_rows(
        scope="project", home=home, project=tmp_path / "proj")}
    # MUST appear (regression: reading the lock as library would drop it).
    assert "ctx7" in rows
    assert rows["ctx7"].state == "library"
    assert rows["ctx7"].source == "npx"     # from the library asset, not a lock
    assert rows["ctx7"].pin == "1.2.3"


def test_build_rows_installed_and_unlisted(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    project = tmp_path / "proj"
    project.mkdir()
    _seed_library(home, "ctx7", install_method="npx", version="1.2.3")
    # ctx7 is also installed at project scope (in the project lock) → installed.
    # 'stray' is in the project lock but NOT the library → unlisted.
    write_lock(lock_path_for_scope("project", home=home, project=project), {
        "ctx7": [McpLockEntry("ctx7", "codex", "npx", "1.2.3")],
        "stray": [McpLockEntry("stray", "codex", "docker", None)],
    })
    monkeypatch.setattr(mcp_state, "_cell_for", lambda *a, **k: None)
    rows = {r.slug: r for r in build_mcp_rows(
        scope="project", home=home, project=project)}
    assert rows["ctx7"].state == "installed"
    assert rows["stray"].state == "unlisted"
    assert rows["stray"].source == "docker"   # unlisted → from the lock entry
