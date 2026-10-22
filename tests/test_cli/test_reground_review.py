"""Regressions for the seven 8a95 lifecycle/safety findings; real local Git."""
import importlib
import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from agent_toolkit_cli._install_core import InstallError
from tests.test_cli.test_reground import sandbox, repo, git, invoke


def commit(root, message="fixture update"):
    git(root, "add", ".")
    git(root, "-c", "user.name=Test", "-c", "user.email=test@example.test", "commit", "-m", message)


def config(home, enabled):
    (home / ".agent-toolkit/config.json").write_text(json.dumps(
        {"projectBacking": "isolated", "allowIsolatedProjects": True} if enabled else {}))


@pytest.mark.parametrize("kind,content", [("agent", "AGENTS.md"), ("command", "COMMAND.md")])
def test_linked_worktree_isolation_never_copies_git_pointer(tmp_path, sandbox, monkeypatch, kind, content):
    source = repo(tmp_path, {content: "Role"})
    invoke(kind, "add", str(source), "--slug", "shared")
    central = sandbox / f".agent-toolkit/{kind}s/shared"
    original = central.with_name("original")
    central.rename(original)
    git(original, "worktree", "add", "-b", "linked", str(central))
    before = (git(central, "rev-parse", "HEAD"), git(central, "status", "--porcelain"), (central / content).read_bytes())
    config(sandbox, True)
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    result = CliRunner().invoke(main, [kind, "install", "shared", "-p", "--harnesses", "pi"])
    # A conservative refusal is supported; sharing a .git pointer is not.
    assert result.exit_code != 0 and "worktree" in result.output.lower()
    paths = importlib.import_module(f"agent_toolkit_cli.{kind}_paths")
    assert not paths.project_store_root(project).exists()
    assert not (project / f"{kind}s-lock.json").exists()
    assert before == (git(central, "rev-parse", "HEAD"), git(central, "status", "--porcelain"), (central / content).read_bytes())


@pytest.mark.parametrize("kind,filename", [("agent", "AGENTS.md"), ("command", "COMMAND.md")])
def test_legacy_copied_gitfile_cannot_update_another_worktree(tmp_path, sandbox, monkeypatch, kind, filename):
    import shutil
    from dataclasses import replace
    source = repo(tmp_path, {filename: "Before"})
    invoke(kind, "add", str(source), "--slug", "shared")
    paths = importlib.import_module(f"agent_toolkit_cli.{kind}_paths")
    locks = importlib.import_module(f"agent_toolkit_cli.{kind}_lock")
    central = getattr(paths, f"canonical_{kind}_dir")("shared", scope="global")
    original = central.with_name("original")
    central.rename(original)
    git(original, "worktree", "add", "-b", "linked", str(central))
    project = tmp_path / "project"
    project.mkdir()
    private = paths.project_store_root(project) / "shared"
    shutil.copytree(central, private)  # reproduce a legacy copied gitdir pointer
    lock = locks.read_lock(paths.library_lock_path())
    lock.skills["shared"] = replace(lock.skills["shared"], extras={"projectBacking": "isolated"})
    locks.write_lock(project / f"{kind}s-lock.json", lock)
    (source / filename).write_text("After")
    commit(source)
    before = git(central, "rev-parse", "HEAD"), (central / filename).read_bytes(), git(central, "status", "--porcelain")
    monkeypatch.chdir(project)
    result = CliRunner().invoke(main, [kind, "update", "shared", "-p"])
    assert result.exit_code != 0 and "worktree" in result.output.lower()
    assert before == (git(central, "rev-parse", "HEAD"), (central / filename).read_bytes(), git(central, "status", "--porcelain"))
    assert (private / filename).read_text() == "Before"
    recorded = (project / f"{kind}s-lock.json").read_bytes()
    result = CliRunner().invoke(main, [kind, "install", "shared", "-p", "--harnesses", "pi", "--migrate-to-central"])
    assert result.exit_code != 0 and "worktree" in result.output.lower()
    assert (project / f"{kind}s-lock.json").read_bytes() == recorded


