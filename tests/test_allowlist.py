"""Tests for src/agent_toolkit/_allowlist.py — section routing and YAML read helpers."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_toolkit._allowlist import (
    SECTIONS,
    kind_to_section,
    section_to_kind,
    read_allowlist,
)


def test_kind_to_section_skill():
    assert kind_to_section("skill") == "skills"


def test_kind_to_section_all_kinds():
    assert kind_to_section("agent") == "agents"
    assert kind_to_section("command") == "commands"
    assert kind_to_section("hook") == "hooks"
    assert kind_to_section("plugin") == "plugins"
    assert kind_to_section("pi-extension") == "pi_extensions"


def test_kind_to_section_mcp_raises():
    with pytest.raises(ValueError, match="not yet scope-routed"):
        kind_to_section("mcp")


def test_section_to_kind_inverse():
    for kind in ("skill", "agent", "command", "hook", "plugin", "pi-extension"):
        assert section_to_kind(kind_to_section(kind)) == kind


def test_sections_constant_matches_routing():
    assert set(SECTIONS) == {"skills", "agents", "commands", "hooks", "plugins", "pi_extensions"}


def test_read_allowlist_missing_file(tmp_path):
    result = read_allowlist(tmp_path / "nope.yaml")
    assert result == {s: [] for s in SECTIONS}


def test_read_allowlist_empty_file(tmp_path):
    f = tmp_path / "a.yaml"
    f.write_text("")
    assert read_allowlist(f) == {s: [] for s in SECTIONS}


def test_read_allowlist_multiline_form(tmp_path):
    f = tmp_path / "a.yaml"
    f.write_text(
        "skills:\n"
        "  - alpha\n"
        "  - beta\n"
        "agents:\n"
        "  - scout\n"
    )
    result = read_allowlist(f)
    assert result["skills"] == ["alpha", "beta"]
    assert result["agents"] == ["scout"]
    assert result["commands"] == []
    assert result["hooks"] == []
    assert result["plugins"] == []


def test_read_allowlist_inline_form(tmp_path):
    f = tmp_path / "a.yaml"
    f.write_text("skills: [alpha, beta]\nagents: []\n")
    result = read_allowlist(f)
    assert result["skills"] == ["alpha", "beta"]
    assert result["agents"] == []


def test_read_allowlist_unknown_section_ignored(tmp_path):
    f = tmp_path / "a.yaml"
    f.write_text("skills: [alpha]\nweirdos: [x]\n")
    result = read_allowlist(f)
    assert result["skills"] == ["alpha"]
    assert "weirdos" not in result


def test_read_allowlist_malformed_yaml_propagates(tmp_path):
    """Pin current behavior: malformed YAML raises yaml.YAMLError.

    Decision deferred to Task 4 (when bash consumer wires up). Today the
    error propagates uncaught; the consumer must decide whether to catch
    and re-raise as a typed exception or degrade silently.
    """
    import yaml as _yaml
    f = tmp_path / "a.yaml"
    f.write_text("skills: [unclosed\n")
    with pytest.raises(_yaml.YAMLError):
        read_allowlist(f)


def test_read_allowlist_root_is_list(tmp_path):
    """Non-dict root yields all-empty sections (defensive fallback)."""
    f = tmp_path / "a.yaml"
    f.write_text("- alpha\n- beta\n")
    assert read_allowlist(f) == {s: [] for s in SECTIONS}


def test_read_allowlist_section_not_a_list(tmp_path):
    """Section with a scalar value (e.g. `skills: alpha`) yields []."""
    f = tmp_path / "a.yaml"
    f.write_text("skills: alpha\n")
    assert read_allowlist(f)["skills"] == []
