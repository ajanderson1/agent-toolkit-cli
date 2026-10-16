import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from agent_toolkit_cli.skill_lock import LockEntry, LockFile, read_lock, write_lock
from agent_toolkit_cli.skill_paths import library_lock_path, library_skill_path


def git(path, *args):
    return subprocess.check_output(
        [
            "git",
            "-C",
            str(path),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            *args,
        ],
        text=True,
    ).strip()


@pytest.fixture
def source(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "AGENT_TOOLKIT_SKILLS_ROOT", str(tmp_path / "library" / "skills")
    )
    root = tmp_path / "repo"
    root.mkdir()
    for name in ("alpha", "beta"):
        (root / name).mkdir()
        (root / name / "SKILL.md").write_text(f"---\nname: {name}\n---\n{name}\n")
    git(root, "init", "-q", "-b", "main")
    git(root, "add", ".")
    git(root, "commit", "-qm", "seed")
    git(root, "branch", "other")
    return root.as_uri()


def invoke(*args):
    return CliRunner().invoke(main, ["skill", "add", *args])


def test_repo_add_registers_real_children_only(source):
    result = invoke(source)
    assert result.exit_code == 0, result.output
    assert set(read_lock(library_lock_path()).skills) == {"alpha", "beta"}
    assert library_skill_path("alpha").is_symlink()


@pytest.mark.parametrize("local_work", ["staged", "unstaged", "untracked", "committed"])
def test_add_reuses_checkout_without_changing_index_or_history(source, local_work):
    first = invoke(source, "--skill", "alpha")
    assert first.exit_code == 0, first.output
    parent = library_skill_path("alpha").resolve().parent
    target = parent / ("local.txt" if local_work == "untracked" else "alpha/SKILL.md")
    target.write_text("preserve exactly\n")
    if local_work in ("staged", "committed"):
        git(parent, "add", ".")
    if local_work == "committed":
        git(parent, "commit", "-qm", "local work")
    before = (
        git(parent, "rev-parse", "HEAD"),
        (parent / ".git/index").read_bytes(),
        git(parent, "status", "--porcelain"),
        target.read_bytes(),
    )
    result = invoke(source, "--skill", "beta")
    assert result.exit_code == 0, result.output
    after = (
        git(parent, "rev-parse", "HEAD"),
        (parent / ".git/index").read_bytes(),
        git(parent, "status", "--porcelain"),
        target.read_bytes(),
    )
    assert after == before


def test_ref_conflict_refuses_before_retargeting(source):
    assert invoke(source, "--skill", "alpha").exit_code == 0
    lock = library_lock_path().read_bytes()
    target = library_skill_path("alpha").readlink()
    result = invoke(source, "--skill", "alpha", "--ref", "other")
    assert result.exit_code != 0
    assert library_lock_path().read_bytes() == lock
    assert library_skill_path("alpha").readlink() == target


def test_batch_collision_refuses_all_registration(source):
    write_lock(
        library_lock_path(),
        LockFile(
            version=1,
            skills={
                "beta": LockEntry(
                    source="someone/else", source_type="github", skill_path="beta"
                ),
            },
        ),
    )
    before = library_lock_path().read_bytes()
    result = invoke(source)
    assert result.exit_code != 0
    assert library_lock_path().read_bytes() == before
    assert not library_skill_path("alpha").exists()


def test_batch_reuses_custom_slug_and_retry_is_noop(source):
    assert invoke(source, "--skill", "alpha", "--slug", "custom-alpha").exit_code == 0
    result = invoke(source)
    assert result.exit_code == 0, result.output
    assert set(read_lock(library_lock_path()).skills) == {"custom-alpha", "beta"}
    before = library_lock_path().read_bytes()
    assert invoke(source).exit_code == 0
    assert library_lock_path().read_bytes() == before
