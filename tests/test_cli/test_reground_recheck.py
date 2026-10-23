"""A–D independent recheck regressions; local Git/temporary HOME only."""
import importlib
import json
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from agent_toolkit_cli._install_core import InstallError
from tests.test_cli.test_reground import sandbox, repo, git, invoke
from tests.test_cli.test_reground_review import commit, config


def index_bytes(root):
    path = Path(git(root, "rev-parse", "--git-path", "index"))
    return (path if path.is_absolute() else root / path).read_bytes()


@pytest.mark.parametrize("verb", ["add", "update", "reset"])
@pytest.mark.parametrize("attacked", ["manager", "sibling"])
@pytest.mark.parametrize("home_alias", [False, True])
def test_refused_shared_agent_refresh_never_exposes_prospective_symlink(tmp_path, sandbox, monkeypatch, verb, attacked, home_alias):
    if home_alias:
        alias = tmp_path / "home-alias"
        alias.symlink_to(sandbox, target_is_directory=True)
        monkeypatch.setenv("HOME", str(alias))
    source = repo(tmp_path, {"manager/AGENTS.md": "Manager role", "manager/MEMORY.md": "Owned memory",
                             "sibling/AGENTS.md": "Sibling role", "sibling/MEMORY.md": "Sibling memory"})
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    for name in ("manager", "sibling"):
        invoke("agent", "add", f"file://{source}/tree/main/{name}")
        invoke("agent", "install", name, "-p", "--harnesses", "pi")
    from agent_toolkit_cli.agent_paths import library_agent_path
    parent = library_agent_path("manager").resolve().parent
    lock = sandbox / ".agent-toolkit/agents-lock.json"
    project_lock = project / "agents-lock.json"
    def state():
        return (git(parent, "rev-parse", "HEAD"), lock.read_bytes(), project_lock.read_bytes(),
                git(parent, "for-each-ref", "--format=%(refname) %(objectname)"), index_bytes(parent))
    before = state()
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "AGENTS.md").write_text("Outside role")
    (foreign / "unrelated-resource").write_text("must not expose")
    shutil.rmtree(source / attacked)
    (source / attacked).symlink_to(foreign, target_is_directory=True)
    commit(source)
    args = ["agent", "add", f"file://{source}/tree/main/manager"] if verb == "add" else ["agent", verb, "manager", "-g"]
    if verb == "reset":
        args.append("--force")
    result = CliRunner().invoke(main, args)
    assert result.exit_code != 0
    assert before == state()
    assert git(parent, "status", "--porcelain") == ""
    for name in ("manager", "sibling"):
        slot = project / f".pi/agents/{name}"
        assert slot.resolve() == parent / name
        assert not (slot / "unrelated-resource").exists()
        assert (slot / "AGENTS.md").read_text() == f"{name.title()} role"


@pytest.mark.parametrize("verb", ["add", "update", "reset"])
def test_unlisted_shared_alias_is_not_silently_exposed(tmp_path, sandbox, verb):
    source = repo(tmp_path, {"manager/AGENTS.md": "Role", "sibling/AGENTS.md": "Sibling"})
    for name in ("manager", "sibling"):
        invoke("agent", "add", f"file://{source}/tree/main/{name}")
    from agent_toolkit_cli.agent_paths import library_agent_path
    parent = library_agent_path("manager").resolve().parent
    lock = sandbox / ".agent-toolkit/agents-lock.json"
    data = json.loads(lock.read_text())
    del data["skills"]["sibling"]  # retained alias may still serve another project
    lock.write_text(json.dumps(data))
    before = lock.read_bytes(), git(parent, "rev-parse", "HEAD"), index_bytes(parent)
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "AGENTS.md").write_text("Outside")
    shutil.rmtree(source / "sibling")
    (source / "sibling").symlink_to(foreign, target_is_directory=True)
    commit(source)
    args = ["agent", "add", f"file://{source}/tree/main/manager"] if verb == "add" else ["agent", verb, "manager", "-g"]
    result = CliRunner().invoke(main, args)
    assert result.exit_code != 0 and "unrecorded agent alias" in result.output
    assert before == (lock.read_bytes(), git(parent, "rev-parse", "HEAD"), index_bytes(parent))
    assert (library_agent_path("sibling") / "AGENTS.md").read_text() == "Sibling"


