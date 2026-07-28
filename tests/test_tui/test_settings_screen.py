"""Settings screen, command-palette, and live application tests (#480)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from textual.widgets import Button, Checkbox, DataTable, Select, Static

import agent_toolkit_tui.app as app_module
from agent_toolkit_tui.app import SettingsCommandProvider, TUIApp
from agent_toolkit_tui.composition import MAIN_HARNESSES
from agent_toolkit_tui.screens.settings import SettingsScreen
from agent_toolkit_tui.settings import DEFAULT_THEME, TuiSettings, load, save


def _settings_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    path = tmp_path / "tui-settings.json"
    monkeypatch.setenv("AGENT_TOOLKIT_TUI_SETTINGS", str(path))
    return path


def _stub_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "build_instruction_rows",
        "build_skill_rows",
        "build_command_rows",
        "build_pi_rows",
        "build_agent_rows",
        "build_mcp_rows",
    ):
        monkeypatch.setattr(app_module, name, lambda **_kwargs: [])


def _labels(app: TUIApp, selector: str) -> list[str]:
    table = app.query_one(selector, DataTable)
    return [str(column.label) for column in table.columns.values()]


def _persisted(path: Path, app: TUIApp) -> TuiSettings:
    assert path.exists()
    return load(available_themes=app.available_themes)


@pytest.mark.asyncio
async def test_palette_exposes_settings_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _settings_path(monkeypatch, tmp_path)
    _stub_rows(monkeypatch)
    app = TUIApp()

    async with app.run_test() as pilot:
        await pilot.pause()
        provider = SettingsCommandProvider(app.screen)
        hits = [hit async for hit in provider.search("settings")]

        assert [hit.text for hit in hits] == ["Settings"]
        assert SettingsCommandProvider in TUIApp.COMMANDS
        assert not any(binding.action == "settings" for binding in TUIApp.BINDINGS)

        hits[0].command()
        await pilot.pause()
        assert isinstance(app.screen, SettingsScreen)


@pytest.mark.asyncio
async def test_settings_screen_opens_and_closes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _settings_path(monkeypatch, tmp_path)
    _stub_rows(monkeypatch)
    app = TUIApp()

    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_settings()
        await pilot.pause()
        assert isinstance(app.screen, SettingsScreen)
        assert set(
            app.screen.query_one("#theme-select", Select)._legal_values
        ) == set(app.available_themes)

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, SettingsScreen)


@pytest.mark.asyncio
async def test_theme_change_applies_and_persists_without_harness_drafts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = _settings_path(monkeypatch, tmp_path)
    _stub_rows(monkeypatch)
    path.write_text(
        json.dumps(
            {
                "schema": "agent-toolkit-tui-settings/v1",
                "theme": DEFAULT_THEME,
                "harnesses": ["pi", "ghost-harness"],
            }
        )
    )
    app = TUIApp()

    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_settings()
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, SettingsScreen)

        # Harness checkbox changes remain drafts while theme writes immediately.
        screen.query_one("#harness-pi", Checkbox).value = False
        screen.query_one("#theme-select", Select).value = "nord"
        await pilot.pause()

        assert app.theme == "nord"
        persisted = _persisted(path, app)
        assert persisted.theme == "nord"
        assert persisted.harnesses == ("pi",)
        assert persisted.unknown_harnesses == ("ghost-harness",)
        assert isinstance(app.screen, SettingsScreen)

        copy = str(screen.query_one("#settings-persistence-note", Static).render())
        assert "Theme changes save immediately" in copy
        assert "Harness changes are drafts until Save" in copy


@pytest.mark.asyncio
async def test_cancel_discards_only_harness_drafts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = _settings_path(monkeypatch, tmp_path)
    _stub_rows(monkeypatch)
    save(TuiSettings(theme=DEFAULT_THEME, harnesses=("pi",)))
    app = TUIApp()

    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_settings()
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, SettingsScreen)
        screen.query_one("#harness-pi", Checkbox).value = False
        screen.query_one("#theme-select", Select).value = "nord"
        await pilot.pause()

        await pilot.press("escape")
        await pilot.pause()

        assert app.theme == "nord"
        persisted = _persisted(path, app)
        assert persisted.theme == "nord"
        assert persisted.harnesses == ("pi",)


@pytest.mark.asyncio
async def test_saving_harness_draft_rebuilds_every_relevant_grid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = _settings_path(monkeypatch, tmp_path)
    _stub_rows(monkeypatch)
    save(TuiSettings(theme=DEFAULT_THEME, harnesses=MAIN_HARNESSES))
    app = TUIApp()

    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_settings()
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, SettingsScreen)
        screen.query_one("#harness-pi", Checkbox).value = False
        assert screen.query_one("#settings-save", Button)
        screen.action_save()
        await pilot.pause()

        assert not isinstance(app.screen, SettingsScreen)
        assert "pi" not in _persisted(path, app).harnesses
        assert "Pi ⓘ" not in _labels(app, "#skill-table")
        assert "Pi ⓘ" not in _labels(app, "#agent-table")
        assert "Pi ⓘ" not in _labels(app, "#command-table")

        app.query_one("#mcp-grid").set_scope("global")
        await pilot.pause()
        assert "Pi ⓘ" not in _labels(app, "#mcp-table")


@pytest.mark.asyncio
async def test_standard_covered_harness_is_shown_as_no_op(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _settings_path(monkeypatch, tmp_path)
    _stub_rows(monkeypatch)
    app = TUIApp()

    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_settings()
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, SettingsScreen)

        label = str(screen.query_one("#harness-cursor", Checkbox).label)
        assert "no standalone column" in label.lower()


@pytest.mark.asyncio
async def test_unticking_everything_leaves_a_usable_grid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = _settings_path(monkeypatch, tmp_path)
    _stub_rows(monkeypatch)
    app = TUIApp()

    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_settings()
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, SettingsScreen)
        for checkbox in screen.query(Checkbox):
            checkbox.value = False
        screen.action_save()
        await pilot.pause()

        assert _persisted(path, app).harnesses == ()
        skill_labels = _labels(app, "#skill-table")
        assert len(skill_labels) == 4
        assert skill_labels[0] == "Skill"
        assert skill_labels[1].startswith("Standard (")
        assert skill_labels[2] == "State ⓘ"
        assert skill_labels[3] == "Source"


@pytest.mark.asyncio
async def test_invalid_utf8_settings_file_surfaces_a_status_bar_notice(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = _settings_path(monkeypatch, tmp_path)
    _stub_rows(monkeypatch)
    path.write_bytes(b"\xff\xfe invalid UTF-8")
    app = TUIApp()

    async with app.run_test() as pilot:
        await pilot.pause()

        status = str(app.query_one("#status-bar", Static).render())
        assert str(path) in status
        assert "UTF-8" in status
        assert app.theme == DEFAULT_THEME


@pytest.mark.asyncio
@pytest.mark.parametrize("override", ("relative-settings.json", " "))
async def test_invalid_settings_override_is_visible_on_startup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, override: str
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / override).write_text(
        json.dumps(
            {
                "schema": "agent-toolkit-tui-settings/v1",
                "theme": "nord",
                "harnesses": ["pi"],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("AGENT_TOOLKIT_TUI_SETTINGS", override)
    _stub_rows(monkeypatch)
    app = TUIApp()

    async with app.run_test() as pilot:
        await pilot.pause()

        status = str(app.query_one("#status-bar", Static).render())
        assert "AGENT_TOOLKIT_TUI_SETTINGS" in status
        assert "absolute" in status
        assert app.theme == DEFAULT_THEME


@pytest.mark.asyncio
async def test_future_schema_harness_save_is_refused_without_overwrite(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = _settings_path(monkeypatch, tmp_path)
    _stub_rows(monkeypatch)
    original = {
        "schema": "agent-toolkit-tui-settings/v99",
        "theme": "future-theme",
        "harnesses": ["future-harness"],
        "future_option": {"must": "survive"},
    }
    path.write_text(json.dumps(original), encoding="utf-8")
    app = TUIApp()

    async with app.run_test() as pilot:
        await pilot.pause()

        status = str(app.query_one("#status-bar", Static).render())
        assert "unsupported schema" in status
        assert app.apply_harness_settings(("pi",)) is False
        await pilot.pause()

    assert json.loads(path.read_text(encoding="utf-8")) == original


@pytest.mark.asyncio
async def test_harness_save_retains_an_unavailable_persisted_theme(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = _settings_path(monkeypatch, tmp_path)
    _stub_rows(monkeypatch)
    path.write_text(
        json.dumps(
            {
                "schema": "agent-toolkit-tui-settings/v1",
                "theme": "retired-theme",
                "harnesses": ["pi"],
            }
        ),
        encoding="utf-8",
    )
    app = TUIApp()

    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.theme == DEFAULT_THEME
        assert app.apply_harness_settings(("codex",)) is True
        await pilot.pause()

    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted["theme"] == "retired-theme"
    assert persisted["harnesses"] == ["codex"]


@pytest.mark.asyncio
async def test_bad_settings_file_surfaces_a_status_bar_notice(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = _settings_path(monkeypatch, tmp_path)
    _stub_rows(monkeypatch)
    path.write_text("{")
    app = TUIApp()

    async with app.run_test() as pilot:
        await pilot.pause()

        status = str(app.query_one("#status-bar", Static).render())
        assert str(path) in status
        assert "malformed JSON" in status
        assert app.theme == DEFAULT_THEME


@pytest.mark.asyncio
async def test_bad_settings_notice_has_a_visible_status_bar_row(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = _settings_path(monkeypatch, tmp_path)
    _stub_rows(monkeypatch)
    path.write_text("{")
    app = TUIApp()

    async with app.run_test() as pilot:
        await pilot.pause()

        status = app.query_one("#status-bar", Static)
        assert status.region.height >= 2
