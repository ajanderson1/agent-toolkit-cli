"""skill push refuses monorepo (read_only) entries with a clear message."""
import subprocess
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main as cli

from tests.conftest import scrub_git_env


FIXTURE = Path(__file__).parent.parent / "fixtures" / "monorepo_skills"


def test_push_monorepo_skill_refuses_with_parent_url(tmp_path, monkeypatch):
    parent = tmp_path / "parent"
    subprocess.run(["cp", "-R", str(FIXTURE), str(parent)], check=True)
    env = scrub_git_env()
    for cmd in (
        ["git", "init", "-q", "-b", "main"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "init"],
    ):
        subprocess.run(cmd, cwd=parent, check=True, env=env)
    parent_url = f"file://{parent}"
    library = tmp_path / "library"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library / "skills"))

    runner = CliRunner()
    r_add = runner.invoke(cli, ["skill", "add", parent_url, "--skill", "mkdocs"])
    assert r_add.exit_code == 0, r_add.output
    result = runner.invoke(cli, ["skill", "push", "mkdocs", "-g"])
    assert result.exit_code != 0
    assert "read-only" in result.output.lower() or "read_only" in result.output.lower()
    assert str(parent) in result.output or parent_url in result.output
