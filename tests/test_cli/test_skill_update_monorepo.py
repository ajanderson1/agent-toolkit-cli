"""skill update for monorepo entries pulls the parent clone."""
import subprocess
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main as cli

from tests.conftest import scrub_git_env


FIXTURE = Path(__file__).parent.parent / "fixtures" / "monorepo_skills"


def _init_parent(tmp_path: Path) -> Path:
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
    return parent


def test_update_monorepo_pulls_parent_and_reflects_new_content(
    tmp_path, monkeypatch,
):
    parent = _init_parent(tmp_path)
    parent_url = f"file://{parent}"
    library = tmp_path / "library"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library / "skills"))

    runner = CliRunner()
    r1 = runner.invoke(cli, ["skill", "add", parent_url, "--skill", "mkdocs"])
    assert r1.exit_code == 0, r1.output

    # Mutate the parent.
    (parent / "mkdocs" / "SKILL.md").write_text(
        "---\nname: mkdocs\ndescription: updated\n---\nnew body\n"
    )
    env = scrub_git_env()
    for cmd in (
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "update"],
    ):
        subprocess.run(cmd, cwd=parent, check=True, env=env)

    r2 = runner.invoke(cli, ["skill", "update", "mkdocs", "-g"])
    assert r2.exit_code == 0, r2.output

    canonical = library / "skills" / "mkdocs"
    assert "new body" in (canonical / "SKILL.md").read_text()


def test_update_monorepo_copy_mode_re_copies(tmp_path, monkeypatch):
    """When materialised: 'copy' is set, update must re-copy from the refreshed
    parent (symlink would auto-pickup; copy must be explicit)."""
    parent = _init_parent(tmp_path)
    parent_url = f"file://{parent}"
    library = tmp_path / "library"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library / "skills"))

    # Force the copy fallback for the install.
    from pathlib import Path as _Path
    def _refuse_symlink(self, target, target_is_directory=False):
        raise OSError("simulated: platform refuses symlinks")
    monkeypatch.setattr(_Path, "symlink_to", _refuse_symlink)

    runner = CliRunner()
    r1 = runner.invoke(cli, ["skill", "add", parent_url, "--skill", "mkdocs"])
    assert r1.exit_code == 0, r1.output

    canonical = library / "skills" / "mkdocs"
    # Should be a real directory, not a symlink.
    assert canonical.is_dir() and not canonical.is_symlink()

    # Mutate the parent.
    (parent / "mkdocs" / "SKILL.md").write_text(
        "---\nname: mkdocs\ndescription: updated\n---\nupdated copy body\n"
    )
    env = scrub_git_env()
    import subprocess as _sp
    for cmd in (
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "update"],
    ):
        _sp.run(cmd, cwd=parent, check=True, env=env)

    r2 = runner.invoke(cli, ["skill", "update", "mkdocs", "-g"])
    assert r2.exit_code == 0, r2.output

    # Re-copy should have happened: the stale snapshot is gone.
    assert "updated copy body" in (canonical / "SKILL.md").read_text()
