"""End-to-end `agent add` against a fixture category-repo (monorepo) parent.

Mirrors `test_skill_add_monorepo.py`. The agent layout is the DIRECTORY form
`<subpath>/<slug>.md`, so the library canonical symlinks at `<parent>/<subpath>`
and `<canonical>/<slug>.md` resolves the content file. Agents isolate via a
monkeypatched HOME (library at `$HOME/.agent-toolkit/agents`), not a `*_ROOT`
env var.
"""
import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main as cli

from tests.conftest import scrub_git_env


def _agent_md(slug: str) -> str:
    return f"---\nname: {slug}\ndescription: CLI test agent {slug}.\n---\n\nBody.\n"


def _make_parent_repo(tmp_path: Path) -> str:
    """Build a 2-agent category repo (directory form) and return its file URL."""
    parent_src = tmp_path / "agents-fixture"
    for slug in ("project-manager", "docs-curator"):
        d = parent_src / slug
        d.mkdir(parents=True)
        (d / f"{slug}.md").write_text(_agent_md(slug))
    env = scrub_git_env()
    git = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run(["git", "init", "-q", "-b", "main"],
                   cwd=parent_src, check=True, env=env)
    subprocess.run([*git, "add", "."], cwd=parent_src, check=True, env=env)
    subprocess.run([*git, "commit", "-q", "-m", "init"],
                   cwd=parent_src, check=True, env=env)
    return f"file://{parent_src}"


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def _lock(home: Path) -> dict:
    return json.loads((home / ".agent-toolkit" / "agents-lock.json").read_text())


def test_add_explicit_subpath_symlinks_canonical(tmp_path, home):
    parent_url = _make_parent_repo(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, [
        "agent", "add", f"{parent_url}/tree/main/project-manager",
    ])
    assert result.exit_code == 0, result.output

    canonical = home / ".agent-toolkit" / "agents" / "project-manager"
    assert canonical.is_symlink(), "monorepo canonical must be a symlink"
    # The content file resolves through the symlink as <canonical>/<slug>.md.
    assert (canonical / "project-manager.md").read_text().startswith(
        "---\nname: project-manager"
    )

    # Parent cached under the AGENT tree, not the skills tree.
    parents_dir = home / ".agent-toolkit" / "agents" / "_parents"
    clones = list(parents_dir.glob("*/*"))
    assert len(clones) == 1
    assert (clones[0] / "project-manager" / "project-manager.md").exists()
    assert (clones[0] / "docs-curator" / "docs-curator.md").exists()

    e = _lock(home)["skills"]["project-manager"]
    assert e["agentPath"] == "project-manager/project-manager.md"
    assert e["readOnly"] is True
    assert e["parentUrl"].endswith("/agents-fixture")
    # Skills tree must be untouched.
    assert not (home / ".agent-toolkit" / "skills" / "_parents").exists()


def test_add_two_agents_share_one_parent_clone(tmp_path, home):
    parent_url = _make_parent_repo(tmp_path)
    runner = CliRunner()
    r1 = runner.invoke(cli, ["agent", "add", f"{parent_url}/tree/main/project-manager"])
    assert r1.exit_code == 0, r1.output
    r2 = runner.invoke(cli, ["agent", "add", f"{parent_url}/tree/main/docs-curator"])
    assert r2.exit_code == 0, r2.output

    clones = list((home / ".agent-toolkit" / "agents" / "_parents").glob("*/*"))
    assert len(clones) == 1, "both agents must reuse the same parent cache"
    lock = _lock(home)["skills"]
    assert lock["project-manager"]["agentPath"] == "project-manager/project-manager.md"
    assert lock["docs-curator"]["agentPath"] == "docs-curator/docs-curator.md"


def test_add_missing_content_file_fails_without_rmtree_of_parent(tmp_path, home):
    parent_url = _make_parent_repo(tmp_path)
    runner = CliRunner()
    # A subpath that exists as a dir would still need <slug>.md inside it; point
    # at a non-existent subpath to exercise the not-found branch.
    result = runner.invoke(cli, ["agent", "add", f"{parent_url}/tree/main/nonexistent"])
    assert result.exit_code != 0
    assert "nonexistent" in result.output


