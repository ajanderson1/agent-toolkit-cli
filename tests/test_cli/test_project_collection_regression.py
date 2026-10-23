"""Project conversion against independent, locally modified Git backings."""

import dataclasses
import hashlib
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli import skill_collection_register, skill_collections, skill_doctor, skill_git
from agent_toolkit_cli.commands import skill as skill_command
from agent_toolkit_tui import app as tui_app, skill_state
from agent_toolkit_cli.cli import main
from agent_toolkit_cli.skill_collections import apply_selection, catalog, projection
from agent_toolkit_cli.skill_lock import LockEntry, LockFile, read_lock, write_lock
from agent_toolkit_cli.skill_paths import (
    canonical_skill_dir,
    library_lock_path,
    library_skill_path,
    lock_file_path,
)
from agent_toolkit_tui.skill_state import build_skill_rows


NAMES = {f"workflow-{i:02}" for i in range(11)}
SELECTED = {f"workflow-{i:02}" for i in range(5)}


def git(root, *args):
    return subprocess.check_output(
        ["git", "--no-optional-locks", "-C", str(root), "-c", "user.name=Test",
         "-c", "user.email=test@example.invalid", *args],
        text=True, stderr=subprocess.STDOUT, timeout=10,
    ).strip()


def snapshot(root):
    return {
        "head": git(root, "rev-parse", "HEAD"),
        "history": git(root, "log", "--all", "--format=%H"),
        "status": git(root, "status", "--porcelain"),
        "index": (root / ".git/index").read_bytes(),
        "files": {
            p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file() and ".git" not in p.relative_to(root).parts
        },
    }


@pytest.fixture
def project_collection(tmp_path, monkeypatch, isolated_project_backing):
    source_root = Path(__file__).resolve().parents[2] / "src"
    for module in (skill_collection_register, skill_collections, skill_doctor, skill_git,
                   skill_command, tui_app, skill_state):
        assert Path(module.__file__).resolve().is_relative_to(source_root)
    home = tmp_path / "home"
    home.mkdir()
    for key in tuple(os.environ):
        if key.startswith(("GIT_", "AGENT_TOOLKIT_")):
            monkeypatch.delenv(key)
    for key, value in {
        "HOME": home, "USERPROFILE": home, "XDG_CONFIG_HOME": home / ".config",
        "XDG_DATA_HOME": home / ".local/share", "XDG_CACHE_HOME": home / ".cache",
        "CLAUDE_CONFIG_DIR": home / ".claude", "HERMES_HOME": home / ".hermes",
        "AGENT_TOOLKIT_SKILLS_ROOT": home / "library/skills",
    }.items():
        monkeypatch.setenv(key, str(value))
    (home / ".gitconfig").write_text(
        '[protocol]\n\tallow = never\n[protocol "file"]\n\tallow = always\n'
    )
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    git(upstream, "init", "-q", "-b", "main")
    for name in sorted(NAMES):
        child = upstream / name
        child.mkdir()
        (child / "SKILL.md").write_text(f"---\nname: {name}\n---\nupstream\n")
    git(upstream, "add", ".")
    git(upstream, "commit", "-qm", "seed")
    git(upstream, "tag", "v1")
    # Both URL spellings used by the parser are intercepted; denied HTTPS is
    # independently exercised below, so a typo cannot silently reach the network.
    with (home / ".gitconfig").open("a") as f:
        f.write(f'[url "{upstream.as_uri()}"]\n\tinsteadOf = https://github.com/owner/workflows\n')
    project = tmp_path / "project"
    project.mkdir()
    git(project, "init", "-q", "-b", "main")
    monkeypatch.chdir(project)
    backings = [library_skill_path("wrapper"), canonical_skill_dir(
        "wrapper", scope="project", home=home, project=project)]
    for i, backing in enumerate(backings):
        backing.parent.mkdir(parents=True, exist_ok=True)
        git(project, "clone", "-q", "https://github.com/owner/workflows", str(backing))
        (backing / "local.txt").write_text(f"unpublished {i}\n")
        git(backing, "add", ".")
        git(backing, "commit", "-qm", "unpublished")
        (backing / "workflow-00/SKILL.md").write_text(f"staged {i}\n")
        git(backing, "add", ".")
        (backing / "workflow-01/SKILL.md").write_text(f"unstaged {i}\n")
        (backing / "untracked.txt").write_text(f"untracked {i}\n")
    entry = LockEntry(source="owner/workflows", source_type="github", skill_path="SKILL.md")
    for path in (library_lock_path(), lock_file_path(scope="project", project=project)):
        write_lock(path, LockFile(version=3, skills={"wrapper": entry}))
    wrapper = projection("wrapper", "standard", scope="project", home=home, project=project)
    wrapper.parent.mkdir(parents=True)
    wrapper.symlink_to(backings[1])
    return home, project, backings, upstream