@pytest.mark.parametrize("kind,filename", [("agent", "AGENTS.md"), ("command", "COMMAND.md")])
def test_legitimate_central_worktree_keeps_its_own_files_and_index(tmp_path, sandbox, monkeypatch, kind, filename):
    source = repo(tmp_path, {filename: "Before"})
    invoke(kind, "add", str(source), "--slug", "shared")
    central = sandbox / f".agent-toolkit/{kind}s/shared"
    original = central.with_name("original")
    central.rename(original)
    git(original, "worktree", "add", "-b", "linked", str(central))
    original_before = git(original, "rev-parse", "HEAD"), (original / filename).read_bytes()
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    invoke(kind, "install", "shared", "-p", "--harnesses", "pi")
    (source / filename).write_text("After")
    commit(source)
    invoke(kind, "update", "shared", "-g")
    assert (central / filename).read_text() == "After"
    assert git(central, "status", "--porcelain") == ""
    assert original_before == (git(original, "rev-parse", "HEAD"), (original / filename).read_bytes())
    assert git(original, "status", "--porcelain") == ""


@pytest.mark.parametrize("scope", ["central", "private"])
def test_recorded_flat_agent_wins_over_maintenance_agents(tmp_path, sandbox, monkeypatch, scope):
    source = repo(tmp_path, {"shared.md": "Legacy role", "AGENTS.md": "Repository maintenance instructions"})
    invoke("agent", "add", str(source), "--slug", "shared")
    lock = sandbox / ".agent-toolkit/agents-lock.json"
    data = json.loads(lock.read_text())
    data["skills"]["shared"]["agentPath"] = "shared.md"  # pre-directory registration
    lock.write_text(json.dumps(data))
    if scope == "private":
        config(sandbox, True)
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    invoke("agent", "install", "shared", "-p", "--harnesses", "standard,pi")
    assert (project / ".claude/agents/shared.md").read_text() == "Legacy role"
    assert (project / ".pi/agents/shared.md").read_text() == "Legacy role"
    assert not (project / ".pi/agents/shared").exists()
    # Detach also uses recorded flat content when recognizing legacy files.
    (project / ".pi/agents/.shared.md.attk").unlink()
    invoke("agent", "uninstall", "shared", "-p", "--harnesses", "standard,pi")
    assert not (project / ".pi/agents/shared.md").exists()


@pytest.mark.parametrize("failure", ["invalid-target", "after-install", "already-central"])
@pytest.mark.parametrize("kind,filename", [("skill", "SKILL.md"), ("agent", "shared.md"), ("command", "COMMAND.md")])
def test_failed_migrating_install_preserves_original_owned_state(tmp_path, sandbox, monkeypatch, failure, kind, filename):
    source = repo(tmp_path, {filename: "---\nname: shared\ndescription: Test\n---\nRole"})
    invoke(kind, "add", str(source), "--slug", "shared")
    config(sandbox, True)
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    flag = "--agents" if kind == "skill" else "--harnesses"
    invoke(kind, "install", "shared", "-p", flag, "pi")
    config(sandbox, False)
    link = project / {"skill": ".agents/skills/shared", "agent": ".pi/agents/shared.md", "command": ".pi/prompts/shared.md"}[kind]
    lock = project / f"{kind}s-lock.json"
    def slots():
        return {str(p.relative_to(project)): ("link", str(p.readlink())) if p.is_symlink() else ("file", p.read_bytes())
                for p in project.rglob("*") if p.is_symlink() or p.is_file()}
    if failure == "already-central":
        invoke(kind, "install", "shared", "-p", flag, "pi", "--migrate-to-central")
    before = slots()
    if failure in ("after-install", "already-central"):
        module = importlib.import_module("agent_toolkit_cli.commands.skill" if kind == "skill" else f"agent_toolkit_cli.{kind}_install")
        attribute = "engine_apply" if kind == "skill" else "apply"
        real_apply = getattr(module, attribute)
        def fail_after_apply(*args, **kwargs):
            real_apply(*args, **kwargs)
            raise InstallError("injected after projection writes")
        monkeypatch.setattr(module, attribute, fail_after_apply)
    target = "not-a-harness" if failure == "invalid-target" else ("standard,claude-code" if kind == "skill" else "pi,standard")
    result = CliRunner().invoke(main, [kind, "install", "shared", "-p", "--migrate-to-central", flag, target])
    assert result.exit_code != 0
    assert slots() == before
    assert link.exists() and lock.exists()


