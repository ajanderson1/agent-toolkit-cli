"""Tests for the authored per-asset-type column-info registry (#479)."""
from __future__ import annotations

import pytest

from agent_toolkit_tui.column_info import COLUMN_INFO, ColumnInfo, get_column_info
from agent_toolkit_tui.display_names import harness_label


def _info(column: str, asset_type: str, scope: str = "global", **context: object) -> ColumnInfo:
    return get_column_info(column, asset_type=asset_type, context={"scope": scope, **context})


def test_registry_uses_asset_type_column_pairs() -> None:
    assert ("skill", "standard") in COLUMN_INFO
    assert ("instruction", "standard") in COLUMN_INFO
    assert ("agent", "standard") in COLUMN_INFO
    assert ("mcp", "standard") in COLUMN_INFO
    assert all(len(pair) == 2 for pair in COLUMN_INFO)


def test_get_column_info_is_recomputed_each_call() -> None:
    """Factories resolve a fresh panel rather than an import-time snapshot."""
    info_a = _info("standard", "skill")
    info_b = _info("standard", "skill")
    assert info_a is not info_b
    assert info_a == info_b


def test_get_column_info_unknown_pair_raises_key_error() -> None:
    with pytest.raises(KeyError):
        _info("does-not-exist", "skill")


@pytest.mark.parametrize(
    ("asset_type", "scope", "sentence"),
    [
        (
            "skill",
            "global",
            "One skill directory at `.agents/skills/<slug>/` that every harness "
            "in this list reads natively, so a single install serves all of them.",
        ),
        (
            "instruction",
            "global",
            "These harnesses read the repo's top-level `AGENTS.md` directly, so no "
            "per-harness pointer file is written for them.",
        ),
        (
            "agent",
            "global",
            "One file at `.claude/agents/<slug>.md` — the de-facto convergence "
            "directory these harnesses read, so the slot is a single artifact, not a bundle.",
        ),
        (
            "mcp",
            "project",
            "One `mcpServers` entry in the project's `.mcp.json`, which these "
            "harnesses read as a shared project-level server list.",
        ),
    ],
)
def test_standard_panel_keeps_the_authored_sentence(
    asset_type: str,
    scope: str,
    sentence: str,
) -> None:
    info = _info("standard", asset_type, scope, global_linked=False)
    assert sentence in info.lines
    assert info.lines[0].startswith("Covered harnesses (")
    assert any(line.startswith("  • ") for line in info.lines)


def test_standard_skill_panel_uses_live_catalog_display_names() -> None:
    from agent_toolkit_cli.skill_agents import get_standard_agents

    info = _info("standard", "skill", global_linked=False)
    text = "\n".join(info.lines)
    for name in get_standard_agents():
        assert harness_label(name) in text


def test_standard_instruction_panel_uses_live_native_readers() -> None:
    from agent_toolkit_cli.instructions_matrix import instructions_matrix_rows

    info = _info("standard", "instruction", global_linked=False)
    text = "\n".join(info.lines)
    native = [row["harness"] for row in instructions_matrix_rows() if row["verdict"] == "native"]
    assert f"Covered harnesses ({len(native)}):" in text
    for name in native:
        assert harness_label(name) in text


def test_standard_agent_panel_preserves_the_devin_global_note() -> None:
    global_info = _info("standard", "agent", "global", global_linked=False)
    project_info = _info("standard", "agent", "project", global_linked=False)
    assert "Devin reads .claude/agents at project scope only." in global_info.lines
    assert "Devin reads .claude/agents at project scope only." not in project_info.lines


@pytest.mark.parametrize(
    ("asset_type", "expected_marker_line"),
    [
        ("skill", "  This skill is also installed globally,"),
        ("instruction", "  merged with (not replaced by) the project one."),
        ("agent", "  This agent is also installed globally."),
    ],
)
def test_standard_project_marker_is_present_only_for_a_globally_linked_asset(
    asset_type: str,
    expected_marker_line: str,
) -> None:
    linked = _info("standard", asset_type, "project", global_linked=True)
    unlinked = _info("standard", asset_type, "project", global_linked=False)
    assert "🌐 marker (project scope only):" in linked.lines
    assert expected_marker_line in linked.lines
    assert "🌐 marker (project scope only):" not in unlinked.lines


