"""skill push refuses monorepo (read_only) entries with a clear message."""
import subprocess
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main as cli

from tests.conftest import scrub_git_env


FIXTURE = Path(__file__).parent.parent / "fixtures" / "monorepo_skills"


def _setup_monorepo_parent(tmp_path, monkeypatch) -> str:
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
    library = tmp_path / "library"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library / "skills"))
    return f"file://{parent}", parent


def test_push_monorepo_skill_refuses_with_parent_url(tmp_path, monkeypatch):
    parent_url, parent = _setup_monorepo_parent(tmp_path, monkeypatch)
    runner = CliRunner()
    r_add = runner.invoke(cli, ["skill", "add", parent_url, "--skill", "mkdocs"])
    assert r_add.exit_code == 0, r_add.output
    result = runner.invoke(cli, ["skill", "push", "mkdocs", "-g"])
    assert result.exit_code != 0
    assert "read-only" in result.output.lower() or "read_only" in result.output.lower()
    assert str(parent) in result.output or parent_url in result.output


def test_push_monorepo_skill_direct_also_refuses(tmp_path, monkeypatch):
    """--direct must NOT bypass the read-only rejection; sharing changes
    back to a monorepo parent still requires a manual PR there."""
    parent_url, parent = _setup_monorepo_parent(tmp_path, monkeypatch)
    runner = CliRunner()
    r_add = runner.invoke(cli, ["skill", "add", parent_url, "--skill", "mkdocs"])
    assert r_add.exit_code == 0, r_add.output
    result = runner.invoke(cli, ["skill", "push", "--direct", "mkdocs", "-g"])
    assert result.exit_code != 0
    assert "read-only" in result.output.lower() or "read_only" in result.output.lower()
    assert str(parent) in result.output or parent_url in result.output
