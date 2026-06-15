"""skill reset for monorepo entries hard-resets the parent clone."""
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


def _add_skill(runner: CliRunner, parent_url: str, library: Path,
               monkeypatch) -> Path:
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library / "skills"))
    r = runner.invoke(cli, ["skill", "add", parent_url, "--skill", "mkdocs"])
    assert r.exit_code == 0, r.output
    candidates = list((library / "skills" / "_parents").glob("*/*"))
    assert len(candidates) == 1, candidates
    return candidates[0]


def test_reset_monorepo_discards_local_commits(tmp_path, monkeypatch):
    """Local commit + upstream commit → reset throws away the local commit
    and snaps to upstream HEAD."""
    parent = _init_parent(tmp_path)
    parent_url = f"file://{parent}"
    library = tmp_path / "library"

    runner = CliRunner()
    parent_clone = _add_skill(runner, parent_url, library, monkeypatch)

    env = scrub_git_env()

    # Local commit the user wouldn't want preserved by --force reset.
    (parent_clone / "mkdocs" / "LOCAL.md").write_text("local change\n")
    for cmd in (
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "local edit"],
    ):
        subprocess.run(cmd, cwd=parent_clone, check=True, env=env)

    # Upstream advances independently.
    (parent / "mkdocs" / "UPSTREAM.md").write_text("upstream change\n")
    for cmd in (
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "upstream edit"],
    ):
        subprocess.run(cmd, cwd=parent, check=True, env=env)

    r = runner.invoke(cli, ["skill", "reset", "mkdocs", "-g"])
    assert r.exit_code == 0, r.output
    assert "reset parent" in r.output

    canonical = library / "skills" / "mkdocs"
    # Local commit gone.
    assert not (canonical / "LOCAL.md").exists()
    # Upstream picked up.
    assert (canonical / "UPSTREAM.md").read_text() == "upstream change\n"


def test_reset_monorepo_refuses_dirty_without_force(tmp_path, monkeypatch):
    """Uncommitted edit in parent clone → reset bails unless --force."""
    parent = _init_parent(tmp_path)
    parent_url = f"file://{parent}"
    library = tmp_path / "library"

    runner = CliRunner()
    parent_clone = _add_skill(runner, parent_url, library, monkeypatch)

    (parent_clone / "mkdocs" / "SKILL.md").write_text("dirty edit\n")

    r = runner.invoke(cli, ["skill", "reset", "mkdocs", "-g"])
    assert r.exit_code != 0, r.output
    assert "dirty" in r.output
    assert "--force" in r.output
    # Uncommitted change must survive the refusal.
    assert (parent_clone / "mkdocs" / "SKILL.md").read_text() == "dirty edit\n"


def test_reset_monorepo_force_discards_dirty_tree(tmp_path, monkeypatch):
    """--force discards both uncommitted edits and local commits."""
    parent = _init_parent(tmp_path)
    parent_url = f"file://{parent}"
    library = tmp_path / "library"

    runner = CliRunner()
    parent_clone = _add_skill(runner, parent_url, library, monkeypatch)

    env = scrub_git_env()

    # Upstream advance.
    (parent / "mkdocs" / "UPSTREAM.md").write_text("upstream\n")
    for cmd in (
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "upstream edit"],
    ):
        subprocess.run(cmd, cwd=parent, check=True, env=env)

    # Uncommitted local mess.
    (parent_clone / "mkdocs" / "SKILL.md").write_text("dirty edit\n")

    r = runner.invoke(cli, ["skill", "reset", "mkdocs", "-g", "--force"])
    assert r.exit_code == 0, r.output

    canonical = library / "skills" / "mkdocs"
    # Upstream picked up.
    assert (canonical / "UPSTREAM.md").read_text() == "upstream\n"
    # Dirty edit obliterated — SKILL.md is upstream's content again.
    assert "dirty edit" not in (canonical / "SKILL.md").read_text()


def test_reset_monorepo_updates_upstream_sha(tmp_path, monkeypatch):
    """After reset, the lock entry's upstreamSha matches the parent clone's
    new HEAD."""
    import json

    parent = _init_parent(tmp_path)
    parent_url = f"file://{parent}"
    library = tmp_path / "library"

    runner = CliRunner()
    parent_clone = _add_skill(runner, parent_url, library, monkeypatch)

    env = scrub_git_env()
    (parent / "mkdocs" / "NEW.md").write_text("new\n")
    for cmd in (
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "upstream advance"],
    ):
        subprocess.run(cmd, cwd=parent, check=True, env=env)

    r = runner.invoke(cli, ["skill", "reset", "mkdocs", "-g"])
    assert r.exit_code == 0, r.output

    head = subprocess.run(
        ["git", "-C", str(parent_clone), "rev-parse", "HEAD"],
        check=True, env=env, capture_output=True, text=True,
    ).stdout.strip()

    lock = json.loads((library / "skills-lock.json").read_text())
    assert lock["skills"]["mkdocs"]["upstreamSha"] == head
