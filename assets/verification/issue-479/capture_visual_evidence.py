from __future__ import annotations

import argparse
import asyncio
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from rich.text import Text
from textual.containers import Vertical
from textual.coordinate import Coordinate
from textual.widgets import DataTable

from agent_toolkit_tui.agent_state import (
    INTERACTIVE_HARNESSES as AGENT_HARNESSES,
    AgentCell,
    AgentRow,
)
from agent_toolkit_tui.app import TUIApp
from agent_toolkit_tui.command_state import (
    INTERACTIVE_HARNESSES as COMMAND_HARNESSES,
    CommandCell,
    CommandRow,
)
from agent_toolkit_tui.instruction_state import (
    INTERACTIVE_HARNESSES as INSTRUCTION_HARNESSES,
    InstructionCell,
    InstructionRow,
)
from agent_toolkit_tui.mcp_state import McpCell, McpRow
from agent_toolkit_tui.pi_extension_state import PiCell, PiExtensionRow
from agent_toolkit_tui.screens.cell_info import CellInfoScreen
from agent_toolkit_tui.skill_state import INTERACTIVE_AGENTS, SkillCell, SkillRow
from agent_toolkit_tui.widgets.column_info_modal import ColumnInfoModal


@dataclass(frozen=True)
class Case:
    asset_type: str
    grid_id: str
    table_id: str
    rows: tuple[object, ...]


SCOPES = ("global", "project")
STANDARD_CAPTURES = {
    ("skill", "project"),
    ("instruction", "project"),
    ("agent", "global"),
    ("agent", "project"),
    ("mcp", "project"),
}
FILE_STEMS = {
    "skill": "skills",
    "instruction": "instructions",
    "agent": "agents",
    "mcp": "mcps",
    "command": "commands",
    "pi-extension": "pi-extensions",
}


def _skill_row() -> SkillRow:
    cells = {
        (harness, scope): SkillCell(
            linked=harness == "standard" and scope == "global",
            drift=False,
            skipped=False,
        )
        for harness in INTERACTIVE_AGENTS
        for scope in SCOPES
    }
    return SkillRow(
        slug="demo-skill",
        source="demo/skills",
        ref="main",
        state="clean",
        cells=cells,
        description="",
    )


def _instruction_row() -> InstructionRow:
    cells = {
        (harness, scope): InstructionCell(
            linked=scope == "global",
            conflict=False,
        )
        for harness in INSTRUCTION_HARNESSES
        for scope in SCOPES
    }
    return InstructionRow(
        slug="AGENTS.md",
        source="AGENTS.md",
        canonical_exists=True,
        cells=cells,
    )


def _agent_row() -> AgentRow:
    cells = {
        (harness, scope): AgentCell(
            linked=harness == "standard" and scope == "global"
        )
        for harness in AGENT_HARNESSES
        for scope in SCOPES
    }
    return AgentRow(
        slug="demo-agent",
        source="demo/agents",
        ref="main",
        state="installed",
        cells=cells,
    )


def _mcp_row() -> McpRow:
    cells = {
        (harness, scope): McpCell(linked=False)
        for harnesses, scope in (
            (("claude-code", "codex", "opencode", "pi"), "global"),
            (("standard", "codex", "opencode"), "project"),
        )
        for harness in harnesses
    }
    return McpRow(
        slug="demo-mcp",
        source="npx",
        pin="1.2.3",
        state="installed",
        cells=cells,
    )


def _command_row() -> CommandRow:
    cells = {
        (harness, scope): CommandCell(linked=False)
        for harness in COMMAND_HARNESSES
        for scope in SCOPES
    }
    return CommandRow(
        slug="demo-command",
        source="demo/commands",
        ref="main",
        state="installed",
        cells=cells,
    )


