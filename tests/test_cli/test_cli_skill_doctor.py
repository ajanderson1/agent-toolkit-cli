"""Integration tests for `agent-toolkit-cli skill doctor`."""
from __future__ import annotations

import shutil
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def _seed(runner, upstream, monkeypatch, tmp_path):
    library_root = tmp_path / "lib" / "skills"
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
    r = runner.invoke(main, ["skill", "add", str(upstream), "--slug", "demo"])
    assert r.exit_code == 0, r.output
    return library_root, fake_home


def test_doctor_clean_tree_exit0(git_sandbox, tmp_path: Path, monkeypatch):
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    runner = CliRunner()
    _seed(runner, git_sandbox.upstream, monkeypatch, tmp_path)
    r = runner.invoke(main, ["skill", "doctor", "-g"])
    assert r.exit_code == 0, r.output
    assert "all clean" in r.output


def test_doctor_no_fix_exits_nonzero_with_findings(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    runner = CliRunner()
    library_root, fake_home = _seed(
        runner, git_sandbox.upstream, monkeypatch, tmp_path,
    )
    shutil.rmtree(library_root / "demo")
    r = runner.invoke(main, ["skill", "doctor", "-g", "--no-fix"])
    assert r.exit_code == 1, r.output
    assert "missing_canonical" in r.output


def test_doctor_yes_fixes_drift(git_sandbox, tmp_path: Path, monkeypatch):
    from dataclasses import replace as dc_replace
    from agent_toolkit_cli import skill_agents

    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "home" / ".claude"))
    runner = CliRunner()
    library_root, fake_home = _seed(
        runner, git_sandbox.upstream, monkeypatch, tmp_path,
    )
    # Patch claude-code's global_skills_dir to a path under fake_home.
    original = skill_agents.AGENTS["claude-code"]
    monkeypatch.setitem(
        skill_agents.AGENTS, "claude-code",
        dc_replace(original, global_skills_dir=fake_home / ".claude" / "skills"),
    )
    # Plant a drifted symlink within library_root so it's drift, not foreign.
    elsewhere = library_root / "elsewhere"
    elsewhere.mkdir(parents=True)
    claude_skills = fake_home / ".claude" / "skills"
    claude_skills.mkdir(parents=True)
    stale = claude_skills / "demo"
    stale.symlink_to(elsewhere)
    # 'y' to apply the fix.
    r = runner.invoke(main, ["skill", "doctor", "-g"], input="y\n")
    assert r.exit_code == 0, r.output
    assert stale.resolve() == (library_root / "demo").resolve()


def test_doctor_no_response_skips_and_exits_nonzero(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    from dataclasses import replace as dc_replace
    from agent_toolkit_cli import skill_agents

    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "home" / ".claude"))
    runner = CliRunner()
    library_root, fake_home = _seed(
        runner, git_sandbox.upstream, monkeypatch, tmp_path,
    )
    original = skill_agents.AGENTS["claude-code"]
    monkeypatch.setitem(
        skill_agents.AGENTS, "claude-code",
        dc_replace(original, global_skills_dir=fake_home / ".claude" / "skills"),
    )
    elsewhere = library_root / "elsewhere"
    elsewhere.mkdir(parents=True)
    claude_skills = fake_home / ".claude" / "skills"
    claude_skills.mkdir(parents=True)
    stale = claude_skills / "demo"
    stale.symlink_to(elsewhere)
    r = runner.invoke(main, ["skill", "doctor", "-g"], input="N\n")
    assert r.exit_code == 1, r.output
    assert stale.resolve() == elsewhere.resolve()  # untouched


def test_doctor_q_breaks_loop(git_sandbox, tmp_path: Path, monkeypatch):
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    runner = CliRunner()
    library_root, fake_home = _seed(
        runner, git_sandbox.upstream, monkeypatch, tmp_path,
    )
    shutil.rmtree(library_root / "demo")
    r = runner.invoke(main, ["skill", "doctor", "-g"], input="q\n")
    assert r.exit_code == 1, r.output
    # Library still missing (we quit before applying).
    assert not (library_root / "demo").exists()