def convert(case):
    home, project, _, _ = case
    group = catalog(scope="project", home=home, project=project)[0]
    apply_selection(group, {"standard": SELECTED}, scope="project", home=home, project=project)


def rows(case):
    home, project, _, _ = case
    return build_skill_rows(scope="project", home=home, project=project)


def findings(case):
    home, project, _, _ = case
    return skill_doctor.diagnose(slugs=None, scope="project", home=home, project=project)


def assert_inventory(inventory):
    assert {r.slug for r in inventory} == NAMES
    assert len({r.collection_key for r in inventory}) == 1
    assert all(not r.collection_error and r.state not in {"missing", "unlisted"} for r in inventory)
    assert {r.slug for r in inventory if r.cells[("standard", "project")].linked} == SELECTED
    assert not any(c.payload_missing for r in inventory for c in r.cells.values())


def test_project_conversion_inventory_survives_new_process(project_collection):
    case = project_collection
    home, project, backings, _ = case
    before = [snapshot(b) for b in backings]
    library = library_lock_path().read_bytes()
    convert(case)
    assert library_lock_path().read_bytes() == library
    assert [snapshot(b) for b in backings] == before
    assert_inventory(rows(case))
    script = '''
import json, pathlib
import agent_toolkit_tui.skill_state as state
assert pathlib.Path(state.__file__).resolve().is_relative_to(pathlib.Path(__import__('sys').argv[1]))
rows = state.build_skill_rows(scope='project', home=pathlib.Path.home(), project=pathlib.Path.cwd())
print(json.dumps([r.slug for r in rows]))
'''
    source_root = Path(skill_collections.__file__).resolve().parents[1]
    probe = project / "fresh_inventory.py"
    probe.write_text(script)
    result = subprocess.run([sys.executable, str(probe), str(source_root)],
                            env={**os.environ, "PYTHONPATH": str(source_root)},
                            cwd=project, text=True, capture_output=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert set(json.loads(result.stdout)) == NAMES


def test_full_doctor_recognizes_healthy_derived_children(project_collection):
    convert(project_collection)
    found = findings(project_collection)
    assert not [f for f in found if f.finding_type in {
        "unlisted", "missing_canonical", "orphan_canonical", "unmanaged"}], found
    home, project, backings, _ = project_collection
    before = [snapshot(b) for b in backings]
    result = CliRunner().invoke(main, ["--project", str(project), "skills", "doctor", "-p", "--no-fix"])
    assert result.exit_code == 0, result.output
    assert [snapshot(b) for b in backings] == before


@pytest.mark.parametrize("damage", ["missing", "source", "ref", "path", "remote", "foreign", "standalone"])
def test_doctor_keeps_genuine_warnings(project_collection, damage):
    home, project, backings, _ = project_collection
    convert(project_collection)
    path = lock_file_path(scope="project", project=project)
    lock = read_lock(path)
    slug = "workflow-00"
    if damage == "missing":
        (backings[1] / slug / "SKILL.md").unlink()
    elif damage in {"source", "ref", "path"}:
        field = {"path": "skill_path"}.get(damage, damage)
        lock.skills[slug] = dataclasses.replace(lock.skills[slug], **{field: "wrong/value"})
        write_lock(path, lock)
    elif damage == "remote":
        git(backings[1], "remote", "set-url", "origin", "https://github.com/foreign/repo")
    elif damage == "foreign":
        link = projection(slug, "claude-code", scope="project", home=home, project=project)
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(backings[1] / "workflow-01")
    else:
        slug = "standalone"
        lock.skills[slug] = LockEntry(source="other/repo", source_type="github")
        write_lock(path, lock)
    found = findings(project_collection)
    assert any(f.slug == slug for f in found), found
    if damage == "missing":
        row = next(r for r in rows(project_collection) if r.slug == slug)
        assert row.state == "missing" and row.cells[("standard", "project")].payload_missing


def seed_post_doctor(case):
    home, project, _, upstream = case
    from agent_toolkit_cli.skill_paths import parent_clone_path
    parent = parent_clone_path("owner", "workflows", ref=None)
    parent.parent.mkdir(parents=True, exist_ok=True)
    git(project, "clone", "-q", upstream.as_uri(), str(parent))
    library_skill_path("workflow-00").symlink_to(parent / "workflow-00")
    entry = LockEntry(source="owner/workflows", source_type="github", skill_path="workflow-00",
                      parent_url=upstream.as_uri())
    lock = read_lock(library_lock_path())
    lock.skills = {"workflow-00": entry, **lock.skills}
    write_lock(library_lock_path(), lock)


def test_post_doctor_bootstrap_shape_preserves_distinct_global_copies(project_collection):
    convert(project_collection)
    seed_post_doctor(project_collection)
    home, project, backings, _ = project_collection
    before = [snapshot(b) for b in backings]
    library = library_lock_path().read_bytes()
    assert set(read_lock(library_lock_path()).skills) == {"wrapper", "workflow-00"}
    assert_inventory(rows(project_collection))
    assert not [f for f in findings(project_collection) if f.finding_type in {"unlisted", "orphan_canonical"}]
    global_groups = catalog(scope="global", home=home, project=None)
    assert any("Ambiguous" in g.error for g in global_groups)
    assert library_lock_path().read_bytes() == library
    assert [snapshot(b) for b in backings] == before


@pytest.mark.parametrize("ref", [None, "v1", "feature/local", "sha"])
def test_readd_preview_and_action_select_exact_recorded_child(project_collection, ref):
    home, project, backings, upstream = project_collection
    if ref == "feature/local":
        git(upstream, "branch", ref)
    if ref == "sha":
        ref = git(upstream, "rev-parse", "HEAD")
    nested = upstream / "packs/deep/child"
    nested.mkdir(parents=True)
    (nested / "SKILL.md").write_text("---\nname: same-name\n---\nnested\n")
    # The selected commit must contain the nested child too.
    git(upstream, "add", ".")
    git(upstream, "commit", "-qm", "nested")
    if ref == "v1":
        git(upstream, "tag", "-f", ref)
    elif ref == "feature/local":
        git(upstream, "branch", "-f", ref)
    elif ref is not None:
        ref = git(upstream, "rev-parse", "HEAD")
    entry = LockEntry(source="local/upstream", source_type="git", ref=ref,
                      skill_path="packs/deep/child", parent_url=upstream.as_uri(),
                      read_only=True)
    action = skill_doctor._make_readd_library_action(slug="custom-child", entry=entry)
    args = shlex.split(action.shell_preview)
    assert args.pop(0) == "agent-toolkit-cli"
    assert "--global" not in args and "-g" not in args
    project_before = lock_file_path(scope="project", project=project).read_bytes()
    backing_before = [snapshot(b) for b in backings]
    result = CliRunner().invoke(main, args)
    assert result.exit_code == 0, result.output
    assert "library" in action.description.lower() and "project" in action.description.lower()
    preview_lock = read_lock(library_lock_path())
    assert set(preview_lock.skills) == {"wrapper", "custom-child"}
    actual = preview_lock.skills["custom-child"]
    assert (actual.source, actual.ref, actual.skill_path, actual.parent_url) == (
        entry.source, ref, entry.skill_path, entry.parent_url)
    assert library_skill_path("custom-child").readlink().as_posix().endswith("/packs/deep/child")
    # Run the accepted action in a separate fresh library, not on preview's output.
    monkey_root = home / "action-library/skills"
    old = os.environ["AGENT_TOOLKIT_SKILLS_ROOT"]
    try:
        os.environ["AGENT_TOOLKIT_SKILLS_ROOT"] = str(monkey_root)
        action.apply()
        action.apply()
        actual = read_lock(library_lock_path()).skills["custom-child"]
        assert (actual.source, actual.ref, actual.skill_path, actual.parent_url) == (
            entry.source, ref, entry.skill_path, entry.parent_url)
        assert (library_skill_path("custom-child") / "SKILL.md").read_bytes() == (nested / "SKILL.md").read_bytes()
        assert not (home / ".agents/skills/custom-child").exists()
    finally:
        os.environ["AGENT_TOOLKIT_SKILLS_ROOT"] = old
    assert lock_file_path(scope="project", project=project).read_bytes() == project_before
    assert [snapshot(b) for b in backings] == backing_before


def test_readd_rejects_existing_wrong_canonical(project_collection):
    home, project, backings, upstream = project_collection
    target = library_skill_path("custom-child")
    target.symlink_to(backings[0] / "workflow-01")
    entry = LockEntry(source="local/upstream", source_type="git", skill_path="workflow-00",
                      parent_url=upstream.as_uri())
    before = library_lock_path().read_bytes()
    action = skill_doctor._make_readd_library_action(slug="custom-child", entry=entry)
    preview = CliRunner().invoke(main, shlex.split(action.shell_preview)[1:])
    assert preview.exit_code != 0 and "conflict" in preview.output
    import click
    with pytest.raises(click.ClickException, match="conflict|ownership"):
        action.apply()
    assert library_lock_path().read_bytes() == before
    assert target.resolve() == backings[0] / "workflow-01"


def test_git_protocol_denial_survives_product_environment_scrubbing(project_collection):
    home, project, _, _ = project_collection
    with pytest.raises(skill_git.GitError, match="not allowed"):
        skill_git.clone_pinned_or_branch("https://invalid.example/never", project / "denied", ref=None, env=None)
    assert not (project / "denied").exists()


@pytest.mark.parametrize("damage", ["foreign-projection", "wrong-backing", "tracked-root"])
def test_container_presentation_does_not_hide_real_damage(project_collection, damage):
    home, project, backings, _ = project_collection
    convert(project_collection)
    if damage == "foreign-projection":
        path = projection("wrapper", "standard", scope="project", home=home, project=project)
        path.symlink_to(backings[1] / "workflow-01")
    elif damage == "wrong-backing":
        git(backings[1], "remote", "set-url", "origin", "https://github.com/foreign/repo")
    else:
        (backings[1] / "SKILL.md").write_text("genuine root\n")
        git(backings[1], "add", "SKILL.md")
        git(backings[1], "commit", "-qm", "real root")
        (backings[1] / "SKILL.md").unlink()
    wrapper = next(r for r in rows(project_collection) if r.slug == "wrapper")
    if damage == "foreign-projection":
        cell = wrapper.cells[("standard", "project")]
        assert cell.drift and cell.stray and cell.exposure_reason
        assert not cell.payload_missing
    else:
        assert wrapper.state == "missing"


def test_library_container_identity_is_not_scoped_mutation_authority(project_collection):
    home, project, backings, _ = project_collection
    convert(project_collection)
    group = catalog(scope="project", home=home, project=project)[0]
    assert group.containers == {"wrapper"}
    assert group.wrapper is None and group.backing is None
    before = library_lock_path().read_bytes()
    apply_selection(group, {"standard": SELECTED}, scope="project", home=home, project=project)
    assert library_lock_path().read_bytes() == before
    assert backings[0].is_dir() and backings[1].is_dir()


def test_doctor_does_not_accept_same_slug_from_another_library_source(project_collection):
    convert(project_collection)
    lock = read_lock(library_lock_path())
    lock.skills["workflow-00"] = LockEntry(source="foreign/repo", source_type="github")
    write_lock(library_lock_path(), lock)
    found = findings(project_collection)
    assert any(f.slug == "workflow-00" and f.finding_type == "lock_source_mismatch"
               and f.fix_action is None for f in found)


def test_doctor_does_not_hide_duplicate_recorded_child_identities(project_collection):
    home, project, backings, _ = project_collection
    convert(project_collection)
    path = lock_file_path(scope="project", project=project)
    lock = read_lock(path)
    lock.skills["custom-alias"] = dataclasses.replace(lock.skills["workflow-00"])
    canonical_skill_dir("custom-alias", scope="project", home=home, project=project).symlink_to(
        backings[1] / "workflow-00")
    write_lock(path, lock)
    unlisted = {f.slug for f in findings(project_collection) if f.finding_type == "unlisted"}
    assert {"workflow-00", "custom-alias"} <= unlisted


@pytest.mark.parametrize("path", ["../escape", "/absolute", "packs/../../escape", "packs\\\\child", ""])
def test_add_path_refuses_unsafe_selector_before_acquisition(project_collection, path):
    before = library_lock_path().read_bytes()
    result = CliRunner().invoke(main, ["skills", "add", "owner/workflows", "--path", path])
    assert result.exit_code != 0 and "--path" in result.output
    assert library_lock_path().read_bytes() == before


def test_add_help_explains_exact_path_without_global_flag(project_collection):
    result = CliRunner().invoke(main, ["skills", "add", "--help"])
    assert result.exit_code == 0 and "--path" in result.output
    assert "repository-relative" in result.output
    assert "--global" not in result.output


def test_add_path_rejects_plain_local_source_without_fake_success(project_collection):
    _, _, _, upstream = project_collection
    before = library_lock_path().read_bytes()
    result = CliRunner().invoke(main, ["skills", "add", str(upstream), "--path", "workflow-00"])
    assert result.exit_code != 0 and "file://" in result.output
    assert library_lock_path().read_bytes() == before


def test_recorded_custom_slug_is_not_silently_replaced_by_library_alias(project_collection):
    _, _, _, upstream = project_collection
    runner = CliRunner()
    added = runner.invoke(main, ["skills", "add", upstream.as_uri(), "--path", "workflow-00", "--slug", "other-alias"])
    assert added.exit_code == 0, added.output
    entry = read_lock(library_lock_path()).skills["other-alias"]
    action = skill_doctor._make_readd_library_action(slug="custom-child", entry=entry)
    before = library_lock_path().read_bytes()
    preview = runner.invoke(main, shlex.split(action.shell_preview)[1:])
    assert preview.exit_code != 0 and "different recorded slug" in preview.output
    import click
    with pytest.raises(click.ClickException, match="different recorded slug"):
        action.apply()
    assert library_lock_path().read_bytes() == before
    assert not library_skill_path("custom-child").exists()


@pytest.mark.parametrize("agent", ["standard", "claude-code"])
def test_unrecorded_matching_wrapper_projection_is_visible_and_diagnosed(project_collection, agent):
    home, project, backings, _ = project_collection
    convert(project_collection)
    link = projection("wrapper", agent, scope="project", home=home, project=project)
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(backings[1])
    before = [snapshot(b) for b in backings]
    project_lock = lock_file_path(scope="project", project=project).read_bytes()
    library = library_lock_path().read_bytes()
    wrapper = next(r for r in rows(project_collection) if r.slug == "wrapper")
    cell = wrapper.cells[(agent, "project")]
    assert cell.stray and cell.exposure_reason and not cell.payload_missing
    found = findings(project_collection)
    assert any(f.slug == "wrapper" and f.finding_type == "stray_symlink" and f.path == link for f in found)
    group = catalog(scope="project", home=home, project=project)[0]
    with pytest.raises(skill_collections.InstallError, match="wrapper"):
        apply_selection(group, {"standard": SELECTED}, scope="project", home=home, project=project)
    assert link.resolve() == backings[1]
    assert lock_file_path(scope="project", project=project).read_bytes() == project_lock
    assert library_lock_path().read_bytes() == library
    assert [snapshot(b) for b in backings] == before


def test_standalone_real_root_readd_with_nested_siblings_selects_only_root(project_collection):
    home, project, backings, upstream = project_collection
    (upstream / "SKILL.md").write_text("---\nname: root-name\n---\ngenuine root\n")
    git(upstream, "add", "SKILL.md")
    git(upstream, "commit", "-qm", "genuine root")
    entry = LockEntry(source="local/upstream", source_type="git", skill_path="SKILL.md",
                      extras={"sourceUrl": upstream.as_uri()})
    root_canonical = canonical_skill_dir("custom-root", scope="project", home=home, project=project)
    git(project, "clone", "-q", upstream.as_uri(), str(root_canonical))
    lock_path = lock_file_path(scope="project", project=project)
    lock = read_lock(lock_path)
    lock.skills["custom-root"] = entry
    write_lock(lock_path, lock)
    action = skill_doctor._make_readd_library_action(slug="custom-root", entry=entry)
    args = shlex.split(action.shell_preview)[1:]
    before = [snapshot(b) for b in backings]
    project_lock = lock_file_path(scope="project", project=project).read_bytes()
    preview = CliRunner().invoke(main, args)
    assert preview.exit_code == 0, preview.output
    assert set(read_lock(library_lock_path()).skills) == {"wrapper", "custom-root"}
    assert (library_skill_path("custom-root") / "SKILL.md").read_bytes() == (upstream / "SKILL.md").read_bytes()
    assert not [f for f in findings(project_collection) if f.slug == "custom-root"]
    old = os.environ["AGENT_TOOLKIT_SKILLS_ROOT"]
    try:
        os.environ["AGENT_TOOLKIT_SKILLS_ROOT"] = str(home / "root-action-library/skills")
        action.apply()
        action.apply()
        assert set(read_lock(library_lock_path()).skills) == {"custom-root"}
        assert read_lock(library_lock_path()).skills["custom-root"].skill_path == "."
        assert (library_skill_path("custom-root") / "SKILL.md").read_bytes() == (upstream / "SKILL.md").read_bytes()
        assert not (home / ".agents/skills/custom-root").exists()
    finally:
        os.environ["AGENT_TOOLKIT_SKILLS_ROOT"] = old
    assert lock_file_path(scope="project", project=project).read_bytes() == project_lock
    assert [snapshot(b) for b in backings] == before