def _pi_extension_row() -> PiExtensionRow:
    cell = PiCell(
        global_loaded=True,
        project_loaded=False,
        origin="store-owned",
    )
    return PiExtensionRow(
        slug="demo-extension",
        origin="store-owned",
        source="demo/extensions",
        global_cell=cell,
        project_cell=cell,
    )


CASES = (
    Case("skill", "skill-grid", "skill-table", (_skill_row(),)),
    Case("instruction", "instruction-grid", "instruction-table", (_instruction_row(),)),
    Case("agent", "agent-grid", "agent-table", (_agent_row(),)),
    Case("mcp", "mcp-grid", "mcp-table", (_mcp_row(),)),
    Case("command", "command-grid", "command-table", (_command_row(),)),
    Case("pi-extension", "pi-grid", "pi-table", (_pi_extension_row(),)),
)


def _post_header(grid: object, table: DataTable, index: int) -> None:
    grid.post_message(  # type: ignore[attr-defined]
        DataTable.HeaderSelected(
            table,
            column_key=list(table.columns)[index],
            column_index=index,
            label=Text(str(list(table.columns.values())[index].label)),
        )
    )


def _write_png(app: TUIApp, path: Path, *, title: str, scratch: Path) -> None:
    svg_path = scratch / f"{path.stem}.svg"
    svg = app.export_screenshot(title=title, simplify=True)
    svg_path.write_text("\n".join(line.rstrip() for line in svg.splitlines()) + "\n")
    subprocess.run(
        ["rsvg-convert", "--output", str(path), str(svg_path)],
        check=True,
    )


async def _capture_case(
    case: Case,
    scope: str,
    *,
    output: Path,
    scratch: Path,
) -> list[str]:
    app = TUIApp()
    lines: list[str] = []
    async with app.run_test(size=(180, 48)) as pilot:
        app.action_asset_type(case.asset_type)
        app.action_scope(scope)
        await pilot.pause()

        grid = app.query_one(f"#{case.grid_id}")
        grid.set_scope(scope)  # type: ignore[attr-defined]
        grid.set_rows(list(case.rows))  # type: ignore[attr-defined]
        await pilot.pause()
        table = app.query_one(f"#{case.table_id}", DataTable)
        labels = [str(column.label) for column in table.columns.values()]

        scope_png = scratch / f"{FILE_STEMS[case.asset_type]}-{scope}.png"
        _write_png(
            app,
            scope_png,
            title=f"{case.asset_type} grid — {scope}",
            scratch=scratch,
        )

        clicked_titles: list[str] = []
        for index, label in enumerate(labels):
            if "ⓘ" not in label:
                continue
            _post_header(grid, table, index)
            await pilot.pause()
            assert isinstance(app.screen, ColumnInfoModal), (
                f"{case.asset_type}/{scope}/{label}: no column modal"
            )
            assert app.screen._info.title.strip()
            assert app.screen._info.lines
            clicked_titles.append(app.screen._info.title)

            key = grid._column_key_for_index(index)  # type: ignore[attr-defined]
            if key == "standard":
                match = re.search(r"Standard \((\d+)\)", label)
                assert match is not None
                assert app.screen._info.lines[0] == (
                    f"Covered harnesses ({match.group(1)}):"
                )
                if (case.asset_type, scope) in STANDARD_CAPTURES:
                    standard_png = output / (
                        f"{FILE_STEMS[case.asset_type]}-standard-{scope}.png"
                    )
                    _write_png(
                        app,
                        standard_png,
                        title=f"{case.asset_type} Standard panel — {scope}",
                        scratch=scratch,
                    )
                    if (case.asset_type, scope) == ("instruction", "project"):
                        panel = app.screen.query_one(Vertical)
                        assert panel.virtual_size.height > panel.size.height
                        assert panel.allow_vertical_scroll
                        panel.scroll_end(animate=False)
                        await pilot.pause()
                        assert panel.scroll_y == panel.max_scroll_y
                        assert panel.scroll_y > 0
                        _write_png(
                            app,
                            output / "instructions-standard-project-scrolled-bottom.png",
                            title="instruction Standard panel — project, scrolled bottom",
                            scratch=scratch,
                        )
                        lines.append(
                            "PASS instruction/project: Standard modal scrolls to its final content."
                        )

            await pilot.press("escape")
            await pilot.pause()

        for index, label in enumerate(labels):
            if "ⓘ" in label:
                continue
            _post_header(grid, table, index)
            await pilot.pause()
            assert not isinstance(app.screen, ColumnInfoModal), (
                f"{case.asset_type}/{scope}/{label}: passive header opened a modal"
            )

        panels: list[tuple[str, str]] = []
        for column in (0, 1, len(labels) - 2):
            table.cursor_coordinate = Coordinate(row=0, column=column)
            table.focus()
            app.action_info_pass()
            await pilot.pause()
            assert isinstance(app.screen, CellInfoScreen)
            panels.append((app.screen._title, app.screen._body_markup))
            await pilot.press("escape")
            await pilot.pause()
        assert panels[0] == panels[1] == panels[2]
        assert "No description in " in panels[0][1]

        grid.set_rows([])  # type: ignore[attr-defined]
        await pilot.pause()
        app.action_info_pass()
        await pilot.pause()
        assert not isinstance(app.screen, CellInfoScreen)

        lines.append(
            f"PASS {case.asset_type}/{scope}: headers={labels!r}; "
            f"column_panels={clicked_titles!r}; i={panels[0][0]!r}; "
            "passive headers and zero-row i are no-ops"
        )
    return lines


