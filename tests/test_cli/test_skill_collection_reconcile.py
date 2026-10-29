import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from agent_toolkit_cli.skill_collection_transaction import Journal
from agent_toolkit_cli.skill_collections import apply_selection, catalog, projection
from agent_toolkit_cli.skill_install import InstallError
from agent_toolkit_cli.skill_lock import LockEntry, LockFile, read_lock, write_lock
from agent_toolkit_cli.skill_paths import (
    library_lock_path,
    library_root,
    library_skill_path,
)


def git(root, *args):
    return subprocess.check_output(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            *args,
        ],
        text=True,
    ).strip()


@pytest.fixture
def legacy(tmp_path, monkeypatch):
    # Isolate project discovery too; HOME alone does not hide checkout locks.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(tmp_path / "library/skills"))
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home / ".claude"))
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    for i in range(11):
        p = upstream / f"workflow-{i:02}"
        p.mkdir()
        (p / "SKILL.md").write_text(f"---\nname: {p.name}\n---\nbody\n")
    git(upstream, "init", "-q", "-b", "main")
    git(upstream, "add", ".")
    git(upstream, "commit", "-qm", "seed")
    backing = library_skill_path("wrapper")
    backing.parent.mkdir(parents=True)
    subprocess.run(["git", "clone", "-q", upstream.as_uri(), str(backing)], check=True)
    write_lock(
        library_lock_path(),
        LockFile(
            version=3,
            skills={
                "wrapper": LockEntry(
                    source="owner/workflows",
                    source_type="github",
                    skill_path="SKILL.md",
                    extras={"sourceUrl": upstream.as_uri()},
                ),
            },
        ),
    )
    path = projection(
        "wrapper", "standard", scope="global", home=Path.home(), project=None
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.symlink_to(backing)
    return backing


def group():
    return catalog(scope="global", home=Path.home(), project=None)[0]


def apply(selected, agent="standard"):
    apply_selection(
        group(), {agent: set(selected)}, scope="global", home=Path.home(), project=None
    )


def test_legacy_fixture_uses_disposable_project_directory(legacy, tmp_path):
    # TUIApp also inspects project locks, independently of the fake HOME/library.
    assert Path.cwd() == tmp_path


def test_source_install_converts_wrapper_without_resurrecting_it(legacy):
    result = CliRunner().invoke(
        main,
        ["skill", "install", "--source", "owner/workflows", "--agents", "standard"],
    )
    assert result.exit_code == 0, result.output
    assert not projection(
        "wrapper", "standard", scope="global", home=Path.home(), project=None
    ).exists()
    for name in group().children:
        assert (
            projection(
                name, "standard", scope="global", home=Path.home(), project=None
            ).resolve()
            == legacy / name
        )


def test_complete_siblings_backing_lifetime_and_retry(legacy):
    other = projection(
        "wrapper", "claude-code", scope="global", home=Path.home(), project=None
    )
    other.parent.mkdir(parents=True, exist_ok=True)
    other.symlink_to(legacy)
    selected = set(group().children) - {"workflow-00"}
    (legacy / "workflow-01/SKILL.md").write_text("active staged edit\n")
    git(legacy, "add", ".")
    index = (legacy / ".git/index").read_bytes()
    head = git(legacy, "rev-parse", "HEAD")
    apply(selected)
    assert other.resolve() == legacy
    assert "wrapper" in read_lock(library_lock_path()).skills
    assert len(list((Path.home() / ".agents/skills").glob("workflow-*"))) == 10
    assert not (Path.home() / ".agents/skills/wrapper").exists()
    assert (legacy / ".git/index").read_bytes() == index
    assert git(legacy, "rev-parse", "HEAD") == head
    assert (legacy / "workflow-01/SKILL.md").read_text() == "active staged edit\n"
    assert (
        CliRunner()
        .invoke(
            main,
            ["skill", "install", "--source", "owner/workflows", "--agents", "standard"],
        )
        .exit_code
        == 0
    )
    assert not (Path.home() / ".agents/skills/wrapper").exists()
    apply(set(group().children), "claude-code")
    assert "wrapper" not in read_lock(library_lock_path()).skills
    assert not other.exists() and legacy.is_dir()
    before = library_lock_path().read_bytes()
    apply(set(group().children), "claude-code")
    assert library_lock_path().read_bytes() == before


@pytest.mark.parametrize("failure", ["child", "wrapper", "lock"])
def test_fault_rolls_back_and_retry_converges(legacy, monkeypatch, failure):
    import agent_toolkit_cli.skill_collection_transaction as locks

    selected = set(group().children) - {"workflow-00"}
    original_link = Path.symlink_to
    original_unlink = Path.unlink
    original_write = locks.commit_document
    fired = False

    def link(path, target, *args, **kwargs):
        nonlocal fired
        if failure == "child" and path.name == "workflow-05" and not fired:
            fired = True
            raise OSError("injected child failure")
        return original_link(path, target, *args, **kwargs)

    def unlink(path, *args, **kwargs):
        nonlocal fired
        if failure == "wrapper" and path.name == "wrapper" and not fired:
            fired = True
            raise OSError("injected retirement failure")
        return original_unlink(path, *args, **kwargs)

    def write(path, lock):
        nonlocal fired
        if failure == "lock" and not fired:
            fired = True
            current = locks.document(path)
            current["skills"]["unrelated"] = {
                "source": "another/repo",
                "sourceType": "github",
            }
            original_write(path, current)
            raise OSError("injected lock failure")
        return original_write(path, lock)

    monkeypatch.setattr(Path, "symlink_to", link)
    monkeypatch.setattr(Path, "unlink", unlink)
    monkeypatch.setattr(locks, "commit_document", write)
    with pytest.raises(InstallError, match="rolled back"):
        apply(selected)
    assert (Path.home() / ".agents/skills/wrapper").resolve() == legacy
    assert not list((Path.home() / ".agents/skills").glob("workflow-*"))
    assert not list(library_root().glob("workflow-*"))
    if failure == "lock":
        assert "unrelated" in read_lock(library_lock_path()).skills
    apply(selected)
    assert len(list((Path.home() / ".agents/skills").glob("workflow-*"))) == 10


def test_rollback_preserves_unrelated_and_detects_affected_record_conflict(
    tmp_path, monkeypatch
):
    import agent_toolkit_cli.skill_lock as locks

    path = tmp_path / "skills-lock.json"
    old = LockEntry(source="old/repo", source_type="github")
    new = LockEntry(source="new/repo", source_type="github")
    write_lock(path, LockFile(version=1, skills={"target": old}))
    j = Journal()
    j.write(path, {"target": old}, {"target": new})
    lock = read_lock(path)
    lock.skills["unrelated"] = old
    write_lock(path, lock)
    assert j.rollback() == []
    assert read_lock(path).skills == {"target": old, "unrelated": old}
    j = Journal()
    j.write(path, {"target": old}, {"target": new})
    lock = read_lock(path)
    lock.skills["target"] = LockEntry(source="third/repo", source_type="github")
    write_lock(path, lock)
    assert "recovery conflict" in j.rollback()[0]
    assert read_lock(path).skills["target"].source == "third/repo"


def test_link_recovery_conflict_is_prominent_and_non_destructive(tmp_path):
    p = tmp_path / "link"
    j = Journal()
    j.link(p, None, tmp_path / "ours")
    p.unlink()
    p.symlink_to(tmp_path / "theirs")
    failure = j.fail(OSError("injected failure"))
    assert "RECOVERY FAILED" in str(failure) and "link recovery conflict" in str(
        failure
    )
    assert p.readlink() == tmp_path / "theirs"
