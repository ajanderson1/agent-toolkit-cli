"""Tests for instruction_state.py — data model for the TUI's instruction tab.

Covers:
1. empty lock + no canonical → no rows
2. empty lock + canonical exists → single AGENTS.md row (canonical_exists=True, cells unlinked)
3. lock with claude-code listed + pointer symlinked → linked=True
4. pointer is a real file → conflict=True, linked=False
5. canonical present → canonical_exists=True
6. scope mismatch path (replit at global) → _cell_for returns None
7. pointer is foreign symlink → conflict=True
"""
from __future__ import annotations

from pathlib import Path

from agent_toolkit_tui.instruction_state import (
    INTERACTIVE_HARNESSES,
    _cell_for,
    build_instruction_rows,
)


# ---------------------------------------------------------------------------
# _cell_for tests
# ---------------------------------------------------------------------------


def test_cell_for_missing_pointer(tmp_path: Path):
    """Pointer slot absent → linked=False, conflict=False."""
    home = tmp_path / "home"
    home.mkdir()
    cell = _cell_for(
        "AGENTS.md", "claude-code",
        scope="global", home=home, project=None,
    )
    assert cell is not None
    assert cell.linked is False
    assert cell.conflict is False


def test_cell_for_linked_pointer(tmp_path: Path):
    """Pointer slot is a symlink resolving to canonical → linked=True."""
    home = tmp_path / "home"
    home.mkdir()
    # Create canonical
    canonical = tmp_path / "AGENTS.md"
    canonical.write_text("# AGENTS\n")
    # Create the pointer: ~/.claude/CLAUDE.md → canonical
    claude_dir = home / ".claude"
    claude_dir.mkdir()
    pointer = claude_dir / "CLAUDE.md"
    pointer.symlink_to(canonical)

    cell = _cell_for(
        "AGENTS.md", "claude-code",
        scope="global", home=home, project=None,
        _canonical=canonical,
    )
    assert cell is not None
    assert cell.linked is True
    assert cell.conflict is False


def test_cell_for_real_file_conflict(tmp_path: Path):
    """Pointer slot is a real file → conflict=True, linked=False."""
    home = tmp_path / "home"
    home.mkdir()
    canonical = tmp_path / "AGENTS.md"
    canonical.write_text("# AGENTS\n")
    claude_dir = home / ".claude"
    claude_dir.mkdir()
    pointer = claude_dir / "CLAUDE.md"
    pointer.write_text("# real file\n")

    cell = _cell_for(
        "AGENTS.md", "claude-code",
        scope="global", home=home, project=None,
        _canonical=canonical,
    )
    assert cell is not None
    assert cell.conflict is True
    assert cell.linked is False


def test_cell_for_foreign_symlink_conflict(tmp_path: Path):
    """Pointer slot is a symlink to a different target → conflict=True."""
    home = tmp_path / "home"
    home.mkdir()
    canonical = tmp_path / "AGENTS.md"
    canonical.write_text("# AGENTS\n")
    elsewhere = tmp_path / "elsewhere.md"
    elsewhere.write_text("not ours\n")
    claude_dir = home / ".claude"
    claude_dir.mkdir()
    pointer = claude_dir / "CLAUDE.md"
    pointer.symlink_to(elsewhere)

    cell = _cell_for(
        "AGENTS.md", "claude-code",
        scope="global", home=home, project=None,
        _canonical=canonical,
    )
    assert cell is not None
    assert cell.conflict is True
    assert cell.linked is False


def test_cell_for_scope_mismatch_returns_none(tmp_path: Path):
    """replit is project-only; _cell_for at global scope → None."""
    home = tmp_path / "home"
    home.mkdir()
    cell = _cell_for(
        "AGENTS.md", "replit",
        scope="global", home=home, project=None,
    )
    assert cell is None


