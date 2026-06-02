"""instructions_install — plan/apply/uninstall over the symlink adapter."""
from __future__ import annotations

import pytest

from agent_toolkit_cli import instructions_install
from agent_toolkit_cli.instructions_lock import (
    InstructionsLockEntry,
    InstructionsLockFile,
    read_lock,
    write_lock,
)


@pytest.fixture
def project(tmp_path):
    p = tmp_path / "proj"
    p.mkdir()
    (p / "AGENTS.md").write_text("# project AGENTS.md\n")
    return p


def test_apply_creates_pointers_for_lock_harnesses(project):
    """apply() reconciles filesystem to match the lock's harnesses[] list."""
    lock_path = project / "instructions-lock.json"
    write_lock(
        lock_path,
        InstructionsLockFile(
            version=1,
            instructions={
                "AGENTS.md": InstructionsLockEntry(
                    scope="project",
                    source="AGENTS.md",
                    harnesses=["claude-code", "gemini-cli"],
                ),
            },
        ),
    )

    instructions_install.apply(scope="project", project_root=project, home=None)

    assert (project / "CLAUDE.md").is_symlink()
    assert (project / "CLAUDE.md").resolve() == (project / "AGENTS.md").resolve()
    assert (project / "GEMINI.md").is_symlink()


def test_apply_refuses_when_canonical_missing(tmp_path):
    """install/apply must refuse if there is no AGENTS.md to point to."""
    project = tmp_path / "proj"
    project.mkdir()
    # No AGENTS.md.
    lock_path = project / "instructions-lock.json"
    write_lock(
        lock_path,
        InstructionsLockFile(
            version=1,
            instructions={
                "AGENTS.md": InstructionsLockEntry(
                    scope="project", source="AGENTS.md", harnesses=["claude-code"],
                ),
            },
        ),
    )

    with pytest.raises(instructions_install.CanonicalMissingError, match="AGENTS.md"):
        instructions_install.apply(scope="project", project_root=project, home=None)


def test_apply_with_empty_lock_is_noop(project):
    """No lock entry → no pointers created."""
    instructions_install.apply(scope="project", project_root=project, home=None)
    assert not (project / "CLAUDE.md").exists()


def test_uninstall_removes_pointers(project):
    """uninstall() removes only pointers we own; lock entry is cleared."""
    lock_path = project / "instructions-lock.json"
    write_lock(
        lock_path,
        InstructionsLockFile(
            version=1,
            instructions={
                "AGENTS.md": InstructionsLockEntry(
                    scope="project", source="AGENTS.md",
                    harnesses=["claude-code", "gemini-cli"],
                ),
            },
        ),
    )
    instructions_install.apply(scope="project", project_root=project, home=None)
    assert (project / "CLAUDE.md").is_symlink()

    instructions_install.uninstall(scope="project", project_root=project, home=None)

    assert not (project / "CLAUDE.md").exists()
    assert not (project / "GEMINI.md").exists()
    # Lock entry cleared at project scope.
    assert read_lock(lock_path).instructions == {}
    # Lock file itself is deleted when the last entry is removed (issue #312).
    assert not lock_path.exists()


def test_install_uninstall_roundtrip_leaves_no_lock_file(project):
    """install → uninstall round-trip leaves no instructions-lock.json (issue #312).

    Regression test: previously uninstall() called write_lock() even when the
    resulting lock was empty, leaving a stray ``{}``-like file on disk.
    """
    lock_path = project / "instructions-lock.json"
    write_lock(
        lock_path,
        InstructionsLockFile(
            version=1,
            instructions={
                "AGENTS.md": InstructionsLockEntry(
                    scope="project", source="AGENTS.md",
                    harnesses=["claude-code"],
                ),
            },
        ),
    )
    instructions_install.apply(scope="project", project_root=project, home=None)
    assert lock_path.exists(), "sanity: lock file must exist after install"

    instructions_install.uninstall(scope="project", project_root=project, home=None)

    # The lock file must be absent — no stray empty {} on disk.
    assert not lock_path.exists(), (
        "instructions-lock.json must be deleted when the last entry is removed"
    )


def test_apply_prunes_pointer_removed_from_lock(project):
    """If a harness is removed from the lock, apply() removes its pointer too."""
    lock_path = project / "instructions-lock.json"
    write_lock(
        lock_path,
        InstructionsLockFile(
            version=1,
            instructions={
                "AGENTS.md": InstructionsLockEntry(
                    scope="project", source="AGENTS.md",
                    harnesses=["claude-code", "gemini-cli"],
                ),
            },
        ),
    )
    instructions_install.apply(scope="project", project_root=project, home=None)
    assert (project / "GEMINI.md").is_symlink()

    # Update lock: drop gemini-cli.
    write_lock(
        lock_path,
        InstructionsLockFile(
            version=1,
            instructions={
                "AGENTS.md": InstructionsLockEntry(
                    scope="project", source="AGENTS.md", harnesses=["claude-code"],
                ),
            },
        ),
    )
    instructions_install.apply(scope="project", project_root=project, home=None)

    assert (project / "CLAUDE.md").is_symlink()
    assert not (project / "GEMINI.md").exists()


def test_apply_skips_unsupported_harness_in_lock(project):
    """A harness not in the symlink-verdict set is ignored (warns later via CLI)."""
    lock_path = project / "instructions-lock.json"
    write_lock(
        lock_path,
        InstructionsLockFile(
            version=1,
            instructions={
                "AGENTS.md": InstructionsLockEntry(
                    scope="project", source="AGENTS.md",
                    harnesses=["claude-code", "codex"],  # codex is `native`, not symlink
                ),
            },
        ),
    )
    # Should not raise; just skips codex.
    instructions_install.apply(scope="project", project_root=project, home=None)
    assert (project / "CLAUDE.md").is_symlink()
