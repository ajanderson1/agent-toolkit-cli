"""Verification artifact for issue #87.

Launches the TUI with a long doc, scrolls partway down, toggles a cell, and
prints before/after scroll_y and cursor_coordinate to confirm they are equal.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from textual.coordinate import Coordinate

from agent_toolkit_tui.app import TUIApp
from agent_toolkit_tui.runner import PlanResult


class FakeRunner:
    def __init__(self, doc: dict) -> None:
        self.doc = doc

    def list_state(self) -> dict:
        return self.doc

    def link_plan(self, *, scope, harness, entries, dry_run=False):
        return PlanResult(ok=len(entries), failed=0)

    def unlink_plan(self, *, scope, harness, entries, dry_run=False):
        return PlanResult(ok=len(entries), failed=0)


def _long_doc(row_count: int = 50, repo: str = "/r") -> dict:
    assets = []
    for i in range(row_count):
        slug = f"skill-{i:03d}"
        assets.append({
            "kind": "skill",
            "slug": slug,
            "origin": "first-party",
            "description": f"Skill {i}.",
            "path": f"{repo}/skills/{slug}/SKILL.md",
            "declared_harnesses": ["claude"],
            "cells": [
                {"harness": "claude", "scope": "user", "status": "unlinked",
                 "target": None, "allowlisted": False},
                {"harness": "claude", "scope": "project", "status": "unlinked",
                 "target": None, "allowlisted": False},
            ],
        })
    return {"toolkit_root": repo, "harnesses": ["claude"], "assets": assets}


async def main() -> None:
    runner = FakeRunner(_long_doc(50))
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        from agent_toolkit_tui.widgets import AssetGrid
        from textual.widgets import DataTable

        grid = app.query_one("#asset-grid", AssetGrid)
        table = grid.query_one("#grid-table", DataTable)
        table.focus()
        await pilot.pause()

        # Position cursor on a harness column, then scroll so the cursor is
        # visible but not at the viewport's minimum scroll position.
        table.cursor_coordinate = Coordinate(row=20, column=1)
        await pilot.pause()
        table.scroll_to(0, 18, animate=False)
        await pilot.pause()

        before_scroll = table.scroll_y
        before_cursor = table.cursor_coordinate
        print(f"before_scroll:  {before_scroll}")
        print(f"before_cursor:  {before_cursor}")

        await pilot.press("space")
        await pilot.pause()

        after_scroll = table.scroll_y
        after_cursor = table.cursor_coordinate
        print(f"after_scroll:   {after_scroll}")
        print(f"after_cursor:   {after_cursor}")

        scroll_ok = after_scroll == before_scroll
        cursor_ok = after_cursor == before_cursor
        print(f"scroll preserved: {scroll_ok}")
        print(f"cursor preserved: {cursor_ok}")
        if scroll_ok and cursor_ok:
            print("PASS")
        else:
            print("FAIL")


if __name__ == "__main__":
    asyncio.run(main())
