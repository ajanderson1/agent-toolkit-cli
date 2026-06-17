"""Tests for the MCP install facade — apply/uninstall/remove + rollback."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_toolkit_cli import mcp_install
from agent_toolkit_cli.mcp_lock import lock_path_for_scope, read_lock


def _seed_library(library: Path, slug="context7"):
    d = library / slug
    d.mkdir(parents=True)
    (d / "config.json").write_text('{"type":"stdio","command":"npx","args":["-y","ctx7@9.9.9"]}\n')
    (d / "README.md").write_text(f"# {slug}\n")
    (library / f"{slug}.toolkit.yaml").write_text(
        f"name: {slug}\ndescription: x.\ntransport: stdio\ninstall_method: npx\nresolved_version: 9.9.9\n"
    )


def test_apply_installs_and_writes_lock_project(tmp_path):
    library = tmp_path / "library"
    _seed_library(library)
    project = tmp_path / "proj"
    project.mkdir()
    mcp_install.apply(
        slug="context7", harnesses=["claude-code"], scope="project",
        library_root=library, home=tmp_path, project=project,
    )
    doc = json.loads((project / ".mcp.json").read_text())
    assert "context7" in doc["mcpServers"]
    lock = read_lock(lock_path_for_scope("project", home=tmp_path, project=project))
    assert lock["context7"][0].harness == "claude-code"


def test_apply_installs_two_harnesses(tmp_path):
    library = tmp_path / "library"
    _seed_library(library)
    project = tmp_path / "proj"
    project.mkdir()
    mcp_install.apply(
        slug="context7", harnesses=["claude-code", "codex"], scope="project",
        library_root=library, home=tmp_path, project=project,
    )
    assert "context7" in json.loads((project / ".mcp.json").read_text())["mcpServers"]
    assert (project / ".codex" / "config.toml").is_file()
    lock = read_lock(lock_path_for_scope("project", home=tmp_path, project=project))
    assert sorted(e.harness for e in lock["context7"]) == ["claude-code", "codex"]


def test_uninstall_removes_projection_keeps_catalog(tmp_path):
    library = tmp_path / "library"
    _seed_library(library)
    project = tmp_path / "proj"
    project.mkdir()
    mcp_install.apply(
        slug="context7", harnesses=["claude-code"], scope="project",
        library_root=library, home=tmp_path, project=project,
    )
    mcp_install.uninstall(
        slug="context7", harnesses=["claude-code"], scope="project",
        library_root=library, home=tmp_path, project=project,
    )
    doc = json.loads((project / ".mcp.json").read_text())
    assert "context7" not in doc["mcpServers"]
    assert (library / "context7" / "config.json").is_file()
    lock = read_lock(lock_path_for_scope("project", home=tmp_path, project=project))
    assert "context7" not in lock


def test_apply_rolls_back_prior_projection_on_later_failure(tmp_path, monkeypatch):
    """If the 2nd harness adapter raises, the 1st harness's projection is rolled back."""
    library = tmp_path / "library"
    _seed_library(library)
    project = tmp_path / "proj"
    project.mkdir()

    from agent_toolkit_cli import mcp_adapters
    real_get = mcp_adapters.get_adapter

    def boom_get(name):
        adapter = real_get(name)
        if name == "codex":
            def explode(*a, **k):
                raise RuntimeError("simulated codex failure")
            adapter.install = explode  # type: ignore[attr-defined]
        return adapter

    monkeypatch.setattr(mcp_install, "get_adapter", boom_get, raising=False)

    with pytest.raises(RuntimeError):
        mcp_install.apply(
            slug="context7", harnesses=["claude-code", "codex"], scope="project",
            library_root=library, home=tmp_path, project=project,
        )
    mcp_path = project / ".mcp.json"
    if mcp_path.is_file():
        assert "context7" not in json.loads(mcp_path.read_text()).get("mcpServers", {})
    lock = read_lock(lock_path_for_scope("project", home=tmp_path, project=project))
    assert "context7" not in lock