def test_cell_for_gemini_cli(tmp_path: Path):
    """gemini-cli pointer at global → ~/.gemini/GEMINI.md; absent → not linked."""
    home = tmp_path / "home"
    home.mkdir()
    cell = _cell_for(
        "AGENTS.md", "gemini-cli",
        scope="global", home=home, project=None,
    )
    assert cell is not None
    assert cell.linked is False
    assert cell.conflict is False


# ---------------------------------------------------------------------------
# build_instruction_rows tests
# ---------------------------------------------------------------------------


def test_build_instruction_rows_empty_lock_no_canonical(tmp_path: Path, monkeypatch):
    """empty lock + no canonical → no rows."""
    home = tmp_path / "home"
    home.mkdir()
    # No lock file, no AGENTS.md
    monkeypatch.setattr(
        "agent_toolkit_cli.instructions_paths.library_root",
        lambda: home / ".agent-toolkit" / "instructions",
    )
    rows = build_instruction_rows(scope="global", home=home, project=None)
    assert rows == []


def test_build_instruction_rows_empty_lock_canonical_exists(tmp_path: Path, monkeypatch):
    """empty lock + canonical AGENTS.md exists → single AGENTS.md row, canonical_exists=True,
    all cells unlinked (fresh user can install from grid)."""
    home = tmp_path / "home"
    home.mkdir()
    # Create canonical AGENTS.md where instructions_paths.global_canonical_agents_md() resolves
    agent_toolkit_dir = home / ".agent-toolkit"
    agent_toolkit_dir.mkdir(parents=True)
    canonical = agent_toolkit_dir / "AGENTS.md"
    canonical.write_text("# AGENTS\n")

    monkeypatch.setattr(
        "agent_toolkit_cli.instructions_paths.library_root",
        lambda: agent_toolkit_dir / "instructions",
    )

    rows = build_instruction_rows(scope="global", home=home, project=None)
    assert len(rows) == 1
    row = rows[0]
    assert row.slug == "AGENTS.md"
    assert row.canonical_exists is True
    # All cells should be unlinked (no pointers installed yet)
    for harness in INTERACTIVE_HARNESSES:
        cell = row.cells.get((harness, "global"))
        if cell is not None:
            assert cell.linked is False


def test_build_instruction_rows_with_lock_entry(tmp_path: Path, monkeypatch):
    """Lock has claude-code listed + pointer symlinked → linked=True for claude-code."""
    home = tmp_path / "home"
    home.mkdir()
    agent_toolkit_dir = home / ".agent-toolkit"
    agent_toolkit_dir.mkdir(parents=True)
    canonical = agent_toolkit_dir / "AGENTS.md"
    canonical.write_text("# AGENTS\n")

    # Create the claude-code pointer: ~/.claude/CLAUDE.md → canonical
    claude_dir = home / ".claude"
    claude_dir.mkdir()
    (claude_dir / "CLAUDE.md").symlink_to(canonical)

    # Write lock file
    lock_dir = agent_toolkit_dir / "instructions"
    lock_dir.mkdir(parents=True)
    lock_file = agent_toolkit_dir / "instructions-lock.json"
    lock_file.write_text(
        '{"version": 1, "instructions": {"AGENTS.md": {"scope": "global", "source": "AGENTS.md", "harnesses": ["claude-code"]}}}\n'
    )

    monkeypatch.setattr(
        "agent_toolkit_cli.instructions_paths.library_root",
        lambda: agent_toolkit_dir / "instructions",
    )

    rows = build_instruction_rows(scope="global", home=home, project=None)
    assert len(rows) == 1
    row = rows[0]
    assert row.slug == "AGENTS.md"
    assert row.canonical_exists is True
    cell = row.cells.get(("claude-code", "global"))
    assert cell is not None
    assert cell.linked is True
    assert cell.conflict is False


def test_build_instruction_rows_canonical_exists_true_when_present(tmp_path: Path, monkeypatch):
    """canonical_exists reflects actual file presence."""
    home = tmp_path / "home"
    home.mkdir()
    agent_toolkit_dir = home / ".agent-toolkit"
    agent_toolkit_dir.mkdir(parents=True)
    canonical = agent_toolkit_dir / "AGENTS.md"
    canonical.write_text("# AGENTS\n")

    monkeypatch.setattr(
        "agent_toolkit_cli.instructions_paths.library_root",
        lambda: agent_toolkit_dir / "instructions",
    )

    rows = build_instruction_rows(scope="global", home=home, project=None)
    assert rows[0].canonical_exists is True