@pytest.mark.parametrize(
    ("asset_type", "column", "sentence"),
    [
        (
            "skill",
            "claude-code",
            "Reads skills from `~/.claude/skills/`, its own directory rather than "
            "the shared `.agents/skills` slot, so it needs a separate install.",
        ),
        (
            "skill",
            "pi",
            "Reads skills from `~/.pi/agent/skills/`, its own directory rather "
            "than the shared `.agents/skills` slot.",
        ),
        (
            "skill",
            "hermes-agent",
            "Reads skills from `~/.hermes/skills/`, its own directory outside the "
            "standard slot.",
        ),
        (
            "skill",
            "paperclip",
            "Projects the skill into a Paperclip company library rather than a "
            "harness home, so its scope is the company, not the machine or the repo.",
        ),
        (
            "instruction",
            "claude-code",
            "Reads `CLAUDE.md`, not `AGENTS.md`, so the toolkit writes a pointer "
            "file that references the canonical instructions.",
        ),
        (
            "instruction",
            "gemini-cli",
            "Reads `GEMINI.md`, so the toolkit writes a pointer file; at project "
            "scope Gemini merges the global and project files rather than replacing "
            "one with the other.",
        ),
        (
            "agent",
            "gemini-cli",
            "Gets a translated agent file at `.gemini/agents/<slug>.md`; the "
            "toolkit rewrites the frontmatter into Gemini's shape rather than symlinking.",
        ),
        (
            "agent",
            "opencode",
            "Gets a translated agent file at `.opencode/agents/<slug>.md` "
            "(project) or the XDG config equivalent (global).",
        ),
        (
            "agent",
            "pi",
            "Gets a symlinked agent file at `.pi/agents/<slug>.md`, so edits to "
            "the library copy are picked up immediately.",
        ),
        (
            "mcp",
            "claude-code",
            "Reads `mcpServers` from a JSON config; at project scope it is covered "
            "by the shared `.mcp.json` slot instead of its own entry.",
        ),
        (
            "mcp",
            "codex",
            "Reads `[mcp_servers.<name>]` from a TOML config, so its entry is "
            "written and round-tripped separately from the JSON readers.",
        ),
        (
            "mcp",
            "opencode",
            "Reads `mcpServers` from its own JSON config, which is not the shared "
            "project `.mcp.json`.",
        ),
        (
            "mcp",
            "pi",
            "Reads `mcpServers` from a JSON config; at project scope it is covered "
            "by the shared `.mcp.json` slot instead of its own entry.",
        ),
        ("command", "claude-code", "Reads command markdown from `.claude/commands/`."),
        (
            "command",
            "pi",
            "Reads command markdown from `.pi/prompts/` (project) or "
            "`.pi/agent/prompts/` (global).",
        ),
        (
            "command",
            "gemini-cli",
            "Needs a TOML command file at `.gemini/commands/<slug>.toml`, so the "
            "markdown is converted rather than copied.",
        ),
        (
            "pi-extension",
            "pi",
            "Extensions are Pi-only; there is no shared slot and no other harness "
            "consumes them, which is why this asset type has no Standard column.",
        ),
    ],
)
def test_harness_panel_keeps_its_authored_copy(
    asset_type: str,
    column: str,
    sentence: str,
) -> None:
    info = _info(column, asset_type)
    assert info.lines == [sentence]
    assert info.title.startswith(harness_label(column))


def test_skill_state_panel_keeps_all_six_badges_in_state_markup_order() -> None:
    info = _info("state", "skill")
    badges = [line.split("—")[0].strip().lstrip("• ") for line in info.lines if line.startswith("•")]
    assert badges == ["clean", "dirty", "missing", "copy", "library", "unlisted"]


@pytest.mark.parametrize("asset_type", ["agent", "command", "mcp"])
def test_non_skill_state_panels_use_the_three_badge_legend(asset_type: str) -> None:
    info = _info("state", asset_type)
    text = "\n".join(info.lines)
    for badge in ("installed", "library", "unlisted"):
        assert f"• {badge} —" in text
    assert "matching `doctor` command" in text


def test_pi_extension_origin_panel_uses_the_three_authored_origins() -> None:
    info = _info("origin", "pi-extension")
    assert info.lines == [
        "• library — owned by the toolkit store",
        "• npm — installed as an npm package",
        "• untracked — present in Pi but not managed by the toolkit",
    ]
