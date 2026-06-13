from agent_toolkit_tui.mcp_state import mcp_interactive_harnesses


def test_interactive_harnesses_project_has_standard_first():
    # ("standard",) + mcp_nonstandard_main("project")
    assert mcp_interactive_harnesses("project") == (
        "standard", "codex", "opencode",
    )


def test_interactive_harnesses_global_no_standard():
    # No standard column at global (KeyError-guarded covered set).
    assert mcp_interactive_harnesses("global") == (
        "claude-code", "codex", "opencode", "pi",
    )