def test_build_instruction_rows_project_scope(tmp_path: Path):
    """Project scope: canonical is <project>/AGENTS.md."""
    project = tmp_path / "proj"
    project.mkdir()
    # No canonical — no rows
    rows = build_instruction_rows(scope="project", home=Path.home(), project=project)
    assert rows == []


def test_build_instruction_rows_project_scope_with_canonical(tmp_path: Path):
    """Project scope with canonical AGENTS.md → single row."""
    project = tmp_path / "proj"
    project.mkdir()
    canonical = project / "AGENTS.md"
    canonical.write_text("# AGENTS\n")

    rows = build_instruction_rows(scope="project", home=Path.home(), project=project)
    assert len(rows) == 1
    assert rows[0].slug == "AGENTS.md"
    assert rows[0].canonical_exists is True


def test_build_instruction_rows_conflict_cell(tmp_path: Path, monkeypatch):
    """Real file in pointer slot → conflict=True for that harness."""
    home = tmp_path / "home"
    home.mkdir()
    agent_toolkit_dir = home / ".agent-toolkit"
    agent_toolkit_dir.mkdir(parents=True)
    canonical = agent_toolkit_dir / "AGENTS.md"
    canonical.write_text("# AGENTS\n")

    # Plant a real file at the claude-code pointer slot
    claude_dir = home / ".claude"
    claude_dir.mkdir()
    (claude_dir / "CLAUDE.md").write_text("# real file\n")

    # Write lock with claude-code
    lock_file = agent_toolkit_dir / "instructions-lock.json"
    lock_file.write_text(
        '{"version": 1, "instructions": {"AGENTS.md": {"scope": "global", "source": "AGENTS.md", "harnesses": ["claude-code"]}}}\n'
    )

    monkeypatch.setattr(
        "agent_toolkit_cli.instructions_paths.library_root",
        lambda: agent_toolkit_dir / "instructions",
    )

    rows = build_instruction_rows(scope="global", home=home, project=None)
    assert len(rows) == 1
    cell = rows[0].cells.get(("claude-code", "global"))
    assert cell is not None
    assert cell.conflict is True
    assert cell.linked is False


def test_interactive_harnesses_are_correct():
    """INTERACTIVE_HARNESSES must be exactly the 2 pinned harnesses."""
    assert INTERACTIVE_HARNESSES == ("claude-code", "gemini-cli")


# ---------------------------------------------------------------------------
# Full-composition cell probing (#351)
# ---------------------------------------------------------------------------

def test_rows_carry_cells_for_longtail_harnesses(tmp_path: Path, monkeypatch):
    """Every loaded row has cells for long-tail harnesses, so expanding the
    long tail never needs a reload (#351)."""
    from agent_toolkit_tui.composition import instructions_longtail

    home = tmp_path / "home"
    home.mkdir()
    agent_toolkit_dir = home / ".agent-toolkit"
    agent_toolkit_dir.mkdir(parents=True)
    (agent_toolkit_dir / "AGENTS.md").write_text("# AGENTS\n")

    monkeypatch.setattr(
        "agent_toolkit_cli.instructions_paths.library_root",
        lambda: home / ".agent-toolkit" / "instructions",
    )
    monkeypatch.setattr(
        "agent_toolkit_cli.instructions_paths.global_canonical_agents_md",
        lambda: agent_toolkit_dir / "AGENTS.md",
    )
    rows = build_instruction_rows(scope="global", home=home, project=None)
    assert rows, "expected the fresh-user AGENTS.md row"
    # augment is global-capable; tabnine-cli etc. may be scope-limited, so
    # assert on a tail harness known to have a global pointer slot.
    assert ("augment", "global") in rows[0].cells
