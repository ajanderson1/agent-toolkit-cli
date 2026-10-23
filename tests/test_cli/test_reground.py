"""REGROUND behavior: disposable homes, real local Git sources, no live install."""
import importlib
import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main as cli
from agent_toolkit_cli._install_core import InstallError, InstallPlan


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_SKILLS_ROOT", raising=False)
    monkeypatch.delenv("PI_CODING_AGENT_DIR", raising=False)
    return home


def git(path, *args):
    return subprocess.check_output(["git", "-C", str(path), *args], text=True).strip()


def repo(tmp_path, files):
    root = tmp_path / "source"
    root.mkdir()
    git(root, "init", "-b", "main")
    for name, content in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    git(root, "add", ".")
    git(root, "-c", "user.name=Test", "-c", "user.email=test@example.test", "commit", "-m", "fixture")
    return root


def invoke(*args):
    result = CliRunner().invoke(cli, list(args))
    assert result.exit_code == 0, result.output + repr(result.exception)
    return result


@pytest.mark.parametrize("kind,files,target", [
    ("skill", {"SKILL.md": "---\nname: shared\ndescription: test\n---\nTest"}, "standard"),
    ("agent", {"shared.md": "Role"}, "pi"),
    ("command", {"COMMAND.md": "---\nname: shared\ndescription: test\n---\nTest"}, "pi"),
])
def test_two_projects_share_backing(tmp_path, sandbox, monkeypatch, kind, files, target):
    source = repo(tmp_path, files)
    invoke(kind, "add", str(source), "--slug", "shared")
    paths = importlib.import_module(f"agent_toolkit_cli.{kind}_paths")
    engine = importlib.import_module(f"agent_toolkit_cli.{kind}_install")
    central = getattr(paths, f"canonical_{kind}_dir")("shared", scope="global")
    for name in ("a", "b"):
        project = tmp_path / name
        project.mkdir()
        monkeypatch.chdir(project)
        flag = "--agents" if kind == "skill" else "--harnesses"
        invoke(kind, "install", "shared", "-p", flag, target)
        assert getattr(paths, f"canonical_{kind}_dir")("shared", scope="project", project=project) == central
        assert not paths.project_store_root(project).exists()
    monkeypatch.chdir(tmp_path / "a")
    flag = "--agents" if kind == "skill" else "--harnesses"
    invoke(kind, "uninstall", "shared", "-p", flag, target)
    assert central.exists()
    assert getattr(paths, f"canonical_{kind}_dir")("shared", scope="project", project=tmp_path / "b").exists()


@pytest.mark.parametrize("kind", ["skill", "agent", "command"])
@pytest.mark.parametrize("source_driven", [False, True])
def test_isolated_config_cannot_bypass_engine(tmp_path, sandbox, kind, source_driven):
    config = sandbox / ".agent-toolkit/config.json"
    config.parent.mkdir()
    config.write_text(json.dumps({"projectBacking": "isolated"}))
    engine = importlib.import_module(f"agent_toolkit_cli.{kind}_install")
    project = tmp_path / "project"
    project.mkdir()
    with pytest.raises(InstallError, match="disabled"):
        from agent_toolkit_cli.skill_source import parse_source
        source = parse_source(str(tmp_path / "unused-source")) if source_driven else None
        engine.apply(InstallPlan(slug="x", scope="project", source=source, ref=None,
                                 add_agents=("pi",), remove_agents=()), project=project)
    assert not list(project.iterdir())


