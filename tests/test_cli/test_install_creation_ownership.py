"""Only successful native creation, not a missing-slot snapshot, owns cleanup."""
import importlib
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli._install_core import InstallError
from agent_toolkit_cli.cli import main
from tests.test_cli.test_reground import sandbox, repo, invoke
from tests.test_cli.test_reground_review import config


CASES = [
    ("agent", "shared.md", "pi"),
    ("agent", "AGENTS.md", "pi"),
    ("agent", "shared.md", "standard"),
    ("agent", "shared.md", "gemini-cli"),
    ("agent", "shared.md", "aider-desk"),
    ("command", "COMMAND.md", "pi"),
    ("command", "COMMAND.md", "standard"),
    ("command", "COMMAND.md", "gemini-cli"),
]


@pytest.mark.parametrize("kind,filename,harness", CASES)
@pytest.mark.parametrize("existing", [False, True])
def test_real_adapter_refusal_never_claims_late_foreign_target(tmp_path, sandbox, monkeypatch, kind, filename, harness, existing):
    source = repo(tmp_path, {filename: "---\nname: shared\ndescription: Fixture\n---\nRole"})
    invoke(kind, "add", str(source), "--slug", "shared")
    config(sandbox, True)
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    paths = importlib.import_module(f"agent_toolkit_cli.{kind}_paths")
    engine = importlib.import_module(f"agent_toolkit_cli.{kind}_install")
    private = paths.project_store_root(project) / "shared"
    args = [kind, "install", "shared", "-p", "--harnesses", harness]
    lock = project / f"{kind}s-lock.json"
    if existing:
        invoke(*args)
        invoke(kind, "uninstall", "shared", "-p", "--harnesses", harness)
        (private / "unique-memory").write_text("existing dirty backing")
        config(sandbox, False)
    before = lock.read_bytes() if lock.exists() else None
    owner = engine.agent_adapters if kind == "agent" else engine
    original = owner.get_adapter
    arrived = []
    class ArrivingForeign:
        def __init__(self, adapter):
            self.adapter = adapter
        def __getattr__(self, name):
            return getattr(self.adapter, name)
        def install(self, *a, **kw):
            slot = self.adapter.destination("shared", scope="project", home=None, project=project)
            if filename == "AGENTS.md":
                slot = slot.with_suffix("")
            if not arrived:
                slot.parent.mkdir(parents=True, exist_ok=True)
                slot.write_text("foreign arrival: not created by installer")
                arrived.append((slot, slot.stat().st_ino))
            return self.adapter.install(*a, **kw)  # actual adapter owns the refusal
    monkeypatch.setattr(owner, "get_adapter", lambda name: ArrivingForeign(original(name)))
    result = CliRunner().invoke(main, args)
    assert result.exit_code != 0, result.output
    slot, inode = arrived[0]
    assert slot.read_text() == "foreign arrival: not created by installer"
    assert slot.stat().st_ino == inode
    assert (lock.read_bytes() if lock.exists() else None) == before
    if existing:
        assert (private / "unique-memory").read_text() == "existing dirty backing"
    else:
        assert not private.exists()
    slot.unlink()  # only the foreign fixture; no backing/metadata cleanup for retry
    invoke(*args)
    assert slot.exists()


@pytest.mark.parametrize("kind,filename,harness", [CASES[0], CASES[1], CASES[5], CASES[7]])
def test_cleanup_preserves_foreign_replacement_after_real_creation(tmp_path, sandbox, monkeypatch, kind, filename, harness):
    source = repo(tmp_path, {filename: "Role"})
    invoke(kind, "add", str(source), "--slug", "shared")
    config(sandbox, True)
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    engine = importlib.import_module(f"agent_toolkit_cli.{kind}_install")
    owner = engine.agent_adapters if kind == "agent" else engine
    original = owner.get_adapter
    foreign = tmp_path / "foreign-file"
    foreign.write_text("replacement must survive")
    inode = foreign.stat().st_ino
    slots = []
    class ReplacedAfterCreation:
        def __init__(self, adapter):
            self.adapter = adapter
        def __getattr__(self, name):
            return getattr(self.adapter, name)
        def install(self, *a, **kw):
            slot = self.adapter.install(*a, **kw)
            slot.unlink()
            foreign.rename(slot)
            slots.append(slot)
            raise InstallError("injected failure after replacement")
    monkeypatch.setattr(owner, "get_adapter", lambda name: ReplacedAfterCreation(original(name)))
    result = CliRunner().invoke(main, [kind, "install", "shared", "-p", "--harnesses", harness])
    assert result.exit_code != 0
    assert slots[0].read_text() == "replacement must survive"
    assert slots[0].stat().st_ino == inode
    assert "preserved" in result.output
    assert not (project / f"{kind}s-lock.json").exists()


