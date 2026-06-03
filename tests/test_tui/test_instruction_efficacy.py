"""Instruction kind symlink efficacy + no-clobber tests.

Discharges the DoD's:
- "efficacy checks confirm symlinks are created on apply and removed on uninstall"
- "PointerConflictError raised when real file present (no clobber)"

These tests exercise instructions_install.apply / uninstall directly (as the
TUI's _apply_instruction_pending does) on a real tmp_path filesystem to confirm
the pointer mechanics work end-to-end.
"""
from __future__ import annotations

import pytest

from agent_toolkit_cli import instructions_install
from agent_toolkit_cli.instructions_adapters.symlink import (
    CELLS,
    PointerConflictError,
    _pointer_path,
)
from agent_toolkit_cli.instructions_lock import (
    InstructionsLockEntry,
    InstructionsLockFile,
    write_lock,
)


def _write_lock(project: object, harnesses: list[str], scope: str = "project") -> None:
    """Write a minimal instructions lock for the given harnesses."""
    from pathlib import Path as _Path

    path = _Path(str(project)) / "instructions-lock.json"
    write_lock(
        path,
        InstructionsLockFile(
            version=1,
            instructions={
                "AGENTS.md": InstructionsLockEntry(
                    scope=scope,
                    source="AGENTS.md",
                    harnesses=harnesses,
                ),
            },
        ),
    )


# ---------------------------------------------------------------------------
# Create: symlink is created on apply
# ---------------------------------------------------------------------------


def test_apply_creates_symlink_for_claude_code(tmp_path):
    """After apply(), the claude-code pointer (CLAUDE.md) is a symlink to AGENTS.md."""
    project = tmp_path / "proj"
    project.mkdir()
    canonical = project / "AGENTS.md"
    canonical.write_text("# AGENTS\n")
    _write_lock(project, harnesses=["claude-code"], scope="project")

    instructions_install.apply(scope="project", project_root=project, home=None)

    pointer = project / "CLAUDE.md"
    assert pointer.is_symlink(), f"Expected CLAUDE.md to be a symlink, got: {pointer}"
    assert pointer.resolve() == canonical.resolve(), (
        f"Expected CLAUDE.md to resolve to {canonical}, got {pointer.resolve()}"
    )


def test_apply_creates_symlink_for_gemini_cli(tmp_path):
    """After apply(), the gemini-cli pointer (GEMINI.md) is a symlink to AGENTS.md."""
    project = tmp_path / "proj"
    project.mkdir()
    canonical = project / "AGENTS.md"
    canonical.write_text("# AGENTS\n")
    _write_lock(project, harnesses=["gemini-cli"], scope="project")

    instructions_install.apply(scope="project", project_root=project, home=None)

    pointer = project / "GEMINI.md"
    assert pointer.is_symlink(), f"Expected GEMINI.md to be a symlink, got: {pointer}"
    assert pointer.resolve() == canonical.resolve(), (
        f"Expected GEMINI.md to resolve to {canonical}, got {pointer.resolve()}"
    )


def test_apply_idempotent(tmp_path):
    """apply() is idempotent — calling it twice does not raise or change the symlink."""
    project = tmp_path / "proj"
    project.mkdir()
    canonical = project / "AGENTS.md"
    canonical.write_text("# AGENTS\n")
    _write_lock(project, harnesses=["claude-code"], scope="project")

    instructions_install.apply(scope="project", project_root=project, home=None)
    instructions_install.apply(scope="project", project_root=project, home=None)

    pointer = project / "CLAUDE.md"
    assert pointer.is_symlink()
    assert pointer.resolve() == canonical.resolve()


# ---------------------------------------------------------------------------
# Remove: symlink is removed on uninstall; canonical AGENTS.md untouched
# ---------------------------------------------------------------------------


def test_uninstall_removes_symlink(tmp_path):
    """After uninstall(), the pointer symlink is removed and AGENTS.md is intact."""
    project = tmp_path / "proj"
    project.mkdir()
    canonical = project / "AGENTS.md"
    canonical.write_text("# AGENTS\n")
    _write_lock(project, harnesses=["claude-code"], scope="project")

    instructions_install.apply(scope="project", project_root=project, home=None)
    pointer = project / "CLAUDE.md"
    assert pointer.is_symlink(), "Precondition: pointer should be a symlink after apply"

    instructions_install.uninstall(scope="project", project_root=project, home=None)

    # Pointer must be gone (or at least no longer our symlink).
    assert not pointer.is_symlink(), f"Expected CLAUDE.md to be removed, still a symlink at {pointer}"
    # Canonical AGENTS.md must be untouched.
    assert canonical.exists(), "Canonical AGENTS.md must not be removed by uninstall"
    assert canonical.read_text() == "# AGENTS\n"


def test_uninstall_leaves_canonical_intact(tmp_path):
    """uninstall() never touches the canonical AGENTS.md file."""
    project = tmp_path / "proj"
    project.mkdir()
    canonical = project / "AGENTS.md"
    canonical.write_text("# canonical content\n")
    _write_lock(project, harnesses=["gemini-cli"], scope="project")

    instructions_install.apply(scope="project", project_root=project, home=None)
    instructions_install.uninstall(scope="project", project_root=project, home=None)

    assert canonical.read_text() == "# canonical content\n"