def test_apply_skips_uninstalled_harness_sentinel(tmp_path, capsys, monkeypatch):
    """A harness whose sentinel dir is absent is warned-and-skipped, exit 0,
    no projection, no lock entry — at GLOBAL scope (where sentinels live in HOME)."""
    library = tmp_path / "library"
    _seed_library(library)
    # HOME = tmp_path; create claude-code's sentinel (~/.claude) but NOT codex's (~/.codex)
    (tmp_path / ".claude").mkdir()
    # Isolate from the host machine: a real claude process (e.g. this session)
    # would trip the running-claude guard at global scope. This test exercises
    # the sentinel skip, not that guard.
    monkeypatch.setattr(mcp_install, "_claude_is_running", lambda: False)
    result = mcp_install.apply(
        slug="context7", harnesses=["claude-code", "codex"], scope="global",
        library_root=library, home=tmp_path, project=None,
    )
    err = capsys.readouterr().err
    assert "codex" in err and "skipping" in err.lower()
    # claude-code installed (sentinel present), codex skipped (sentinel absent)
    lock = read_lock(lock_path_for_scope("global", home=tmp_path, project=None))
    assert [e.harness for e in lock["context7"]] == ["claude-code"]
    assert not (tmp_path / ".codex" / "config.toml").exists()
    assert result.installed == ["claude-code"]
    assert result.skipped == ["codex"]


def test_apply_global_claude_refused_when_claude_running(tmp_path, monkeypatch):
    """Global-scope claude-code write is refused when a claude process is detected,
    unless --force. We monkeypatch the running-claude probe to simulate detection."""
    library = tmp_path / "library"
    _seed_library(library)
    (tmp_path / ".claude").mkdir()
    monkeypatch.setattr(mcp_install, "_claude_is_running", lambda: True)
    with pytest.raises(mcp_install.RunningClaudeError):
        mcp_install.apply(
            slug="context7", harnesses=["claude-code"], scope="global",
            library_root=library, home=tmp_path, project=None, force=False,
        )
    # No projection, no lock entry
    assert not (tmp_path / ".claude.json").exists() or "context7" not in json.loads((tmp_path / ".claude.json").read_text()).get("mcpServers", {})


def test_apply_global_claude_force_bypasses_running_guard(tmp_path, monkeypatch):
    library = tmp_path / "library"
    _seed_library(library)
    (tmp_path / ".claude").mkdir()
    monkeypatch.setattr(mcp_install, "_claude_is_running", lambda: True)
    mcp_install.apply(
        slug="context7", harnesses=["claude-code"], scope="global",
        library_root=library, home=tmp_path, project=None, force=True,
    )
    doc = json.loads((tmp_path / ".claude.json").read_text())
    assert "context7" in doc["mcpServers"]


def test_apply_warns_on_handrolled_collision(tmp_path, capsys):
    """Upserting over a same-name entry NOT in our lock prints a loud collision warning."""
    library = tmp_path / "library"
    _seed_library(library)
    project = tmp_path / "proj"
    project.mkdir()
    # Pre-seed a hand-rolled context7 entry NOT tracked in our lock
    (project / ".mcp.json").write_text(json.dumps({"mcpServers": {"context7": {"command": "handrolled"}}}, indent=2) + "\n")
    result = mcp_install.apply(
        slug="context7", harnesses=["claude-code"], scope="project",
        library_root=library, home=tmp_path, project=project,
    )
    err = capsys.readouterr().err
    assert "hand-rolled" in err.lower() or "not previously managed" in err.lower()
    assert "context7" in err
    assert result.collisions == ["claude-code"]


def test_remove_fans_out_to_every_locked_harness(tmp_path):
    """remove() uninstalls the slug from every harness recorded in the lock."""
    library = tmp_path / "library"
    _seed_library(library)
    project = tmp_path / "proj"
    project.mkdir()
    mcp_install.apply(
        slug="context7", harnesses=["claude-code", "codex"], scope="project",
        library_root=library, home=tmp_path, project=project,
    )
    mcp_install.remove(
        slug="context7", scope="project",
        library_root=library, home=tmp_path, project=project,
    )
    doc = json.loads((project / ".mcp.json").read_text())
    assert "context7" not in doc["mcpServers"]
    # Codex table removed too
    codex_target = project / ".codex" / "config.toml"
    if codex_target.is_file():
        assert "context7" not in codex_target.read_text()
    lock = read_lock(lock_path_for_scope("project", home=tmp_path, project=project))
    assert "context7" not in lock
    # Library entry preserved (remove is library-sourced; library is SSOT)
    assert (library / "context7" / "config.json").is_file()