@pytest.mark.parametrize("verb", ["add", "update", "reset"])
def test_safe_shared_refresh_accepts_all_consumers_and_internal_resources(tmp_path, sandbox, monkeypatch, verb):
    source = repo(tmp_path, {"manager/AGENTS.md": "Role", "manager/MEMORY.md": "Before",
                             "manager/resources/data.txt": "bundled", "sibling/AGENTS.md": "Sibling",
                             "sibling/MEMORY.md": "Before"})
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    for name in ("manager", "sibling"):
        invoke("agent", "add", f"file://{source}/tree/main/{name}")
        invoke("agent", "install", name, "-p", "--harnesses", "pi")
    for name in ("manager", "sibling"):
        (source / name / "MEMORY.md").write_text("After")
    (source / "manager/resources/alias.txt").symlink_to("data.txt")
    commit(source)
    args = ["agent", "add", f"file://{source}/tree/main/manager"] if verb == "add" else ["agent", verb, "manager", "-g"]
    invoke(*args)
    for name in ("manager", "sibling"):
        assert (project / f".pi/agents/{name}/MEMORY.md").read_text() == "After"
    assert (project / ".pi/agents/manager/resources/alias.txt").read_text() == "bundled"


@pytest.mark.parametrize("verb", ["add", "import"])
def test_missing_parent_reacquisition_cannot_revive_unsafe_sibling(tmp_path, sandbox, monkeypatch, verb):
    source = repo(tmp_path, {"manager/AGENTS.md": "Role", "newcomer/AGENTS.md": "New"})
    invoke("agent", "add", f"file://{source}/tree/main/manager")
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    invoke("agent", "install", "manager", "-p", "--harnesses", "pi")
    from agent_toolkit_cli.agent_paths import library_agent_path
    parent = library_agent_path("manager").resolve().parent
    shutil.rmtree(parent)  # simulate cache loss; existing projection stays broken
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "AGENTS.md").write_text("Outside")
    (foreign / "unrelated-resource").write_text("not registered")
    shutil.rmtree(source / "manager")
    (source / "manager").symlink_to(foreign, target_is_directory=True)
    commit(source)
    lock = sandbox / ".agent-toolkit/agents-lock.json"
    before = lock.read_bytes()
    if verb == "add":
        args = ["agent", "add", f"file://{source}/tree/main/newcomer"]
    else:
        incoming = tmp_path / "incoming.json"
        incoming.write_text(json.dumps({"version": 1, "skills": {"newcomer": {
            "source": "local/source", "sourceType": "git", "ref": "main",
            "parentUrl": f"file://{source}", "agentPath": "newcomer/AGENTS.md", "readOnly": True}}}))
        args = ["agent", "import", str(incoming), "--latest"]
    result = CliRunner().invoke(main, args)
    assert result.exit_code != 0 and "symlink" in result.output
    assert lock.read_bytes() == before and not parent.exists()
    assert not (project / ".pi/agents/manager/unrelated-resource").exists()


