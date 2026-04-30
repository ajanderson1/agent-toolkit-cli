"""Tests for the conventions-prose-leak check inside `agent-toolkit check`."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_toolkit.commands.check import _drift_for_conventions_prose


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)


def test_no_drift_when_prose_uses_neutral_path(tmp_path: Path) -> None:
    _write(tmp_path / "CONVENTIONS.md", "imports `@~/.conventions/CONVENTIONS.md`\n")
    _write(tmp_path / "AGENTS.md", "Skills reference `~/.conventions/conventions/foo.md`\n")
    assert _drift_for_conventions_prose(tmp_path) is None


def test_drift_when_prose_uses_claude_specific_path(tmp_path: Path) -> None:
    _write(tmp_path / "CONVENTIONS.md", "imports `@~/.claude/CONVENTIONS.md`\n")
    drift = _drift_for_conventions_prose(tmp_path)
    assert drift is not None
    assert "CONVENTIONS.md" in drift
    assert "~/.claude/CONVENTIONS.md" in drift


def test_drift_when_prose_uses_claude_conventions_dir(tmp_path: Path) -> None:
    _write(tmp_path / "skills" / "foo" / "SKILL.md", "See `~/.claude/conventions/git.md`.\n")
    drift = _drift_for_conventions_prose(tmp_path)
    assert drift is not None
    assert "~/.claude/conventions/" in drift


def test_archived_plans_are_allowed_to_use_old_paths(tmp_path: Path) -> None:
    _write(
        tmp_path / "docs" / "plans" / "2026-04-25-old.md",
        "Refers to `~/.claude/CONVENTIONS.md` (historical).\n",
    )
    _write(
        tmp_path / "docs" / "superpowers" / "plans" / "2026-04-25-old.md",
        "Refers to `~/.claude/conventions/git.md` (historical).\n",
    )
    assert _drift_for_conventions_prose(tmp_path) is None


def test_drift_excludes_files_inside_dot_git(tmp_path: Path) -> None:
    _write(tmp_path / ".git" / "ignored.md", "`~/.claude/CONVENTIONS.md`\n")
    assert _drift_for_conventions_prose(tmp_path) is None


def test_design_specs_allowed_to_use_old_paths(tmp_path: Path) -> None:
    _write(
        tmp_path / "docs" / "superpowers" / "specs" / "2026-04-30-design.md",
        "We replace `~/.claude/CONVENTIONS.md` with the neutral path.\n",
    )
    assert _drift_for_conventions_prose(tmp_path) is None


def test_check_module_itself_allowed_to_use_old_paths(tmp_path: Path) -> None:
    _write(
        tmp_path / "src" / "agent_toolkit" / "commands" / "check.py",
        '_LEAK_PATTERN = re.compile(r"~/.claude/(CONVENTIONS|conventions/)")\n',
    )
    assert _drift_for_conventions_prose(tmp_path) is None


def test_cli_docs_allowed_to_use_old_paths_in_architecture_table(tmp_path: Path) -> None:
    _write(
        tmp_path / "docs" / "agent-toolkit" / "cli.md",
        "Claude:    ~/.claude/CONVENTIONS.md   -> ~/.conventions/CONVENTIONS.md\n",
    )
    assert _drift_for_conventions_prose(tmp_path) is None


def test_readme_allowed_to_use_old_paths_in_diagram(tmp_path: Path) -> None:
    _write(
        tmp_path / "README.md",
        "Layer 3: ~/.claude/CONVENTIONS.md → ~/.conventions/CONVENTIONS.md\n",
    )
    assert _drift_for_conventions_prose(tmp_path) is None


def test_sibling_worktree_content_is_skipped(tmp_path: Path) -> None:
    # `.worktrees/<branch>/...` holds sibling git worktrees that aren't part of
    # the current branch. Their content is owned by other branches and must not
    # block this branch's drift check.
    _write(
        tmp_path / ".worktrees" / "other-feature" / "AGENTS.md",
        "Skills reference these via `~/.claude/conventions/<topic>.md`.\n",
    )
    assert _drift_for_conventions_prose(tmp_path) is None
