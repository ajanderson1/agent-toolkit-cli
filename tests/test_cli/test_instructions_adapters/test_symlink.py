"""Per-harness symlink adapter for the instructions kind.

Drops a same-name pointer symlink (CLAUDE.md, GEMINI.md, etc.) at each
harness's expected path, pointing at the canonical AGENTS.md.
"""
from __future__ import annotations

import pytest

from agent_toolkit_cli.instructions_adapters import symlink


def test_cells_match_phase_a_symlink_verdict_set():
    """The 7 cells must exactly match the symlink-verdict set in the matrix."""
    expected = {
        "augment", "claude-code", "codebuddy",
        "gemini-cli", "iflow-cli", "replit", "tabnine-cli",
    }
    assert set(symlink.CELLS) == expected


def test_each_cell_has_global_and_project_template():
    for harness, cell in symlink.CELLS.items():
        assert "global" in cell, f"{harness}: missing 'global' template"
        assert "project" in cell, f"{harness}: missing 'project' template"
        assert "{POINTER_NAME}" in (cell["global"] + cell["project"]), (
            f"{harness}: at least one template must use {{POINTER_NAME}}"
        )


def test_install_creates_project_pointer_symlink(tmp_path):
    """install(): a fresh project pointer is symlink → canonical AGENTS.md."""
    project = tmp_path / "proj"
    project.mkdir()
    canonical = project / "AGENTS.md"
    canonical.write_text("# AGENTS.md\nproject canon\n")

    adapter = symlink.adapter_for("claude-code")
    adapter.install(scope="project", project_root=project, canonical=canonical, home=None)

    pointer = project / "CLAUDE.md"
    assert pointer.is_symlink()
    assert pointer.resolve() == canonical.resolve()


def test_install_creates_global_pointer_symlink(tmp_path):
    """install(): a fresh global pointer is at ~/.claude/CLAUDE.md → ~/.agent-toolkit/AGENTS.md."""
    home = tmp_path / "home"
    home.mkdir()
    canonical = home / ".agent-toolkit" / "AGENTS.md"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("# AGENTS.md\nglobal canon\n")

    adapter = symlink.adapter_for("claude-code")
    adapter.install(scope="global", project_root=None, canonical=canonical, home=home)

    pointer = home / ".claude" / "CLAUDE.md"
    assert pointer.is_symlink()
    assert pointer.resolve() == canonical.resolve()


def test_install_is_idempotent_when_pointer_already_correct(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    canonical = project / "AGENTS.md"
    canonical.write_text("# canon\n")

    adapter = symlink.adapter_for("claude-code")
    adapter.install(scope="project", project_root=project, canonical=canonical, home=None)
    adapter.install(scope="project", project_root=project, canonical=canonical, home=None)  # no error

    pointer = project / "CLAUDE.md"
    assert pointer.resolve() == canonical.resolve()


def test_install_refuses_when_pointer_is_real_file(tmp_path):
    """No-clobber: never overwrite a real file. Raise; user must intervene."""
    project = tmp_path / "proj"
    project.mkdir()
    canonical = project / "AGENTS.md"
    canonical.write_text("# canon\n")
    pointer = project / "CLAUDE.md"
    pointer.write_text("# user-authored content\n")  # NOT a symlink

    adapter = symlink.adapter_for("claude-code")
    with pytest.raises(symlink.PointerConflictError, match="CLAUDE.md.*real file"):
        adapter.install(scope="project", project_root=project, canonical=canonical, home=None)

    # File contents preserved.
    assert pointer.read_text() == "# user-authored content\n"


def test_install_refuses_when_pointer_is_foreign_symlink(tmp_path):
    """No-clobber: never replace a symlink pointing elsewhere."""
    project = tmp_path / "proj"
    project.mkdir()
    canonical = project / "AGENTS.md"
    canonical.write_text("# canon\n")
    other = project / "OTHER.md"
    other.write_text("other\n")
    pointer = project / "CLAUDE.md"
    pointer.symlink_to(other)

    adapter = symlink.adapter_for("claude-code")
    with pytest.raises(symlink.PointerConflictError, match="CLAUDE.md.*points elsewhere"):
        adapter.install(scope="project", project_root=project, canonical=canonical, home=None)

    # Symlink target preserved.
    assert pointer.resolve() == other.resolve()


def test_uninstall_removes_our_pointer(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    canonical = project / "AGENTS.md"
    canonical.write_text("# canon\n")

    adapter = symlink.adapter_for("claude-code")
    adapter.install(scope="project", project_root=project, canonical=canonical, home=None)
    pointer = project / "CLAUDE.md"
    assert pointer.is_symlink()

    adapter.uninstall(scope="project", project_root=project, canonical=canonical, home=None)
    assert not pointer.exists()


def test_uninstall_leaves_foreign_symlink_alone(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    canonical = project / "AGENTS.md"
    canonical.write_text("# canon\n")
    other = project / "OTHER.md"
    other.write_text("other\n")
    pointer = project / "CLAUDE.md"
    pointer.symlink_to(other)

    adapter = symlink.adapter_for("claude-code")
    adapter.uninstall(scope="project", project_root=project, canonical=canonical, home=None)

    assert pointer.is_symlink()
    assert pointer.resolve() == other.resolve()


def test_uninstall_leaves_real_file_alone(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    canonical = project / "AGENTS.md"
    canonical.write_text("# canon\n")
    pointer = project / "CLAUDE.md"
    pointer.write_text("real file\n")

    adapter = symlink.adapter_for("claude-code")
    adapter.uninstall(scope="project", project_root=project, canonical=canonical, home=None)

    assert pointer.exists()
    assert not pointer.is_symlink()
    assert pointer.read_text() == "real file\n"


def test_adapter_for_unknown_harness_raises():
    with pytest.raises(symlink.UnknownHarnessError, match="unknown"):
        symlink.adapter_for("notarealharness")
