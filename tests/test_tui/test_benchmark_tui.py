"""Benchmark comparisons must retain the same expanded, child-toggle workload."""
import json

import pytest
from textual.widgets import DataTable

from scripts.benchmark_tui import measure
from agent_toolkit_tui.widgets.skill_grid import SkillGrid


@pytest.mark.asyncio
async def test_benchmark_expands_inventory_and_toggles_one_child(monkeypatch):
    pending_counts = []
    reports = []
    original = SkillGrid.action_toggle_cell

    def checked_toggle(grid):
        table = grid.query_one(DataTable)
        assert table.row_count == 22  # Twenty children and two collection parents.
        assert not grid._visible_rows()[table.cursor_coordinate.row].is_collection
        original(grid)
        pending_counts.append(len(grid.pending_entries()))

    monkeypatch.setattr(SkillGrid, "action_toggle_cell", checked_toggle)
    monkeypatch.setattr("scripts.benchmark_tui.print", reports.append, raising=False)
    await measure(20, 2, None)
    assert pending_counts == [1, 0]
    assert len(reports) == 1
    result = json.loads(reports[0])
    assert result["rows"] == 20
    assert result["samples"] == 2
    assert set(result["milliseconds"]) == {"toggle", "filter"}
