"""Tests for instruction_state.py — TUI data model for the instruction kind."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_toolkit_tui.instruction_state import (
    INTERACTIVE_HARNESSES,
    InstructionCell,
    InstructionRow,
    build_instruction_rows,
)


def test_interactive_harnesses_constant():
    """INTERACTIVE_HARNESSES must be exactly ('claude-code', 'gemini-cli')."""
    assert INTERACTIVE_HARNESSES == ("claude-code", "gemini-cli")


def test_instruction_cell_dataclass():
    """InstructionCell must have applicable and linked fields."""
    cell = InstructionCell(applicable=True, linked=True)
    assert cell.applicable is True
    assert cell.linked is True

    cell2 = InstructionCell(applicable=False, linked=False)
    assert cell2.applicable is False
    assert cell2.linked is False


def test_instruction_row_dataclass():
    """InstructionRow must have slug, scope, general_linked, and cells."""
    row = InstructionRow(
        slug="AGENTS.md",
        scope="global",
        general_linked=True,
        cells={"claude-code": InstructionCell(applicable=True, linked=True)},
    )
    assert row.slug == "AGENTS.md"
    assert row.scope == "global"
    assert row.general_linked is True
    assert "claude-code" in row.cells


def _write_lock(path: Path, harnesses: list[str], scope: str = "project") -> None:
    """Write a minimal instructions lock at the given path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "version": 1,
        "instructions": {
            "AGENTS.md": {
                "scope": scope,
                "source": "AGENTS.md",
                "harnesses": harnesses,
            }
        },
    }
    path.write_text(json.dumps(data))


def test_build_instruction_rows_project_claude_linked(tmp_path):
    """A project with AGENTS.md + a symlinked CLAUDE.md → claude-code linked, gemini-cli not."""
    project = tmp_path / "proj"
    project.mkdir()

    # Write canonical AGENTS.md
    canonical = project / "AGENTS.md"
    canonical.write_text("# AGENTS\n")

    # Write lock with claude-code harness
    lock_path = project / "instructions-lock.json"
    _write_lock(lock_path, harnesses=["claude-code"], scope="project")

    # Create the claude-code pointer symlink (CLAUDE.md → AGENTS.md)
    claude_md = project / "CLAUDE.md"
    claude_md.symlink_to(canonical)

    rows = build_instruction_rows(home=None, project=project)

    assert len(rows) == 1
    row = rows[0]
    assert row.scope == "project"
    assert row.slug == "AGENTS.md"
    assert row.general_linked is True  # canonical AGENTS.md exists

    # claude-code: linked (symlink points to canonical)
    assert "claude-code" in row.cells
    assert row.cells["claude-code"].applicable is True
    assert row.cells["claude-code"].linked is True

    # gemini-cli: applicable but NOT linked (no GEMINI.md symlink)
    assert "gemini-cli" in row.cells
    assert row.cells["gemini-cli"].applicable is True
    assert row.cells["gemini-cli"].linked is False


def test_build_instruction_rows_no_lock(tmp_path):
    """Missing lock → empty rows (no crash)."""
    rows = build_instruction_rows(home=None, project=tmp_path)
    assert rows == []


def test_build_instruction_rows_general_linked_false(tmp_path):
    """When canonical AGENTS.md is absent, general_linked is False."""
    project = tmp_path / "proj"
    project.mkdir()
    lock_path = project / "instructions-lock.json"
    _write_lock(lock_path, harnesses=["claude-code"], scope="project")
    # No AGENTS.md created

    rows = build_instruction_rows(home=None, project=project)
    assert len(rows) == 1
    assert rows[0].general_linked is False


def test_build_instruction_rows_global_scope(tmp_path):
    """Global scope row is built when global lock exists."""
    home = tmp_path / "home"
    lib = home / ".agent-toolkit"
    lib.mkdir(parents=True)
    canonical = lib / "AGENTS.md"
    canonical.write_text("# global canon\n")

    lock_path = lib / "instructions-lock.json"
    data = {
        "version": 1,
        "instructions": {
            "AGENTS.md": {
                "scope": "global",
                "source": "AGENTS.md",
                "harnesses": ["claude-code"],
            }
        },
    }
    lock_path.write_text(json.dumps(data))

    # Create global claude-code pointer: ~/.claude/CLAUDE.md → canonical
    claude_dir = home / ".claude"
    claude_dir.mkdir()
    claude_md = claude_dir / "CLAUDE.md"
    claude_md.symlink_to(canonical)

    rows = build_instruction_rows(home=home, project=None)

    assert len(rows) == 1
    row = rows[0]
    assert row.scope == "global"
    assert row.general_linked is True
    assert row.cells["claude-code"].linked is True


def test_not_applicable_probe_for_project_only_harness(tmp_path):
    """Direct unit test: a project-only harness raises ValueError on global scope.

    The replit harness has no global slot. Verify the guard by calling _pointer_path
    directly so we confirm it raises ValueError (not applicable) at global scope.
    """
    from agent_toolkit_cli.instructions_adapters.symlink import _pointer_path

    with pytest.raises(ValueError):
        _pointer_path("replit", "global", None, None)


def test_build_instruction_rows_both_scopes(tmp_path):
    """When both global and project locks exist, two rows are returned."""
    home = tmp_path / "home"
    lib = home / ".agent-toolkit"
    lib.mkdir(parents=True)
    (lib / "AGENTS.md").write_text("# global\n")
    data_global = {
        "version": 1,
        "instructions": {
            "AGENTS.md": {
                "scope": "global",
                "source": "AGENTS.md",
                "harnesses": [],
            }
        },
    }
    (lib / "instructions-lock.json").write_text(json.dumps(data_global))

    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# project\n")
    data_project = {
        "version": 1,
        "instructions": {
            "AGENTS.md": {
                "scope": "project",
                "source": "AGENTS.md",
                "harnesses": [],
            }
        },
    }
    (project / "instructions-lock.json").write_text(json.dumps(data_project))

    rows = build_instruction_rows(home=home, project=project)
    scopes = {r.scope for r in rows}
    assert "global" in scopes
    assert "project" in scopes
    assert len(rows) == 2
