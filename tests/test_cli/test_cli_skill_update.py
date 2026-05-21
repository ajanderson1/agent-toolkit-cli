import subprocess
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def _add_demo_project(runner, upstream_path, project):
    (project / ".claude").mkdir(exist_ok=True)
    return runner.invoke(main, [
        "--project", str(project),
        "skill", "add", str(upstream_path), "--slug", "demo", "-p",
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
    project = tmp_path / "proj"
    project.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)

    runner = CliRunner()
    assert _add_demo_project(runner, git_sandbox.upstream, project).exit_code == 0
    _advance_upstream(git_sandbox, {"NEW.md": "from upstream\n"})
    result = runner.invoke(main, [
        "--project", str(project), "skill", "update", "demo", "-p",
    ])
    assert result.exit_code == 0, result.output
    assert (project / ".agents" / "skills" / "demo" / "NEW.md").exists()


def test_update_surfaces_conflict_and_exits_nonzero(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    project = tmp_path / "proj"
    project.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)

    runner = CliRunner()
    assert _add_demo_project(runner, git_sandbox.upstream, project).exit_code == 0

    canonical = project / ".agents" / "skills" / "demo"
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
    result = runner.invoke(main, [
        "--project", str(project), "skill", "update", "demo", "-p",
    ])
    assert result.exit_code != 0
    assert "conflict" in result.output.lower()
    assert "<<<<<<<" in (canonical / "SKILL.md").read_text()
