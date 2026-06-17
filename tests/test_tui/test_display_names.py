from agent_toolkit_tui.display_names import (
    asset_type_label,
    harness_label,
    pi_extension_origin_label,
    standard_label,
)


def test_asset_type_labels_are_plural_for_navigation():
    assert asset_type_label("instruction", plural=True) == "Instructions"
    assert asset_type_label("skill", plural=True) == "Skills"
    assert asset_type_label("pi-extension", plural=True) == "Pi Extensions"
    assert asset_type_label("agent", plural=True) == "Agents"
    assert asset_type_label("mcp", plural=True) == "MCPs"


def test_asset_type_labels_are_title_case_for_row_headers():
    assert asset_type_label("instruction") == "Instruction"
    assert asset_type_label("skill") == "Skill"
    assert asset_type_label("pi-extension") == "Pi Extension"
    assert asset_type_label("agent") == "Agent"
    assert asset_type_label("mcp") == "MCP"


def test_harness_labels_hide_internal_cli_suffixes():
    assert harness_label("claude-code") == "Claude"
    assert harness_label("gemini-cli") == "Gemini"
    assert harness_label("codex") == "Codex"
    assert harness_label("opencode") == "OpenCode"
    assert harness_label("pi") == "Pi"
    assert harness_label("cursor") == "Cursor"


def test_harness_label_falls_back_to_titleized_key():
    assert harness_label("custom-harness") == "Custom Harness"


def test_standard_label_always_includes_count():
    assert standard_label(2) == "Standard (2)"
    assert standard_label(17) == "Standard (17)"


def test_pi_extension_origin_label_uses_library():
    assert pi_extension_origin_label("store-owned") == "library"
    assert pi_extension_origin_label("npm") == "npm"
    assert pi_extension_origin_label("untracked") == "untracked"