@pytest.mark.parametrize("kind,harness,creation", [("agent", "pi", "file"), ("command", "pi", "symlink"), ("command", "standard", "symlink"), ("command", "gemini-cli", "file")])
def test_native_claim_refuses_arrival_after_adapter_guard(tmp_path, sandbox, monkeypatch, kind, harness, creation):
    filename = "shared.md" if kind == "agent" else "COMMAND.md"
    source = repo(tmp_path, {filename: "Role"})
    invoke(kind, "add", str(source), "--slug", "shared")
    config(sandbox, True)
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    engine = importlib.import_module(f"agent_toolkit_cli.{kind}_install")
    adapter = (engine.agent_adapters.get_adapter if kind == "agent" else engine.get_adapter)(harness)
    slot = adapter.destination("shared", scope="project", home=None, project=project)
    arrived = []
    original_open, original_link = Path.open, Path.symlink_to
    def arrive(path):
        path.write_text("foreign at native claim")
        arrived.append(path.stat().st_ino)
    def open_file(self, mode="r", *a, **kw):
        if self == slot and mode == "xb" and not arrived:
            arrive(self)
        return original_open(self, mode, *a, **kw)
    def link(self, *a, **kw):
        if self == slot and not arrived:
            arrive(self)
        return original_link(self, *a, **kw)
    monkeypatch.setattr(Path, "open" if creation == "file" else "symlink_to", open_file if creation == "file" else link)
    result = CliRunner().invoke(main, [kind, "install", "shared", "-p", "--harnesses", harness])
    assert result.exit_code != 0
    assert slot.read_text() == "foreign at native claim" and slot.stat().st_ino == arrived[0]
    assert not (project / f"{kind}s-lock.json").exists()


@pytest.mark.parametrize("kind,harness,module", [("agent", "pi", "agent_adapters.symlink"), ("command", "gemini-cli", "command_adapters.gemini")])
def test_partial_real_file_creation_still_cleans_before_sidecar(tmp_path, sandbox, monkeypatch, kind, harness, module):
    filename = "shared.md" if kind == "agent" else "COMMAND.md"
    source = repo(tmp_path, {filename: "Role"})
    invoke(kind, "add", str(source), "--slug", "shared")
    config(sandbox, True)
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    owner = importlib.import_module("agent_toolkit_cli." + module)
    original = owner.write_projection
    def fail_after_write(path, *a, **kw):
        original(path, *a, **kw)
        raise InstallError("injected after real file creation, before sidecar")
    monkeypatch.setattr(owner, "write_projection", fail_after_write)
    result = CliRunner().invoke(main, [kind, "install", "shared", "-p", "--harnesses", harness])
    assert result.exit_code != 0 and "injected after real file creation" in result.output
    assert not [p for p in project.rglob("*") if p.is_file() or p.is_symlink()]
    paths = importlib.import_module(f"agent_toolkit_cli.{kind}_paths")
    assert not (paths.project_store_root(project) / "shared").exists()


