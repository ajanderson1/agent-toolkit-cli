"""#360: agent doctor `unlisted` finding — project lock entry missing from the
library lock. Inert in the wild until #362 (CLI writes no project lock);
exercised here via programmatically-written locks."""
from __future__ import annotations

from pathlib import Path

from agent_toolkit_cli.agent_lock import LockEntry, LockFile, read_lock, write_lock
from agent_toolkit_cli.agent_paths import library_lock_path, lock_file_path
from agent_toolkit_cli.commands.agent.doctor_cmd import _diagnose


def _entry(source: str) -> LockEntry:
    return LockEntry(source=source, source_type="github", ref="main")


def test_unlisted_finding_fires(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    proj_lock = lock_file_path(scope="project", project=project)
    write_lock(proj_lock, LockFile(version=1, skills={"reviewer": _entry("o/reviewer")}))

    findings = _diagnose(slugs=None, scope="project", home=tmp_path, project=project)
    unlisted = [f for f in findings if f.finding_type == "unlisted"]
    assert len(unlisted) == 1
    assert unlisted[0].slug == "reviewer"
    assert unlisted[0].fix_action is not None


def test_unlisted_fix_action_writes_library_entry(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    proj_lock = lock_file_path(scope="project", project=project)
    write_lock(proj_lock, LockFile(version=1, skills={"reviewer": _entry("o/reviewer")}))

    findings = _diagnose(slugs=None, scope="project", home=tmp_path, project=project)
    fix = next(f for f in findings if f.finding_type == "unlisted").fix_action
    # The clone leg may fail for a fake source; the lock leg is the contract
    # under test — monkeypatch the clone to a no-op that creates the dir.
    # NOTE: `import agent_toolkit_cli.commands.agent.doctor_cmd as dc` yields
    # the Click Command (shadowed by the package __init__ re-export), so we
    # use importlib to get the actual module.
    import importlib
    dc = importlib.import_module("agent_toolkit_cli.commands.agent.doctor_cmd")

    def _fake_clone(url, dest, *, ref=None, env=None, depth=None):
        Path(dest).mkdir(parents=True, exist_ok=True)
        (Path(dest) / "reviewer.md").write_text("stub\n")

    monkeypatch.setattr(dc.skill_git, "clone", _fake_clone)
    fix.apply()
    fix.apply()  # idempotent: second apply is a no-op, not an error
    assert "reviewer" in read_lock(library_lock_path()).skills


def test_no_finding_when_library_tracks_slug(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    lib = library_lock_path()
    lib.parent.mkdir(parents=True, exist_ok=True)
    write_lock(lib, LockFile(version=1, skills={"reviewer": _entry("o/reviewer")}))
    proj_lock = lock_file_path(scope="project", project=project)
    write_lock(proj_lock, LockFile(version=1, skills={"reviewer": _entry("o/reviewer")}))

    findings = _diagnose(slugs=None, scope="project", home=tmp_path, project=project)
    assert not [f for f in findings if f.finding_type == "unlisted"]