# ---------------------------------------------------------------------------
# No-clobber: PointerConflictError when real file at target
# ---------------------------------------------------------------------------


def test_no_clobber_real_file_raises_pointer_conflict_error(tmp_path):
    """apply() raises PointerConflictError when a real file occupies the pointer slot."""
    project = tmp_path / "proj"
    project.mkdir()
    canonical = project / "AGENTS.md"
    canonical.write_text("# AGENTS\n")
    _write_lock(project, harnesses=["claude-code"], scope="project")

    # Place a real CLAUDE.md at the slot.
    real_file = project / "CLAUDE.md"
    real_file.write_text("# real claude instructions\n")
    original_content = real_file.read_text()

    with pytest.raises(PointerConflictError):
        instructions_install.apply(scope="project", project_root=project, home=None)

    # Real file must be completely unmodified.
    assert real_file.exists(), "Real file must not be deleted after conflict"
    assert not real_file.is_symlink(), "Real file must still be a real file after conflict"
    assert real_file.read_text() == original_content, (
        "Real file content must be unchanged after PointerConflictError"
    )


def test_no_clobber_real_file_content_unchanged(tmp_path):
    """The real file's content is fully preserved after a PointerConflictError."""
    project = tmp_path / "proj"
    project.mkdir()
    canonical = project / "AGENTS.md"
    canonical.write_text("# AGENTS\n")
    _write_lock(project, harnesses=["gemini-cli"], scope="project")

    real_file = project / "GEMINI.md"
    real_file.write_text("# my custom gemini instructions\n")

    with pytest.raises(PointerConflictError):
        instructions_install.apply(scope="project", project_root=project, home=None)

    assert real_file.read_text() == "# my custom gemini instructions\n"


def test_no_clobber_foreign_symlink_raises_pointer_conflict_error(tmp_path):
    """apply() raises PointerConflictError when a foreign symlink occupies the slot."""
    project = tmp_path / "proj"
    project.mkdir()
    canonical = project / "AGENTS.md"
    canonical.write_text("# AGENTS\n")
    # Create a foreign target (not our canonical).
    foreign = tmp_path / "other.md"
    foreign.write_text("# foreign\n")
    _write_lock(project, harnesses=["claude-code"], scope="project")

    # Place a foreign symlink at CLAUDE.md.
    pointer = project / "CLAUDE.md"
    pointer.symlink_to(foreign)

    with pytest.raises(PointerConflictError):
        instructions_install.apply(scope="project", project_root=project, home=None)

    # Foreign symlink must remain intact.
    assert pointer.is_symlink()
    assert pointer.resolve() == foreign.resolve()


# ---------------------------------------------------------------------------
# Global scope: symlink is created/removed in home directory
# ---------------------------------------------------------------------------


def test_global_scope_apply_creates_symlink(tmp_path, monkeypatch):
    """Global scope: apply() creates the pointer in the harness's home dir.

    monkeypatch.setenv("HOME", ...) is required because _resolve_canonical calls
    Path.home() which reads $HOME from the environment.
    """
    home = tmp_path / "home"
    lib = home / ".agent-toolkit"
    lib.mkdir(parents=True)
    canonical = lib / "AGENTS.md"
    canonical.write_text("# global AGENTS\n")
    monkeypatch.setenv("HOME", str(home))

    # Write global lock.
    lock_path = lib / "instructions-lock.json"
    write_lock(
        lock_path,
        InstructionsLockFile(
            version=1,
            instructions={
                "AGENTS.md": InstructionsLockEntry(
                    scope="global",
                    source="AGENTS.md",
                    harnesses=["claude-code"],
                ),
            },
        ),
    )

    instructions_install.apply(scope="global", project_root=None, home=home)

    pointer = _pointer_path("claude-code", "global", None, home)
    assert pointer.is_symlink(), f"Expected {pointer} to be a symlink"
    assert pointer.resolve() == canonical.resolve()


def test_global_scope_uninstall_removes_symlink(tmp_path, monkeypatch):
    """Global scope: uninstall() removes the pointer; AGENTS.md untouched.

    monkeypatch.setenv("HOME", ...) is required because _resolve_canonical calls
    Path.home() which reads $HOME from the environment.
    """
    home = tmp_path / "home"
    lib = home / ".agent-toolkit"
    lib.mkdir(parents=True)
    canonical = lib / "AGENTS.md"
    canonical.write_text("# global AGENTS\n")
    monkeypatch.setenv("HOME", str(home))

    lock_path = lib / "instructions-lock.json"
    write_lock(
        lock_path,
        InstructionsLockFile(
            version=1,
            instructions={
                "AGENTS.md": InstructionsLockEntry(
                    scope="global",
                    source="AGENTS.md",
                    harnesses=["claude-code"],
                ),
            },
        ),
    )

    instructions_install.apply(scope="global", project_root=None, home=home)
    pointer = _pointer_path("claude-code", "global", None, home)
    assert pointer.is_symlink(), "Precondition: pointer should exist after apply"

    instructions_install.uninstall(scope="global", project_root=None, home=home)

    assert not pointer.is_symlink(), f"Expected pointer removed, still exists at {pointer}"
    assert canonical.read_text() == "# global AGENTS\n"
