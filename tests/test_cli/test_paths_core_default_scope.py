from __future__ import annotations

from pathlib import Path

from agent_toolkit_cli._paths_core import default_scope


def test_default_scope_project_when_a_lock_present(tmp_path: Path):
    (tmp_path / "skills-lock.json").write_text("{}")
    assert default_scope(tmp_path) == "project"


def test_default_scope_project_for_any_kind_lock(tmp_path: Path):
    (tmp_path / "agents-lock.json").write_text("{}")
    assert default_scope(tmp_path) == "project"
    (tmp_path / "pi-extensions-lock.json").write_text("{}")
    assert default_scope(tmp_path) == "project"


def test_default_scope_global_when_no_lock(tmp_path: Path):
    assert default_scope(tmp_path) == "global"