@pytest.mark.parametrize("unsafe", [False, True])
def test_legacy_source_install_refresh_validates_before_checkout(tmp_path, sandbox, unsafe):
    source = repo(tmp_path, {"AGENTS.md": "Role", "MEMORY.md": "Before"})
    invoke("agent", "add", str(source), "--slug", "shared")
    from agent_toolkit_cli.agent_paths import library_agent_path
    from agent_toolkit_cli.agent_install import install
    from agent_toolkit_cli.skill_source import parse_source
    canonical = library_agent_path("shared")
    before = git(canonical, "rev-parse", "HEAD")
    if unsafe:
        foreign = tmp_path / "foreign.md"
        foreign.write_text("Outside role")
        (source / "AGENTS.md").unlink()
        (source / "AGENTS.md").symlink_to(foreign)
    else:
        (source / "MEMORY.md").write_text("After")
    commit(source)
    def refresh():
        return install(parsed=parse_source(str(source)), slug="shared", scope="global",
                       home=sandbox, project=None, harnesses=("pi",), env=None)
    if unsafe:
        with pytest.raises(InstallError, match="symlink"):
            refresh()
        assert git(canonical, "rev-parse", "HEAD") == before
        assert not (canonical / "AGENTS.md").is_symlink()
    else:
        refresh()
        assert (canonical / "MEMORY.md").read_text() == "After"


@pytest.mark.parametrize("verb", ["update", "reset"])
def test_refresh_rejects_escaping_directory_resources_before_checkout(tmp_path, sandbox, verb):
    source = repo(tmp_path, {"AGENTS.md": "Role"})
    invoke("agent", "add", str(source), "--slug", "shared")
    canonical = sandbox / ".agent-toolkit/agents/shared"
    before = git(canonical, "rev-parse", "HEAD")
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "unrelated-resource").write_text("do not expose")
    (source / "resources").symlink_to(foreign, target_is_directory=True)
    commit(source)
    result = CliRunner().invoke(main, ["agent", verb, "shared", "-g"])
    assert result.exit_code != 0 and "symlink" in result.output
    assert git(canonical, "rev-parse", "HEAD") == before and not (canonical / "resources").exists()


@pytest.mark.parametrize("shape", ["clone", "worktree", "detached-worktree", "copied-gitfile", "missing", "dirty", "shared-branch", "central-alias", "other-alias", "core-worktree"])
def test_private_agent_reset_owns_only_selected_checkout(tmp_path, sandbox, monkeypatch, shape):
    source = repo(tmp_path, {"AGENTS.md": "Role"})
    invoke("agent", "add", str(source), "--slug", "shared")
    config(sandbox, True)
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    invoke("agent", "install", "shared", "-p", "--harnesses", "pi")
    central = sandbox / ".agent-toolkit/agents/shared"
    private = (project / ".pi/agents/shared").resolve()
    other = None
    if shape in ("central-alias", "other-alias"):
        shutil.rmtree(private)
        if shape == "central-alias":
            private.symlink_to(central, target_is_directory=True)
        else:
            other = tmp_path / "other-checkout"
            git(source, "clone", str(source), str(other))
            (other / "other-only").write_text("unrelated checkout work")
            commit(other)
            private.symlink_to(other, target_is_directory=True)
    elif shape in ("worktree", "detached-worktree", "copied-gitfile", "shared-branch"):
        shutil.rmtree(private)
        if shape == "detached-worktree":
            git(central, "worktree", "add", "--detach", str(private))
        elif shape == "shared-branch":
            git(central, "worktree", "add", "--force", str(private), "main")
        elif shape == "worktree":
            git(central, "worktree", "add", "-b", "private", str(private))
        else:
            original = central.with_name("original")
            central.rename(original)
            git(original, "worktree", "add", "-b", "central", str(central))
            shutil.copytree(central, private)
    (central / "central-only").write_text("central commit must survive")
    (central / "AGENTS.md").write_text("central role must survive")
    commit(central)
    if shape == "missing":
        shutil.rmtree(private)
    elif shape not in ("copied-gitfile", "central-alias", "other-alias"):
        (private / "private-only").write_text("discard this explicit private commit")
        commit(private)
        if shape == "dirty":
            (private / "AGENTS.md").write_text("unique uncommitted private role")
    if shape == "core-worktree":
        git(private, "checkout", "--detach")
        git(private, "config", "core.worktree", str(central))
    config(sandbox, False)
    before = git(central, "rev-parse", "HEAD"), git(central, "status", "--porcelain"), (central / "central-only").read_bytes(), index_bytes(central)
    other_before = (git(other, "rev-parse", "HEAD"), index_bytes(other)) if other else None
    result = CliRunner().invoke(main, ["agent", "reset", "shared", "-p", *(["--force"] if shape == "core-worktree" else [])])
    if shape == "copied-gitfile":
        assert result.exit_code != 0 and "worktree" in result.output.lower()
    elif shape in ("central-alias", "other-alias", "core-worktree"):
        assert result.exit_code != 0, result.output
        if other:
            assert other_before == (git(other, "rev-parse", "HEAD"), index_bytes(other))
            assert (other / "other-only").read_text() == "unrelated checkout work"
    elif shape == "shared-branch":
        assert result.exit_code != 0 and "worktree" in result.output.lower()
        assert (private / "private-only").exists()
    elif shape == "missing":
        assert result.exit_code != 0 and not private.exists()
    elif shape == "dirty":
        assert result.exit_code != 0 and "dirty" in result.output
        assert (private / "AGENTS.md").read_text() == "unique uncommitted private role"
        assert (private / "private-only").exists()
    else:
        assert result.exit_code == 0, result.output
        assert git(private, "rev-parse", "HEAD") == git(source, "rev-parse", "HEAD")
        assert not (private / "private-only").exists()
        assert git(private, "status", "--porcelain") == ""
    assert before == (git(central, "rev-parse", "HEAD"), git(central, "status", "--porcelain"), (central / "central-only").read_bytes(), index_bytes(central))


