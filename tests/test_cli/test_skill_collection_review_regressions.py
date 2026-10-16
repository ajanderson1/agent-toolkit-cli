"""Regression coverage for independent p11/p12 findings on candidate 3751ecd."""

from pathlib import Path

import pytest

from agent_toolkit_cli.skill_install import InstallError
from agent_toolkit_cli.skill_lock import LockEntry, LockFile, read_lock, write_lock
from agent_toolkit_cli.skill_paths import library_lock_path, library_skill_path
from tests.test_cli.test_skill_collection_registration import source, git, invoke
from tests.test_cli.test_skill_collection_reconcile import legacy, group, apply


@pytest.mark.parametrize("change", ["affected", "unrelated"])
def test_fresh_document_cannot_redefine_affected_ownership(
    tmp_path, monkeypatch, change
):
    import agent_toolkit_cli.skill_collection_transaction as tx

    path = tmp_path / "skills-lock.json"
    old = LockEntry(source="old/repo", source_type="github")
    new = LockEntry(source="new/repo", source_type="github")
    third = LockEntry(source="third/repo", source_type="github")
    write_lock(path, LockFile(version=1, skills={"target": old}))
    original = tx.document
    calls = 0

    def changed_document(p):
        nonlocal calls
        calls += 1
        if calls == 2:
            lock = read_lock(path)
            lock.skills["target" if change == "affected" else "unrelated"] = third
            write_lock(path, lock)
        return original(p)

    monkeypatch.setattr(tx, "document", changed_document)
    journal = tx.Journal()
    if change == "affected":
        with pytest.raises(InstallError, match="ownership changed") as failure:
            journal.write(path, {"target": old}, {"target": new})
        assert read_lock(path).skills["target"] == third
        recovery = journal.fail(failure.value)
        assert "RECOVERY FAILED" in str(recovery)
        assert read_lock(path).skills["target"] == third
    else:
        journal.write(path, {"target": old}, {"target": new})
        assert read_lock(path).skills == {"target": new, "unrelated": third}
        assert not journal.rollback()
        assert read_lock(path).skills == {"target": old, "unrelated": third}


@pytest.mark.parametrize("annotated", [False, True])
def test_matching_detached_tag_add_and_collection_install_preserve_index_and_contents(
    source, monkeypatch, tmp_path, annotated
):
    from agent_toolkit_cli.skill_collections import apply_selection, catalog

    root = Path(source.removeprefix("file://"))
    git(root, "tag", *(["-a", "-m", "release"] if annotated else []), "v1.0.0")
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    first = invoke(source, "--ref", "v1.0.0")
    assert first.exit_code == 0, first.output
    backing = library_skill_path("alpha").resolve().parent
    assert git(backing, "rev-parse", "--abbrev-ref", "HEAD") == "HEAD"
    (backing / "alpha/SKILL.md").write_text("staged at the matching tag\n")
    git(backing, "add", ".")
    (backing / "alpha/SKILL.md").write_text("unstaged over the index\n")
    (backing / "untracked.txt").write_text("preserve untracked\n")
    before = (
        git(backing, "rev-parse", "HEAD"),
        (backing / ".git/index").read_bytes(),
        (backing / "alpha/SKILL.md").read_bytes(),
        library_lock_path().read_bytes(),
    )
    second = invoke(source, "--ref", "v1.0.0")
    assert second.exit_code == 0, second.output
    group = catalog(scope="global", home=home, project=None)[0]
    apply_selection(
        group,
        {"standard": set(group.children)},
        scope="global",
        home=home,
        project=None,
    )
    assert (
        git(backing, "rev-parse", "HEAD"),
        (backing / ".git/index").read_bytes(),
        (backing / "alpha/SKILL.md").read_bytes(),
        library_lock_path().read_bytes(),
    ) == before
    assert (backing / "untracked.txt").read_text() == "preserve untracked\n"
    # A different detached commit is not adopted merely because this clone has the tag.
    git(backing, "add", ".")
    git(backing, "commit", "-qm", "different detached commit")
    refused = invoke(source, "--ref", "v1.0.0")
    assert refused.exit_code != 0 and "Ref conflict" in refused.output
    assert (backing / "alpha/SKILL.md").read_text() == "unstaged over the index\n"


@pytest.mark.parametrize("fail", [False, True])
def test_combined_local_commit_index_unstaged_and_untracked_preservation(
    legacy, monkeypatch, fail
):
    (legacy / "local-commit.txt").write_text("local history\n")
    git(legacy, "add", ".")
    git(legacy, "commit", "-qm", "local history")
    (legacy / "workflow-01/SKILL.md").write_text("staged contents\n")
    git(legacy, "add", ".")
    (legacy / "workflow-01/SKILL.md").write_text("unstaged contents\n")
    (legacy / "untracked.txt").write_text("untracked contents\n")

    def snapshot():
        return (
            git(legacy, "rev-parse", "HEAD"),
            git(legacy, "symbolic-ref", "HEAD"),
            (legacy / ".git/index").read_bytes(),
            git(legacy, "show", ":workflow-01/SKILL.md"),
            (legacy / "workflow-01/SKILL.md").read_bytes(),
            (legacy / "untracked.txt").read_bytes(),
            git(legacy, "log", "--format=%H"),
        )

    before = snapshot()
    lock_before = library_lock_path().read_bytes()
    original = Path.symlink_to
    fired = False

    def create(path, target, *args, **kwargs):
        nonlocal fired
        if fail and not fired and path == Path.home() / ".agents/skills/workflow-05":
            fired = True
            raise OSError("late child projection failure")
        return original(path, target, *args, **kwargs)

    monkeypatch.setattr(Path, "symlink_to", create)
    selected = set(group().children) - {"workflow-00"}
    if fail:
        with pytest.raises(InstallError, match="rolled back"):
            apply(selected)
        assert library_lock_path().read_bytes() == lock_before
        assert (Path.home() / ".agents/skills/wrapper").resolve() == legacy
        assert not list((Path.home() / ".agents/skills").glob("workflow-*"))
    else:
        apply(selected)
        assert len(list((Path.home() / ".agents/skills").glob("workflow-*"))) == 10
        assert not (Path.home() / ".agents/skills/wrapper").exists()
    assert snapshot() == before
