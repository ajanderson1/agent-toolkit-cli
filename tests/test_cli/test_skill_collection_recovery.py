import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from agent_toolkit_cli.skill_collection_transaction import (
    Journal,
    commit_document,
    document,
)
from agent_toolkit_cli.skill_collections import apply_selection, catalog, projection
from agent_toolkit_cli.skill_doctor import (
    _scan_orphan_canonicals,
    _scan_unmanaged_skills,
    discover_unmanaged_skills,
)
from agent_toolkit_cli.skill_install import InstallError
from agent_toolkit_cli.skill_lock import LockEntry, read_lock, write_lock
from agent_toolkit_cli.skill_paths import (
    library_lock_path,
    library_root,
    lock_file_path,
    project_store_root,
)
from tests.test_cli.test_skill_collection_reconcile import legacy, group, apply
from tests.test_cli.test_skill_collection_registration import source


def test_project_conversion_preserves_global_and_doctor_backing_ownership(
    legacy, tmp_path
):
    project = tmp_path / "project"
    project.mkdir()
    backing = project_store_root(project) / "wrapper"
    backing.parent.mkdir(parents=True)
    subprocess.run(["git", "clone", "-q", str(legacy), str(backing)], check=True)
    origin = subprocess.check_output(
        ["git", "-C", str(legacy), "remote", "get-url", "origin"], text=True
    ).strip()
    subprocess.run(
        ["git", "-C", str(backing), "remote", "set-url", "origin", origin], check=True
    )
    scoped = lock_file_path(scope="project", project=project)
    write_lock(scoped, read_lock(library_lock_path()))
    wrapper = project / ".agents/skills/wrapper"
    wrapper.parent.mkdir(parents=True)
    wrapper.symlink_to(backing)
    global_before = library_lock_path().read_bytes()
    g = catalog(scope="project", home=Path.home(), project=project)[0]
    apply_selection(
        g,
        {"standard": set(g.children) - {"workflow-00"}},
        scope="project",
        home=Path.home(),
        project=project,
    )
    assert library_lock_path().read_bytes() == global_before
    assert (Path.home() / ".agents/skills/wrapper").resolve() == legacy
    assert not wrapper.exists()
    assert (project / ".agents/skills/workflow-01").resolve() == backing / "workflow-01"
    lock = read_lock(scoped)
    assert "wrapper" not in lock.skills and backing.is_dir()
    assert not _scan_orphan_canonicals(
        scope="project", home=Path.home(), project=project, lock=lock
    )
    assert not _scan_unmanaged_skills(
        scope="project", home=Path.home(), project=project, lock=lock
    )


def test_v3_forward_and_rollback_preserve_unrelated_raw_records_and_wrapper_fields(
    legacy,
):
    path = library_lock_path()
    raw = document(path)
    raw["lastSelectedAgents"] = ["standard"]
    raw["unknownWrapperField"] = {"keep": True}
    raw["skills"]["other"] = {
        "source": "o/r",
        "sourceType": "github",
        "updatedAt": "original",
        "custom": [1, 2],
    }
    commit_document(path, raw)
    old = read_lock(path).skills["wrapper"]
    j = Journal()
    j.write(path, {"wrapper": old}, {"wrapper": None})
    intermediate = document(path)
    assert intermediate["skills"]["other"] == raw["skills"]["other"]
    intermediate["skills"]["inserted"] = {"source": "new/r", "sourceType": "github"}
    commit_document(path, intermediate)
    assert not j.rollback()
    final = document(path)
    assert final["skills"]["wrapper"] == raw["skills"]["wrapper"]
    assert final["skills"]["other"] == raw["skills"]["other"]
    assert "inserted" in final["skills"]
    assert final["unknownWrapperField"] == raw["unknownWrapperField"]
    assert final["lastSelectedAgents"] == raw["lastSelectedAgents"]


def test_last_moment_affected_record_change_refuses_links(legacy, monkeypatch):
    original = Journal.link
    fired = False

    def change(journal, path, before, after):
        nonlocal fired
        if not fired:
            fired = True
            raw = document(library_lock_path())
            raw["skills"]["wrapper"]["ref"] = "third-party-ref"
            commit_document(library_lock_path(), raw)
        return original(journal, path, before, after)

    monkeypatch.setattr(Journal, "link", change)
    with pytest.raises(
        InstallError, match="record ownership changed before link write"
    ):
        apply(set(group().children) - {"workflow-00"})
    assert read_lock(library_lock_path()).skills["wrapper"].ref == "third-party-ref"
    assert (Path.home() / ".agents/skills/wrapper").resolve() == legacy
    assert not list(library_root().glob("workflow-*"))


def test_last_moment_link_retarget_is_not_unlinked(legacy, monkeypatch):
    original = Journal.link
    wrapper = Path.home() / ".agents/skills/wrapper"

    def change(journal, path, before, after):
        if path == wrapper and after is None:
            path.unlink()
            path.symlink_to(legacy / "workflow-00")
        return original(journal, path, before, after)

    monkeypatch.setattr(Journal, "link", change)
    with pytest.raises(InstallError, match="Ownership changed immediately"):
        apply(set(group().children) - {"workflow-00"})
    assert wrapper.readlink() == legacy / "workflow-00"
    assert not list(library_root().glob("workflow-*"))


@pytest.mark.parametrize("recovery_failure", ["link", "lock"])
def test_recovery_write_failures_remain_prominent(
    legacy, monkeypatch, recovery_failure
):
    import agent_toolkit_cli.skill_collection_transaction as tx

    original_commit = tx.commit_document
    original_link = Path.symlink_to

    def commit(path, raw):
        if "wrapper" not in raw["skills"]:
            original_commit(path, raw)
            raise OSError("after forward commit")
        if recovery_failure == "lock":
            raise OSError("recovery lock failure")
        return original_commit(path, raw)

    def link(path, target, *args, **kwargs):
        if recovery_failure == "link" and path.name == "wrapper":
            raise OSError("recovery wrapper-link failure")
        return original_link(path, target, *args, **kwargs)

    monkeypatch.setattr(tx, "commit_document", commit)
    monkeypatch.setattr(Path, "symlink_to", link)
    with pytest.raises(InstallError, match="RECOVERY FAILED") as failure:
        apply(set(group().children) - {"workflow-00"})
    assert "recovery" in str(failure.value)
    assert legacy.exists()


def test_root_plus_nested_refuses_unproven_independent_disable_before_writes(source):
    root = Path(source.removeprefix("file://"))
    (root / "SKILL.md").write_text("---\nname: root\ndescription: root\n---\nroot\n")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "real root",
        ],
        check=True,
    )
    added = CliRunner().invoke(main, ["skill", "add", source])
    assert added.exit_code == 0, added.output
    g = catalog(scope="global", home=Path.home(), project=None)[0]
    assert g.children["repo"].entry.skill_path == "."
    before = library_lock_path().read_bytes()
    with pytest.raises(InstallError, match="Cannot prove independent nested isolation"):
        apply_selection(
            g,
            {"standard": {"repo", "alpha"}},
            scope="global",
            home=Path.home(),
            project=None,
        )
    assert library_lock_path().read_bytes() == before
    assert not (Path.home() / ".agents/skills/repo").exists()
    apply_selection(
        g, {"standard": set(g.children)}, scope="global", home=Path.home(), project=None
    )
    discovered = discover_unmanaged_skills(Path.home() / ".agents/skills")
    assert {"repo", "repo:alpha", "repo:beta", "alpha", "beta"} <= {
        n for n, p in discovered
    }
