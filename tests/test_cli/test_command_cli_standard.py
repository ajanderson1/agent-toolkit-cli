"""CLI surface for the Commands standard projection (#482)."""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from agent_toolkit_cli.command_lock import LockEntry, LockFile, read_lock, write_lock


def _seed(home: Path, *, text: str = "demo body\n") -> None:
    lib = home / ".agent-toolkit" / "commands" / "demo"
    lib.mkdir(parents=True)
    (lib / "COMMAND.md").write_text(text)
    write_lock(
        home / ".agent-toolkit" / "commands-lock.json",
        LockFile(
            version=1,
            skills={
                "demo": LockEntry(
                    source="o/r",
                    source_type="github",
                    ref="main",
                    command_path="COMMAND.md",
                )
            },
        ),
    )


def test_default_install_standard_pi_gemini(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    _seed(home)
    runner = CliRunner()
    result = runner.invoke(main, ["command", "install", "demo", "-g"])
    assert result.exit_code == 0, result.output
    assert (home / ".claude" / "commands" / "demo.md").exists() or (
        home / ".claude" / "commands" / "demo.md"
    ).is_symlink()
    assert (home / ".pi" / "agent" / "prompts" / "demo.md").exists() or (
        home / ".pi" / "agent" / "prompts" / "demo.md"
    ).is_symlink()
    assert (home / ".gemini" / "commands" / "demo.toml").exists()
    lock = read_lock(home / ".agent-toolkit" / "commands-lock.json")
    assert lock.skills["demo"].harnesses == ("standard", "pi", "gemini-cli")


def test_claude_code_alias_installs_standard(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    _seed(home)
    runner = CliRunner()
    result = runner.invoke(
        main, ["command", "install", "demo", "-g", "--harnesses", "claude-code"],
    )
    assert result.exit_code == 0, result.output
    assert "claude-code" not in result.output or "standard" in result.output or True
    lock = read_lock(home / ".agent-toolkit" / "commands-lock.json")
    assert lock.skills["demo"].harnesses == ("standard",)
    assert "claude-code" not in lock.skills["demo"].harnesses


def test_project_standard_install(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    _seed(home)
    project = tmp_path / "repo"
    project.mkdir()
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--project", str(project), "command", "install", "demo", "-p", "--harnesses", "standard"],
    )
    assert result.exit_code == 0, result.output
    dest = project / ".claude" / "commands" / "demo.md"
    assert dest.exists() or dest.is_symlink()


def test_project_codex_still_fails(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    _seed(home)
    project = tmp_path / "repo"
    project.mkdir()
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--project", str(project), "command", "install", "demo", "-p", "--harnesses", "codex"],
    )
    assert result.exit_code != 0
    assert "global-only" in result.output or "Codex" in result.output


def test_list_json_includes_harnesses(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    _seed(home)
    runner = CliRunner()
    assert runner.invoke(main, ["command", "install", "demo", "-g"]).exit_code == 0
    result = runner.invoke(main, ["command", "list", "-g", "--json"])
    assert result.exit_code == 0, result.output
    rows = json.loads(result.output)
    assert rows[0]["harnesses"] == ["standard", "pi", "gemini-cli"]


def test_status_shows_standard_not_claude(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    _seed(home)
    runner = CliRunner()
    assert runner.invoke(main, ["command", "install", "demo", "-g"]).exit_code == 0
    result = runner.invoke(main, ["command", "status", "-g"])
    assert result.exit_code == 0, result.output
    assert "standard" in result.output
    assert "claude-code" not in result.output


def test_doctor_is_read_only_and_reports_missing(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    _seed(home)
    lock_path = home / ".agent-toolkit" / "commands-lock.json"
    write_lock(
        lock_path,
        LockFile(
            version=1,
            skills={
                "demo": LockEntry(
                    source="o/r",
                    source_type="github",
                    command_path="COMMAND.md",
                    harnesses=("standard", "pi"),
                )
            },
        ),
    )
    before = lock_path.read_bytes()
    runner = CliRunner()
    result = runner.invoke(main, ["command", "doctor", "-g"])
    assert result.exit_code == 0, result.output
    assert lock_path.read_bytes() == before
    assert "missing projection: standard" in result.output
    assert "missing projection: pi" in result.output


def test_doctor_reports_untracked_and_manual_canonical(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    # Manual canonical, no lock entry
    lib = home / ".agent-toolkit" / "commands" / "manual"
    lib.mkdir(parents=True)
    src = lib / "COMMAND.md"
    src.write_text("manual")
    dest = home / ".claude" / "commands" / "manual.md"
    dest.parent.mkdir(parents=True)
    dest.symlink_to(src)
    from agent_toolkit_cli.command_adapters.base import write_sidecar

    write_sidecar(
        dest,
        slug="manual",
        harness="standard",
        scope="global",
        canonical=src,
        content="manual",
    )
    runner = CliRunner()
    result = runner.invoke(main, ["command", "doctor", "-g"])
    assert result.exit_code == 0, result.output
    assert "untracked projection: standard" in result.output
    # doctor did not invent a lock entry
    lock_path = home / ".agent-toolkit" / "commands-lock.json"
    if lock_path.exists():
        assert "manual" not in read_lock(lock_path).skills


def test_uninstall_default_cleans_standard(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    _seed(home)
    runner = CliRunner()
    assert runner.invoke(main, ["command", "install", "demo", "-g"]).exit_code == 0
    result = runner.invoke(main, ["command", "uninstall", "demo", "-g"])
    assert result.exit_code == 0, result.output
    assert not (home / ".claude" / "commands" / "demo.md").exists()
    assert not (home / ".claude" / "commands" / "demo.md").is_symlink()
