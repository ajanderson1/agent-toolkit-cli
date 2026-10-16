from __future__ import annotations

import json
from pathlib import Path

import pytest
from rich.text import Text
from textual.app import App, ComposeResult
from textual.widgets import DataTable

from agent_toolkit_tui.agent_state import AgentRow
from agent_toolkit_tui.command_state import CommandRow
from agent_toolkit_tui.pi_extension_state import PiCell, PiExtensionRow
from agent_toolkit_tui.skill_state import SkillRow
from agent_toolkit_tui.widgets.agent_grid import AgentGrid
from agent_toolkit_tui.widgets.command_grid import CommandGrid
from agent_toolkit_tui.widgets.pi_grid import PiGrid
from agent_toolkit_tui.widgets.skill_grid import SkillGrid


class InventoryEvidenceApp(App):
    def compose(self) -> ComposeResult:
        yield SkillGrid([
            SkillRow("standalone-skill", "untracked", "(untracked)", "unlisted"),
            SkillRow("superpowers:brainstorming", "untracked", "(untracked)", "unlisted"),
        ], id="skills")
        yield AgentGrid([
            AgentRow("local-agent", "untracked", "(untracked)", "unlisted"),
        ], id="agents")
        yield CommandGrid([
            CommandRow("local-command", "untracked", "(untracked)", "unlisted"),
        ], id="commands")
        cell = PiCell(
            global_loaded=True, project_loaded=False, origin="local-package",
            managed=False, package_spec="../local-package",
            config_path="/tmp/home/.pi/agent/settings.json",
        )
        yield PiGrid([
            PiExtensionRow(
                slug="local-package", origin="local-package", source="../local-package",
                global_cell=cell, project_cell=cell, managed=False,
                global_config_path=cell.config_path,
                global_package_spec=cell.package_spec,
            ),
        ], id="pi")


def _cell_value(table: DataTable, row: int, column: int) -> str:
    value = table.get_cell_at((row, column))
    return value.plain if isinstance(value, Text) else str(value)


@pytest.mark.asyncio
async def test_rendered_unmanaged_inventory_evidence():
    """Capture visible cells and stable row keys for every discovered asset type."""
    artifact_dir = Path("assets/verification/515")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    app = InventoryEvidenceApp()
    async with app.run_test(size=(132, 36)) as pilot:
        await pilot.pause()
        cases = [
            ("skills", "skill-table", ["standalone-skill", "superpowers:brainstorming"], "unlisted", 2),
            ("agents", "agent-table", ["local-agent"], "unlisted", 2),
            ("commands", "command-table", ["local-command"], "unlisted", 2),
            ("pi", "pi-table", ["local-package"], "local package · untracked", 2),
        ]
        evidence = {}
        for widget_id, table_id, slugs, expected_label, badge_column in cases:
            widget = app.query_one(f"#{widget_id}")
            table = app.query_one(f"#{table_id}", DataTable)
            assert widget.display
            keys = [str(key.value) for key in table.rows]
            prefix = {"skills": "skill", "agents": "agent", "commands": "command", "pi": "pi"}[widget_id]
            assert keys == [f"{prefix}:{slug}" for slug in slugs]
            visible = [[_cell_value(table, i, j) for j in range(len(table.columns))] for i in range(len(slugs))]
            if widget_id == "pi":
                assert all(expected_label in row[badge_column] for row in visible)
            else:
                state_column = next(i for i, col in enumerate(table.columns.values()) if "State" in str(col.label))
                assert all("unlisted" in row[state_column] for row in visible), (widget_id, visible)
            evidence[widget_id] = {
                "row_keys": keys,
                "columns": [str(c.label) for c in table.columns.values()],
                "visible_rows": visible,
            }
        (artifact_dir / "inventory.svg").write_text(app.export_screenshot(), encoding="utf-8")
        assert (artifact_dir / "inventory.svg").stat().st_size > 1000
        payload = {
            "screen_size": [132, 36],
            "rendered_rows": evidence,
            "artifact": "inventory.svg",
        }
        (artifact_dir / "inventory.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
