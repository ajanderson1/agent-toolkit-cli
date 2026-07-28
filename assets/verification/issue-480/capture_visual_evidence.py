"""Capture deterministic visual verification evidence for issue #480.

Uses a temporary AGENT_TOOLKIT_TUI_SETTINGS path; it never reads or writes the
operator's normal ~/.agent-toolkit/tui-settings.json.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import tempfile
from pathlib import Path

from textual.containers import VerticalScroll
from textual.widgets import Checkbox, DataTable, Select, Static

from agent_toolkit_tui.app import TUIApp
from agent_toolkit_tui.composition import MAIN_HARNESSES
from agent_toolkit_tui.screens.settings import SettingsScreen
from agent_toolkit_tui.settings import DEFAULT_THEME, SCHEMA, TuiSettings

_SIZE = (180, 48)


class Capture:
    def __init__(self, output: Path, scratch: Path) -> None:
        self.output = output
        self.scratch = scratch
        self.images: list[Path] = []
        self.lines: list[str] = []

    def image(self, app: TUIApp, name: str, title: str) -> Path:
        destination = self.output / name
        svg_path = self.scratch / f"{destination.stem}.svg"
        svg = app.export_screenshot(title=title, simplify=True)
        svg_path.write_text("\n".join(line.rstrip() for line in svg.splitlines()) + "\n")
        subprocess.run(
            ["rsvg-convert", "--output", str(destination), str(svg_path)],
            check=True,
        )
        self.images.append(destination)
        return destination

    def passed(self, text: str) -> None:
        self.lines.append(f"PASS {text}")


def _write_settings(path: Path, *, theme: str, harnesses: tuple[str, ...]) -> None:
    path.write_text(
        json.dumps(
            {
                "schema": SCHEMA,
                "theme": theme,
                "harnesses": list(harnesses),
            },
            indent=2,
        )
        + "\n"
    )


def _read_json(path: Path) -> dict[str, object]:
    parsed = json.loads(path.read_text())
    assert isinstance(parsed, dict)
    return parsed


def _labels(app: TUIApp, selector: str) -> list[str]:
    table = app.query_one(selector, DataTable)
    return [str(column.label) for column in table.columns.values()]


def _assert_pi_absent(labels: list[str], asset_type: str) -> None:
    assert not any(label.startswith("Pi") for label in labels), (
        f"Pi remained in {asset_type}: {labels!r}"
    )


async def _open_settings(app: TUIApp, pilot: object) -> SettingsScreen:
    app.action_settings()
    await pilot.pause()  # type: ignore[attr-defined]
    assert isinstance(app.screen, SettingsScreen)
    return app.screen


async def _case_palette(capture: Capture, settings_path: Path) -> None:
    _write_settings(settings_path, theme=DEFAULT_THEME, harnesses=MAIN_HARNESSES)
    app = TUIApp()
    async with app.run_test(size=_SIZE) as pilot:
        await pilot.pause()
        await pilot.press("ctrl+p")
        await pilot.pause()
        await pilot.press("s", "e", "t", "t", "i", "n", "g", "s")
        await pilot.pause()
        palette_svg = app.export_screenshot(title="Command palette — Settings", simplify=True)
        assert "Settings" in palette_svg
        capture.image(app, "palette-settings.png", "ctrl+p palette — Settings")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, SettingsScreen)
        capture.image(app, "settings-screen.png", "Settings screen")
        capture.passed("palette: ctrl+p search exposes Settings and opens the Settings screen.")


async def _case_theme_live_and_restart(capture: Capture, settings_path: Path) -> None:
    _write_settings(settings_path, theme=DEFAULT_THEME, harnesses=MAIN_HARNESSES)
    app = TUIApp()
    async with app.run_test(size=_SIZE) as pilot:
        await pilot.pause()
        screen = await _open_settings(app, pilot)
        theme_select = screen.query_one("#theme-select", Select)
        assert "nord" in app.available_themes
        theme_select.value = "nord"
        await pilot.pause()
        assert app.theme == "nord"
        assert isinstance(app.screen, SettingsScreen)
        assert _read_json(settings_path)["theme"] == "nord"
        capture.image(app, "theme-live-modal-nord.png", "Theme applies live — Settings remains open")

    restarted = TUIApp()
    async with restarted.run_test(size=_SIZE) as pilot:
        await pilot.pause()
        assert restarted.theme == "nord"
        capture.image(restarted, "theme-restart-nord.png", "Restart loads persisted Nord theme")
        capture.passed("theme: Nord applies while the modal remains open and a second app instance loads it.")


async def _case_theme_preserves_harness_draft(capture: Capture, settings_path: Path) -> None:
    _write_settings(settings_path, theme=DEFAULT_THEME, harnesses=MAIN_HARNESSES)
    app = TUIApp()
    async with app.run_test(size=_SIZE) as pilot:
        await pilot.pause()
        screen = await _open_settings(app, pilot)
        screen.query_one("#harness-pi", Checkbox).value = False
        screen.query_one("#theme-select", Select).value = "nord"
        await pilot.pause()
        persisted = _read_json(settings_path)
        assert "pi" in persisted["harnesses"]
        assert app.tui_settings.harnesses == MAIN_HARNESSES
        capture.image(app, "theme-change-keeps-pi-draft.png", "Theme save preserves unsaved Pi harness draft")
        capture.passed("draft split: unchecking Pi then changing theme keeps Pi in persisted harnesses until Save.")


async def _assert_pi_absent_in_all_grids(app: TUIApp) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for asset_type, selector in (
        ("skill", "#skill-table"),
        ("agent", "#agent-table"),
        ("command", "#command-table"),
    ):
        app.action_asset_type(asset_type)
        await asyncio.sleep(0)
        labels = _labels(app, selector)
        _assert_pi_absent(labels, asset_type)
        result[asset_type] = labels

    app.action_scope("global")
    app.action_asset_type("mcp")
    await asyncio.sleep(0)
    labels = _labels(app, "#mcp-table")
    _assert_pi_absent(labels, "global MCP")
    result["mcp-global"] = labels
    return result


async def _case_save_pi(capture: Capture, settings_path: Path) -> None:
    _write_settings(settings_path, theme=DEFAULT_THEME, harnesses=MAIN_HARNESSES)
    app = TUIApp()
    async with app.run_test(size=_SIZE) as pilot:
        await pilot.pause()
        screen = await _open_settings(app, pilot)
        screen.query_one("#harness-pi", Checkbox).value = False
        screen.action_save()
        await pilot.pause()
        assert not isinstance(app.screen, SettingsScreen)
        persisted = _read_json(settings_path)
        assert "pi" not in persisted["harnesses"]
        labels_by_grid = await _assert_pi_absent_in_all_grids(app)
        for asset_type, filename, title in (
            ("skill", "pi-unchecked-skills.png", "Pi unchecked — Skills"),
            ("agent", "pi-unchecked-agents.png", "Pi unchecked — Agents"),
            ("command", "pi-unchecked-commands.png", "Pi unchecked — Commands"),
            ("mcp", "pi-unchecked-mcps-global.png", "Pi unchecked — global MCPs"),
        ):
            app.action_asset_type(asset_type)
            await pilot.pause()
            capture.image(app, filename, title)

    restarted = TUIApp()
    async with restarted.run_test(size=_SIZE) as pilot:
        await pilot.pause()
        assert "pi" not in restarted.tui_settings.harnesses
        restart_labels = await _assert_pi_absent_in_all_grids(restarted)
        restarted.action_asset_type("skill")
        await pilot.pause()
        capture.image(restarted, "pi-unchecked-restart.png", "Restart preserves Pi column removal")
        capture.passed(
            "Pi save: Pi disappears from Skills, Agents, Commands, and global MCPs; restart preserves it. "
            f"labels={labels_by_grid!r}; restart={restart_labels!r}"
        )


async def _case_cursor_copy(capture: Capture, settings_path: Path) -> None:
    _write_settings(settings_path, theme=DEFAULT_THEME, harnesses=MAIN_HARNESSES)
    app = TUIApp()
    async with app.run_test(size=_SIZE) as pilot:
        await pilot.pause()
        screen = await _open_settings(app, pilot)
        label = str(screen.query_one("#harness-cursor", Checkbox).label)
        assert "no standalone column to hide" in label.lower()
        screen.query_one("#harness-list", VerticalScroll).scroll_end(animate=False)
        await pilot.pause()
        capture.image(app, "cursor-no-standalone-column.png", "Cursor has no standalone column to hide")
        capture.passed("Cursor checkbox: visibly states it has no standalone column to hide.")


async def _case_empty_selection(capture: Capture, settings_path: Path) -> None:
    _write_settings(settings_path, theme=DEFAULT_THEME, harnesses=MAIN_HARNESSES)
    app = TUIApp()
    async with app.run_test(size=_SIZE) as pilot:
        await pilot.pause()
        screen = await _open_settings(app, pilot)
        for harness in MAIN_HARNESSES:
            screen.query_one(f"#harness-{harness}", Checkbox).value = False
        screen.action_save()
        await pilot.pause()
        assert app.tui_settings.harnesses == ()
        app.action_asset_type("skill")
        await pilot.pause()
        skill_labels = _labels(app, "#skill-table")
        assert len(skill_labels) == 4
        assert skill_labels[0] == "Skill"
        assert skill_labels[1].startswith("Standard (")
        assert skill_labels[2] == "State ⓘ"
        assert skill_labels[3] == "Source"
        capture.image(app, "empty-selection-skills.png", "Empty selection leaves Skills usable")
        capture.passed(f"empty selection: usable Skills grid remains {skill_labels!r}.")


async def _case_malformed(capture: Capture, settings_path: Path) -> None:
    settings_path.write_text("{")
    app = TUIApp()
    async with app.run_test(size=_SIZE) as pilot:
        await pilot.pause()
        status = str(app.query_one("#status-bar", Static).render())
        assert app.theme == DEFAULT_THEME
        assert str(settings_path) in status
        assert "malformed JSON" in status
        capture.image(app, "malformed-settings-notice.png", "Malformed settings produce named status-bar notice")
        capture.passed("malformed file: defaults load and the status bar names the file and malformed JSON.")


async def _case_unknown_harness(capture: Capture, settings_path: Path) -> None:
    _write_settings(
        settings_path,
        theme=DEFAULT_THEME,
        harnesses=(*MAIN_HARNESSES, "ghost-harness"),
    )
    app = TUIApp()
    async with app.run_test(size=_SIZE) as pilot:
        await pilot.pause()
        status = str(app.query_one("#status-bar", Static).render())
        assert "ghost-harness" in status
        capture.image(app, "ghost-harness-notice.png", "Unknown harness is reported but retained")
        screen = await _open_settings(app, pilot)
        screen.query_one("#theme-select", Select).value = "nord"
        await pilot.pause()
        persisted = _read_json(settings_path)
        assert "ghost-harness" in persisted["harnesses"]
        assert persisted["theme"] == "nord"
        capture.image(app, "ghost-harness-after-theme-save.png", "Theme save retains unknown harness")
        (capture.output / "ghost-settings-after-theme-save.json").write_text(
            json.dumps(persisted, indent=2) + "\n"
        )
        capture.passed("unknown harness: ghost-harness is reported and survives a theme save unchanged.")


def _contact_sheet(capture: Capture) -> Path:
    destination = capture.output / "visual-contact-sheet.png"
    subprocess.run(
        [
            "magick",
            "montage",
            *[str(image) for image in capture.images],
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
    old_override = os.environ.get("AGENT_TOOLKIT_TUI_SETTINGS")
    with tempfile.TemporaryDirectory(prefix="issue480-settings-", dir="/tmp") as temp:
        scratch = Path(temp)
        settings_path = scratch / "tui-settings.json"
        os.environ["AGENT_TOOLKIT_TUI_SETTINGS"] = str(settings_path)
        capture = Capture(output, scratch)
        try:
            await _case_palette(capture, settings_path)
            await _case_theme_live_and_restart(capture, settings_path)
            await _case_theme_preserves_harness_draft(capture, settings_path)
            await _case_save_pi(capture, settings_path)
            await _case_cursor_copy(capture, settings_path)
            await _case_empty_selection(capture, settings_path)
            await _case_malformed(capture, settings_path)
            await _case_unknown_harness(capture, settings_path)
        finally:
            if old_override is None:
                os.environ.pop("AGENT_TOOLKIT_TUI_SETTINGS", None)
            else:
                os.environ["AGENT_TOOLKIT_TUI_SETTINGS"] = old_override

    contact_sheet = _contact_sheet(capture)
    capture.lines.append(f"Contact sheet: {contact_sheet.as_posix()}")
    (output / "visual-checks.txt").write_text("\n".join(capture.lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="assets/verification/issue-480")
    args = parser.parse_args()
    asyncio.run(_run(Path(args.output)))
    print(Path(args.output).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