def test_directory_agent_projects_complete_tree(tmp_path, sandbox, monkeypatch):
    source = repo(tmp_path, {"AGENTS.md": "Role", "MEMORY.md": "Current",
        "memory/detail.md": "Detail", ".pi/skills/expert/SKILL.md": "Expert",
        "scripts/check.py": "print('ok')", "resources/data.txt": "Data"})
    invoke("agent", "add", str(source), "--slug", "shared")
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    invoke("agent", "install", "shared", "-p", "--harnesses", "pi")
    projection = project / ".pi/agents/shared"
    assert projection.is_symlink()
    for name in ("AGENTS.md", "MEMORY.md", "memory/detail.md", ".pi/skills/expert/SKILL.md", "scripts/check.py", "resources/data.txt"):
        assert (projection / name).read_text() == (source / name).read_text()
    invoke("agent", "uninstall", "shared", "-p", "--harnesses", "pi")
    assert not projection.is_symlink()
    assert (sandbox / ".agent-toolkit/agents/shared/AGENTS.md").exists()


@pytest.mark.parametrize("url", ["https://gitea.example:8443/team/repo.git", "http://gitea.example:3000/team/repo.git", "ssh://git@gitea.example:2222/team/repo.git"])
def test_gitea_identity_roundtrip(url, tmp_path):
    from agent_toolkit_cli.skill_source import parse_source
    from agent_toolkit_cli.skill_lock import LockEntry, LockFile, write_lock, read_lock, clone_url_from_entry
    parsed = parse_source(url)
    assert parsed.url == url
    entry = LockEntry(source=parsed.identity, source_type=parsed.type, ref="release/test")
    path = tmp_path / "lock.json"
    write_lock(path, LockFile(version=1, skills={"x": entry}))
    assert clone_url_from_entry(read_lock(path).skills["x"]) == url


@pytest.mark.parametrize("kind,filename,target", [("skill", "SKILL.md", "standard"), ("agent", "AGENTS.md", "pi"), ("command", "COMMAND.md", "pi")])
def test_enabled_isolation_preservation_and_migration(tmp_path, sandbox, monkeypatch, kind, filename, target):
    source = repo(tmp_path, {filename: "---\nname: shared\ndescription: test\n---\nRole", "resources/data": "kept"})
    invoke(kind, "add", str(source), "--slug", "shared")
    config = sandbox / ".agent-toolkit/config.json"
    config.write_text(json.dumps({"projectBacking": "isolated", "allowIsolatedProjects": True}))
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    flag = "--agents" if kind == "skill" else "--harnesses"
    invoke(kind, "install", "shared", "-p", flag, target)
    paths = importlib.import_module(f"agent_toolkit_cli.{kind}_paths")
    canonical = getattr(paths, f"canonical_{kind}_dir")
    private = canonical("shared", scope="project", project=project)
    central = canonical("shared", scope="global")
    assert private != central
    assert private.is_dir()
    lock_path = project / f"{kind}s-lock.json"
    before = lock_path.read_bytes()
    config.write_text('{}')
    invoke(kind, "install", "shared", "-p", flag, target)
    assert lock_path.read_bytes() == before
    assert canonical("shared", scope="project", project=project) == private
    invoke(kind, "install", "shared", "-p", flag, target, "--migrate-to-central")
    assert canonical("shared", scope="project", project=project) == central
    assert (private / "resources/data").read_text() == "kept"
    assert git(private, "status", "--porcelain") == ""


def test_explicit_in_tree_legacy_migration_preserves_checkout(tmp_path, sandbox, monkeypatch):
    source = repo(tmp_path, {"SKILL.md": "---\nname: shared\ndescription: test\n---\nRole"})
    invoke("skill", "add", str(source), "--slug", "shared")
    project = tmp_path / "project"
    project.mkdir()
    old = project / ".agents/skills/shared"
    old.parent.mkdir(parents=True)
    subprocess.run(["git", "clone", str(source), str(old)], check=True, capture_output=True)
    lock = project / "skills-lock.json"
    lock.write_bytes((sandbox / ".agent-toolkit/skills-lock.json").read_bytes())
    monkeypatch.chdir(project)
    invoke("skill", "install", "shared", "-p")
    assert old.is_dir() and not old.is_symlink()  # ordinary install preserves it
    invoke("skill", "install", "shared", "-p", "--migrate-to-central")
    assert old.is_symlink()
    backup = old.with_name("shared.pre-central")
    assert (backup / ".git").is_dir()
    assert (backup / "SKILL.md").read_bytes() == (source / "SKILL.md").read_bytes()