@pytest.mark.parametrize("kind,harness,slot_name,marker_name", [
    ("agent", "pi", ".pi/agents/shared.md", ".pi/agents/.shared.md.attk"),
    ("command", "standard", ".claude/commands/shared.md", ".claude/commands/shared.md.attk"),
])
def test_late_foreign_marker_is_not_overwritten_or_cleanup_owned(tmp_path, sandbox, monkeypatch, kind, harness, slot_name, marker_name):
    source = repo(tmp_path, {"shared.md" if kind == "agent" else "COMMAND.md": "Role"})
    invoke(kind, "add", str(source), "--slug", "shared")
    config(sandbox, True)
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    slot, marker = project / slot_name, project / marker_name
    original = Path.open
    arrived = []
    def late(self, mode="r", *a, **kw):
        if self == marker and mode in ("w", "wb", "x", "xb") and not arrived:
            arrived.append(True)
            self.write_text("foreign marker")
            arrived.append(self.stat().st_ino)
        return original(self, mode, *a, **kw)
    monkeypatch.setattr(Path, "open", late)
    result = CliRunner().invoke(main, [kind, "install", "shared", "-p", "--harnesses", harness])
    assert result.exit_code != 0
    assert marker.read_text() == "foreign marker" and marker.stat().st_ino == arrived[1]
    assert not slot.exists() and not slot.is_symlink()
    assert not (project / f"{kind}s-lock.json").exists()


def test_collection_does_not_claim_same_target_link_arriving_before_create(tmp_path, sandbox, monkeypatch):
    source = repo(tmp_path, {"one/SKILL.md": "---\nname: one\ndescription: One\n---\nOne",
                             "two/SKILL.md": "---\nname: two\ndescription: Two\n---\nTwo"})
    invoke("skill", "add", f"file://{source}")
    config(sandbox, True)
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    slot = project / ".claude/skills/one"
    original = Path.symlink_to
    arrived = []
    def late(self, target, *a, **kw):
        if self == slot and not arrived:
            original(self, target, *a, **kw)
            arrived.append((self.lstat().st_ino, self.readlink()))
        return original(self, target, *a, **kw)
    monkeypatch.setattr(Path, "symlink_to", late)
    result = CliRunner().invoke(main, ["skill", "install", "one", "-p", "--agents", "claude-code"])
    assert result.exit_code != 0
    assert slot.is_symlink() and (slot.lstat().st_ino, slot.readlink()) == arrived[0]
    assert not (project / "skills-lock.json").exists()


def test_collection_rollback_preserves_replaced_same_target_link(tmp_path):
    from agent_toolkit_cli.skill_collection_transaction import Journal
    target = tmp_path / "target"
    target.mkdir()
    slot, foreign = tmp_path / "slot", tmp_path / "foreign"
    foreign.symlink_to(target)
    inode = foreign.lstat().st_ino
    journal = Journal()
    journal.link(slot, None, target)
    slot.unlink()
    foreign.rename(slot)
    errors = journal.rollback()
    assert errors and slot.is_symlink() and slot.lstat().st_ino == inode
    assert slot.readlink() == target


@pytest.mark.parametrize("harness,relative", [("standard", ".agents/skills/shared"), ("claude-code", ".claude/skills/shared")])
def test_skill_exclusive_creation_preserves_late_foreign_slot(tmp_path, sandbox, monkeypatch, harness, relative):
    source = repo(tmp_path, {"SKILL.md": "---\nname: shared\ndescription: Fixture\n---\nRole"})
    invoke("skill", "add", str(source), "--slug", "shared")
    config(sandbox, True)
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    slot = project / relative
    original = Path.symlink_to
    arrived = []
    def late(self, *a, **kw):
        if self == slot and not arrived:
            self.write_text("foreign skill arrival")
            arrived.append(self.stat().st_ino)
        return original(self, *a, **kw)
    monkeypatch.setattr(Path, "symlink_to", late)
    result = CliRunner().invoke(main, ["skill", "install", "shared", "-p", "--agents", harness])
    assert result.exit_code != 0
    assert slot.read_text() == "foreign skill arrival" and slot.stat().st_ino == arrived[0]
    assert not (project / "skills-lock.json").exists()
    from agent_toolkit_cli.skill_paths import project_store_root
    assert not (project_store_root(project) / "shared").exists()
