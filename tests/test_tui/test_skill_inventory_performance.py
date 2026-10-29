"""Real discovery resource bounds, with no persistent inventory cache."""
from pathlib import Path
import subprocess

import pytest
from click.testing import CliRunner

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.cli import main
from agent_toolkit_cli.skill_lock import LockFormatError, read_lock, write_lock
from agent_toolkit_cli.skill_paths import (
    library_skill_path,
    lock_file_path,
    project_store_root,
)
from agent_toolkit_tui.skill_state import build_skill_rows
from tests.test_cli.test_skill_collection_registration import source, invoke, git


@pytest.fixture
def inventory(source, tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home / ".claude"))
    monkeypatch.chdir(project)
    result = invoke(source)
    assert result.exit_code == 0, result.output
    for slug in ("alpha", "beta"):
        result = CliRunner().invoke(main, [
            "--project", str(project), "skills", "install", slug,
            "--scope", "project", "--agents", "standard",
        ])
        assert result.exit_code == 0, result.output
    return home, project, library_skill_path("alpha").resolve().parent


@pytest.mark.parametrize("scope", ["global", "project"])
def test_clean_shared_checkout_checks_origin_and_status_once(inventory, monkeypatch, scope):
    home, project, backing = inventory
    commands = []
    original = skill_git._run

    def traced(command, **kwargs):
        commands.append(command)
        return original(command, **kwargs)

    monkeypatch.setattr(skill_git, "_run", traced)
    before = (backing / ".git/index").read_bytes()
    rows = build_skill_rows(scope=scope, home=home, project=project if scope == "project" else None)
    assert {r.slug: r.state for r in rows} == {"alpha": "clean", "beta": "clean"}
    assert (backing / ".git/index").read_bytes() == before
    assert sum("config" in cmd for cmd in commands) == 1
    assert sum("status" in cmd for cmd in commands) == 1


def test_project_lock_reads_are_bounded_per_scan(inventory, monkeypatch):
    home, project, _ = inventory
    path = lock_file_path(scope="project", project=project)
    reads = []
    original = Path.read_text

    def traced(self, *args, **kwargs):
        if self == path:
            reads.append(self)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", traced)
    rows = build_skill_rows(scope="project", home=home, project=project)
    assert {r.slug for r in rows} == {"alpha", "beta"}
    # Initial validated snapshot plus collection document/lock validation.
    assert len(reads) <= 4


@pytest.mark.parametrize("change", ["unstaged", "staged", "untracked", "deleted", "root"])
def test_dirty_checkout_retains_child_checks(inventory, change):
    home, project, backing = inventory
    if change == "root":
        (backing / "ROOT.md").write_text("root edit\n")
    elif change == "deleted":
        (backing / "alpha/SKILL.md").unlink()
    elif change == "untracked":
        (backing / "alpha/local.txt").write_text("local edit\n")
    else:
        (backing / "alpha/SKILL.md").write_text("local edit\n")
        if change == "staged":
            git(backing, "add", "alpha/SKILL.md")
    index = (backing / ".git/index").read_bytes()
    rows = build_skill_rows(scope="project", home=home, project=project)
    expected = "clean" if change == "root" else "missing" if change == "deleted" else "dirty"
    assert {r.slug: r.state for r in rows} == {"alpha": expected, "beta": "clean"}
    assert all(r.repository_state == "dirty" for r in rows)
    assert (backing / ".git/index").read_bytes() == index


def test_next_scan_reads_changed_lock_and_worktree(inventory):
    home, project, backing = inventory
    assert all(r.state == "clean" for r in build_skill_rows(scope="project", home=home, project=project))
    (backing / "alpha/SKILL.md").write_text("new local change\n")
    path = lock_file_path(scope="project", project=project)
    lock = read_lock(path)
    del lock.skills["beta"]
    write_lock(path, lock)
    rows = build_skill_rows(scope="project", home=home, project=project)
    assert {r.slug: r.state for r in rows} == {"alpha": "dirty", "beta": "library"}


def test_private_copy_is_not_merged_with_same_source_central_backing(inventory, tmp_path):
    home, project, backing = inventory
    private = tmp_path / "private-checkout"
    subprocess.run(["git", "clone", "-q", str(backing), str(private)], check=True)
    git(private, "remote", "set-url", "origin", git(backing, "config", "--get", "remote.origin.url"))
    canonical = project_store_root(project) / "alpha"
    canonical.parent.mkdir(parents=True, exist_ok=True)
    canonical.symlink_to(private / "alpha")
    projection = project / ".agents/skills/alpha"
    projection.unlink()
    projection.symlink_to(canonical)
    path = lock_file_path(scope="project", project=project)
    lock = read_lock(path)
    lock.skills["alpha"].extras["projectBacking"] = "isolated"
    write_lock(path, lock)
    (private / "alpha/SKILL.md").write_text("---\nname: alpha\ndescription: private copy\n---\n")
    rows = build_skill_rows(scope="project", home=home, project=project)
    assert {r.slug: r.state for r in rows} == {"alpha": "dirty", "beta": "clean"}
    assert next(r for r in rows if r.slug == "alpha").description == "private copy"
    assert canonical.resolve() == private / "alpha"
    assert (backing / "alpha/SKILL.md").read_text() != (private / "alpha/SKILL.md").read_text()


def test_malformed_project_lock_still_fails_closed(inventory):
    home, project, _ = inventory
    lock_file_path(scope="project", project=project).write_text('{"version": 3, "skills": []}')
    with pytest.raises(LockFormatError):
        build_skill_rows(scope="project", home=home, project=project)