@pytest.mark.parametrize("kind,filename,destination,target", [
    ("skill", "SKILL.md", ".claude/skills/shared", "claude-code"),
    ("agent", "AGENTS.md", ".pi/agents/shared", "pi"),
    ("command", "COMMAND.md", ".pi/prompts/shared.md", "pi"),
])
def test_failed_first_private_install_removes_only_owned_backing_and_allows_retry(tmp_path, sandbox, monkeypatch, kind, filename, destination, target):
    source = repo(tmp_path, {filename: "---\nname: shared\ndescription: Fixture\n---\nRole"})
    invoke(kind, "add", str(source), "--slug", "shared")
    config(sandbox, True)
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    slot = project / destination
    slot.parent.mkdir(parents=True)
    slot.write_text("foreign: preserve exactly")
    paths = importlib.import_module(f"agent_toolkit_cli.{kind}_paths")
    private = paths.project_store_root(project) / "shared"
    flag = "--agents" if kind == "skill" else "--harnesses"
    args = [kind, "install", "shared", "-p", flag, target]
    result = CliRunner().invoke(main, args)
    assert result.exit_code != 0
    assert slot.read_bytes() == b"foreign: preserve exactly"
    assert not private.exists() and not private.is_symlink()
    assert not (project / f"{kind}s-lock.json").exists()
    slot.unlink()  # remove only this foreign fixture, not the backing
    invoke(*args)
    assert private.exists()
    assert slot.exists()
    (private / "unique-dirty-memory").write_text("preserve on future failed installs")
    config(sandbox, False)
    invoke(kind, "uninstall", "shared", "-p", flag, target)
    slot.write_text("second foreign slot")
    result = CliRunner().invoke(main, args)
    assert result.exit_code != 0 and slot.read_text() == "second foreign slot"
    assert (private / "unique-dirty-memory").read_text() == "preserve on future failed installs"
    assert "shared" in json.loads((project / f"{kind}s-lock.json").read_text())["skills"]
    slot.unlink()
    invoke(*args)
    assert (private / "unique-dirty-memory").read_text() == "preserve on future failed installs"