def _combine_scope_images(output: Path, scratch: Path) -> list[Path]:
    combined: list[Path] = []
    for case in CASES:
        stem = FILE_STEMS[case.asset_type]
        destination = output / f"{stem}-grids-global-project.png"
        subprocess.run(
            [
                "magick",
                str(scratch / f"{stem}-global.png"),
                str(scratch / f"{stem}-project.png"),
                "-append",
                str(destination),
            ],
            check=True,
        )
        combined.append(destination)
    return combined


def _contact_sheet(output: Path, images: list[Path]) -> Path:
    destination = output / "visual-contact-sheet.png"
    subprocess.run(
        [
            "magick",
            "montage",
            *[str(image) for image in images],
            "-font",
            "/System/Library/Fonts/SFNS.ttf",
            "-thumbnail",
            "900x900",
            "-tile",
            "2x",
            "-geometry",
            "+12+28",
            "-background",
            "#202020",
            "-fill",
            "white",
            "-set",
            "label",
            "%t",
            str(destination),
        ],
        check=True,
    )
    return destination


async def _run(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    with tempfile.TemporaryDirectory(prefix="issue-479-visual-") as tmp:
        scratch = Path(tmp)
        for case in CASES:
            for scope in SCOPES:
                lines.extend(
                    await _capture_case(
                        case,
                        scope,
                        output=output,
                        scratch=scratch,
                    )
                )

        grid_images = _combine_scope_images(output, scratch)
        standard_images = sorted(output.glob("*-standard-*.png"))
        contact_sheet = _contact_sheet(output, [*grid_images, *standard_images])

    global_agent = next(
        line for line in lines if line.startswith("PASS agent/global:")
    )
    project_agent = next(
        line for line in lines if line.startswith("PASS agent/project:")
    )
    assert "Standard (5)" in global_agent
    assert "Standard (6)" in project_agent
    lines.append(
        "PASS agent scope toggle: Standard changed from 5 covered harnesses "
        "globally to 6 in project scope (Devin joins the covered list)."
    )
    lines.append(f"Contact sheet: {contact_sheet.as_posix()}")
    (output / "visual-checks.txt").write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default="assets/verification/issue-479",
    )
    args = parser.parse_args()
    asyncio.run(_run(Path(args.output)))
    print(Path(args.output).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