@pytest.mark.parametrize("kind,filename", [("skill", "SKILL.md"), ("agent", "AGENTS.md"), ("command", "COMMAND.md")])
def test_private_detach_reinstall_keeps_provenance_and_unique_work(tmp_path, sandbox, monkeypatch, kind, filename):
    source = repo(tmp_path, {filename: "---\nname: shared\ndescription: Test\n---\nRole"})
    invoke(kind, "add", str(source), "--slug", "shared")
    config(sandbox, True)
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    flag = "--agents" if kind == "skill" else "--harnesses"
    invoke(kind, "install", "shared", "-p", flag, "pi")
    paths = importlib.import_module(f"agent_toolkit_cli.{kind}_paths")
    canonical = getattr(paths, f"canonical_{kind}_dir")("shared", scope="project", project=project)
    (canonical / "unique-local-memory").write_text("must survive")
    lock = project / f"{kind}s-lock.json"
    source_identity = json.loads(lock.read_text())["skills"]["shared"]["source"]
    config(sandbox, False)
    invoke(kind, "uninstall", "shared", "-p", flag, "pi")
    invoke(kind, "install", "shared", "-p", flag, "pi")
    assert (canonical / "unique-local-memory").read_text() == "must survive"
    assert json.loads(lock.read_text())["skills"]["shared"]["source"] == source_identity
    assert getattr(paths, f"canonical_{kind}_dir")("shared", scope="project", project=project) == canonical


@pytest.mark.parametrize("escape", ["entry-directory", "entry-content", "recorded-entry"])
def test_agent_registration_and_projection_refuse_outside_symlinks(tmp_path, sandbox, monkeypatch, escape):
    source = repo(tmp_path, {"manager/AGENTS.md": "Role", "manager/MEMORY.md": "Owned"})
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "AGENTS.md").write_text("Foreign role")
    (foreign / "secret-resource").write_text("Do not expose")
    url = f"file://{source}/tree/main/manager"
    if escape == "recorded-entry":
        invoke("agent", "add", url)
        from agent_toolkit_cli.agent_paths import library_agent_path
        backing = library_agent_path("manager").resolve()
        moved = backing.with_name("preserved-manager")
        backing.rename(moved)
        backing.symlink_to(foreign, target_is_directory=True)
        project = tmp_path / "project"
        project.mkdir()
        monkeypatch.chdir(project)
        result = CliRunner().invoke(main, ["agent", "install", "manager", "-p", "--harnesses", "pi"])
        assert result.exit_code != 0
        assert not (project / ".pi/agents/manager").exists()
        assert not (project / "agents-lock.json").exists()
    else:
        if escape == "entry-directory":
            (source / "manager/AGENTS.md").unlink()
            (source / "manager/MEMORY.md").unlink()
            (source / "manager").rmdir()
            (source / "manager").symlink_to(foreign, target_is_directory=True)
        else:
            (source / "manager/AGENTS.md").unlink()
            (source / "manager/AGENTS.md").symlink_to(foreign / "AGENTS.md")
        commit(source)
        result = CliRunner().invoke(main, ["agent", "add", url])
        assert result.exit_code != 0
        assert not (sandbox / ".agent-toolkit/agents-lock.json").exists()
    assert (foreign / "secret-resource").read_text() == "Do not expose"


@pytest.mark.parametrize("monorepo", [False, True])
def test_new_flat_registration_keeps_maintenance_instructions_separate(tmp_path, sandbox, monorepo):
    prefix = "manager/" if monorepo else ""
    source = repo(tmp_path, {prefix + "shared.md": "Flat role", prefix + "AGENTS.md": "Maintenance"})
    url = f"file://{source}/tree/main/manager" if monorepo else str(source)
    invoke("agent", "add", url, "--slug", "shared")
    entry = json.loads((sandbox / ".agent-toolkit/agents-lock.json").read_text())["skills"]["shared"]
    assert entry["agentPath"] == prefix + "shared.md"


