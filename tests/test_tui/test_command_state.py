from agent_toolkit_cli.command_lock import LockEntry, LockFile, write_lock
from agent_toolkit_cli.command_paths import library_lock_path
from agent_toolkit_tui.command_state import interactive_harnesses, build_command_rows
from agent_toolkit_tui.composition import commands_main


def test_interactive_harnesses_standard_first():
    assert interactive_harnesses("global") == ("standard", "pi", "gemini-cli")
    assert interactive_harnesses("project") == ("standard", "pi", "gemini-cli")
    assert interactive_harnesses("global", ("claude-code", "pi")) == ("standard", "pi")
    assert interactive_harnesses("project", ()) == ("standard",)
    assert "hermes-agent" not in interactive_harnesses("global")


def test_commands_main_contracts():
    assert commands_main("global") == ("standard", "pi", "gemini-cli")
    assert commands_main("project") == ("standard", "pi", "gemini-cli")
    assert commands_main("global", ("claude-code", "pi")) == ("standard", "pi")
    assert commands_main("project", ()) == ("standard",)


def test_command_rows_include_library_lock(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    write_lock(
        library_lock_path(),
        LockFile(
            version=1,
            skills={
                "demo": LockEntry(
                    source="owner/repo",
                    source_type="github",
                    ref="main",
                    command_path="COMMAND.md",
                )
            },
        ),
    )
    rows = build_command_rows(scope="global", home=tmp_path, project=None)
    assert [r.slug for r in rows] == ["demo"]
    assert rows[0].state == "library"
    assert rows[0].cells[("standard", "global")].linked is False
    assert ("claude-code", "global") not in rows[0].cells
