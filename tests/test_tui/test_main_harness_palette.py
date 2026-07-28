"""Tests for the command-palette Theme and Main harnesses flows (#491)."""

from pathlib import Path
import pytest

from agent_toolkit_cli.skill_agents import AGENTS
from agent_toolkit_tui.app import (
    ConfirmDiscardScreen,
    HarnessCommandProvider,
    PersistentThemeProvider,
    TUIApp,
)
from agent_toolkit_tui.composition import (
    DEFAULT_MAIN_HARNESSES,
    MAIN_HARNESS_CANDIDATES,
)
from agent_toolkit_tui.settings import load as load_settings


@pytest.fixture
def temp_settings_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "tui-settings.json"
    monkeypatch.setenv("AGENT_TOOLKIT_TUI_SETTINGS", str(path))
    return path


@pytest.mark.asyncio
async def test_system_commands_include_main_harnesses(temp_settings_path: Path):
    app = TUIApp()
    async with app.run_test():
        cmds = list(app.get_system_commands(app.screen))
        titles = [cmd.title for cmd in cmds]
        assert "Main harnesses" in titles
        assert "Theme" in titles
        assert "Settings" not in titles


@pytest.mark.asyncio
async def test_theme_provider_persists_choice(temp_settings_path: Path):
    app = TUIApp()
    async with app.run_test() as pilot:
        provider = PersistentThemeProvider(app.screen)
        commands = provider.commands
        theme_names = [name for name, _cb in commands]
        assert "nord" in theme_names

        nord_cb = next(cb for name, cb in commands if name == "nord")
        nord_cb()
        await pilot.pause()

        assert app.theme == "nord"
        loaded = load_settings()
        assert loaded.theme == "nord"


@pytest.mark.asyncio
async def test_harness_command_provider_candidates_and_search(temp_settings_path: Path):
    app = TUIApp()
    async with app.run_test():
        provider = HarnessCommandProvider(app.screen)
        items = provider.commands

        keys = [key for key, _disp, _lbl, _cb in items]
        assert "claude-code" in keys
        assert "aider-desk" in keys
        assert "standard" not in keys
        assert "standard-skill" not in keys
        assert "standard-agent" not in keys

        claude_item = next(item for item in items if item[0] == "claude-code")
        assert "[x]" in claude_item[2]

        aider_item = next(item for item in items if item[0] == "aider-desk")
        assert "[ ]" in aider_item[2]

        hits_key = [hit async for hit in provider.search("aider-desk")]
        assert len(hits_key) > 0

        hits_display = [hit async for hit in provider.search("Claude Code")]
        assert len(hits_display) > 0


@pytest.mark.asyncio
async def test_toggle_main_harness_persistence_and_order(temp_settings_path: Path):
    app = TUIApp()
    async with app.run_test() as pilot:
        assert app.tui_settings.harnesses == DEFAULT_MAIN_HARNESSES

        app.toggle_main_harness("aider-desk")
        await pilot.pause()

        assert "aider-desk" in app.tui_settings.harnesses
        candidates_order = [h for h in MAIN_HARNESS_CANDIDATES if h in app.tui_settings.harnesses]
        assert list(app.tui_settings.harnesses) == candidates_order

        loaded = load_settings()
        assert "aider-desk" in loaded.harnesses

        app.toggle_main_harness("aider-desk")
        await pilot.pause()

        assert "aider-desk" not in app.tui_settings.harnesses
        loaded = load_settings()
        assert "aider-desk" not in loaded.harnesses


@pytest.mark.asyncio
async def test_toggle_main_harness_protected_by_pending_edits(temp_settings_path: Path):
    app = TUIApp()
    async with app.run_test() as pilot:
        grid = app.query_one("#skill-grid")
        grid.restore_pending({("project", "test-skill"): "link"})

        assert len(app._get_all_pending_edits()) == 1

        app.toggle_main_harness("aider-desk")
        await pilot.pause()

        assert isinstance(app.screen, ConfirmDiscardScreen)

        app.screen.action_cancel()
        await pilot.pause()

        assert "aider-desk" not in app.tui_settings.harnesses
        assert len(app._get_all_pending_edits()) == 1
