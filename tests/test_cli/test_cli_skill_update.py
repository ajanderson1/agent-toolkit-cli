import subprocess
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def _add_demo(runner, upstream_path):
    return runner.invoke(main, [
        "skill", "add", str(upstream_path), "--slug", "demo", "-g",
        "--harness", "claude",
    ])


def _advance_upstream(git_sandbox, files: dict[str, str]):
    import shutil
    other = git_sandbox.upstream.parent / "advancer"
    if other.exists():
        shutil.rmtree(other)
    subprocess.run(
        ["git", "clone", str(git_sandbox.upstream), str(other)],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    for name, content in files.items():
        (other / name).write_text(content)
        subprocess.run(
            ["git", "-C", str(other), "add", name],
            check=True, env=git_sandbox.env, capture_output=True,
        )
    subprocess.run(
        ["git", "-C", str(other), "commit", "-m", "advance"],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(other), "push", "origin", "main"],
        check=True, env=git_sandbox.env, capture_output=True,
    )


def test_update_fast_forwards_clean(git_sandbox, tmp_path: Path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(fake_home))

    runner = CliRunner()
    assert _add_demo(runner, git_sandbox.upstream).exit_code == 0
    _advance_upstream(git_sandbox, {"NEW.md": "from upstream\n"})
    result = runner.invoke(main, ["skill", "update", "demo", "-g"])
    assert result.exit_code == 0, result.output
    assert (fake_home / ".agents" / "skills" / "demo" / "NEW.md").exists()


def test_update_surfaces_conflict_and_exits_nonzero(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(fake_home))

    runner = CliRunner()
    assert _add_demo(runner, git_sandbox.upstream).exit_code == 0

    canonical = fake_home / ".agents" / "skills" / "demo"
    (canonical / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Local edit.\n---\n# demo local\n"
    )
    subprocess.run(
        ["git", "-C", str(canonical), "add", "SKILL.md"],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(canonical), "commit", "-m", "local"],
        check=True, env=git_sandbox.env, capture_output=True,
    )

    _advance_upstream(git_sandbox, {
        "SKILL.md":
            "---\nname: demo\ndescription: Upstream edit.\n---\n# demo upstream\n"
    })
    result = runner.invoke(main, ["skill", "update", "demo", "-g"])
    assert result.exit_code != 0
    assert "conflict" in result.output.lower()
    assert "<<<<<<<" in (canonical / "SKILL.md").read_text()