def test_default_ref_update_does_not_change_registration_identity(tmp_path, sandbox):
    source = repo(tmp_path, {"manager/AGENTS.md": "Role", "manager/MEMORY.md": "Before"})
    # --ref absent is distinct from an explicit main request.
    invoke("agent", "add", f"file://{source}/tree/main/manager")
    from agent_toolkit_cli.agent_paths import library_agent_path, agent_parent_clone_path
    from agent_toolkit_cli.agent_lock import read_lock, write_lock
    path = sandbox / ".agent-toolkit/agents-lock.json"
    lock = read_lock(path)
    explicit = agent_parent_clone_path("local", "source", ref="main")
    default = agent_parent_clone_path("local", "source", ref=None)
    explicit.rename(default)
    canonical = library_agent_path("manager")
    canonical.unlink()
    canonical.symlink_to(default / "manager")
    lock.skills["manager"].ref = None
    write_lock(path, lock)
    (source / "manager/MEMORY.md").write_text("After")
    commit(source)
    invoke("agent", "update", "manager", "-g")
    assert read_lock(path).skills["manager"].ref is None
    assert (canonical / "MEMORY.md").read_text() == "After"
    project = tmp_path / "project"
    project.mkdir()
    invoke("--project", str(project), "agent", "install", "manager", "-p", "--harnesses", "pi")
    assert (project / ".pi/agents/manager/MEMORY.md").read_text() == "After"


def test_gitea_dotgit_tree_identity_remains_projectable_after_import(tmp_path, sandbox, monkeypatch):
    source = repo(tmp_path, {"manager/AGENTS.md": "Role", "manager/MEMORY.md": "Memory"})
    url = "http://gitea.fixture.invalid:3000/team/source.git"
    mapping = f'[url "file://{source}"]\n    insteadOf = {url}\n'
    (sandbox / ".gitconfig").write_text(mapping)
    invoke("agent", "add", url + "/tree/main/manager")
    incoming = tmp_path / "incoming.json"
    incoming.write_bytes((sandbox / ".agent-toolkit/agents-lock.json").read_bytes())
    second = tmp_path / "second-home"
    second.mkdir()
    (second / ".gitconfig").write_text(mapping)
    monkeypatch.setenv("HOME", str(second))
    invoke("agent", "import", str(incoming))
    project = tmp_path / "project"
    project.mkdir()
    invoke("--project", str(project), "agent", "install", "manager", "-p", "--harnesses", "pi")
    assert (project / ".pi/agents/manager/MEMORY.md").read_text() == "Memory"
    entry = json.loads((project / "agents-lock.json").read_text())["skills"]["manager"]
    assert (entry["parentUrl"], entry["ref"]) == (url, "main")


def test_malformed_agent_lock_refused_before_parent_refresh(tmp_path, sandbox):
    source = repo(tmp_path, {"manager/AGENTS.md": "Role", "manager/MEMORY.md": "Before"})
    url = f"file://{source}/tree/main/manager"
    invoke("agent", "add", url)
    from agent_toolkit_cli.agent_paths import library_agent_path
    canonical = library_agent_path("manager")
    before_head = git(canonical, "rev-parse", "HEAD")
    (source / "manager/MEMORY.md").write_text("After")
    commit(source)
    lock = sandbox / ".agent-toolkit/agents-lock.json"
    lock.write_text('{broken')
    result = CliRunner().invoke(main, ["agent", "add", url])
    assert result.exit_code != 0
    assert lock.read_bytes() == b'{broken'
    assert git(canonical, "rev-parse", "HEAD") == before_head
    assert (canonical / "MEMORY.md").read_text() == "Before"
    assert git(canonical, "status", "--porcelain") == ""


def test_monorepo_agent_changed_ref_refused_before_new_backing(tmp_path, sandbox):
    source = repo(tmp_path, {"manager/AGENTS.md": "Role", "manager/MEMORY.md": "Main"})
    git(source, "checkout", "-b", "release")
    (source / "manager/MEMORY.md").write_text("Release")
    commit(source)
    git(source, "checkout", "main")
    invoke("agent", "add", f"file://{source}/tree/main/manager")
    lock = sandbox / ".agent-toolkit/agents-lock.json"
    before = lock.read_bytes()
    from agent_toolkit_cli.agent_paths import agent_parent_clone_path, library_agent_path
    result = CliRunner().invoke(main, ["agent", "add", f"file://{source}/tree/release/manager"])
    assert result.exit_code != 0 and "ref" in result.output.lower()
    assert lock.read_bytes() == before
    assert (library_agent_path("manager") / "MEMORY.md").read_text() == "Main"
    assert not agent_parent_clone_path("local", "source", ref="release").exists()
