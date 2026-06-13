"""CLI smoke tests for the mcp command group."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import yaml
from click.testing import CliRunner

from agent_toolkit_cli.cli import main


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