@pytest.mark.parametrize("kind,filename", [("skill", "SKILL.md"), ("agent", "shared.md"), ("command", "COMMAND.md")])
def test_partial_first_install_cleans_new_slots_and_backing_not_foreign_parent(tmp_path, sandbox, monkeypatch, kind, filename):
    source = repo(tmp_path, {filename: "---\nname: shared\ndescription: Test\n---\nRole"})
    invoke(kind, "add", str(source), "--slug", "shared")
    config(sandbox, True)
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    blocked = project / ".claude"
    blocked.write_text("foreign parent must survive")
    flag = "--agents" if kind == "skill" else "--harnesses"
    targets = "standard,claude-code" if kind == "skill" else "pi,standard"
    args = [kind, "install", "shared", "-p", flag, targets]
    paths = importlib.import_module(f"agent_toolkit_cli.{kind}_paths")
    private = paths.project_store_root(project) / "shared"
    result = CliRunner().invoke(main, args)
    assert result.exit_code != 0
    files = [p for p in project.rglob("*") if p.is_file() or p.is_symlink()]
    assert files == [blocked] and blocked.read_text() == "foreign parent must survive"
    assert not private.exists() and not private.is_symlink()
    blocked.unlink()
    invoke(*args)
    assert private.exists() and (project / f"{kind}s-lock.json").exists()


@pytest.mark.parametrize("kind,filename", [("skill", "SKILL.md"), ("agent", "AGENTS.md"), ("command", "COMMAND.md")])
def test_failed_initial_materializer_removes_its_partial_tree_and_retries(tmp_path, sandbox, monkeypatch, kind, filename):
    source = repo(tmp_path, {filename: "---\nname: shared\ndescription: Test\n---\nRole"})
    invoke(kind, "add", str(source), "--slug", "shared")
    config(sandbox, True)
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    paths = importlib.import_module(f"agent_toolkit_cli.{kind}_paths")
    private = paths.project_store_root(project) / "shared"
    flag = "--agents" if kind == "skill" else "--harnesses"
    args = [kind, "install", "shared", "-p", flag, "pi"]
    def fail_materializer(_source, destination, **kwargs):
        destination.mkdir(parents=True, exist_ok=True)  # emulate a partial native clone/copy
        (destination / "partial").write_text("new operation-owned data")
        raise InstallError("injected materialization failure")
    with monkeypatch.context() as patch:
        if kind == "skill":
            from agent_toolkit_cli import skill_git
            patch.setattr(skill_git, "clone_pinned_or_branch", fail_materializer)
        else:
            patch.setattr(shutil, "copytree", fail_materializer)
        result = CliRunner().invoke(main, args)
        assert result.exit_code != 0 and "injected materialization failure" in result.output
    assert not private.exists() and not (project / f"{kind}s-lock.json").exists()
    assert (sandbox / f".agent-toolkit/{kind}s/shared" / filename).exists()
    invoke(*args)
    assert private.exists()


def test_command_cleanup_preserves_replaced_foreign_backing(tmp_path, sandbox, monkeypatch):
    source = repo(tmp_path, {"COMMAND.md": "Prompt"})
    invoke("command", "add", str(source), "--slug", "shared")
    config(sandbox, True)
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    from agent_toolkit_cli import command_install
    from agent_toolkit_cli.command_paths import project_store_root
    private = project_store_root(project) / "shared"
    foreign = tmp_path / "foreign-tree"
    foreign.mkdir()
    (foreign / "unique").write_text("foreign replacement must survive")
    saved = tmp_path / "operation-owned-before-replacement"
    original = command_install.get_adapter
    class ReplacingFailure:
        def __init__(self, adapter):
            self.adapter = adapter
        def __getattr__(self, name):
            return getattr(self.adapter, name)
        def install(self, *args, **kwargs):
            private.rename(saved)
            foreign.rename(private)
            raise InstallError("injected later-target failure")
    monkeypatch.setattr(command_install, "get_adapter", lambda name: ReplacingFailure(original(name)) if name == "standard" else original(name))
    result = CliRunner().invoke(main, ["command", "install", "shared", "-p", "--harnesses", "pi,standard"])
    assert result.exit_code != 0
    assert (private / "unique").read_text() == "foreign replacement must survive"
    assert "preserved" in result.output
    assert not (project / ".pi/prompts/shared.md").exists()
    assert not (project / "commands-lock.json").exists()


