"""Git checks follow library backing, not catalogue provenance."""

import json
import shutil
from dataclasses import replace

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from agent_toolkit_cli.skill_update_check import read_check
from agent_toolkit_tui.asset_info import catalog_skill_info
from tests.test_cli.test_reground import sandbox, repo, git, invoke


@pytest.mark.parametrize("named", [False, True])
def test_check_named_and_default_git_library_without_catalog(tmp_path, sandbox, named):
    source = repo(tmp_path, {"SKILL.md": "---\nname: demo\ndescription: demo\n---\n"})
    invoke("skills", "add", source.as_uri(), "--slug", "demo", "--ref", "main")
    lock = sandbox / ".agent-toolkit/skills-lock.json"
    before = lock.read_bytes()
    canonical = sandbox / ".agent-toolkit/skills/demo"
    head = git(canonical, "rev-parse", "HEAD")
    args = ("demo",) if named else ()
    result = json.loads(invoke("skills", "check", *args, "-g", "--json").stdout)
    assert len(result) == 1
    assert result[0]["status"] == "current" and result[0]["checked_at"]
    assert git(canonical, "rev-parse", "HEAD") == head and lock.read_bytes() == before
    assert not (sandbox / ".agent-toolkit/config.json").exists()
    (canonical / "local.txt").write_text("keep")
    (source / "new.txt").write_text("upstream")
    git(source, "add", ".")
    git(
        source,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.test",
        "commit",
        "-m",
        "advance",
    )
    row = json.loads(invoke("skills", "check", "demo", "-g", "--json").stdout)[0]
    assert row["status"] == "different" and row["local_changes"]
    assert (
        git(canonical, "rev-parse", "HEAD") == head
        and (canonical / "local.txt").read_text() == "keep"
    )
    source.rename(tmp_path / "offline")
    result = CliRunner().invoke(main, ["skills", "check", "demo", "-g", "--json"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)[0]["status"] == "unknown"
    assert (
        read_check("demo", scope="global", home=sandbox, project=None)["status"]
        == "unknown"
    )


@pytest.mark.parametrize("damage", ["missing", "non-git", "origin"])
def test_check_missing_or_non_git_backing_is_not_clean(tmp_path, sandbox, damage):
    source = repo(tmp_path, {"SKILL.md": "---\nname: demo\n---\n"})
    invoke("skills", "add", source.as_uri(), "--slug", "demo")
    canonical = sandbox / ".agent-toolkit/skills/demo"
    if damage == "missing":
        shutil.rmtree(canonical)
    elif damage == "non-git":
        shutil.rmtree(canonical / ".git")
    else:
        git(canonical, "remote", "set-url", "origin", (tmp_path / "foreign").as_uri())
    result = CliRunner().invoke(main, ["skills", "check", "demo", "-g", "--json"])
    assert result.exit_code == 1
    row = json.loads(result.stdout)[0]
    assert row["status"] == "unknown" and row["error"]
    assert "catalog-associated" not in row["error"]


def test_info_without_catalog_shows_local_revision_and_observation(tmp_path, sandbox):
    source = repo(tmp_path, {"SKILL.md": "---\nname: demo\n---\n"})
    invoke("skills", "add", source.as_uri(), "--slug", "demo", "--ref", "main")
    sha = git(sandbox / ".agent-toolkit/skills/demo", "rev-parse", "HEAD")
    text = "\n".join(
        catalog_skill_info("demo", scope="global", home=sandbox, project=None)
    )
    assert sha in text and "not checked" in text
    assert "Catalog:" not in text
    row = json.loads(invoke("skills", "check", "demo", "-g", "--json").stdout)[0]
    assert row["checked_at"] in "\n".join(
        catalog_skill_info("demo", scope="global", home=sandbox, project=None)
    )
    invoke("skills", "update", "demo", "-g")
    # A new actual local commit invalidates the old observation.
    canonical = sandbox / ".agent-toolkit/skills/demo"
    (canonical / "note").write_text("local")
    git(canonical, "add", ".")
    git(
        canonical,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.test",
        "commit",
        "-m",
        "local",
    )
    assert (
        read_check("demo", scope="global", home=sandbox, project=None)["status"]
        == "stale"
    )


def test_sha_pin_without_catalog_does_not_query_upstream(tmp_path, sandbox):
    source = repo(tmp_path, {"SKILL.md": "---\nname: demo\n---\n"})
    sha = git(source, "rev-parse", "HEAD")
    invoke(
        "skills", "add", source.as_uri(), "--path", ".", "--slug", "demo", "--ref", sha
    )
    source.rename(tmp_path / "offline")
    row = json.loads(invoke("skills", "check", "demo", "-g", "--json").stdout)[0]
    assert row["status"] == "pinned" and row["local_sha"] == sha


def test_project_private_backing_and_central_checks_without_catalog(
    tmp_path, sandbox, monkeypatch
):
    from agent_toolkit_cli.skill_paths import (
        project_store_root,
        library_lock_path,
        lock_file_path,
    )
    from agent_toolkit_cli.skill_lock import LockFile, read_lock, write_lock

    source = repo(tmp_path, {"SKILL.md": "---\nname: demo\n---\n"})
    invoke("skills", "add", source.as_uri(), "--slug", "demo", "--ref", "main")
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    invoke("skills", "install", "demo", "--scope", "project", "--agents", "standard")
    central = json.loads(invoke("skills", "check", "demo", "-p", "--json").stdout)[0]
    assert central["status"] == "current"
    # Reproduce an explicitly recorded legacy private store without migrating it.
    entry = read_lock(library_lock_path()).skills["demo"]
    private = project_store_root(project) / "demo"
    private.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(sandbox / ".agent-toolkit/skills/demo", private)
    write_lock(
        lock_file_path(scope="project", project=project),
        LockFile(
            version=3,
            skills={"demo": replace(entry, extras={"projectBacking": "isolated"})},
        ),
    )
    (private / "private.txt").write_text("preserve")
    row = json.loads(invoke("skills", "check", "demo", "-p", "--json").stdout)[0]
    assert row["status"] == "current" and row["local_changes"]
    assert row["identity"]["backing"] == str(private.resolve())
    assert (private / "private.txt").read_text() == "preserve"
    assert " -p" in "\n".join(
        catalog_skill_info("demo", scope="project", home=sandbox, project=project)
    )


def test_shared_parent_check_batches_one_upstream_probe(tmp_path, sandbox, monkeypatch):
    import agent_toolkit_cli.skill_update_check as checks

    source = repo(
        tmp_path,
        {"a/SKILL.md": "---\nname: a\n---\n", "b/SKILL.md": "---\nname: b\n---\n"},
    )
    invoke("skills", "add", source.as_uri(), "--ref", "main")
    original = checks.run_git
    probes = []

    def run(args, **kwargs):
        if args[0] == "ls-remote":
            probes.append(tuple(args))
        return original(args, **kwargs)

    monkeypatch.setattr(checks, "run_git", run)
    result = json.loads(invoke("skills", "check", "-g", "--json").stdout)
    assert {r["slug"] for r in result} == {"a", "b"}
    assert all(r["status"] == "current" for r in result)
    assert len(probes) == 1
