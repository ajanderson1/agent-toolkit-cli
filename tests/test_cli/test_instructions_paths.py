"""instructions_paths facade — paths + canonical AGENTS.md resolution."""
from __future__ import annotations

import pytest

from agent_toolkit_cli import instructions_paths


def test_library_root(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert instructions_paths.library_root() == tmp_path / ".agent-toolkit" / "instructions"


def test_library_lock_path(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert instructions_paths.library_lock_path() == tmp_path / ".agent-toolkit" / "instructions-lock.json"


def test_global_canonical_agents_md(monkeypatch, tmp_path):
    """The canonical global AGENTS.md lives at ~/.agent-toolkit/AGENTS.md."""
    monkeypatch.setenv("HOME", str(tmp_path))
    assert instructions_paths.global_canonical_agents_md() == tmp_path / ".agent-toolkit" / "AGENTS.md"


def test_project_canonical_agents_md(tmp_path):
    """Project canonical is `<project>/AGENTS.md` — sibling of the pointers."""
    project = tmp_path / "myproj"
    project.mkdir()
    assert instructions_paths.project_canonical_agents_md(project) == project / "AGENTS.md"


def test_project_lock_path(tmp_path):
    """Project lock at <project>/instructions-lock.json."""
    project = tmp_path / "myproj"
    project.mkdir()
    assert instructions_paths.project_lock_path(project) == project / "instructions-lock.json"


def test_lock_file_path_global_scope(monkeypatch, tmp_path):
    """`lock_file_path(scope, project_root)` dispatch matches skill_paths shape."""
    monkeypatch.setenv("HOME", str(tmp_path))
    assert instructions_paths.lock_file_path("global", None) == tmp_path / ".agent-toolkit" / "instructions-lock.json"


def test_lock_file_path_project_scope(tmp_path):
    project = tmp_path / "myproj"
    project.mkdir()
    assert instructions_paths.lock_file_path("project", project) == project / "instructions-lock.json"


def test_lock_file_path_project_scope_requires_root():
    """Project scope without a project_root is a programmer error."""
    with pytest.raises(ValueError, match="project scope requires project_root"):
        instructions_paths.lock_file_path("project", None)