@pytest.mark.parametrize("problem", ["dirty", "divergent", "foreign", "malformed", "foreign-destination"])
def test_migration_refuses_without_mutation(tmp_path, sandbox, monkeypatch, problem):
    source = repo(tmp_path, {"SKILL.md": "---\nname: shared\ndescription: test\n---\nRole"})
    invoke("skill", "add", str(source), "--slug", "shared")
    config = sandbox / ".agent-toolkit/config.json"
    config.write_text('{"projectBacking":"isolated","allowIsolatedProjects":true}')
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    invoke("skill", "install", "shared", "-p")
    from agent_toolkit_cli.skill_paths import canonical_skill_dir
    private = canonical_skill_dir("shared", scope="project", project=project)
    link = project / ".agents/skills/shared"
    lock = project / "skills-lock.json"
    config.write_text('{}')
    if problem == "dirty":
        (private / "unique").write_text("keep")
    elif problem == "divergent":
        (private / "SKILL.md").write_text("local commit")
        git(private, "add", ".")
        git(private, "-c", "user.name=Test", "-c", "user.email=test@example.test", "commit", "-m", "unique")
    elif problem == "foreign":
        git(private, "remote", "set-url", "origin", "https://other.example/team/source")
    elif problem == "malformed":
        lock.write_text('{broken')
    else:
        link.unlink()
        link.symlink_to(source)
    before = lock.read_bytes(), link.readlink(), git(private, "rev-parse", "HEAD")
    result = CliRunner().invoke(cli, ["skill", "install", "shared", "-p", "--migrate-to-central"])
    assert result.exit_code != 0
    assert (lock.read_bytes(), link.readlink(), git(private, "rev-parse", "HEAD")) == before
    if problem == "dirty":
        assert (private / "unique").read_text() == "keep"


def test_migration_rolls_back_failed_link_creation(tmp_path, sandbox, monkeypatch):
    source = repo(tmp_path, {"SKILL.md": "---\nname: shared\ndescription: test\n---\nSkill"})
    invoke("skill", "add", str(source), "--slug", "shared")
    config = sandbox / ".agent-toolkit/config.json"
    config.write_text('{"projectBacking":"isolated","allowIsolatedProjects":true}')
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    invoke("skill", "install", "shared", "-p")
    config.write_text('{}')
    link = project / ".agents/skills/shared"
    old = link.readlink()
    lock = project / "skills-lock.json"
    before = lock.read_bytes()
    central = sandbox / ".agent-toolkit/skills/shared"
    original = Path.symlink_to
    def fail_new_link(self, target, *args, **kwargs):
        if self == link and target == central:
            raise OSError("injected link failure")
        return original(self, target, *args, **kwargs)
    monkeypatch.setattr(Path, "symlink_to", fail_new_link)
    result = CliRunner().invoke(cli, ["skill", "install", "shared", "-p", "--migrate-to-central"])
    assert result.exit_code != 0
    assert link.is_symlink() and link.readlink() == old
    assert lock.read_bytes() == before


def test_collection_projects_share_central_and_disabled_isolation_refused(tmp_path, sandbox, monkeypatch):
    source = repo(tmp_path, {"one/SKILL.md": "---\nname: one\ndescription: one\n---\nOne", "two/SKILL.md": "---\nname: two\ndescription: two\n---\nTwo"})
    invoke("skill", "add", f"file://{source}")
    from agent_toolkit_cli.skill_paths import canonical_skill_dir, project_store_root
    for name in ("a", "b"):
        project = tmp_path / name
        project.mkdir()
        monkeypatch.chdir(project)
        invoke("skill", "install", "one", "-p")
        assert canonical_skill_dir("one", scope="project", project=project) == canonical_skill_dir("one", scope="global")
        assert not project_store_root(project).exists()
    config = sandbox / ".agent-toolkit/config.json"
    config.write_text('{"projectBacking":"isolated"}')
    third = tmp_path / "third"
    third.mkdir()
    monkeypatch.chdir(third)
    result = CliRunner().invoke(cli, ["skill", "install", "one", "-p"])
    assert result.exit_code != 0 and "disabled" in result.output
    assert not project_store_root(third).exists()
    assert not (third / "skills-lock.json").exists()


