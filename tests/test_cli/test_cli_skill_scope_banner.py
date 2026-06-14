"""Tests for #413 — implicit-scope reminder banner + 4-tuple resolution."""
from __future__ import annotations

from pathlib import Path

from agent_toolkit_cli.commands.skill._common import scope_and_roots


def test_scope_and_roots_explicit_flags_are_not_implicit(tmp_path: Path):
    g = scope_and_roots(True, False, None, read_only=True)
    p = scope_and_roots(False, True, tmp_path, read_only=True)
    assert g == ("global", Path.home(), None, False)
    assert p == ("project", None, tmp_path, False)


def test_scope_and_roots_implicit_project_when_cwd_lock(tmp_path: Path):
    (tmp_path / "skills-lock.json").write_text("{}")
    scope, home, root, implicit = scope_and_roots(
        False, False, tmp_path, read_only=True,
    )
    assert (scope, home, root, implicit) == ("project", None, tmp_path, True)


def test_scope_and_roots_implicit_global_when_no_cwd_lock(tmp_path: Path):
    scope, home, root, implicit = scope_and_roots(
        False, False, tmp_path, read_only=True,
    )
    assert (scope, home, root, implicit) == ("global", Path.home(), None, True)
