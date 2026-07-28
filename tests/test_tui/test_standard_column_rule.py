"""The Standard-column rule (#478).

Rule: for every asset type that HAS a standard slot at a given scope, the
first column after the slug column is headed `Standard (N)` with the live
covered count. Asset types with no standard slot are listed explicitly below,
with the reason — so a new asset type cannot drift in silently.
"""
from __future__ import annotations

import re

import pytest

from agent_toolkit_tui.display_names import standard_column_header

STANDARD_RE = re.compile(r"^Standard \(\d+\)$")

# (asset_type, scope) -> reason there is no standard slot. Spec R4/R5.
NO_STANDARD_SLOT = {
    ("pi-extension", "global"): "single-harness asset type; no convergence dir",
    ("pi-extension", "project"): "single-harness asset type; no convergence dir",
    ("mcp", "global"): "the standard projection IS the project .mcp.json",
}

ASSET_TYPES = ["instruction", "command", "skill", "agent", "mcp", "pi-extension"]


@pytest.mark.parametrize("asset_type", ASSET_TYPES)
@pytest.mark.parametrize("scope", ["global", "project"])
def test_standard_header_rule(asset_type: str, scope: str):
    header = standard_column_header(asset_type, scope)
    if (asset_type, scope) in NO_STANDARD_SLOT:
        assert header is None, (
            f"{asset_type}/{scope} is on the no-standard-slot exception list "
            f"({NO_STANDARD_SLOT[(asset_type, scope)]}) but returned {header!r}. "
            "If it gained a standard slot, remove it from the list."
        )
        return
    assert header is not None, f"{asset_type}/{scope} has no standard header"
    assert STANDARD_RE.match(header), f"{asset_type}/{scope} header was {header!r}"


def test_unknown_asset_type_is_loud():
    """Fail loudly: an unregistered asset type is a bug, not a None."""
    with pytest.raises(KeyError):
        standard_column_header("nonsense", "global")


def test_agents_count_differs_by_scope():
    """devin reads .claude/agents at project scope only, so the count moves.
    A stale header is a live defect, not a hypothetical (spec R3)."""
    assert standard_column_header("agent", "global") != standard_column_header(
        "agent", "project"
    )


def test_commands_standard_counts():
    assert standard_column_header("command", "global") == "Standard (2)"
    assert standard_column_header("command", "project") == "Standard (3)"
