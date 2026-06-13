"""Tests for the MCP standard projection: covered set, adapter, normalization, collapse."""
from __future__ import annotations

import json

import pytest


def test_standard_covered_project_is_claude_and_pi():
    from agent_toolkit_cli.mcp_standard import mcp_standard_covered
    assert mcp_standard_covered("project") == frozenset({"claude-code", "pi"})


def test_standard_covered_unknown_scope_raises():
    from agent_toolkit_cli.mcp_standard import mcp_standard_covered
    with pytest.raises(KeyError):
        mcp_standard_covered("global")
