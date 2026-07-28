"""Tests for the command-palette Theme and Main harnesses flows (#491)."""

from pathlib import Path
import pytest

from agent_toolkit_tui.app import (
    ConfirmDiscardScreen,
    MainHarnessSelectScreen,
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
async def test_main_harness_screen_candidates_and_preselection(temp_settings_path: Path):
    app = TUIApp()
    async with app.run_test() as pilot:
        app.search_main_harnesses()
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, MainHarnessSelectScreen)

        candidates = list(screen._candidates)
        assert "claude-code" in candidates
        assert "aider-desk" in candidates
        assert "standard" not in candidates
        assert "standard-skill" not in candidates
        assert "standard-agent" not in candidates

        # Claude Code ships selected by default; Aider does not.
        assert "claude-code" in screen._selected
        assert "aider-desk" not in screen._selected


@pytest.mark.asyncio
async def test_main_harness_screen_filter_narrows_options(temp_settings_path: Path):
    from textual.widgets import Input, SelectionList

    app = TUIApp()
    async with app.run_test() as pilot:
        app.search_main_harnesses()
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, MainHarnessSelectScreen)

        screen.query_one("#mh-filter", Input).value = "aider"
        await pilot.pause()

        sl = screen.query_one("#mh-list", SelectionList)
        values = [sl.get_option_at_index(i).value for i in range(sl.option_count)]
        assert values == ["aider-desk"]


@pytest.mark.asyncio
async def test_main_harness_screen_space_toggle_updates_selection(temp_settings_path: Path):
    from textual.widgets import SelectionList

    app = TUIApp()
    async with app.run_test() as pilot:
        app.search_main_harnesses()
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, MainHarnessSelectScreen)

        # Highlight the first (aider-desk) row and toggle it via the space action.
        sl = screen.query_one("#mh-list", SelectionList)
        sl.highlighted = 0
        assert "aider-desk" not in screen._selected

        screen.action_toggle_harness()
        await pilot.pause()

        # The screen stays open and the selection now includes the toggled row.
        assert isinstance(app.screen, MainHarnessSelectScreen)
        assert "aider-desk" in screen._selected

        screen.action_toggle_harness()
        await pilot.pause()
        assert "aider-desk" not in screen._selected


@pytest.mark.asyncio
async def test_main_harness_screen_multi_toggle_applies_once(temp_settings_path: Path):
    app = TUIApp()
    async with app.run_test() as pilot:
        app.search_main_harnesses()
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, MainHarnessSelectScreen)

        # Toggle two harnesses on without the screen closing, then apply.
        screen._selected.add("aider-desk")
        screen._selected.add("amp")
        screen.action_apply()
        await pilot.pause()

        assert not isinstance(app.screen, MainHarnessSelectScreen)
        assert "aider-desk" in app.tui_settings.harnesses
        assert "amp" in app.tui_settings.harnesses

        loaded = load_settings()
        assert "aider-desk" in loaded.harnesses
        assert "amp" in loaded.harnesses


@pytest.mark.asyncio
async def test_main_harness_screen_cancel_changes_nothing(temp_settings_path: Path):
    app = TUIApp()
    async with app.run_test() as pilot:
        initial = app.tui_settings.harnesses
        app.search_main_harnesses()
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, MainHarnessSelectScreen)
        screen._selected.add("aider-desk")
        screen.action_cancel()
        await pilot.pause()

        assert app.tui_settings.harnesses == initial


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


@pytest.mark.asyncio
async def test_all_grid_pending_enumeration_includes_mcp_and_commands(temp_settings_path: Path):
    app = TUIApp()
    async with app.run_test():
        cmd_grid = app.query_one("#command-grid")
        cmd_grid.restore_pending({("project", "claude-code", "my-cmd"): "link"})

        mcp_grid = app.query_one("#mcp-grid")
        mcp_grid.restore_pending({("project", "codex", "my-mcp"): "link"})

        pending = app._get_all_pending_edits()
        assert len(pending) == 2
        assert ("project", "claude-code", "my-cmd") in pending
        assert ("project", "codex", "my-mcp") in pending


@pytest.mark.asyncio
async def test_toggle_main_harness_discard_and_change_path(temp_settings_path: Path):
    app = TUIApp()
    async with app.run_test() as pilot:
        grid = app.query_one("#skill-grid")
        grid.restore_pending({("project", "test-skill"): "link"})

        app.toggle_main_harness("aider-desk")
        await pilot.pause()

        assert isinstance(app.screen, ConfirmDiscardScreen)

        app.screen.action_discard()
        await pilot.pause()

        assert "aider-desk" in app.tui_settings.harnesses
        loaded = load_settings()
        assert "aider-desk" in loaded.harnesses
        assert len(app._get_all_pending_edits()) == 0


@pytest.mark.asyncio
async def test_apply_harness_settings_save_failure_retains_pending_and_selection(
    temp_settings_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("AGENT_TOOLKIT_TUI_SETTINGS", " relative/path ")

    app = TUIApp()
    async with app.run_test() as pilot:
        initial_selection = app.tui_settings.harnesses
        grid = app.query_one("#skill-grid")
        grid.restore_pending({("project", "test-skill"): "link"})

        success = app.apply_harness_settings(("aider-desk",))
        await pilot.pause()

        assert success is False
        assert app.tui_settings.harnesses == initial_selection
        assert len(app._get_all_pending_edits()) == 1
