"""Preserve observed installed 5.11.0 exact-path registration, using local fixtures."""
import json
import subprocess

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from tests.test_cli.test_reground import sandbox, repo, git, invoke  # sandbox fixture


SKILL = "---\nname: reground\ndescription: Fixture authoring skill\n---\nBody\n"


def test_exact_gitea_path_is_library_only_and_projects_centrally(tmp_path, sandbox, monkeypatch):
    source = repo(tmp_path, {
        "skills/reground/SKILL.md": SKILL,
        "skills/reground/references/detail.md": "Resource",
        "skills/reground/scripts/check.py": "print('ok')\n",
        "other/reground/SKILL.md": SKILL,
    })
    git(source, "branch", "release/test")
    url = "http://gitea.fixture.invalid:3000/team/reground.git"
    (sandbox / ".gitconfig").write_text(f'[url "file://{source}"]\n    insteadOf = {url}\n')
    project = tmp_path / "a"
    project.mkdir()
    monkeypatch.chdir(project)
    invoke("skills", "add", url, "--path", "skills/reground", "--slug", "reground", "--ref", "release/test")
    lock = json.loads((sandbox / ".agent-toolkit/skills-lock.json").read_text())
    assert set(lock["skills"]) == {"reground"}
    entry = lock["skills"]["reground"]
    assert (entry["parentUrl"], entry["ref"], entry["skillPath"]) == (url, "release/test", "skills/reground")
    assert not list(project.iterdir()), "--path is library registration, not a project install"
    central = sandbox / ".agent-toolkit/skills/reground"
    assert (central / "references/detail.md").read_text() == "Resource"
    assert (central / "scripts/check.py").is_file()
    for project in (project, tmp_path / "b"):
        project.mkdir(exist_ok=True)
        monkeypatch.chdir(project)
        invoke("skills", "install", "reground", "-p", "--agents", "pi")
        assert (project / ".agents/skills/reground").resolve() == central.resolve()


@pytest.mark.parametrize("path", ["", "../escape", "/absolute", "skills/../escape", "skills\\escape"])
def test_unsafe_path_is_rejected_before_registration(tmp_path, sandbox, path):
    source = repo(tmp_path, {"skills/reground/SKILL.md": SKILL})
    result = CliRunner().invoke(main, ["skills", "add", f"file://{source}", "--path", path])
    assert result.exit_code != 0 and "safe repository-relative" in result.output
    assert not (sandbox / ".agent-toolkit/skills-lock.json").exists()
    assert not (sandbox / ".agent-toolkit/skills").exists()


@pytest.mark.parametrize("args", [
    ["team/source", "--path", "skills/reground", "--skill", "reground"],
    ["team/source/skills/reground", "--path", "skills/reground"],
    ["--source", "team/source", "--path", "skills/reground"],
])
def test_path_selector_conflicts_refused_without_clone(tmp_path, sandbox, args):
    result = CliRunner().invoke(main, ["skills", "add", *args])
    assert result.exit_code != 0 and "--path" in result.output
    assert not (sandbox / ".agent-toolkit/skills").exists()


def test_path_dot_registers_exact_real_root(tmp_path, sandbox):
    source = repo(tmp_path, {"SKILL.md": SKILL, "nested/SKILL.md": SKILL})
    invoke("skills", "add", f"file://{source}", "--path", ".", "--slug", "root")
    entry = json.loads((sandbox / ".agent-toolkit/skills-lock.json").read_text())["skills"]
    assert set(entry) == {"root"} and entry["root"]["skillPath"] == "."


def test_exact_path_identity_cannot_silently_substitute_slug(tmp_path, sandbox):
    source = repo(tmp_path, {"skills/reground/SKILL.md": SKILL})
    invoke("skills", "add", f"file://{source}", "--path", "skills/reground", "--slug", "first")
    lock = sandbox / ".agent-toolkit/skills-lock.json"
    before = lock.read_bytes()
    result = CliRunner().invoke(main, ["skills", "add", f"file://{source}", "--path", "skills/reground", "--slug", "second"])
    assert result.exit_code != 0 and "already registered as first" in result.output
    assert lock.read_bytes() == before
    assert not (sandbox / ".agent-toolkit/skills/second").exists()


@pytest.mark.parametrize("escape", ["directory", "content"])
def test_exact_path_refuses_foreign_symlink(tmp_path, sandbox, escape):
    source = repo(tmp_path, {"placeholder": "Fixture"})
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "SKILL.md").write_text(SKILL)
    selected = source / "selected"
    if escape == "directory":
        selected.symlink_to(foreign, target_is_directory=True)
    else:
        selected.mkdir()
        (selected / "SKILL.md").symlink_to(foreign / "SKILL.md")
    git(source, "add", ".")
    git(source, "-c", "user.name=Test", "-c", "user.email=test@example.test", "commit", "-m", "foreign link")
    result = CliRunner().invoke(main, ["skills", "add", f"file://{source}", "--path", "selected"])
    assert result.exit_code != 0
    assert (foreign / "SKILL.md").read_text() == SKILL
    assert not (sandbox / ".agent-toolkit/skills-lock.json").exists()


def test_standalone_add_refuses_foreign_canonical(tmp_path, sandbox):
    wanted_dir = tmp_path / "wanted"
    wanted_dir.mkdir()
    wanted = repo(wanted_dir, {"SKILL.md": SKILL})
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    other = repo(other_dir, {"SKILL.md": "Foreign"})
    canonical = sandbox / ".agent-toolkit/skills/reground"
    canonical.parent.mkdir(parents=True)
    subprocess.run(["git", "clone", str(other), str(canonical)], check=True, capture_output=True)
    result = CliRunner().invoke(main, ["skills", "add", str(wanted), "--slug", "reground"])
    assert result.exit_code != 0 and "source/ref ownership" in result.output
    assert (canonical / "SKILL.md").read_text() == "Foreign"
    assert not (sandbox / ".agent-toolkit/skills-lock.json").exists()
