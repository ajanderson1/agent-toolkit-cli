"""Relocated project canonical: external store + uniform projection symlinks."""
import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli import skill_install
from agent_toolkit_cli.cli import main as cli
from agent_toolkit_cli.skill_lock import LockEntry, add_entry, read_lock, write_lock
from agent_toolkit_cli.skill_paths import (
    canonical_skill_dir, library_lock_path, project_store_root,
)

from tests.conftest import scrub_git_env

FIXTURE = Path(__file__).parent.parent / "fixtures" / "monorepo_skills"


def _make_parent_repo(tmp_path: Path) -> str:
    parent_src = tmp_path / "parent-src"
    subprocess.run(["cp", "-R", str(FIXTURE), str(parent_src)], check=True)
    env = scrub_git_env()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=parent_src, check=True, env=env)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
                   cwd=parent_src, check=True, env=env)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "-m", "init"], cwd=parent_src, check=True, env=env)
    return f"file://{parent_src}"


@pytest.fixture
def isolated_library(tmp_path, monkeypatch):
    library = tmp_path / "library"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library / "skills"))
    return library


def _seed_global_monorepo_entry(parent_url: str, slug: str, subpath: str) -> None:
    lock_path = library_lock_path()
    lock = read_lock(lock_path)
    entry = LockEntry(
        source="vercel-labs/agent-browser", source_type="github", ref=None,
        skill_path=subpath, upstream_sha=None, local_sha=None,
        parent_url=parent_url, read_only=True,
    )
    write_lock(lock_path, add_entry(lock, slug, entry))


def test_project_universal_gets_symlink_into_external_store(
    tmp_path, isolated_library, monkeypatch,
):
    parent_url = _make_parent_repo(tmp_path)
    _seed_global_monorepo_entry(parent_url, "mkdocs", "mkdocs")
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.chdir(project)

    # codex is a universal agent (skills_dir == ".agents/skills"). Under the
    # inverted skip rule it must now get a real projection symlink there, since
    # the canonical no longer lives in the tree for it to read directly.
    runner = CliRunner(env=scrub_git_env())
    result = runner.invoke(cli, ["skill", "install", "mkdocs",
                                 "--agents", "codex", "-p"])
    assert result.exit_code == 0, result.output

    canonical = canonical_skill_dir("mkdocs", scope="project", project=project)
    assert canonical == project_store_root(project) / "mkdocs"
    assert (canonical / "SKILL.md").exists()

    uni = project / ".agents" / "skills" / "mkdocs"
    assert uni.is_symlink(), "project-universal must now get a projection symlink"
    assert (uni / "SKILL.md").exists()

    # The _parents cache lives in the external store, never in the project tree.
    assert not (project / ".agents" / "skills" / "_parents").exists()


def test_ensure_project_canonical_writes_to_external_store(
    tmp_path, isolated_library,
):
    parent_url = _make_parent_repo(tmp_path)
    _seed_global_monorepo_entry(parent_url, "mkdocs", "mkdocs")
    project = tmp_path / "proj"
    project.mkdir()

    canonical = skill_install.ensure_project_canonical(
        slug="mkdocs", project=project,
        global_lock_path=library_lock_path(), env=scrub_git_env(),
    )
    assert canonical == project_store_root(project) / "mkdocs"
    assert canonical.is_symlink()  # monorepo → symlink into store _parents
    assert (canonical / "SKILL.md").exists()
    assert (project_store_root(project) / "_parents").exists()
    assert not (project / ".agents" / "skills" / "_parents").exists()
    e = json.loads((project / "skills-lock.json").read_text())["skills"]["mkdocs"]
    assert e["parentUrl"].endswith("/parent-src")


def _make_intree_clone(project: Path, slug: str, marker: str) -> Path:
    """Simulate an old-layout in-tree single-skill clone with a marker file."""
    old = project / ".agents" / "skills" / slug
    old.mkdir(parents=True)
    (old / "SKILL.md").write_text(f"---\nname: {slug}\n---\n")
    (old / "MARKER.txt").write_text(marker)
    env = scrub_git_env()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=old, check=True, env=env)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "add", "."], cwd=old, check=True, env=env)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "-m", "x"], cwd=old, check=True, env=env)
    return old


def test_migrate_moves_intree_clone_to_store(tmp_path, isolated_library):
    project = tmp_path / "proj"
    project.mkdir()
    _make_intree_clone(project, "solo", "keepme")

    skill_install.migrate_project_canonical(project=project, slug="solo")

    dest = project_store_root(project) / "solo"
    assert dest.is_dir() and not dest.is_symlink()
    assert (dest / "MARKER.txt").read_text() == "keepme"  # dirty work preserved
    assert (dest / ".git").exists()  # git history travels
    old = project / ".agents" / "skills" / "solo"
    assert old.is_symlink()
    assert old.resolve() == dest.resolve()


def test_migrate_is_idempotent(tmp_path, isolated_library):
    project = tmp_path / "proj"
    project.mkdir()
    _make_intree_clone(project, "solo", "v1")
    skill_install.migrate_project_canonical(project=project, slug="solo")
    skill_install.migrate_project_canonical(project=project, slug="solo")
    dest = project_store_root(project) / "solo"
    assert (dest / "MARKER.txt").read_text() == "v1"
    assert not list((project_store_root(project)).glob("solo.bak-*"))


def test_migrate_backs_up_destination_collision(tmp_path, isolated_library):
    project = tmp_path / "proj"
    project.mkdir()
    dest = project_store_root(project) / "solo"
    dest.mkdir(parents=True)
    (dest / "OLD.txt").write_text("old-dest")
    _make_intree_clone(project, "solo", "new-intree")

    skill_install.migrate_project_canonical(project=project, slug="solo")

    assert (dest / "MARKER.txt").read_text() == "new-intree"
    baks = list(project_store_root(project).glob("solo.bak-*"))
    assert len(baks) == 1
    assert (baks[0] / "OLD.txt").read_text() == "old-dest"


def test_migrate_intree_symlink_is_removed(tmp_path, isolated_library):
    """v2.9.0 monorepo layout: in-tree path is a symlink (holds no work)."""
    project = tmp_path / "proj"
    project.mkdir()
    target = tmp_path / "somewhere"
    target.mkdir()
    old = project / ".agents" / "skills" / "mono"
    old.parent.mkdir(parents=True)
    old.symlink_to(target)

    skill_install.migrate_project_canonical(project=project, slug="mono")

    assert not old.exists() and not old.is_symlink()
