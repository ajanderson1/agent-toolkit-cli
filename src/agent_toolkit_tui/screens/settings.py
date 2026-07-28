"""Palette-only Settings modal for theme and main-harness preferences (#480)."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Label, Select, Static

from agent_toolkit_cli.agent_adapters.standard import agents_standard_covered
from agent_toolkit_cli.instructions_matrix import instructions_matrix_rows
from agent_toolkit_cli.mcp_standard import mcp_standard_covered
from agent_toolkit_cli.skill_agents import AGENTS
from agent_toolkit_tui.composition import (
    MAIN_HARNESSES,
    agents_nonstandard_main,
    commands_main,
    instructions_nonstandard_main,
    mcp_nonstandard_main,
    skills_nonstandard_main,
)
from agent_toolkit_tui.display_names import harness_label
from agent_toolkit_tui.settings import TuiSettings


def _standard_coverage(harness: str) -> tuple[str, ...]:
    """Asset types where ``harness`` is folded into a Standard column."""
    covered: list[str] = []
    if AGENTS[harness].is_standard:
        covered.append("Skills")

    verdicts = {
        row["harness"]: row["verdict"] for row in instructions_matrix_rows()
    }
    if verdicts.get(harness) == "native":
        covered.append("Instructions")

    if harness in (
        agents_standard_covered("global") | agents_standard_covered("project")
    ):
        covered.append("Agents")

    if harness in mcp_standard_covered("project"):
        covered.append("MCPs")
    return tuple(covered)


def _has_standalone_column(harness: str) -> bool:
    """Whether any asset type currently renders a column for ``harness``."""
    return any(
        (
            harness in skills_nonstandard_main(),
            harness in instructions_nonstandard_main(),
            harness in agents_nonstandard_main("global"),
            harness in agents_nonstandard_main("project"),
            harness in mcp_nonstandard_main("global"),
            harness in mcp_nonstandard_main("project"),
            harness in commands_main(),
        )
    )


def _harness_checkbox_label(harness: str) -> str:
    label = harness_label(harness)
    covered = _standard_coverage(harness)
    if not _has_standalone_column(harness):
        return f"{label} — Standard-covered; no standalone column to hide"
    if covered:
        return (
            f"{label} — Standard covers {', '.join(covered)}; "
            "only standalone columns are hidden"
        )
    return label


class SettingsScreen(ModalScreen[None]):
    """Edit TUI-only settings; theme commits immediately, harnesses on Save."""

    DEFAULT_CSS = """
    SettingsScreen {
        align: center middle;
    }
    SettingsScreen > Vertical {
        background: $panel;
        border: round $primary;
        padding: 1 2;
        width: 78;
        height: auto;
        max-height: 90%;
        overflow-y: auto;
    }
    SettingsScreen #settings-title {
        width: 100%;
        content-align: center middle;
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }
    SettingsScreen .settings-heading {
        text-style: bold;
        margin-top: 1;
    }
    SettingsScreen Select {
        width: 100%;
    }
    SettingsScreen #harness-list {
        height: auto;
        max-height: 14;
        margin-bottom: 1;
    }
    SettingsScreen Checkbox {
        width: 100%;
    }
    SettingsScreen #settings-persistence-note {
        color: $text-muted;
        margin: 1 0;
        height: auto;
    }
    SettingsScreen #settings-buttons {
        height: auto;
        align: center middle;
    }
    SettingsScreen Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, settings: TuiSettings) -> None:
        super().__init__()
        self._settings_at_open = settings
        self._resetting_theme = False

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Settings", id="settings-title")
            yield Static("Theme", classes="settings-heading")
            yield Select[str](
                ((theme, theme) for theme in self.app.available_themes),
                allow_blank=False,
                value=self._settings_at_open.theme,
                id="theme-select",
            )
            yield Static("Main harness columns", classes="settings-heading")
            with VerticalScroll(id="harness-list"):
                for harness in MAIN_HARNESSES:
                    yield Checkbox(
                        _harness_checkbox_label(harness),
                        value=harness in self._settings_at_open.harnesses,
                        id=f"harness-{harness}",
                    )
            yield Static(
                "Theme changes save immediately. Harness changes are drafts "
                "until Save; Cancel or Escape discards only harness drafts.",
                id="settings-persistence-note",
            )
            with Horizontal(id="settings-buttons"):
                yield Button("Save", variant="primary", id="settings-save")
                yield Button("Cancel", id="settings-cancel")

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "theme-select" or self._resetting_theme:
            return
        if not isinstance(event.value, str):
            return
        if self._tui_app().apply_theme_setting(event.value):
            return

        self._resetting_theme = True
        event.select.value = self._tui_app().tui_settings.theme
        self._resetting_theme = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "settings-save":
            self.action_save()
        elif event.button.id == "settings-cancel":
            self.action_cancel()

    def action_save(self) -> None:
        selected = tuple(
            harness
            for harness in MAIN_HARNESSES
            if self.query_one(f"#harness-{harness}", Checkbox).value
        )
        if self._tui_app().apply_harness_settings(selected):
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _tui_app(self):
        # Runtime import avoids app.py -> settings screen -> app.py at import time.
        from agent_toolkit_tui.app import TUIApp

        app = self.app
        assert isinstance(app, TUIApp)
        return app