def test_legacy_shared_agent_skill_namespace_is_not_reused(tmp_path, sandbox):
    from agent_toolkit_cli.agent_paths import canonical_agent_dir, project_store_root as agent_store
    from agent_toolkit_cli.skill_paths import project_store_root as skill_store
    project = tmp_path / "project"
    project.mkdir()
    old = skill_store(project) / "shared"
    old.mkdir(parents=True)
    (old / "shared.md").write_text("legacy role")
    (old / "SKILL.md").write_text("legacy skill")
    (project / "agents-lock.json").write_text(json.dumps({"version": 1, "skills": {"shared": {"source": "team/source", "sourceType": "github", "agentPath": "shared.md"}}}))
    assert canonical_agent_dir("shared", scope="project", project=project) == old
    assert agent_store(project) != skill_store(project)


def test_gitea_branch_url_and_directory_agent_import_update(tmp_path, sandbox, monkeypatch):
    from agent_toolkit_cli.skill_source import parse_source
    parsed = parse_source("http://gitea.example:3000/team/agents/src/branch/main/manager")
    assert (parsed.url, parsed.ref, parsed.subpath) == ("http://gitea.example:3000/team/agents", "main", "manager")
    source = repo(tmp_path, {"manager/AGENTS.md": "Role", "manager/MEMORY.md": "Before"})
    invoke("agent", "add", f"file://{source}/tree/main/manager")
    exported = (sandbox / ".agent-toolkit/agents-lock.json").read_bytes()
    # A fresh disposable HOME imports the exported provenance, not a host shorthand.
    second = tmp_path / "second-home"
    second.mkdir()
    monkeypatch.setenv("HOME", str(second))
    incoming = tmp_path / "export.json"
    incoming.write_bytes(exported)
    invoke("agent", "import", str(incoming))
    (source / "manager/MEMORY.md").write_text("After")
    git(source, "add", ".")
    git(source, "-c", "user.name=Test", "-c", "user.email=test@example.test", "commit", "-m", "learn")
    invoke("agent", "update", "manager", "-g")
    assert (second / ".agent-toolkit/agents/manager/MEMORY.md").read_text() == "After"


@pytest.mark.parametrize("kind,filename", [("skill", "SKILL.md"), ("agent", "AGENTS.md"), ("command", "COMMAND.md")])
def test_gitea_registration_import_real_git(tmp_path, sandbox, monkeypatch, kind, filename):
    source = repo(tmp_path, {filename: "---\nname: shared\ndescription: test\n---\nContent"})
    url = "http://gitea.example:3000/team/source.git"
    # Ordinary Git insteadOf in temporary HOME: no network or live config.
    config_text = f'[url "file://{source}"]\n    insteadOf = {url}\n'
    (sandbox / ".gitconfig").write_text(config_text)
    git(source, "branch", "release/test")
    invoke(kind, "add", url, "--slug", "shared", "--ref", "release/test")
    lock = sandbox / f".agent-toolkit/{kind}s-lock.json"
    data = json.loads(lock.read_text())
    assert data["skills"]["shared"]["source"] == url
    assert data["skills"]["shared"]["ref"] == "release/test"
    incoming = tmp_path / "incoming.json"
    incoming.write_bytes(lock.read_bytes())
    second = tmp_path / "second"
    second.mkdir()
    (second / ".gitconfig").write_text(config_text)
    monkeypatch.setenv("HOME", str(second))
    invoke(kind, "import", str(incoming))
    imported = json.loads((second / f".agent-toolkit/{kind}s-lock.json").read_text())
    assert imported["skills"]["shared"]["source"] == url
    assert imported["skills"]["shared"]["ref"] == "release/test"
    paths = importlib.import_module(f"agent_toolkit_cli.{kind}_paths")
    canonical = getattr(paths, f"canonical_{kind}_dir")("shared", scope="global")
    assert git(canonical, "config", "--get", "remote.origin.url") == url
    assert (canonical / filename).exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["skill", "agent", "command"])
