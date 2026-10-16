"""Real collection transactions coexist with lockless Instructions after #525."""
from pathlib import Path

import pytest
from textual.widgets import Static

from agent_toolkit_cli.skill_paths import library_lock_path
from agent_toolkit_tui.app import TUIApp
from agent_toolkit_tui.widgets.instruction_grid import InstructionGrid
from agent_toolkit_tui.widgets.skill_grid import SkillGrid
from tests.test_cli.test_skill_collection_reconcile import legacy


@pytest.mark.asyncio
@pytest.mark.parametrize("conflict_kind", [None, "skill", "instruction"])
async def test_hidden_apply_preserves_completed_kind_and_retries_only_failure(
    legacy, tmp_path, monkeypatch, conflict_kind
):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    home = Path.home()
    canonical = home / ".agent-toolkit/AGENTS.md"
    canonical.parent.mkdir(parents=True, exist_ok=True)
    canonical.write_text("user-owned instructions\n")
    pointer = home / ".claude/CLAUDE.md"
    conflict = home / ".agents/skills/workflow-05"
    if conflict_kind == "instruction":
        pointer.parent.mkdir(parents=True, exist_ok=True)
        pointer.write_text("foreign user file\n")
    elif conflict_kind == "skill":
        conflict.symlink_to(legacy / "workflow-06")
    index = (legacy / ".git/index").read_bytes()
    before_lock = library_lock_path().read_bytes()
    skill_pending = {("global", "standard", "workflow-00"): "unlink"}
    instruction_pending = {("global", "claude-code", "AGENTS.md"): "link"}

    app = TUIApp()
    app._scope = "global"
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        skills = app.query_one("#skill-grid", SkillGrid)
        instructions = app.query_one("#instruction-grid", InstructionGrid)
        skills.restore_pending(skill_pending)
        instructions.restore_pending(instruction_pending)
        for kind in ("instruction", "skill", "mcp"):
            app.action_asset_type(kind)
            await pilot.pause()
        app._refresh_skill_view()
        assert skills.pending_entries() == skill_pending
        assert instructions.pending_entries() == instruction_pending
        assert library_lock_path().read_bytes() == before_lock
        assert (home / ".agents/skills/wrapper").resolve() == legacy

        app.action_apply()
        await pilot.pause()
        footer = str(app.query_one("#footer-pending", Static).render())
        assert ("apply failed" in footer) == (conflict_kind is not None)
        assert skills.pending_entries() == (skill_pending if conflict_kind == "skill" else {})
        assert instructions.pending_entries() == (
            instruction_pending if conflict_kind == "instruction" else {}
        )
        if conflict_kind == "skill":
            assert library_lock_path().read_bytes() == before_lock
            assert (home / ".agents/skills/wrapper").resolve() == legacy
            assert conflict.readlink() == legacy / "workflow-06"
            completed_pointer = pointer.lstat()
            conflict.unlink()  # Only the test-owned obstruction is removed.
        else:
            assert not (home / ".agents/skills/wrapper").exists()
            assert len(list((home / ".agents/skills").glob("workflow-*"))) == 10
            completed_lock = library_lock_path().read_bytes()
        if conflict_kind == "instruction":
            assert pointer.read_text() == "foreign user file\n"
            pointer.unlink()  # Only the test-owned obstruction is removed.
        else:
            assert pointer.is_symlink() and pointer.resolve() == canonical

        app.action_apply()
        await pilot.pause()
        assert not app._get_all_pending_edits()
        assert pointer.is_symlink() and pointer.resolve() == canonical
        assert not (home / ".agents/skills/wrapper").exists()
        assert len(list((home / ".agents/skills").glob("workflow-*"))) == 10
        if conflict_kind == "skill":
            assert pointer.lstat().st_ino == completed_pointer.st_ino
        else:
            assert library_lock_path().read_bytes() == completed_lock

        settled_lock = library_lock_path().read_bytes()
        settled_pointer = pointer.lstat()
        skills.restore_pending({("global", "standard", "workflow-00"): "link"})
        instructions.restore_pending({("global", "claude-code", "AGENTS.md"): "unlink"})
        app.action_revert()
        assert not app._get_all_pending_edits()
        assert library_lock_path().read_bytes() == settled_lock
        assert pointer.lstat().st_ino == settled_pointer.st_ino
    assert canonical.read_text() == "user-owned instructions\n"
    assert (legacy / ".git/index").read_bytes() == index
    assert not (canonical.parent / "instructions-lock.json").exists()
    assert not (project / "instructions-lock.json").exists()
