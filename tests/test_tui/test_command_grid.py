from agent_toolkit_tui.command_state import CommandCell, CommandRow
from agent_toolkit_tui.widgets.command_grid import CommandGrid


def test_command_grid_renders_rows():
    grid = CommandGrid([CommandRow(slug="demo", source="owner/repo", ref="main", cells={("claude-code", "global"): CommandCell(False)})])
    assert grid.row_count == 1
    assert grid.row_slugs == ["demo"]
