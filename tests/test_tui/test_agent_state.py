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
