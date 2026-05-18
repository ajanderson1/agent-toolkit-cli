"""Tests for the (harness, kind) support matrix SSOT."""
from __future__ import annotations

import pytest

from agent_toolkit_cli._support import (
    ALL_HARNESSES,
    ALL_KINDS,
    SUPPORTED_PAIRS,
    UnsupportedPair,
    _PROJECT_TARGETS,
    _USER_TARGETS,
    is_supported,
    validate_pair,
)


def test_all_harnesses_is_canonical():
    assert ALL_HARNESSES == ("claude", "codex", "opencode", "pi")


def test_all_kinds_is_canonical():
    assert ALL_KINDS == (
        "skill", "agent", "command", "hook", "plugin", "mcp", "pi-extension",
    )


def test_supported_pairs_match_target_keys():
    """SUPPORTED_PAIRS is derived from _USER_TARGETS — no second SSOT.

    _PROJECT_TARGETS is a subset of _USER_TARGETS: project scope can omit a
    pair the harness only reads at user scope (e.g. pi agents at user scope
    only — see issue #49).
    """
    assert SUPPORTED_PAIRS == frozenset(_USER_TARGETS.keys())
    assert frozenset(_PROJECT_TARGETS.keys()) <= frozenset(_USER_TARGETS.keys())


def test_supported_pairs_known_members():
    # Spot-check: claude has the full kind set; codex/opencode have only skill.
    assert ("claude", "skill") in SUPPORTED_PAIRS
    assert ("claude", "agent") in SUPPORTED_PAIRS
    assert ("claude", "command") in SUPPORTED_PAIRS
    assert ("claude", "hook") in SUPPORTED_PAIRS
    assert ("claude", "plugin") in SUPPORTED_PAIRS
    assert ("codex", "skill") in SUPPORTED_PAIRS
    assert ("opencode", "skill") in SUPPORTED_PAIRS
    assert ("pi", "pi-extension") in SUPPORTED_PAIRS


def test_supported_pairs_known_holes():
    """The matrix gaps that issue #32 will close.

    opencode agent and command are now supported (translate cells added in
    Phase 3 — T8). The remaining holes are codex agent and pi command.
    """
    assert ("codex", "agent") not in SUPPORTED_PAIRS
    assert ("pi", "command") not in SUPPORTED_PAIRS


def test_is_supported_matches_set_membership():
    assert is_supported("claude", "skill") is True
    assert is_supported("opencode", "agent") is True   # translate cell added in Phase 3
    assert is_supported("codex", "agent") is False
    assert is_supported("nonsense", "skill") is False


def test_unsupported_pair_message_names_pair():
    exc = UnsupportedPair("opencode", "agent")
    assert "opencode" in str(exc)
    assert "agent" in str(exc)


def test_validate_pair_accepts_supported():
    import click

    ctx = click.Context(click.Command("noop"))
    validate_pair(ctx, "claude", "skill")  # must not raise


def test_validate_pair_rejects_unsupported_with_exit_2(capsys):
    import click

    # opencode agent is now supported (Phase 3 translate cell); use codex agent
    # which remains a known gap.
    ctx = click.Context(click.Command("noop"))
    with pytest.raises(click.exceptions.Exit) as exc:
        validate_pair(ctx, "codex", "agent")
    assert exc.value.exit_code == 2
    captured = capsys.readouterr()
    assert "codex" in captured.err
    assert "agent" in captured.err
    # The error names supported kinds for the given harness as a hint.
    assert "skill" in captured.err


# ---- direct coverage for helpers exercised only indirectly above ----------


def test_supported_kinds_for_claude_returns_full_kind_set():
    """`supported_kinds_for` must return the kinds in `ALL_KINDS` order
    for the harness given. claude has all five non-MCP, non-pi-extension
    kinds; mcp is intentionally absent from the SSOT (handled separately
    by per-harness MCP adapters)."""
    from agent_toolkit_cli._support import supported_kinds_for

    assert supported_kinds_for("claude") == (
        "skill", "agent", "command", "hook", "plugin",
    )


def test_supported_kinds_for_unknown_harness_is_empty():
    from agent_toolkit_cli._support import supported_kinds_for

    assert supported_kinds_for("nonsense") == ()


