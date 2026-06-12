"""#360: agent row universe = union(library lock, scope lock).

Pre-#362 the project lock is never written by the CLI, so project-lock cases
are exercised via locks written programmatically with agent_lock.write_lock.
"""
from __future__ import annotations

from pathlib import Path

from agent_toolkit_cli.agent_lock import LockEntry, LockFile, write_lock
from agent_toolkit_cli.agent_paths import library_lock_path, lock_file_path
from agent_toolkit_tui.agent_state import build_agent_rows


def _entry(source: str) -> LockEntry:
    return LockEntry(source=source, source_type="github", ref="main")


def _write_library(slugs: dict) -> None:
    path = library_lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    write_lock(path, LockFile(version=1, skills=slugs))


def test_library_only_slug_is_dim_available_at_project(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    _write_library({"reviewer": _entry("o/reviewer")})

    rows = build_agent_rows(scope="project", home=tmp_path, project=project)
    assert [r.slug for r in rows] == ["reviewer"]
    assert rows[0].state == "library"


def test_project_only_slug_is_unlisted(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    _write_library({})
    proj_path = lock_file_path(scope="project", project=project)
    write_lock(proj_path, LockFile(version=1, skills={"reviewer": _entry("o/reviewer")}))

    rows = build_agent_rows(scope="project", home=tmp_path, project=project)
    assert [r.slug for r in rows] == ["reviewer"]
    assert rows[0].state == "unlisted"
    assert rows[0].source == "o/reviewer"


def test_both_locks_slug_is_installed(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    _write_library({"reviewer": _entry("o/reviewer")})
    proj_path = lock_file_path(scope="project", project=project)
    write_lock(proj_path, LockFile(version=1, skills={"reviewer": _entry("o/reviewer")}))

    rows = build_agent_rows(scope="project", home=tmp_path, project=project)
    assert rows[0].state == "installed"


def test_global_scope_all_installed(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _write_library({"reviewer": _entry("o/reviewer")})
    rows = build_agent_rows(scope="global", home=tmp_path, project=None)
    assert [r.slug for r in rows] == ["reviewer"]
    assert rows[0].state == "installed"


def test_no_locks_no_rows(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    rows = build_agent_rows(scope="project", home=tmp_path, project=project)
    assert rows == []


def test_project_scope_probes_global_cells(tmp_path: Path, monkeypatch):
    """#374: at project scope every row also carries (harness, 'global')
    cells so the grid can render the globally-installed indicator."""
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    _write_library({"reviewer": _entry("o/reviewer")})
    # Simulate a global install in the standard .claude/agents slot.
    slot = tmp_path / ".claude" / "agents"
    slot.mkdir(parents=True)
    (slot / "reviewer.md").write_text("# reviewer\n")

    rows = build_agent_rows(scope="project", home=tmp_path, project=project)
    cell = rows[0].cells.get(("standard", "global"))
    assert cell is not None and cell.linked


def test_project_scope_global_probe_runs_for_unlisted_rows(tmp_path: Path, monkeypatch):
    """#374: the probe is a lock-independent filesystem check — unlisted
    (project-lock-only) rows get global cells too, matching skill_state."""
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    _write_library({})
    proj_path = lock_file_path(scope="project", project=project)
    write_lock(proj_path, LockFile(version=1, skills={"reviewer": _entry("o/reviewer")}))
    slot = tmp_path / ".claude" / "agents"
    slot.mkdir(parents=True)
    (slot / "reviewer.md").write_text("# reviewer\n")

    rows = build_agent_rows(scope="project", home=tmp_path, project=project)
    assert rows[0].state == "unlisted"
    cell = rows[0].cells.get(("standard", "global"))
    assert cell is not None and cell.linked


def test_project_scope_home_none_skips_global_probe(tmp_path: Path, monkeypatch):
    """#374: callers that pass home=None don't care about the indicator —
    no (harness, 'global') cells, mirroring skill_state's escape hatch."""
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    _write_library({"reviewer": _entry("o/reviewer")})

    rows = build_agent_rows(scope="project", home=None, project=project)
    assert all(scope != "global" for (_, scope) in rows[0].cells)
