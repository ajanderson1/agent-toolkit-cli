from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from textual.app import App

from agent_toolkit_tui.skill_state import INTERACTIVE_AGENTS, SkillCell, SkillRow
from agent_toolkit_tui.widgets.skill_grid import SkillGrid


def _row(slug: str) -> SkillRow:
    cells = {
        (agent, "global"): SkillCell(linked=False, drift=False, skipped=False)
        for agent in INTERACTIVE_AGENTS
    }
    return SkillRow(
        slug=slug,
        source=f"demo/{slug}",
        ref="main",
        state="clean",
        cells=cells,
        description="Hermes verification row",
    )


class _CaptureApp(App[None]):
    CSS = """
    Screen { align: center middle; }
    SkillGrid { width: 120; height: 12; }
    """

    def compose(self):
        yield SkillGrid([_row("demo-skill")], id="skill-grid")


async def _capture(output: Path) -> None:
    app = _CaptureApp()
    async with app.run_test(size=(140, 24)) as pilot:
        await pilot.pause()
        screenshot = app.export_screenshot(title="Hermes Skills grid", simplify=True)
        normalized = "\n".join(line.rstrip() for line in screenshot.splitlines()) + "\n"
        output.write_text(normalized)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default="assets/verification/issue-469/hermes-skill-grid.svg",
    )
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(_capture(output))
    print(output.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
