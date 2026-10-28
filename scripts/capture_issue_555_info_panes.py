"""Capture #555 Info panes through production grids with disposable data.

Run: uv run python scripts/capture_issue_555_info_panes.py --output /tmp/issue-555
"""
from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def _cells(scope: str):
    from agent_toolkit_tui.skill_state import SkillCell, interactive_agents

    return {(name, scope): SkillCell(False, False, False) for name in interactive_agents()}


async def _capture_grid(name: str, grid, output: Path, size: tuple[int, int], *, scroll_end: bool = False) -> None:
    from textual.app import App, ComposeResult
    from textual.containers import VerticalScroll
    from textual.coordinate import Coordinate
    from textual.widgets import DataTable
    from agent_toolkit_tui.screens.cell_info import CellInfoScreen

    class CaptureApp(App[None]):
        def compose(self) -> ComposeResult:
            yield grid

    app = CaptureApp()
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        table = app.query_one(DataTable)
        table.cursor_coordinate = Coordinate(0, 0)
        grid.action_info()
        await pilot.pause()
        assert isinstance(app.screen, CellInfoScreen)
        if scroll_end:
            app.screen.query_one(VerticalScroll).scroll_end(animate=False)
            await pilot.pause()
        svg = app.export_screenshot(title=f"Issue 555 after — {name} — {size[0]}x{size[1]}")
        assert str(ROOT) not in svg and str(Path.home()) not in svg
        (output / f"{name}-{size[0]}x{size[1]}.svg").write_text(
            "\n".join(line.rstrip() for line in svg.splitlines()) + "\n"
        )


async def _capture_column(name: str, column: str, output: Path, size: tuple[int, int]) -> None:
    from textual.app import App
    from agent_toolkit_tui.column_info import get_column_info
    from agent_toolkit_tui.widgets.column_info_modal import ColumnInfoModal

    class CaptureApp(App[None]):
        def on_mount(self) -> None:
            info = get_column_info(column, asset_type="pi-extension", context={"scope": "project"})
            self.push_screen(ColumnInfoModal(info))

    app = CaptureApp()
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        svg = app.export_screenshot(title=f"Issue 555 after — {name} — {size[0]}x{size[1]}")
        assert str(ROOT) not in svg and str(Path.home()) not in svg
        (output / f"{name}-{size[0]}x{size[1]}.svg").write_text(
            "\n".join(line.rstrip() for line in svg.splitlines()) + "\n"
        )


async def capture(output: Path) -> None:
    """Capture with HOME/configuration/project isolated before TUI imports."""

    real_home = Path.home()
    original_cwd = Path.cwd()
    original_env = dict(os.environ)
    with tempfile.TemporaryDirectory(prefix="atk-555-info-") as raw:
        fixture = Path(raw)
        home = fixture / "home"
        project = fixture / "project"
        home.mkdir()
        project.mkdir()
        os.environ.update({
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "CLAUDE_CONFIG_DIR": str(home / ".claude"),
            "CODEX_HOME": str(home / ".codex"),
            "VIBE_HOME": str(home / ".vibe"),
            "AGENT_TOOLKIT_SKILLS_ROOT": str(home / ".agent-toolkit" / "skills"),
            "AGENT_TOOLKIT_NO_UPDATE_CHECK": "1",
        })
        os.chdir(project)
        assert Path.home() == home
        from agent_toolkit_tui.skill_state import SkillRow
        from agent_toolkit_tui.widgets.skill_grid import SkillGrid

        output.mkdir(parents=True, exist_ok=True)
        local = fixture / "local" / "deep" / "asset.md"
        local.parent.mkdir(parents=True)
        local.write_text("fixture")
        rows = {
            "short": SkillRow("journal", "example/journal", "main", "clean", _cells("global"), "A short daily note workflow."),
            "long": SkillRow("very-long-workflow-name", "file:///tmp/" + "long-source/" * 8 + "skill", "feature/a-very-long-branch-name-for-testing", "clean", _cells("global"), "A deliberately long description that wraps in a narrow terminal."),
            "local": SkillRow("local-workflow", str(local), "(untracked)", "clean", _cells("global"), origin="local"),
            "library": SkillRow("review", "example/review", "main", "library", _cells("global")),
            "catalogue": SkillRow("catalogue-offer", "example/catalogue", "main", "catalog", _cells("global"), origin="catalog"),
        }
        for name, row in rows.items():
            for size in ((110, 32), (58, 20)):
                await _capture_grid(name, SkillGrid([row]), output, size)
        for size in ((110, 32), (58, 20)):
            await _capture_grid("local-actions", SkillGrid([rows["local"]]), output, size, scroll_end=True)
            await _capture_column("pi", "pi", output, size)
            await _capture_column("npm", "origin", output, size)
    os.chdir(original_cwd)
    os.environ.clear()
    os.environ.update(original_env)
    assert Path.home() == real_home


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(capture(args.output.resolve()))


if __name__ == "__main__":
    main()
