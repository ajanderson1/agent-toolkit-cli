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


def test_project_scope_probes_global_shadow_cell(tmp_path: Path, monkeypatch):
    """At project scope, build_instruction_rows probes (harness, 'global') for
    each row when home is set, mirroring agent_state (#374). The global pointer
    being linked surfaces as a (harness, 'global') cell with linked=True."""
    from agent_toolkit_cli import instructions_paths

    home = tmp_path / "home"
    home.mkdir()
    project = tmp_path / "proj"
    project.mkdir()

    # Isolate the global canonical under tmp_path (mirrors the existing
    # test_build_instruction_rows_* tests). The global canonical is then
    # <agent_toolkit_dir>/AGENTS.md.
    agent_toolkit_dir = home / ".agent-toolkit"
    agent_toolkit_dir.mkdir(parents=True)
    monkeypatch.setattr(
        "agent_toolkit_cli.instructions_paths.library_root",
        lambda: agent_toolkit_dir / "instructions",
    )
    glob_canonical = agent_toolkit_dir / "AGENTS.md"
    glob_canonical.write_text("# global AGENTS\n")

    # Project canonical so the locked row's project cells resolve.
    proj_canonical = instructions_paths.project_canonical_agents_md(project)
    proj_canonical.write_text("# project AGENTS\n")

    # Project lock entry → locked-entry branch.
    lock_file = instructions_paths.project_lock_path(project)
    lock_file.write_text(
        '{"version": 1, "instructions": {"AGENTS.md": '
        '{"scope": "project", "source": "AGENTS.md", "harnesses": ["claude-code"]}}}\n'
    )

    # Install the GLOBAL claude-code pointer (~/.claude/CLAUDE.md → global canonical).
    from agent_toolkit_cli.instructions_adapters.symlink import _pointer_path
    glob_pointer = _pointer_path("claude-code", "global", None, home)
    glob_pointer.parent.mkdir(parents=True, exist_ok=True)
    glob_pointer.symlink_to(glob_canonical)

    rows = build_instruction_rows(scope="project", home=home, project=project)
    assert rows, "expected one AGENTS.md row"
    global_cell = rows[0].cells.get(("claude-code", "global"))
    assert global_cell is not None
    assert global_cell.linked is True


def test_empty_lock_fresh_user_row_probes_global_shadow_cell(tmp_path: Path, monkeypatch):
    """The empty-lock fresh-user row (canonical exists, no lock entries) also
    gets the (harness, 'global') shadow cell at project scope (#388)."""
    from agent_toolkit_cli import instructions_paths

    home = tmp_path / "home"
    home.mkdir()
    project = tmp_path / "proj"
    project.mkdir()

    agent_toolkit_dir = home / ".agent-toolkit"
    agent_toolkit_dir.mkdir(parents=True)
    monkeypatch.setattr(
        "agent_toolkit_cli.instructions_paths.library_root",
        lambda: agent_toolkit_dir / "instructions",
    )
    glob_canonical = agent_toolkit_dir / "AGENTS.md"
    glob_canonical.write_text("# global AGENTS\n")

    # Project canonical exists but NO project lock entries → fresh-user branch.
    proj_canonical = instructions_paths.project_canonical_agents_md(project)
    proj_canonical.write_text("# project AGENTS\n")

    # Global claude-code pointer linked.
    from agent_toolkit_cli.instructions_adapters.symlink import _pointer_path
    glob_pointer = _pointer_path("claude-code", "global", None, home)
    glob_pointer.parent.mkdir(parents=True, exist_ok=True)
    glob_pointer.symlink_to(glob_canonical)

    rows = build_instruction_rows(scope="project", home=home, project=project)
    assert rows and rows[0].slug == "AGENTS.md"
    gcell = rows[0].cells.get(("claude-code", "global"))
    assert gcell is not None and gcell.linked is True


def test_project_scope_home_none_skips_global_probe(tmp_path: Path, monkeypatch):
    """#388: callers that pass home=None don't care about the indicator — the
    `home is not None` gate fires the negative way, so NO (harness, 'global')
    cells appear. Mirrors test_agent_state.py and exercises BOTH build branches
    (empty-lock fresh-user row and locked-entry row)."""
    from agent_toolkit_cli import instructions_paths

    project = tmp_path / "proj"
    project.mkdir()
    agent_toolkit_dir = tmp_path / ".agent-toolkit"
    agent_toolkit_dir.mkdir(parents=True)
    monkeypatch.setattr(
        "agent_toolkit_cli.instructions_paths.library_root",
        lambda: agent_toolkit_dir / "instructions",
    )
    proj_canonical = instructions_paths.project_canonical_agents_md(project)
    proj_canonical.write_text("# project AGENTS\n")

    # Empty-lock fresh-user branch (canonical exists, no project lock).
    rows = build_instruction_rows(scope="project", home=None, project=project)
    assert rows and rows[0].slug == "AGENTS.md"
    assert all(scope != "global" for (_, scope) in rows[0].cells)

    # Locked-entry branch (seed a project lock entry).
    lock_file = instructions_paths.project_lock_path(project)
    lock_file.write_text(
        '{"version": 1, "instructions": {"AGENTS.md": '
        '{"scope": "project", "source": "AGENTS.md", "harnesses": ["claude-code"]}}}\n'
    )
    rows = build_instruction_rows(scope="project", home=None, project=project)
    assert rows
    assert all(scope != "global" for (_, scope) in rows[0].cells)
