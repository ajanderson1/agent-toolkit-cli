"""Company-only Paperclip availability, toggling, and apply feedback in the TUI."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_toolkit_tui.skill_state import (
    INTERACTIVE_AGENTS,
    SkillCell,
    SkillRow,
    _cell_for,
)
from agent_toolkit_tui.widgets.skill_grid import SkillGrid


def _company(tmp_path: Path):
    company = tmp_path / ".paperclip/instances/default/companies/company-123"
    company.mkdir(parents=True)
    return company


def _row_with_paperclip(*, available: bool, scope: str = "project") -> SkillRow:
    cells = {}
    for a in INTERACTIVE_AGENTS:
        if a == "paperclip":
            cells[(a, scope)] = SkillCell(
                linked=False, drift=False, skipped=False,
                available=available,
                unavailable_reason="" if available else "company-scoped",
            )
        else:
            cells[(a, scope)] = SkillCell(
                linked=False, drift=False, skipped=False,
            )
    return SkillRow(
        slug="demo", source="x/demo", ref="main", state="clean", cells=cells,
    )


def test_paperclip_cell_unavailable_in_generic_project(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    cell = _cell_for(
        "demo", "paperclip",
        scope="project", home=None, project=tmp_path / "ordinary",
    )
    assert not cell.available
    assert "company-scoped" in cell.unavailable_reason


def test_paperclip_cell_unavailable_at_global_in_company(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    company = _company(tmp_path)
    monkeypatch.chdir(company)
    cell = _cell_for(
        "demo", "paperclip", scope="global", home=tmp_path, project=None,
    )
    assert not cell.available
    assert "switch the TUI to Project scope" in cell.unavailable_reason


def test_paperclip_cell_available_in_company_project(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    company = _company(tmp_path)
    cell = _cell_for(
        "demo", "paperclip", scope="project", home=None, project=company,
    )
    assert cell.available
    # No projection on disk yet → not linked, but toggleable.
    assert not cell.linked


@pytest.mark.asyncio
async def test_unavailable_paperclip_cell_cannot_queue(tmp_path):
    from textual.app import App

    class _A(App):
        def compose(self):
            yield SkillGrid([_row_with_paperclip(available=False)], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        g = a.query_one("#g", SkillGrid)
        g.set_scope("project")
        await pilot.pause()
        g.cursor_to_cell(row_slug="demo", agent_name="paperclip")
        await pilot.pause()
        await pilot.press("space")
        assert g.pending_entries() == {}


@pytest.mark.asyncio
async def test_company_paperclip_cell_queues_project_link(tmp_path):
    from textual.app import App

    class _A(App):
        def compose(self):
            yield SkillGrid([_row_with_paperclip(available=True)], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        g = a.query_one("#g", SkillGrid)
        g.set_scope("project")
        await pilot.pause()
        g.cursor_to_cell(row_slug="demo", agent_name="paperclip")
        await pilot.pause()
        await pilot.press("space")
        assert g.pending_entries() == {("project", "paperclip", "demo"): "link"}


@pytest.mark.asyncio
async def test_unavailable_paperclip_column_bulk_toggle_queues_nothing(tmp_path):
    from textual.app import App

    class _A(App):
        def compose(self):
            yield SkillGrid([_row_with_paperclip(available=False)], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        g = a.query_one("#g", SkillGrid)
        g.set_scope("project")
        await pilot.pause()
        g.cursor_to_cell(row_slug="demo", agent_name="paperclip")
        await pilot.pause()
        await pilot.press("a")
        assert all(
            k[1] != "paperclip" for k in g.pending_entries()
        ), g.pending_entries()