def test_install_then_remove_unlinks_without_error(tmp_path, home):
    parent_url = _make_parent_repo(tmp_path)
    runner = CliRunner()
    assert runner.invoke(
        cli, ["agent", "add", f"{parent_url}/tree/main/project-manager"]
    ).exit_code == 0
    assert runner.invoke(
        cli, ["agent", "add", f"{parent_url}/tree/main/docs-curator"]
    ).exit_code == 0

    # Install both into the standard claude-code slot.
    inst = runner.invoke(cli, [
        "agent", "install", "project-manager", "-g", "--harnesses", "claude-code",
    ])
    assert inst.exit_code == 0, inst.output
    projected = home / ".claude" / "agents" / "project-manager.md"
    assert projected.exists()
    assert projected.read_text().startswith("---\nname: project-manager")

    # Remove project-manager: must unlink the symlink canonical (NOT rmtree),
    # drop the projection + lock entry, and LEAVE docs-curator + the shared
    # parent clone intact (sibling still points into it).
    rm = runner.invoke(cli, ["agent", "remove", "project-manager"])
    assert rm.exit_code == 0, rm.output
    assert not (home / ".agent-toolkit" / "agents" / "project-manager").exists()
    assert not projected.exists()
    assert "project-manager" not in _lock(home)["skills"]
    assert "docs-curator" in _lock(home)["skills"]
    clones = list((home / ".agent-toolkit" / "agents" / "_parents").glob("*/*"))
    assert len(clones) == 1, "parent clone must survive while a sibling uses it"


def test_remove_last_agent_sweeps_orphaned_parent_clone(tmp_path, home):
    parent_url = _make_parent_repo(tmp_path)
    runner = CliRunner()
    assert runner.invoke(
        cli, ["agent", "add", f"{parent_url}/tree/main/project-manager"]
    ).exit_code == 0

    rm = runner.invoke(cli, ["agent", "remove", "project-manager"])
    assert rm.exit_code == 0, rm.output
    # No surviving lock entry points into the parent → it is swept.
    clones = list((home / ".agent-toolkit" / "agents" / "_parents").glob("*/*"))
    assert clones == [], "orphaned parent clone must be swept on last remove"


def test_add_subpath_agent_added_after_first_clone(tmp_path, home):
    """#276 class: an agent pushed to the category repo AFTER the parent cache
    was first cloned must still resolve (cache is fetch+reset-refreshed)."""
    parent_url = _make_parent_repo(tmp_path)
    parent_src = Path(parent_url[len("file://"):])
    env = scrub_git_env()
    git = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]

    runner = CliRunner()
    assert runner.invoke(
        cli, ["agent", "add", f"{parent_url}/tree/main/project-manager"]
    ).exit_code == 0

    # Grow the category repo with a brand-new agent and commit it.
    fresh = parent_src / "release-manager"
    fresh.mkdir()
    (fresh / "release-manager.md").write_text(_agent_md("release-manager"))
    subprocess.run([*git, "add", "-A"], cwd=parent_src, check=True, env=env)
    subprocess.run([*git, "commit", "-q", "-m", "add release-manager"],
                   cwd=parent_src, check=True, env=env)

    r2 = runner.invoke(cli, ["agent", "add", f"{parent_url}/tree/main/release-manager"])
    assert r2.exit_code == 0, r2.output
    assert "not found in parent" not in r2.output
    clones = list((home / ".agent-toolkit" / "agents" / "_parents").glob("*/*"))
    assert len(clones) == 1, "same reused cache, now refreshed"


def test_single_repo_add_still_works(tmp_path, home):
    """Regression: the no-subpath form must keep cloning the whole repo as the
    canonical with <slug>.md at root — unchanged by the monorepo branch."""
    repo = tmp_path / "solo-agent"
    repo.mkdir()
    (repo / "solo-agent.md").write_text(_agent_md("solo-agent"))
    env = scrub_git_env()
    git = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True, env=env)
    subprocess.run([*git, "add", "."], cwd=repo, check=True, env=env)
    subprocess.run([*git, "commit", "-q", "-m", "init"], cwd=repo, check=True, env=env)

    runner = CliRunner()
    result = runner.invoke(cli, ["agent", "add", f"file://{repo}"])
    assert result.exit_code == 0, result.output
    canonical = home / ".agent-toolkit" / "agents" / "solo-agent"
    assert canonical.is_dir() and not canonical.is_symlink()
    assert (canonical / "solo-agent.md").exists()
    e = _lock(home)["skills"]["solo-agent"]
    assert e["agentPath"] == "solo-agent.md"
    assert e.get("readOnly", False) is False
