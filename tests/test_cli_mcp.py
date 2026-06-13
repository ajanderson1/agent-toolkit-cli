"""CLI smoke tests for the mcp command group."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def _seed_global_sentinels(home: Path) -> None:
    """Create the per-harness global-scope sentinel dirs so an install isn't skipped.

    At global scope the facade refuses to mkdir-p a harness into existence: a
    harness whose sentinel dir is absent is warned-and-skipped. These four dirs
    mark all four harnesses as "installed on this machine" so the install fans
    out to every adapter. (At PROJECT scope no sentinel is needed — the config
    file is project-rooted.)
    """
    (home / ".claude").mkdir(parents=True, exist_ok=True)
    (home / ".codex").mkdir(parents=True, exist_ok=True)
    (home / ".config" / "opencode").mkdir(parents=True, exist_ok=True)
    (home / ".pi" / "agent" / "npm" / "node_modules" / "pi-mcp-adapter").mkdir(
        parents=True, exist_ok=True
    )


def _git(directory: Path, *args: str) -> None:
    """Run a git command in `directory`, isolated from the caller's identity."""
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@e",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@e",
        "HOME": str(directory),  # keep global git config out of the test
        "PATH": __import__("os").environ.get("PATH", ""),
    }
    subprocess.run(
        ["git", "-C", str(directory), *args],
        check=True, capture_output=True, env=env,
    )