async def test_tui_uses_real_shared_engine(tmp_path, sandbox, monkeypatch, kind):
    source = repo(tmp_path, {"SKILL.md": "---\nname: shared\ndescription: test\n---\nSkill", "shared.md": "Role", "COMMAND.md": "Prompt"})
    invoke(kind, "add", str(source), "--slug", "shared")
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    from agent_toolkit_tui.app import TUIApp
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one(f"#{kind}-grid")
        grid.restore_pending({("project", "pi", "shared"): "link"})
        result = getattr(app, f"_apply_{kind}_pending")()
        assert result.failed == 0, result.errors
        paths = importlib.import_module(f"agent_toolkit_cli.{kind}_paths")
        assert not paths.project_store_root(project).exists()
        canonical = getattr(paths, f"canonical_{kind}_dir")
        assert canonical("shared", scope="project", project=project) == canonical("shared", scope="global")


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["skill", "agent", "command"])
async def test_tui_refuses_disabled_private_creation(tmp_path, sandbox, monkeypatch, kind):
    source = repo(tmp_path, {"SKILL.md": "---\nname: shared\ndescription: test\n---\nSkill", "shared.md": "Role", "COMMAND.md": "Prompt"})
    invoke(kind, "add", str(source), "--slug", "shared")
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    (sandbox / ".agent-toolkit/config.json").write_text('{"projectBacking":"isolated"}')
    from agent_toolkit_tui.app import TUIApp
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.query_one(f"#{kind}-grid").restore_pending({("project", "pi", "shared"): "link"})
        result = getattr(app, f"_apply_{kind}_pending")()
        assert result.failed == 1 and "disabled" in " ".join(result.errors)
        assert not (project / f"{kind}s-lock.json").exists()
        paths = importlib.import_module(f"agent_toolkit_cli.{kind}_paths")
        assert not paths.project_store_root(project).exists()


def test_directory_agent_unsupported_harness_is_honest(tmp_path, sandbox, monkeypatch):
    source = repo(tmp_path, {"AGENTS.md": "Role", "MEMORY.md": "Memory"})
    invoke("agent", "add", str(source), "--slug", "shared")
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    result = invoke("agent", "install", "shared", "-p", "--harnesses", "standard")
    assert "skipped (unsupported mechanism): standard" in result.output
    assert not (project / ".claude/agents/shared.md").exists()
    assert not (project / "agents-lock.json").exists()


def test_foreign_project_skill_does_not_acquire_ownership(tmp_path, sandbox, monkeypatch):
    source = repo(tmp_path, {"SKILL.md": "---\nname: shared\ndescription: test\n---\nSkill"})
    invoke("skill", "add", str(source), "--slug", "shared")
    project = tmp_path / "project"
    project.mkdir()
    foreign = project / ".claude/skills/shared"
    foreign.mkdir(parents=True)
    (foreign / "unique").write_text("keep")
    monkeypatch.chdir(project)
    result = CliRunner().invoke(cli, ["skill", "install", "shared", "-p", "--agents", "claude-code"])
    assert result.exit_code != 0
    assert (foreign / "unique").read_text() == "keep"
    assert not (project / "skills-lock.json").exists()


def test_malformed_lock_refused(tmp_path):
    from agent_toolkit_cli.skill_lock import read_lock
    path = tmp_path / "skills-lock.json"
    path.write_text('{"version": 1, "skills": {"x": {"source": 12}}}')
    with pytest.raises(ValueError):
        read_lock(path)