def test_failed_collection_install_cleans_only_new_parent_then_retries(tmp_path, sandbox, monkeypatch):
    source = repo(tmp_path, {"one/SKILL.md": "---\nname: one\ndescription: One\n---\nOne",
                             "two/SKILL.md": "---\nname: two\ndescription: Two\n---\nTwo"})
    invoke("skill", "add", f"file://{source}")
    config(sandbox, True)
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    blocked = project / ".claude"
    blocked.write_text("foreign parent")
    from agent_toolkit_cli.skill_paths import project_store_root, canonical_skill_dir
    store = project_store_root(project)
    result = CliRunner().invoke(main, ["skill", "install", "one", "-p", "--agents", "standard,claude-code"])
    assert result.exit_code != 0 and blocked.read_text() == "foreign parent"
    assert not list(store.rglob(".git"))
    assert not (store / "one").is_symlink() and not (store / "two").is_symlink()
    assert not (project / "skills-lock.json").exists()
    blocked.unlink()
    invoke("skill", "install", "one", "-p", "--agents", "pi")
    one = canonical_skill_dir("one", scope="project", project=project)
    (one / "unique-memory").write_text("existing parent must survive")
    before = (project / "skills-lock.json").read_bytes()
    config(sandbox, False)
    foreign = project / ".claude/skills/two"
    foreign.parent.mkdir(parents=True)
    foreign.write_text("foreign slot")
    result = CliRunner().invoke(main, ["skill", "install", "two", "-p", "--agents", "claude-code"])
    assert result.exit_code != 0 and foreign.read_text() == "foreign slot"
    assert (project / "skills-lock.json").read_bytes() == before
    assert (one / "unique-memory").read_text() == "existing parent must survive"


@pytest.mark.asyncio
async def test_unlisted_private_tui_detach_status_reregister_and_disabled_reinstall(tmp_path, sandbox, monkeypatch):
    source = repo(tmp_path, {"SKILL.md": "---\nname: shared\ndescription: Fixture\n---\nRole"})
    invoke("skill", "add", str(source), "--slug", "shared")
    config(sandbox, True)
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    invoke("skill", "install", "shared", "-p", "--agents", "pi")
    slot = project / ".agents/skills/shared"
    private = slot.resolve()
    (private / "unique-memory").write_text("keep")
    config(sandbox, False)
    library_lock = sandbox / ".agent-toolkit/skills-lock.json"
    library_lock.write_text('{"version":1,"skills":{}}')
    project_lock = project / "skills-lock.json"
    before = project_lock.read_bytes()
    from agent_toolkit_tui.app import TUIApp
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#skill-grid")
        grid.restore_pending({("project", "pi", "shared"): "unlink"})
        result = app._apply_skill_pending()
        assert result.failed == 0, result.errors
        await pilot.pause()
        assert grid.pending_entries() == {}
        assert not slot.exists() and not slot.is_symlink()
        assert project_lock.read_bytes() == before
        row = next(row for row in grid._rows if row.slug == "shared")
        assert row.state == "unlisted"
        from agent_toolkit_tui.skill_state import _cell_for
        assert not _cell_for("shared", "pi", scope="project", home=None, project=project).linked
        assert all(not cell.linked for (agent, scope), cell in row.cells.items()
                   if scope == "project" and not cell.skipped)
    assert json.loads(invoke("skill", "list", "-p", "--agent", "pi", "--json").output) == []
    invoke("skill", "add", str(source), "--slug", "shared")
    invoke("skill", "install", "shared", "-p", "--agents", "pi")
    assert slot.resolve() == private and (private / "unique-memory").read_text() == "keep"
