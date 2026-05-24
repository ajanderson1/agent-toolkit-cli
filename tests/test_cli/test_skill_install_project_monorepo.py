"""Project-scope monorepo install: _parents clone + canonical symlink."""
import json
import subprocess
from pathlib import Path

import pytest

from agent_toolkit_cli import skill_install
from agent_toolkit_cli.skill_lock import (
    LockEntry, add_entry, read_lock, write_lock,
)
from agent_toolkit_cli.skill_paths import library_lock_path

from tests.conftest import scrub_git_env


FIXTURE = Path(__file__).parent.parent / "fixtures" / "monorepo_skills"


def _make_parent_repo(tmp_path: Path) -> str:
    parent_src = tmp_path / "parent-src"
    subprocess.run(["cp", "-R", str(FIXTURE), str(parent_src)], check=True)
    env = scrub_git_env()
    subprocess.run(["git", "init", "-q", "-b", "main"],
                   cwd=parent_src, check=True, env=env)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "add", "."], cwd=parent_src, check=True, env=env)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "-m", "init"],
                   cwd=parent_src, check=True, env=env)
    return f"file://{parent_src}"


@pytest.fixture
def isolated_library(tmp_path, monkeypatch):
    library = tmp_path / "library"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library / "skills"))
    return library


def _seed_global_monorepo_entry(library: Path, parent_url: str, slug: str,
                                 subpath: str) -> None:
    """Write a global lock entry as `skill add` would for a monorepo skill."""
    lock_path = library_lock_path()
    lock = read_lock(lock_path)
    entry = LockEntry(
        source="vercel-labs/agent-browser",
        source_type="github",
        ref=None,
        skill_path=subpath,
        upstream_sha=None,
        local_sha=None,
        parent_url=parent_url,
        read_only=True,
    )
    write_lock(lock_path, add_entry(lock, slug, entry))


def test_ensure_project_canonical_monorepo_symlinks_into_parent(
    tmp_path, isolated_library,
):
    library = isolated_library
    parent_url = _make_parent_repo(tmp_path)
    _seed_global_monorepo_entry(library, parent_url, "mkdocs", "mkdocs")

    project = tmp_path / "proj"
    project.mkdir()

    canonical = skill_install.ensure_project_canonical(
        slug="mkdocs",
        project=project,
        global_lock_path=library_lock_path(),
        env=scrub_git_env(),
    )

    # Canonical is a symlink into the project-local parent clone.
    assert canonical.is_symlink()
    assert (canonical / "SKILL.md").exists()
    assert (canonical / "SKILL.md").read_text().startswith("---\nname: mkdocs")

    parents = project / ".agents" / "skills" / "_parents"
    parent_clones = list(parents.glob("*/*"))
    assert len(parent_clones) == 1
    assert (parent_clones[0] / "mkdocs" / "SKILL.md").exists()

    # Project lock carries parentUrl + skillPath so downstream cmds detect it.
    proj_lock = json.loads((project / "skills-lock.json").read_text())
    e = proj_lock["skills"]["mkdocs"]
    assert e["skillPath"] == "mkdocs"
    assert e["parentUrl"].endswith("/parent-src")