def _head_sha(directory: Path) -> str:
    out = subprocess.run(
        ["git", "-C", str(directory), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    )
    return out.stdout.strip()


def _seed(home: Path, slug: str = "context7", *, env: list[str] | None = None) -> Path:
    """Seed a library entry under ~/.agent-toolkit/mcps/. Returns the library root."""
    library = home / ".agent-toolkit" / "mcps"
    d = library / slug
    d.mkdir(parents=True)
    (d / "config.json").write_text('{"type":"stdio","command":"npx","args":["-y","ctx7@9.9.9"]}\n')
    (d / "README.md").write_text(f"# {slug}\n")
    sidecar = (
        f"name: {slug}\ndescription: x.\ntransport: stdio\n"
        f"install_method: npx\nresolved_version: 9.9.9\n"
    )
    if env:
        sidecar += "env:\n" + "".join(f"  - {v}\n" for v in env)
    (library / f"{slug}.toolkit.yaml").write_text(sidecar)
    return library


def test_mcp_group_registered():
    result = CliRunner().invoke(main, ["mcp", "--help"])
    assert result.exit_code == 0
    assert "install" in result.output
    assert "uninstall" in result.output


def test_mcps_alias_registered():
    result = CliRunner().invoke(main, ["mcps", "--help"])
    assert result.exit_code == 0
    assert "install" in result.output


def test_mcp_install_project_claude(tmp_path, monkeypatch):
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    result = CliRunner().invoke(
        main, ["mcp", "install", "context7", "--harness", "claude-code", "-p"],
    )
    assert result.exit_code == 0, result.output
    doc = json.loads((project / ".mcp.json").read_text())
    assert "context7" in doc["mcpServers"]


def test_mcp_install_absent_slug_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.chdir(project)
    result = CliRunner().invoke(
        main, ["mcp", "install", "nope", "--harness", "claude-code", "-p"],
    )
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


def test_mcp_list_shows_seeded_slug(tmp_path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(main, ["mcp", "list", "-g"])
    assert result.exit_code == 0, result.output
    assert "context7" in result.output
    assert "9.9.9" in result.output


def test_mcp_status_after_install(tmp_path, monkeypatch):
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    CliRunner().invoke(main, ["mcp", "install", "context7", "--harness", "claude-code", "-p"])
    result = CliRunner().invoke(main, ["mcp", "status", "-p"])
    assert result.exit_code == 0, result.output
    assert "context7" in result.output
    assert "claude-code" in result.output


def test_mcp_uninstall_round_trip(tmp_path, monkeypatch):
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    CliRunner().invoke(main, ["mcp", "install", "context7", "--harness", "claude-code", "-p"])
    result = CliRunner().invoke(main, ["mcp", "uninstall", "context7", "-p"])
    assert result.exit_code == 0, result.output
    doc = json.loads((project / ".mcp.json").read_text())
    assert "context7" not in doc.get("mcpServers", {})


def test_mcp_add_url_authors_entry(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(
        main, ["mcp", "add", "--url", "https://mcp.example.com/sse", "--slug", "exmcp"],
    )
    assert result.exit_code == 0, result.output
    cfg = json.loads((tmp_path / ".agent-toolkit" / "mcps" / "exmcp" / "config.json").read_text())
    assert cfg == {"type": "http", "url": "https://mcp.example.com/sse"}


def test_mcp_add_reauthor_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    CliRunner().invoke(main, ["mcp", "add", "--url", "https://x/sse", "--slug", "dup"])
    result = CliRunner().invoke(main, ["mcp", "add", "--url", "https://x/sse", "--slug", "dup"])
    assert result.exit_code != 0
    assert "already in the library" in result.output
    assert "mcp update dup" in result.output


def test_mcp_add_two_sources_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(
        main, ["mcp", "add", "--url", "https://x/sse", "--docker", "img:1"],
    )
    assert result.exit_code != 0


def test_mcp_add_npx_resolution_failure_floats(tmp_path, monkeypatch):
    """A failed version resolution stores the entry floating, exit 0, with a note."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "agent_toolkit_cli.commands.mcp._resolve.resolve_npm_version",
        lambda pkg: None,
    )
    result = CliRunner().invoke(main, ["mcp", "add", "--npx", "some-pkg", "--slug", "floaty"])
    assert result.exit_code == 0, result.output
    assert "stored floating" in result.output
    sidecar = (tmp_path / ".agent-toolkit" / "mcps" / "floaty.toolkit.yaml").read_text()
    assert "resolved_version" not in sidecar
    cfg = json.loads((tmp_path / ".agent-toolkit" / "mcps" / "floaty" / "config.json").read_text())
    # Floating: no @version appended.
    assert cfg["args"] == ["-y", "some-pkg"]


def test_mcp_add_npx_resolution_pins(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "agent_toolkit_cli.commands.mcp._resolve.resolve_npm_version",
        lambda pkg: "1.2.3",
    )
    result = CliRunner().invoke(main, ["mcp", "add", "--npx", "some-pkg", "--slug", "pinned"])
    assert result.exit_code == 0, result.output
    cfg = json.loads((tmp_path / ".agent-toolkit" / "mcps" / "pinned" / "config.json").read_text())
    assert cfg["args"] == ["-y", "some-pkg@1.2.3"]


def test_mcp_doctor_env_name_only_no_value_leak(tmp_path, monkeypatch):
    """doctor warns with the env var NAME; a seeded VALUE must never appear."""
    _seed(tmp_path, slug="hasenv", env=["DATABASE_URL"])
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    # Ensure the declared var is UNSET so doctor warns about it.
    monkeypatch.delenv("DATABASE_URL", raising=False)
    CliRunner().invoke(main, ["mcp", "install", "hasenv", "--harness", "claude-code", "-p"])
    result = CliRunner().invoke(main, ["mcp", "doctor", "-p"])
    assert "DATABASE_URL" in result.output
    assert "is not set" in result.output


def test_mcp_doctor_env_value_never_leaks(tmp_path, monkeypatch):
    """If the var IS set, doctor must not warn AND must never print its value."""
    _seed(tmp_path, slug="hasenv2", env=["SECRET_TOKEN"])
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SECRET_TOKEN", "super-secret-value-xyz")
    monkeypatch.chdir(project)
    CliRunner().invoke(main, ["mcp", "install", "hasenv2", "--harness", "claude-code", "-p"])
    result = CliRunner().invoke(main, ["mcp", "doctor", "-p"])
    assert "super-secret-value-xyz" not in result.output


def test_mcp_doctor_clean(tmp_path, monkeypatch):
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    CliRunner().invoke(main, ["mcp", "install", "context7", "--harness", "claude-code", "-p"])
    result = CliRunner().invoke(main, ["mcp", "doctor", "-p"])
    assert result.exit_code == 0, result.output
    assert "all clean" in result.output


def test_mcp_doctor_missing_projection(tmp_path, monkeypatch):
    """A lock entry with no live config projection is reported `missing` (exit 1)."""
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    CliRunner().invoke(main, ["mcp", "install", "context7", "--harness", "claude-code", "-p"])
    # Delete the live config behind the lock's back → missing projection.
    (project / ".mcp.json").unlink()
    result = CliRunner().invoke(main, ["mcp", "doctor", "-p"])
    assert result.exit_code == 1
    assert "missing" in result.output


def test_mcp_list_surfaces_unmanaged(tmp_path, monkeypatch):
    """An entry hand-rolled into a harness config (not in our lock) is surfaced."""
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    # Hand-roll a foreign entry directly into .mcp.json.
    (project / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"handrolled": {"type": "stdio", "command": "x"}}}) + "\n"
    )
    # Also create a project lock so list resolves to project scope.
    (project / "mcps-lock.json").write_text('{"version":1,"mcps":{}}\n')
    result = CliRunner().invoke(main, ["mcp", "list", "-p"])
    assert result.exit_code == 0, result.output
    assert "unmanaged" in result.output
    assert "handrolled" in result.output


def test_mcp_list_managed_shared_file_not_flagged_unmanaged(tmp_path, monkeypatch):
    """A slug we manage for claude-code in the shared .mcp.json must NOT be
    reported as `[!] unmanaged (pi)` — pi shares that file and the slug is
    tracked for claude-code there (spec shared-file de-dup). A GENUINELY
    unmanaged entry in the same file MUST still be surfaced (no over-correction).
    """
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)

    # Install context7 for claude-code ONLY at project scope. Pi shares the
    # SAME .mcp.json file but is NOT in the lock for context7.
    inst = CliRunner().invoke(
        main, ["mcp", "install", "context7", "--harness", "claude-code", "-p"]
    )
    assert inst.exit_code == 0, inst.output

    # Hand-write a genuinely-unmanaged entry directly into .mcp.json (not via our
    # CLI, not in any lock). It shares the file but is managed by nobody.
    target = project / ".mcp.json"
    doc = json.loads(target.read_text())
    doc["mcpServers"]["notmine"] = {"type": "stdio", "command": "x"}
    target.write_text(json.dumps(doc, indent=2) + "\n")

    result = CliRunner().invoke(main, ["mcp", "list", "-p"])
    assert result.exit_code == 0, result.output

    # Managed-shared half: context7 is NOT reported unmanaged for ANY harness
    # (it is managed for claude-code in the shared file pi also reads).
    assert "unmanaged: context7" not in result.output

    # Genuine-unmanaged half: notmine IS still surfaced (de-dup didn't hide it).
    assert "[!] unmanaged: notmine" in result.output


def test_mcp_remove_fans_out(tmp_path, monkeypatch):
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    CliRunner().invoke(main, ["mcp", "install", "context7", "--harness", "claude-code", "-p"])
    result = CliRunner().invoke(main, ["mcp", "remove", "context7", "-p"])
    assert result.exit_code == 0, result.output
    doc = json.loads((project / ".mcp.json").read_text())
    assert "context7" not in doc.get("mcpServers", {})
    # Library entry is KEPT (remove is fan-out uninstall, not library delete).
    assert (tmp_path / ".agent-toolkit" / "mcps" / "context7" / "config.json").is_file()


def test_mcp_uninstall_global_claude_running_guard(tmp_path, monkeypatch):
    """`mcp uninstall <slug> -g --harness claude-code` exits non-zero when a
    claude process is detected, and succeeds with --force (symmetric with install)."""
    _seed(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    _seed_global_sentinels(tmp_path)

    # Seed a global claude-code projection with the guard patched OFF.
    monkeypatch.setattr("agent_toolkit_cli.mcp_install._claude_is_running", lambda: False)
    inst = CliRunner().invoke(
        main, ["mcp", "install", "context7", "--harness", "claude-code", "-g"]
    )
    assert inst.exit_code == 0, inst.output
    assert "context7" in json.loads((tmp_path / ".claude.json").read_text())["mcpServers"]

    # Now claude is "running": uninstall without --force must refuse (non-zero).
    monkeypatch.setattr("agent_toolkit_cli.mcp_install._claude_is_running", lambda: True)
    blocked = CliRunner().invoke(
        main, ["mcp", "uninstall", "context7", "-g", "--harness", "claude-code"]
    )
    assert blocked.exit_code != 0
    assert "claude process is running" in blocked.output
    # Projection untouched.
    assert "context7" in json.loads((tmp_path / ".claude.json").read_text())["mcpServers"]

    # With --force it proceeds.
    forced = CliRunner().invoke(
        main, ["mcp", "uninstall", "context7", "-g", "--harness", "claude-code", "--force"]
    )
    assert forced.exit_code == 0, forced.output
    assert "context7" not in json.loads((tmp_path / ".claude.json").read_text())["mcpServers"]


def test_mcp_remove_global_claude_running_guard(tmp_path, monkeypatch):
    """`mcp remove <slug> -g` (fan-out) honors the running-claude guard and --force."""
    _seed(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    _seed_global_sentinels(tmp_path)

    monkeypatch.setattr("agent_toolkit_cli.mcp_install._claude_is_running", lambda: False)
    inst = CliRunner().invoke(
        main, ["mcp", "install", "context7", "--harness", "claude-code", "-g"]
    )
    assert inst.exit_code == 0, inst.output

    monkeypatch.setattr("agent_toolkit_cli.mcp_install._claude_is_running", lambda: True)
    blocked = CliRunner().invoke(main, ["mcp", "remove", "context7", "-g"])
    assert blocked.exit_code != 0
    assert "claude process is running" in blocked.output
    assert "context7" in json.loads((tmp_path / ".claude.json").read_text())["mcpServers"]

    forced = CliRunner().invoke(main, ["mcp", "remove", "context7", "-g", "--force"])
    assert forced.exit_code == 0, forced.output
    assert "context7" not in json.loads((tmp_path / ".claude.json").read_text())["mcpServers"]


def test_mcp_update_repins_and_reprojects(tmp_path, monkeypatch):
    """update re-resolves a moved version, rewrites the library, re-projects."""
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    CliRunner().invoke(main, ["mcp", "install", "context7", "--harness", "claude-code", "-p"])
    monkeypatch.setattr(
        "agent_toolkit_cli.commands.mcp._resolve.resolve_npm_version",
        lambda pkg: "10.0.0",
    )
    result = CliRunner().invoke(main, ["mcp", "update", "context7"])
    assert result.exit_code == 0, result.output
    # Library config re-pinned.
    cfg = json.loads((tmp_path / ".agent-toolkit" / "mcps" / "context7" / "config.json").read_text())
    assert cfg["args"] == ["-y", "ctx7@10.0.0"]
    # Project projection re-pinned.
    doc = json.loads((project / ".mcp.json").read_text())
    assert doc["mcpServers"]["context7"]["args"] == ["-y", "ctx7@10.0.0"]


def test_mcp_add_local_records_source_dir_and_sha(tmp_path, monkeypatch):
    """`add --local` into a git repo records source_dir + HEAD SHA as the version."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    repo = tmp_path / "myserver"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "server.py").write_text("print('v1')\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "v1")
    first_sha = _head_sha(repo)

    result = CliRunner().invoke(
        main, ["mcp", "add", "--local", str(repo), "--command", "python server.py", "--slug", "loc"]
    )
    assert result.exit_code == 0, result.output
    sidecar = yaml.safe_load(
        (tmp_path / ".agent-toolkit" / "mcps" / "loc.toolkit.yaml").read_text()
    )
    assert sidecar["source_dir"] == str(repo.resolve())
    assert sidecar["resolved_version"] == first_sha


def test_mcp_update_local_refreshes_head_sha(tmp_path, monkeypatch):
    """`update` on a --local entry advances resolved_version to the new HEAD SHA,
    and re-projects + re-pins the locked harness to the new SHA."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    repo = tmp_path / "myserver"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "server.py").write_text("print('v1')\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "v1")
    first_sha = _head_sha(repo)

    CliRunner().invoke(
        main, ["mcp", "add", "--local", str(repo), "--command", "python server.py", "--slug", "loc"]
    )
    sidecar_path = tmp_path / ".agent-toolkit" / "mcps" / "loc.toolkit.yaml"
    assert yaml.safe_load(sidecar_path.read_text())["resolved_version"] == first_sha

    # Install into a project so update has a locked projection to refresh.
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.chdir(project)
    CliRunner().invoke(main, ["mcp", "install", "loc", "--harness", "claude-code", "-p"])

    # Advance the repo: a NEW commit → a NEW HEAD SHA.
    (repo / "server.py").write_text("print('v2')\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "v2")
    second_sha = _head_sha(repo)
    assert second_sha != first_sha

    result = CliRunner().invoke(main, ["mcp", "update", "loc"])
    assert result.exit_code == 0, result.output
    # The refresh actually happened: sidecar advanced to the new HEAD SHA.
    assert yaml.safe_load(sidecar_path.read_text())["resolved_version"] == second_sha
    # The moved-version report uses the LIBRARY old→new (not a sampled pin).
    assert f"{first_sha} → {second_sha}" in result.output
    # The project projection's lock pin advanced too.
    lock = json.loads((project / "mcps-lock.json").read_text())
    pins = [e.get("pin") for e in lock["mcps"]["loc"]]
    assert second_sha in pins


def test_mcp_update_local_without_source_dir_is_honest(tmp_path, monkeypatch):
    """A --local entry with no recorded source_dir reports honestly, never crashes
    and never prints a false 'up to date'."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    # Author a local-method entry by hand WITHOUT a source_dir (pre-fix shape).
    library = tmp_path / ".agent-toolkit" / "mcps"
    (library / "legacy").mkdir(parents=True)
    (library / "legacy" / "config.json").write_text(
        '{"type":"stdio","command":"python","args":["server.py"]}\n'
    )
    (library / "legacy.toolkit.yaml").write_text(
        "name: legacy\ninstall_method: local\ntransport: stdio\n"
    )
    result = CliRunner().invoke(main, ["mcp", "update", "legacy"])
    assert result.exit_code == 0, result.output
    assert "no recorded source_dir" in result.output
    assert "up to date" not in result.output


# ---------------------------------------------------------------------------
# Task 9 — both-scope install→uninstall round-trip guards (the project-memory
# mandate). v3 install machinery has repeatedly shipped silently-broken
# global-scope / orphan paths with green CI because tests covered only ONE
# scope or only the happy install. These guards make that impossible for MCP:
# they exercise BOTH scopes and the FULL install→uninstall round-trip.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("scope_flag, scope_name", [("-g", "global"), ("-p", "project")])
def test_install_uninstall_round_trip_both_scopes(tmp_path, monkeypatch, scope_flag, scope_name):
    """install → uninstall leaves the harness config with NO managed entry, at BOTH scopes."""
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    if scope_name == "global":
        # Global claude-code writes ~/.claude.json (live state): the running-claude
        # guard refuses unless we patch it off, and the sentinel must exist.
        _seed_global_sentinels(tmp_path)
        monkeypatch.setattr(
            "agent_toolkit_cli.mcp_install._claude_is_running", lambda: False
        )
    runner = CliRunner()

    r1 = runner.invoke(main, ["mcp", "install", "context7", "--harness", "claude-code", scope_flag])
    assert r1.exit_code == 0, r1.output

    target = (tmp_path / ".claude.json") if scope_name == "global" else (project / ".mcp.json")
    assert "context7" in json.loads(target.read_text())["mcpServers"]

    r2 = runner.invoke(main, ["mcp", "uninstall", "context7", "--harness", "claude-code", scope_flag])
    assert r2.exit_code == 0, r2.output
    assert "context7" not in json.loads(target.read_text())["mcpServers"]


@pytest.mark.parametrize("scope_flag, scope_name", [("-g", "global"), ("-p", "project")])
def test_install_all_four_harnesses_round_trip(tmp_path, monkeypatch, scope_flag, scope_name):
    """All four adapters install AND fully uninstall at both scopes (no orphan projections)."""
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    if scope_name == "global":
        _seed_global_sentinels(tmp_path)
        monkeypatch.setattr(
            "agent_toolkit_cli.mcp_install._claude_is_running", lambda: False
        )
    runner = CliRunner()

    r1 = runner.invoke(main, ["mcp", "install", "context7", scope_flag])  # default = all four
    assert r1.exit_code == 0, r1.output

    r2 = runner.invoke(main, ["mcp", "uninstall", "context7", scope_flag])
    assert r2.exit_code == 0, r2.output

    from agent_toolkit_cli.mcp_adapters import get_adapter
    home = tmp_path
    proj = None if scope_name == "global" else project
    for h in ("claude-code", "codex", "opencode", "pi"):
        assert not get_adapter(h).is_installed(
            "context7", scope=scope_name, home=home, project=proj,
        ), f"{h} left an orphan projection at {scope_name} scope"

    from agent_toolkit_cli.mcp_lock import lock_path_for_scope, read_lock
    lock = read_lock(lock_path_for_scope(scope_name, home=home, project=proj))
    assert "context7" not in lock


@pytest.mark.parametrize("scope_flag, scope_name", [("-g", "global"), ("-p", "project")])
def test_uninstall_preserves_hand_rolled_neighbour(tmp_path, monkeypatch, scope_flag, scope_name):
    """A hand-rolled MCP in the same file survives our install+uninstall."""
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    if scope_name == "global":
        _seed_global_sentinels(tmp_path)
        monkeypatch.setattr(
            "agent_toolkit_cli.mcp_install._claude_is_running", lambda: False
        )

    target = (tmp_path / ".claude.json") if scope_name == "global" else (project / ".mcp.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"mcpServers": {"handrolled": {"command": "x"}}}, indent=2) + "\n")

    runner = CliRunner()
    runner.invoke(main, ["mcp", "install", "context7", "--harness", "claude-code", scope_flag])
    runner.invoke(main, ["mcp", "uninstall", "context7", "--harness", "claude-code", scope_flag])

    doc = json.loads(target.read_text())
    assert doc["mcpServers"]["handrolled"] == {"command": "x"}
    assert "context7" not in doc["mcpServers"]


def test_mcp_update_bump_rewrites_library_sidecar_lock_and_reports(tmp_path, monkeypatch):
    """update with a moved version: library config.json args + sidecar
    resolved_version rewritten, the locked harness shows the new version, the
    lock pin is refreshed, and output carries the `old → new` transparency."""
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    CliRunner().invoke(main, ["mcp", "install", "context7", "--harness", "claude-code", "-p"])

    monkeypatch.setattr(
        "agent_toolkit_cli.commands.mcp._resolve.resolve_npm_version",
        lambda pkg: "10.0.0",
    )
    result = CliRunner().invoke(main, ["mcp", "update", "context7"])
    assert result.exit_code == 0, result.output

    # Library config.json args re-pinned.
    cfg = json.loads((tmp_path / ".agent-toolkit" / "mcps" / "context7" / "config.json").read_text())
    assert cfg["args"] == ["-y", "ctx7@10.0.0"]
    # Library sidecar resolved_version rewritten.
    sidecar = yaml.safe_load(
        (tmp_path / ".agent-toolkit" / "mcps" / "context7.toolkit.yaml").read_text()
    )
    assert sidecar["resolved_version"] == "10.0.0"
    # The locked harness's installed entry shows the new version.
    doc = json.loads((project / ".mcp.json").read_text())
    assert doc["mcpServers"]["context7"]["args"] == ["-y", "ctx7@10.0.0"]
    # Lock pin refreshed.
    lock = json.loads((project / "mcps-lock.json").read_text())
    assert lock["mcps"]["context7"][0]["pin"] == "10.0.0"
    # Transparency: old → new in the output.
    assert "9.9.9 → 10.0.0" in result.output


def test_mcp_update_up_to_date_no_false_bump(tmp_path, monkeypatch):
    """update when the resolver returns the SAME version: no false bump, says `up to date`."""
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    CliRunner().invoke(main, ["mcp", "install", "context7", "--harness", "claude-code", "-p"])

    monkeypatch.setattr(
        "agent_toolkit_cli.commands.mcp._resolve.resolve_npm_version",
        lambda pkg: "9.9.9",  # unchanged
    )
    result = CliRunner().invoke(main, ["mcp", "update", "context7"])
    assert result.exit_code == 0, result.output
    assert "up to date" in result.output
    # No version-bump line (`<old> → <new>`); the bare `→ writing` facade
    # progress line is fine and expected (re-projection is idempotent).
    assert "9.9.9 →" not in result.output
    # Library + projection unchanged.
    cfg = json.loads((tmp_path / ".agent-toolkit" / "mcps" / "context7" / "config.json").read_text())
    assert cfg["args"] == ["-y", "ctx7@9.9.9"]


def test_mcp_update_greedy_cross_scope_refreshes_both(tmp_path, monkeypatch):
    """One flagless `mcp update` from inside a project re-projects + re-pins BOTH
    the global and the current-project projections (greedy cross-scope)."""
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_global_sentinels(tmp_path)
    monkeypatch.setattr("agent_toolkit_cli.mcp_install._claude_is_running", lambda: False)

    # Install at GLOBAL and at PROJECT scope, both with the old pin (9.9.9).
    monkeypatch.chdir(project)
    g = CliRunner().invoke(main, ["mcp", "install", "context7", "--harness", "claude-code", "-g"])
    assert g.exit_code == 0, g.output
    p = CliRunner().invoke(main, ["mcp", "install", "context7", "--harness", "claude-code", "-p"])
    assert p.exit_code == 0, p.output

    # Resolver moves the version; ONE flagless update from inside the project.
    monkeypatch.setattr(
        "agent_toolkit_cli.commands.mcp._resolve.resolve_npm_version",
        lambda pkg: "11.0.0",
    )
    result = CliRunner().invoke(main, ["mcp", "update", "context7"])
    assert result.exit_code == 0, result.output

    # Library rewritten once.
    cfg = json.loads((tmp_path / ".agent-toolkit" / "mcps" / "context7" / "config.json").read_text())
    assert cfg["args"] == ["-y", "ctx7@11.0.0"]

    # GLOBAL projection + lock pin advanced.
    g_doc = json.loads((tmp_path / ".claude.json").read_text())
    assert g_doc["mcpServers"]["context7"]["args"] == ["-y", "ctx7@11.0.0"]
    g_lock = json.loads((tmp_path / ".agent-toolkit" / "mcps-lock.json").read_text())
    assert g_lock["mcps"]["context7"][0]["pin"] == "11.0.0"

    # PROJECT projection + lock pin advanced.
    p_doc = json.loads((project / ".mcp.json").read_text())
    assert p_doc["mcpServers"]["context7"]["args"] == ["-y", "ctx7@11.0.0"]
    p_lock = json.loads((project / "mcps-lock.json").read_text())
    assert p_lock["mcps"]["context7"][0]["pin"] == "11.0.0"

    # Both scopes reported with the old→new transparency.
    assert "9.9.9 → 11.0.0" in result.output
    assert "[global]" in result.output
    assert "[project]" in result.output


def test_mcp_unmanaged_sibling_survives_managed_update(tmp_path, monkeypatch):
    """A hand-rolled (unmanaged) entry stays listed and intact through an update
    of a managed sibling in the same harness config."""
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    CliRunner().invoke(main, ["mcp", "install", "context7", "--harness", "claude-code", "-p"])

    # Hand-roll a foreign neighbour into the same .mcp.json (NOT in our lock).
    target = project / ".mcp.json"
    doc = json.loads(target.read_text())
    doc["mcpServers"]["handrolled"] = {"type": "stdio", "command": "x"}
    target.write_text(json.dumps(doc, indent=2) + "\n")

    # Update the managed sibling; the unmanaged neighbour must be untouched.
    monkeypatch.setattr(
        "agent_toolkit_cli.commands.mcp._resolve.resolve_npm_version",
        lambda pkg: "12.0.0",
    )
    upd = CliRunner().invoke(main, ["mcp", "update", "context7"])
    assert upd.exit_code == 0, upd.output

    after = json.loads(target.read_text())
    assert after["mcpServers"]["handrolled"] == {"type": "stdio", "command": "x"}
    assert after["mcpServers"]["context7"]["args"] == ["-y", "ctx7@12.0.0"]

    # And `list` still surfaces it as unmanaged.
    lst = CliRunner().invoke(main, ["mcp", "list", "-p"])
    assert "unmanaged" in lst.output
    assert "handrolled" in lst.output


def test_mcp_install_project_default_is_standard_not_double_write(tmp_path, monkeypatch):
    """No --harness at project scope → one `standard` lock row for .mcp.json,
    NOT separate claude-code + pi rows (the de-dup #399 delivers)."""
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    result = CliRunner().invoke(main, ["mcp", "install", "context7", "-p"])
    assert result.exit_code == 0, result.output
    doc = json.loads((project / ".mcp.json").read_text())
    assert "context7" in doc["mcpServers"]
    lock = json.loads((project / "mcps-lock.json").read_text())
    harnesses = {e["harness"] for e in lock["mcps"]["context7"]}
    assert "standard" in harnesses
    assert "claude-code" not in harnesses
    assert "pi" not in harnesses


def test_mcp_install_claude_and_pi_collapse_to_standard(tmp_path, monkeypatch):
    """Explicit --harness claude-code --harness pi at project scope → one write,
    one standard row."""
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    result = CliRunner().invoke(
        main,
        ["mcp", "install", "context7", "--harness", "claude-code", "--harness", "pi", "-p"],
    )
    assert result.exit_code == 0, result.output
    lock = json.loads((project / "mcps-lock.json").read_text())
    harnesses = [e["harness"] for e in lock["mcps"]["context7"]]
    assert harnesses == ["standard"]


def test_mcp_install_collapses_preexisting_legacy_lock(tmp_path, monkeypatch):
    """A pre-existing legacy claude-code+pi lock is COLLAPSED by `install -p`
    (the doctor remediation genuinely converges, not a no-op)."""
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    (project / "mcps-lock.json").write_text(json.dumps({
        "version": 1, "mcps": {"context7": [
            {"harness": "claude-code", "source": "npx", "pin": "9.9.9"},
            {"harness": "pi", "source": "npx", "pin": "9.9.9"},
        ]}}, indent=2) + "\n")
    result = CliRunner().invoke(main, ["mcp", "install", "context7", "-p"])
    assert result.exit_code == 0, result.output
    lock = json.loads((project / "mcps-lock.json").read_text())
    harnesses = sorted(e["harness"] for e in lock["mcps"]["context7"])
    assert harnesses == ["codex", "opencode", "standard"]  # legacy rows gone


def test_mcp_uninstall_standard_removes_only_named_entry(tmp_path, monkeypatch):
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    CliRunner().invoke(main, ["mcp", "install", "context7", "-p"])
    doc = json.loads((project / ".mcp.json").read_text())
    doc["mcpServers"]["sibling"] = {"command": "z"}
    (project / ".mcp.json").write_text(json.dumps(doc, indent=2) + "\n")
    result = CliRunner().invoke(
        main, ["mcp", "uninstall", "context7", "--harness", "standard", "-p"],
    )
    assert result.exit_code == 0, result.output
    doc2 = json.loads((project / ".mcp.json").read_text())
    assert "context7" not in doc2["mcpServers"]
    assert doc2["mcpServers"]["sibling"] == {"command": "z"}


def test_mcp_uninstall_claude_normalizes_to_standard(tmp_path, monkeypatch):
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    CliRunner().invoke(main, ["mcp", "install", "context7", "-p"])  # standard row
    result = CliRunner().invoke(
        main, ["mcp", "uninstall", "context7", "--harness", "claude-code", "-p"],
    )
    assert result.exit_code == 0, result.output
    doc = json.loads((project / ".mcp.json").read_text())
    assert "context7" not in doc["mcpServers"]
    lock = json.loads((project / "mcps-lock.json").read_text())
    # claude-code normalized to standard; the standard row is gone (the no-flag
    # `install -p` also wrote codex + opencode rows, which are untouched here).
    harnesses = {e["harness"] for e in lock["mcps"].get("context7", [])}
    assert "standard" not in harnesses  # standard row removed


def test_mcp_list_standard_row_shows_covered_set(tmp_path, monkeypatch):
    """A standard lock row prints its covered set: claude-code, pi."""
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    CliRunner().invoke(main, ["mcp", "install", "context7", "-p"])  # standard row
    result = CliRunner().invoke(main, ["mcp", "list", "-p"])
    assert result.exit_code == 0, result.output
    assert "standard" in result.output
    assert "claude-code" in result.output and "pi" in result.output


def test_mcp_list_standard_install_not_flagged_unmanaged(tmp_path, monkeypatch):
    """A managed standard entry must NOT be falsely re-surfaced as [!] unmanaged."""
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    CliRunner().invoke(main, ["mcp", "install", "context7", "-p"])  # standard row
    result = CliRunner().invoke(main, ["mcp", "list", "-p"])
    assert result.exit_code == 0, result.output
    assert "unmanaged: context7" not in result.output
