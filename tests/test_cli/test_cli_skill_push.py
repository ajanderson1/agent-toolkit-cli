import subprocess
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def test_push_publishes_local_edits(git_sandbox, tmp_path: Path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(fake_home))

    runner = CliRunner()
    runner.invoke(main, [
        "skill", "add", str(git_sandbox.upstream), "--slug", "demo", "-g",
        "--harness", "claude",
    ])
    canonical = fake_home / ".agents" / "skills" / "demo"
    (canonical / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Improved.\n---\n# improved\n"
    )

    result = runner.invoke(main, ["skill", "push", "demo", "-g"])
    assert result.exit_code == 0, result.output

    verify = tmp_path / "verify"
    subprocess.run(
        ["git", "clone", str(git_sandbox.upstream), str(verify)],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    assert "Improved" in (verify / "SKILL.md").read_text()


def test_push_clean_is_noop(git_sandbox, tmp_path: Path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(fake_home))

    runner = CliRunner()
    runner.invoke(main, [
        "skill", "add", str(git_sandbox.upstream), "--slug", "demo", "-g",
        "--harness", "claude",
    ])
    result = runner.invoke(main, ["skill", "push", "demo", "-g"])
    assert result.exit_code == 0
    assert "clean" in result.output.lower() or "nothing" in result.output.lower()


def test_push_does_not_leak_into_outer_repo(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    """Regression: a leaked GIT_DIR from the parent process must not divert
    the self-improvement commit into the outer repo.

    See feedback_git_env_leak.md — this is the exact failure that produced a
    spurious 'self-improvement: ...' commit on the worktree's branch during
    lefthook's pre-commit pytest run.
    """
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(fake_home))

    # Set up an "outer" repo to act as the would-be hijack target.
    outer = tmp_path / "outer"
    subprocess.run(
        ["git", "init", "--initial-branch=main", str(outer)],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    (outer / "seed").write_text("seed\n")
    subprocess.run(
        ["git", "-C", str(outer), "add", "seed"],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(outer), "commit", "-m", "outer-seed"],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    outer_head_before = subprocess.run(
        ["git", "-C", str(outer), "rev-parse", "HEAD"],
        check=True, env=git_sandbox.env, capture_output=True, text=True,
    ).stdout.strip()

    # Simulate the leak.
    monkeypatch.setenv("GIT_DIR", str(outer / ".git"))
    monkeypatch.setenv("GIT_INDEX_FILE", str(outer / ".git" / "index"))

    runner = CliRunner()
    runner.invoke(main, [
        "skill", "add", str(git_sandbox.upstream), "--slug", "demo", "-g",
        "--harness", "claude",
    ])
    canonical = fake_home / ".agents" / "skills" / "demo"
    (canonical / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Improved.\n---\n# improved\n"
    )

    result = runner.invoke(main, ["skill", "push", "demo", "-g"])
    assert result.exit_code == 0, result.output

    outer_head_after = subprocess.run(
        ["git", "-C", str(outer), "rev-parse", "HEAD"],
        check=True, env=git_sandbox.env, capture_output=True, text=True,
    ).stdout.strip()
    assert outer_head_after == outer_head_before, (
        "push leaked into outer repo (GIT_DIR/GIT_INDEX_FILE scrub failed)"
    )
