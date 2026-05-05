"""Tests for the (harness, kind) support matrix SSOT."""
from __future__ import annotations

import pytest

from agent_toolkit._support import (
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
    """SUPPORTED_PAIRS is derived from the target tables — no second SSOT."""
    assert SUPPORTED_PAIRS == frozenset(_USER_TARGETS.keys())
    assert frozenset(_USER_TARGETS.keys()) == frozenset(_PROJECT_TARGETS.keys())


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
    """The matrix gaps that issue #32 will close."""
    assert ("codex", "agent") not in SUPPORTED_PAIRS
    assert ("opencode", "agent") not in SUPPORTED_PAIRS
    assert ("opencode", "command") not in SUPPORTED_PAIRS
    assert ("pi", "command") not in SUPPORTED_PAIRS


def test_is_supported_matches_set_membership():
    assert is_supported("claude", "skill") is True
    assert is_supported("opencode", "agent") is False
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

    ctx = click.Context(click.Command("noop"))
    with pytest.raises(click.exceptions.Exit) as exc:
        validate_pair(ctx, "opencode", "agent")
    assert exc.value.exit_code == 2
    captured = capsys.readouterr()
    assert "opencode" in captured.err
    assert "agent" in captured.err
    # The error names supported kinds for the given harness as a hint.
    assert "skill" in captured.err
