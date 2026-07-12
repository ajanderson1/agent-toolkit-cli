from agent_toolkit_cli.command_lock import LockEntry, LockFile, write_lock
from agent_toolkit_cli.command_paths import library_lock_path
from agent_toolkit_tui.command_state import INTERACTIVE_HARNESSES, build_command_rows


def test_command_rows_include_library_lock(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    write_lock(library_lock_path(), LockFile(version=1, skills={"demo": LockEntry(source="owner/repo", source_type="github", ref="main", command_path="COMMAND.md")}))
    rows = build_command_rows(scope="global", home=tmp_path, project=None)
    assert [r.slug for r in rows] == ["demo"]
    assert rows[0].cells[("claude-code", "global")].linked is False
    assert "hermes-agent" not in INTERACTIVE_HARNESSES