def test_remove_no_lock_entry_is_noop(tmp_path, capsys):
    library = tmp_path / "library"
    _seed_library(library)
    project = tmp_path / "proj"
    project.mkdir()
    mcp_install.remove(
        slug="context7", scope="project",
        library_root=library, home=tmp_path, project=project,
    )
    err = capsys.readouterr().err
    assert "nothing to remove" in err.lower()


def _seed_global_claude_projection(library: Path, tmp_path: Path, monkeypatch) -> None:
    """Install context7 for claude-code at GLOBAL scope so a removal has something
    to undo. The running-claude guard is patched off for the SETUP install only."""
    (tmp_path / ".claude").mkdir(exist_ok=True)
    monkeypatch.setattr(mcp_install, "_claude_is_running", lambda: False)
    mcp_install.apply(
        slug="context7", harnesses=["claude-code"], scope="global",
        library_root=library, home=tmp_path, project=None, force=True,
    )


def test_uninstall_global_claude_refused_when_claude_running(tmp_path, monkeypatch):
    """A global-scope claude-code uninstall is refused when a claude process is
    detected (symmetric with apply()) — ~/.claude.json is live state."""
    library = tmp_path / "library"
    _seed_library(library)
    _seed_global_claude_projection(library, tmp_path, monkeypatch)
    # Now simulate a running claude and attempt the removal without --force.
    monkeypatch.setattr(mcp_install, "_claude_is_running", lambda: True)
    with pytest.raises(mcp_install.RunningClaudeError):
        mcp_install.uninstall(
            slug="context7", harnesses=["claude-code"], scope="global",
            library_root=library, home=tmp_path, project=None, force=False,
        )
    # Refused BEFORE any write: the projection + lock entry are still present.
    assert "context7" in json.loads((tmp_path / ".claude.json").read_text())["mcpServers"]
    lock = read_lock(lock_path_for_scope("global", home=tmp_path, project=None))
    assert "context7" in lock


def test_uninstall_global_claude_force_bypasses_running_guard(tmp_path, monkeypatch):
    """--force lets a global-scope claude-code uninstall proceed despite a
    detected claude process."""
    library = tmp_path / "library"
    _seed_library(library)
    _seed_global_claude_projection(library, tmp_path, monkeypatch)
    monkeypatch.setattr(mcp_install, "_claude_is_running", lambda: True)
    mcp_install.uninstall(
        slug="context7", harnesses=["claude-code"], scope="global",
        library_root=library, home=tmp_path, project=None, force=True,
    )
    assert "context7" not in json.loads((tmp_path / ".claude.json").read_text())["mcpServers"]
    lock = read_lock(lock_path_for_scope("global", home=tmp_path, project=None))
    assert "context7" not in lock


def test_uninstall_project_scope_unaffected_by_running_claude(tmp_path, monkeypatch):
    """The running-claude guard is GLOBAL-scope claude-code only: a project-scope
    uninstall (.mcp.json, not ~/.claude.json) proceeds even with claude running."""
    library = tmp_path / "library"
    _seed_library(library)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setattr(mcp_install, "_claude_is_running", lambda: False)
    mcp_install.apply(
        slug="context7", harnesses=["claude-code"], scope="project",
        library_root=library, home=tmp_path, project=project,
    )
    monkeypatch.setattr(mcp_install, "_claude_is_running", lambda: True)
    mcp_install.uninstall(
        slug="context7", harnesses=["claude-code"], scope="project",
        library_root=library, home=tmp_path, project=project, force=False,
    )
    assert "context7" not in json.loads((project / ".mcp.json").read_text())["mcpServers"]