def test_slot_dir_user_scope_returns_home_anchored_absolute_path(tmp_path, monkeypatch):
    """`slot_dir` for `scope="user"` expands the `{home}` template and
    returns an absolute path. project_root is unused for user scope."""
    from agent_toolkit_cli._support import slot_dir

    monkeypatch.setenv("HOME", str(tmp_path))
    p = slot_dir("claude", "skill", "user", project_root=tmp_path / "ignored")
    assert p == tmp_path / ".claude" / "skills"
    assert p is not None and p.is_absolute()


def test_slot_dir_project_scope_returns_project_root_relative(tmp_path):
    """`slot_dir` for project scope returns a path under `project_root`."""
    from agent_toolkit_cli._support import slot_dir

    project = tmp_path / "myproject"
    p = slot_dir("claude", "skill", "project", project_root=project)
    assert p == project / ".claude" / "skills"


def test_slot_dir_unsupported_pair_returns_none(tmp_path):
    """Unsupported (harness, kind) returns None for both scopes — caller's
    responsibility to fail loudly via UnsupportedPair, not slot_dir.

    opencode agent is now supported (Phase 3 translate cell); use codex agent
    which remains a known gap."""
    from agent_toolkit_cli._support import slot_dir

    assert slot_dir("codex", "agent", "user", project_root=tmp_path) is None
    assert slot_dir("codex", "agent", "project", project_root=tmp_path) is None


def test_is_supported_back_compat_no_scope_for_pi_agent():
    """Acceptance #1: is_supported('pi','agent') returns True without a scope arg."""
    assert is_supported("pi", "agent") is True


def test_is_supported_user_scope_for_pi_agent_is_true():
    """Acceptance #2: pi agents ARE supported at user scope (~/.pi/agent/agents)."""
    assert is_supported("pi", "agent", scope="user") is True


def test_is_supported_project_scope_for_pi_agent_is_true():
    """#75: pi-subagents reads `<root>/.pi/agents/` and `<root>/.agents/` at
    project scope (it's the extension, not pi core, that loads them). Project
    scope is now supported with dual-write via alias targets."""
    assert is_supported("pi", "agent", scope="project") is True


def test_is_supported_unknown_scope_returns_false():
    """Defensive: any scope string other than 'user' or 'project' returns False."""
    assert is_supported("claude", "skill", scope="bogus") is False


def test_slot_dir_pi_agent_project_returns_primary(tmp_path):
    """#75: slot_dir returns the PRIMARY (`.pi/agents`) for the project scope."""
    from agent_toolkit_cli._support import slot_dir

    assert slot_dir("pi", "agent", "project", project_root=tmp_path) == tmp_path / ".pi" / "agents"


def test_slot_dirs_pi_agent_user_returns_primary_plus_alias(tmp_path, monkeypatch):
    """#75: slot_dirs at user scope returns BOTH `~/.pi/agent/agents/` (primary)
    and `~/.agents/` (alias) — pi-subagents reads both."""
    from agent_toolkit_cli._support import slot_dirs

    monkeypatch.setenv("HOME", str(tmp_path))
    dirs = slot_dirs("pi", "agent", "user", project_root=tmp_path)
    assert dirs == [
        tmp_path / ".pi" / "agent" / "agents",
        tmp_path / ".agents",
    ]


def test_slot_dirs_pi_agent_project_returns_primary_plus_alias(tmp_path):
    """#75: slot_dirs at project scope returns `.pi/agents/` (primary) and `.agents/`."""
    from agent_toolkit_cli._support import slot_dirs

    dirs = slot_dirs("pi", "agent", "project", project_root=tmp_path)
    assert dirs == [
        tmp_path / ".pi" / "agents",
        tmp_path / ".agents",
    ]


def test_slot_dirs_pair_without_aliases_returns_singleton(tmp_path, monkeypatch):
    """Pairs without alias entries return `[primary]` — same as `[slot_dir]`."""
    from agent_toolkit_cli._support import slot_dirs

    monkeypatch.setenv("HOME", str(tmp_path))
    dirs = slot_dirs("claude", "skill", "user", project_root=tmp_path)
    assert dirs == [tmp_path / ".claude" / "skills"]
