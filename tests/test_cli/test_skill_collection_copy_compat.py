from pathlib import Path

from agent_toolkit_cli.skill_lock import read_lock
from agent_toolkit_cli.skill_paths import library_lock_path, library_skill_path
from tests.test_cli.test_skill_collection_registration import source, invoke


def refuse_symlinks(monkeypatch):
    def refuse(path, target, *args, **kwargs):
        raise OSError("platform refuses symlinks")

    monkeypatch.setattr(Path, "symlink_to", refuse)


def test_explicit_single_child_copy_fallback_and_repeat_preserve_local_contents(
    source, monkeypatch
):
    refuse_symlinks(monkeypatch)
    first = invoke(source, "--skill", "alpha")
    assert first.exit_code == 0, first.output
    path = library_skill_path("alpha")
    assert path.is_dir() and not path.is_symlink()
    assert (
        read_lock(library_lock_path()).skills["alpha"].extras["materialised"] == "copy"
    )
    (path / "SKILL.md").write_text("local active snapshot\n")
    before = library_lock_path().read_bytes()
    repeated = invoke(source, "--skill", "alpha")
    assert repeated.exit_code == 0, repeated.output
    assert (path / "SKILL.md").read_text() == "local active snapshot\n"
    assert library_lock_path().read_bytes() == before


def test_single_child_copy_lock_failure_removes_only_owned_matching_snapshot(
    source, monkeypatch
):
    import agent_toolkit_cli.skill_collection_transaction as tx

    refuse_symlinks(monkeypatch)

    def fail(path, raw):
        raise OSError("injected lock failure")

    monkeypatch.setattr(tx, "commit_document", fail)
    result = invoke(source, "--skill", "alpha")
    assert result.exit_code != 0 and "rolled back" in result.output
    assert not library_skill_path("alpha").exists()
    assert not read_lock(library_lock_path()).skills


def test_copy_recovery_conflict_retains_changed_files(source, monkeypatch):
    import agent_toolkit_cli.skill_collection_transaction as tx

    refuse_symlinks(monkeypatch)

    def fail(path, raw):
        (library_skill_path("alpha") / "SKILL.md").write_text(
            "changed by another writer\n"
        )
        raise OSError("injected lock failure")

    monkeypatch.setattr(tx, "commit_document", fail)
    result = invoke(source, "--skill", "alpha")
    assert result.exit_code != 0
    assert (
        "RECOVERY FAILED" in result.output
        and "copy content recovery conflict" in result.output
    )
    assert (
        library_skill_path("alpha") / "SKILL.md"
    ).read_text() == "changed by another writer\n"
    assert not read_lock(library_lock_path()).skills
