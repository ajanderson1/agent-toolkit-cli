"""Unit tests for KindsSidebar — pure-function counting, no Textual pilot needed."""
from __future__ import annotations

from pathlib import Path

from agent_toolkit_tui.state import AssetRow, CellState, InventoryState
from agent_toolkit_tui.widgets.kinds_sidebar import KIND_LABELS, KINDS, KindsSidebar


def _row(kind: str, slug: str) -> AssetRow:
    return AssetRow(
        slug=slug,
        kind=kind,
        origin="first-party",
        description="",
        path=Path(f"/r/{kind}s/{slug}"),
        declared_harnesses=("claude",),
        cells={("claude", "user"): CellState(status="unsupported", target_path=None, allowlisted=False)},
    )


def _state(*rows: AssetRow) -> InventoryState:
    return InventoryState(toolkit_root=Path("/r"), rows=rows, all_harnesses=("claude",))


def test_kinds_includes_mcp() -> None:
    assert "mcp" in KINDS
    assert KIND_LABELS["mcp"] == "MCPs"


def test_count_tallies_mcp_rows() -> None:
    state = _state(
        _row("skill", "alpha"),
        _row("mcp", "demo-mcp"),
        _row("mcp", "other-mcp"),
        _row("agent", "my-agent"),
    )
    counts = KindsSidebar._count(state)
    assert counts["mcp"] == 2
    assert counts["skill"] == 1
    assert counts["agent"] == 1


def test_count_returns_zero_when_no_mcps() -> None:
    state = _state(_row("skill", "alpha"), _row("agent", "my-agent"))
    counts = KindsSidebar._count(state)
    assert counts["mcp"] == 0


def test_count_keys_match_kinds_tuple() -> None:
    counts = KindsSidebar._count(_state())
    assert tuple(counts.keys()) == KINDS