def test_remove_global_claude_refused_when_claude_running(tmp_path, monkeypatch):
    """remove() threads force through to uninstall(): a global-scope claude-code
    removal is refused when claude is running, unless force=True."""
    library = tmp_path / "library"
    _seed_library(library)
    _seed_global_claude_projection(library, tmp_path, monkeypatch)
    monkeypatch.setattr(mcp_install, "_claude_is_running", lambda: True)
    with pytest.raises(mcp_install.RunningClaudeError):
        mcp_install.remove(
            slug="context7", scope="global",
            library_root=library, home=tmp_path, project=None, force=False,
        )
    assert "context7" in json.loads((tmp_path / ".claude.json").read_text())["mcpServers"]
    # With --force it proceeds.
    mcp_install.remove(
        slug="context7", scope="global",
        library_root=library, home=tmp_path, project=None, force=True,
    )
    assert "context7" not in json.loads((tmp_path / ".claude.json").read_text())["mcpServers"]


def test_apply_returns_result_with_installed_skipped(tmp_path, monkeypatch):
    """apply() returns an ApplyResult naming installed + skipped harnesses."""
    library = tmp_path / "library"
    _seed_library(library)
    # HOME = tmp_path; claude-code sentinel present, codex sentinel absent.
    (tmp_path / ".claude").mkdir()
    monkeypatch.setattr(mcp_install, "_claude_is_running", lambda: False)
    result = mcp_install.apply(
        slug="context7", harnesses=["claude-code", "codex"], scope="global",
        library_root=library, home=tmp_path, project=None,
    )
    assert result.installed == ["claude-code"]
    assert "codex" in result.skipped
    assert result.collisions == []


def test_apply_skips_harness_that_cannot_translate(tmp_path, capsys):
    """A harness whose adapter raises InstallError (e.g. opencode cannot
    translate a URL-based MCP) is warned-and-skipped, not a fatal rollback."""
    library = tmp_path / "library"
    d = library / "http-mcp"
    d.mkdir(parents=True)
    (d / "config.json").write_text('{"type":"http","url":"https://example.com/mcp"}\n')
    (d / "README.md").write_text("# http-mcp\n")
    (library / "http-mcp.toolkit.yaml").write_text(
        "name: http-mcp\ntransport: http\ninstall_method: url\n"
    )
    project = tmp_path / "proj"
    project.mkdir()
    result = mcp_install.apply(
        slug="http-mcp", harnesses=["standard", "codex", "opencode"], scope="project",
        library_root=library, home=tmp_path, project=project,
    )
    err = capsys.readouterr().err
    assert "opencode" in err and "cannot translate" in err.lower()
    # standard + codex installed; opencode skipped
    assert sorted(result.installed) == ["codex", "standard"]
    assert result.skipped == ["opencode"]
    lock = read_lock(lock_path_for_scope("project", home=tmp_path, project=project))
    assert sorted(e.harness for e in lock["http-mcp"]) == ["codex", "standard"]


def test_apply_standard_collapses_legacy_claude_pi_rows(tmp_path):
    """Writing a `standard` row drops pre-existing claude-code/pi rows for the
    same slug (collapse-on-install), so the lock converges to one row."""
    # Seed a library asset.
    library = tmp_path / ".agent-toolkit" / "mcps"
    d = library / "context7"
    d.mkdir(parents=True)
    (d / "config.json").write_text('{"type":"stdio","command":"npx","args":["-y","ctx7"]}\n')
    (d / "README.md").write_text("# context7\n")
    (library / "context7.toolkit.yaml").write_text(
        "name: context7\ndescription: x.\ntransport: stdio\ninstall_method: npx\nresolved_version: 1.0.0\n"
    )
    project = tmp_path / "proj"
    project.mkdir()
    # Seed a legacy two-row project lock.
    (project / "mcps-lock.json").write_text(json.dumps({
        "version": 1, "mcps": {"context7": [
            {"harness": "claude-code", "source": "npx", "pin": "1.0.0"},
            {"harness": "pi", "source": "npx", "pin": "1.0.0"},
        ]}}, indent=2) + "\n")

    mcp_install.apply(
        slug="context7", harnesses=["standard"], scope="project",
        library_root=library, home=tmp_path, project=project,
    )

    lock = json.loads((project / "mcps-lock.json").read_text())
    harnesses = [e["harness"] for e in lock["mcps"]["context7"]]
    assert harnesses == ["standard"]  # claude-code + pi collapsed away
