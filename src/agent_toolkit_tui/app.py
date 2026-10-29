"""The Textual App + main() entry point for agent-toolkit-tui.

Skill + Pi-extension cockpit over the v3 `agent-toolkit-cli` surface. Reads
locks + filesystem directly via `agent_toolkit_cli.*` modules and applies
pending toggles by calling the shipped CLI facades in-process.

Layout (matches existing CSS scaffold in css/app.tcss):

  Header
  Horizontal#main
    Vertical#asset-types-sidebar
      Static.rail-header
      OptionList#asset-types-list  ("Instructions" / "Commands" / "Skills" / "Agents" / "MCPs" / "Pi Extensions")
    Vertical#content
      Horizontal#content-header-row
        Static#content-header
        [ScopeToggle — skill, instruction, and agent asset types only]
      InstructionGrid | SkillGrid | PiGrid | AgentGrid   (swapped by action_asset_type)
  Static#status-bar
  Static#footer-pending
  Footer
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
from time import monotonic
from typing import Any, Callable, Iterable, Literal, cast

from textual.app import App, ComposeResult, SystemCommand
from textual.binding import Binding
from textual.command import DiscoveryHit, Hit, Hits, Provider
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    OptionList,
    SelectionList,
    Static,
)
from textual.widgets.option_list import Option, OptionDoesNotExist
from textual.widgets.selection_list import Selection
from rich.markup import escape
from rich.text import Text

from agent_toolkit_cli.skill_agents import AGENTS
from agent_toolkit_tui import __version__
from agent_toolkit_tui.agent_state import build_agent_rows
from agent_toolkit_tui.command_state import build_command_rows
from agent_toolkit_tui.composition import (
    MAIN_HARNESS_CANDIDATES,
)
from agent_toolkit_tui.display_names import asset_type_label
from agent_toolkit_tui.instruction_state import build_instruction_rows
from agent_toolkit_tui.mcp_state import build_mcp_rows
from agent_toolkit_tui.pi_extension_state import build_pi_rows
from agent_toolkit_tui.settings import (
    SettingsPathError,
    SettingsWriteError,
    TuiSettings,
    default_path as settings_path,
    load as load_settings,
    save as save_settings,
)
from agent_toolkit_tui.skill_state import build_skill_rows
from agent_toolkit_tui.widgets import (
    AgentGrid,
    CommandGrid,
    InstructionGrid,
    McpGrid,
    PiGrid,
    ScopeToggle,
    SkillGrid,
)

AssetType = Literal["instruction", "skill", "command", "pi-extension", "agent", "mcp"]


def _asset_type_label(asset_type: AssetType, *, plural: bool = False) -> str:
    return asset_type_label(asset_type, plural=plural)


_DOUBLE_CTRL_C_QUIT_SECONDS = 1.5

# Single owner of the AssetType -> filter-input selector map. Consumed by
# `/` (action_focus_filter), by every asset-type switch (action_asset_type),
# and by startup (on_mount) — so the three cannot drift (#477).
_FILTER_SELECTORS: dict[AssetType, str] = {
    "instruction": "#instruction-filter",
    "skill": "#skill-filter",
    "command": "#command-filter",
    "pi-extension": "#pi-filter",
    "agent": "#agent-filter",
    "mcp": "#mcp-filter",
}


def _scope_tag(keys: Iterable[tuple[str, ...]]) -> str:
    """Return ' (N global, M project)' when pending ops span both scopes.

    Every grid's pending key starts with the scope string — (scope, slug)
    for pi, (scope, harness, slug) for the rest — so key[0] is the scope in
    all four shapes. Iterating a pending dict yields its keys, so both dicts
    and key lists are accepted. Empty or single-scope input returns ''.
    """
    ks = list(keys)
    n_global = sum(1 for k in ks if k[0] == "global")
    n_project = len(ks) - n_global
    if n_global and n_project:
        return f" ({n_global} global, {n_project} project)"
    return ""


@dataclass(frozen=True)
class ApplyResult:
    """Outcome of an apply operation across a single asset kind."""

    ok: int
    failed: int
    errors: list[str]
    keys: list[tuple[str, ...]]


class ConfirmDiscardScreen(ModalScreen[bool]):
    """Yes/No prompt shown when quitting with unapplied pending edits."""

    DEFAULT_CSS = """
    ConfirmDiscardScreen {
        align: center middle;
    }
    ConfirmDiscardScreen > Vertical {
        background: $panel;
        border: thick $warning;
        padding: 1 2;
        width: 50;
        height: auto;
    }
    ConfirmDiscardScreen Label {
        width: 100%;
        content-align: center middle;
        text-style: bold;
        color: $warning;
        margin-bottom: 1;
    }
    ConfirmDiscardScreen #buttons {
        layout: horizontal;
        height: auto;
        align: center middle;
    }
    ConfirmDiscardScreen Button {
        margin: 0 2;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("y", "discard", "Discard"),
        Binding("n", "cancel", "Cancel"),
    ]

    def __init__(self, n_pending: int, message: str | None = None) -> None:
        super().__init__()
        self._n_pending = n_pending
        self._message = message or f"Discard {self._n_pending} pending change(s)?"

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self._message)
            with Horizontal(id="buttons"):
                yield Button("Discard", variant="warning", id="discard")
                yield Button("Cancel", variant="primary", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "discard")

    def action_discard(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


class MainHarnessSelectScreen(ModalScreen["tuple[str, ...] | None"]):
    """Multi-select modal for choosing which main harnesses get grid columns.

    Focus stays in the filter box; priority bindings drive the SelectionList so
    ``space`` toggles the highlighted harness in place (the palette no longer
    closes on every toggle), arrows move the cursor, and ``enter`` applies the
    whole selection at once. Dismisses with the chosen keys ordered by
    ``MAIN_HARNESS_CANDIDATES``, or ``None`` on cancel.
    """

    DEFAULT_CSS = """
    MainHarnessSelectScreen {
        align: center middle;
    }
    MainHarnessSelectScreen > Vertical {
        background: $panel;
        border: round $primary;
        padding: 1 2;
        width: 60;
        height: auto;
        max-height: 80%;
    }
    MainHarnessSelectScreen #mh-title {
        width: 100%;
        content-align: center middle;
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }
    MainHarnessSelectScreen #mh-filter {
        margin-bottom: 1;
    }
    MainHarnessSelectScreen SelectionList {
        height: auto;
        max-height: 18;
        background: $panel;
        border: none;
        padding: 0;
    }
    MainHarnessSelectScreen #mh-hint {
        width: 100%;
        content-align: center middle;
        color: $text-muted;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "apply", "Apply", priority=True),
        Binding("space", "toggle_harness", "Toggle", priority=True),
        Binding("up", "cursor_up", "Up", priority=True, show=False),
        Binding("down", "cursor_down", "Down", priority=True, show=False),
    ]

    def __init__(
        self,
        candidates: tuple[str, ...],
        display_names: dict[str, str],
        selected: tuple[str, ...],
    ) -> None:
        super().__init__()
        self._candidates = candidates
        self._display_names = display_names
        self._selected: set[str] = set(selected)
        self._filter = ""

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Main harnesses", id="mh-title")
            yield Input(placeholder="Search for main harnesses…", id="mh-filter")
            yield SelectionList[str](id="mh-list")
            yield Static("space toggle · enter apply · esc cancel", id="mh-hint")

    def on_mount(self) -> None:
        self._rebuild_options()
        self.query_one("#mh-filter", Input).focus()

    def _visible_keys(self) -> list[str]:
        needle = self._filter.strip().lower()
        if not needle:
            return list(self._candidates)
        return [
            key
            for key in self._candidates
            if needle in self._display_names[key].lower() or needle in key.lower()
        ]

    def _rebuild_options(self) -> None:
        sl = self.query_one("#mh-list", SelectionList)
        sl.clear_options()
        sl.add_options(
            [
                Selection(
                    self._display_names[key], key, initial_state=key in self._selected
                )
                for key in self._visible_keys()
            ]
        )

    def on_input_changed(self, event: Input.Changed) -> None:
        self._filter = event.value
        self._rebuild_options()

    def on_selection_list_selected_changed(
        self, event: SelectionList.SelectedChanged
    ) -> None:
        visible = set(self._visible_keys())
        chosen = set(event.selection_list.selected)
        # Keep selections made under previous filters; only the currently
        # visible keys can change state here.
        self._selected = (self._selected - visible) | (chosen & visible)

    def action_toggle_harness(self) -> None:
        self.query_one("#mh-list", SelectionList).action_select()

    def action_cursor_up(self) -> None:
        self.query_one("#mh-list", SelectionList).action_cursor_up()

    def action_cursor_down(self) -> None:
        self.query_one("#mh-list", SelectionList).action_cursor_down()

    def action_apply(self) -> None:
        ordered = tuple(k for k in self._candidates if k in self._selected)
        self.dismiss(ordered)

    def action_cancel(self) -> None:
        self.dismiss(None)


class SidebarOptionList(OptionList):
    """Sidebar specifically to capture 1-6 bindings when focused."""

    BINDINGS = [
        Binding("1", "asset_type('instruction')", "Instructions", show=False),
        Binding("2", "asset_type('command')", "Commands", show=False),
        Binding("3", "asset_type('skill')", "Skills", show=False),
        Binding("4", "asset_type('agent')", "Agents", show=False),
        Binding("5", "asset_type('mcp')", "MCPs", show=False),
        Binding("6", "asset_type('pi-extension')", "Pi Extensions", show=False),
    ]

    def action_asset_type(self, asset_type: str) -> None:
        """Forward sidebar-only number bindings to the owning TUI app."""
        cast("TUIApp", self.app).action_asset_type(asset_type)


class PersistentThemeProvider(Provider):
    """Command palette provider for themes that persists theme choice on selection."""

    @property
    def commands(self) -> list[tuple[str, Callable[[], None]]]:
        themes = self.app.available_themes

        def make_callback(theme_name: str) -> Callable[[], None]:
            def callback() -> None:
                cast("TUIApp", self.app).apply_theme_setting(theme_name)

            return callback

        return [
            (theme_name, make_callback(theme_name))
            for theme_name in sorted(themes.keys())
        ]

    async def discover(self) -> Hits:
        for name, callback in self.commands:
            yield DiscoveryHit(name, callback, help=f"Set theme to {name}")

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        for name, callback in self.commands:
            if (score := matcher.match(name)) > 0:
                yield Hit(
                    score,
                    matcher.highlight(name),
                    callback,
                    help=f"Set theme to {name}",
                )


class TUIApp(App):
    """agent-toolkit-tui — Textual cockpit over `agent-toolkit-cli`."""

    CSS_PATH = "css/app.tcss"
    TITLE = "agent-toolkit-tui"

    BINDINGS = [
        Binding("ctrl+s", "apply", "Apply", priority=True),
        Binding("ctrl+d", "diff", "Diff", priority=True),
        Binding("ctrl+r", "refresh", "Refresh", priority=True),
        Binding("ctrl+z", "revert", "Revert", priority=True),
        Binding("slash", "focus_filter", "Filter", priority=True),
        Binding("escape", "focus_filter", "Filter", show=False),
        Binding("ctrl+w", "focus_sidebar", "Focus Sidebar", priority=True),
        Binding("ctrl+g", "scope_toggle", "toggle scope", priority=True),
        Binding("i", "info_pass", "Info"),
        Binding("ctrl+c", "double_ctrl_c_quit", "Quit", priority=True),
        Binding("q", "quit", "Quit"),
    ]

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        yield from super().get_system_commands(screen)
        yield SystemCommand(
            "Main harnesses",
            "Choose which harnesses receive standalone grid columns",
            self.action_main_harnesses,
        )

    def __init__(self, cwd: Path | None = None) -> None:
        super().__init__()
        self._cwd_override: Path | None = cwd
        self._scope: str = "project"
        self._active_asset_type: AssetType = "skill"
        self._last_ctrl_c_quit_at: float | None = None
        self._tui_settings = TuiSettings()
        self._settings_diagnostics: tuple[str, ...] = ()
        self._catalog_status_label: Static | None = None
        self.sub_title = f"v{__version__}"

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            with Vertical(id="asset-types-sidebar"):
                yield Static("Asset Types", classes="rail-header")
                yield SidebarOptionList(
                    Option(_asset_type_label("instruction", plural=True), id="asset-type-instruction"),
                    Option(_asset_type_label("command", plural=True), id="asset-type-command"),
                    Option(_asset_type_label("skill", plural=True), id="asset-type-skill"),
                    Option(_asset_type_label("agent", plural=True), id="asset-type-agent"),
                    Option(_asset_type_label("mcp", plural=True), id="asset-type-mcp"),
                    Option(_asset_type_label("pi-extension", plural=True), id="asset-type-pi-extension"),
                    id="asset-types-list",
                )
            with Vertical(id="content"):
                with Horizontal(id="content-header-row"):
                    yield Static(self._build_content_header(), id="content-header")
                    yield ScopeToggle(active=self._scope, id="scope-toggle")
                yield InstructionGrid([], id="instruction-grid")
                yield SkillGrid([], id="skill-grid")
                yield CommandGrid([], id="command-grid")
                yield PiGrid([], id="pi-grid")
                yield AgentGrid([], id="agent-grid")
                yield McpGrid([], id="mcp-grid")
        yield Static(self._build_proj_path_markup(), id="proj-path")
        yield Static("", id="status-bar")
        with Horizontal(id="footer-status"):
            yield Static("", id="footer-pending")
            self._catalog_status_label = Static("Catalogue: not subscribed", id="catalog-status", markup=False)
            yield self._catalog_status_label
        yield Footer()

    @property
    def tui_settings(self) -> TuiSettings:
        return self._tui_settings

    def on_mount(self) -> None:
        try:
            loaded = load_settings(available_themes=self.available_themes)
        except OSError as exc:
            path = settings_path()
            loaded = TuiSettings(diagnostics=(f"{path}: unreadable settings ({exc})",))
        self._tui_settings = loaded
        self._settings_diagnostics = loaded.diagnostics
        self.theme = loaded.theme
        self._set_grid_harness_selection(loaded.harnesses)
        # Start with the skill asset type active; hide others initially.
        self._show_asset_type("skill")
        self._refresh_skill_view()
        self._refresh_content_header()
        self._refresh_proj_path()
        self._refresh_pending_label()
        self._refresh_status_bar()
        # Focus the filter box on open (#249) via the same path as every
        # asset-type switch (#477), so startup and switch cannot drift.
        self._focus_filter(self._active_asset_type)
        if not self.is_headless:
            self.run_worker(self._check_toolkit_update, thread=True, group="toolkit-update", exclusive=True)

    def _check_toolkit_update(self) -> None:
        from agent_toolkit_cli.self_update import startup_notice
        notice = startup_notice()
        if notice:
            self.call_from_thread(self.notify, notice, title="Toolkit update", timeout=15)

    # ----- asset-type switching -----------------------------------------------------

    def _show_asset_type(self, asset_type: AssetType) -> None:
        """Show the active grid and hide the inactive ones."""
        try:
            instruction_grid = self.query_one("#instruction-grid", InstructionGrid)
            skill_grid = self.query_one("#skill-grid", SkillGrid)
            command_grid = self.query_one("#command-grid", CommandGrid)
            pi_grid = self.query_one("#pi-grid", PiGrid)
            agent_grid = self.query_one("#agent-grid", AgentGrid)
            mcp_grid = self.query_one("#mcp-grid", McpGrid)
            scope_toggle = self.query_one("#scope-toggle", ScopeToggle)
        except NoMatches:
            return

        # Keep the sidebar highlight in lock-step with the displayed grid (#328).
        # This is the choke point both on_mount and action_asset_type call, so every
        # asset-type switch — however triggered — moves the highlight, not just a
        # direct click on the option.
        try:
            asset_types_list = self.query_one("#asset-types-list", SidebarOptionList)
            asset_types_list.highlighted = asset_types_list.get_option_index(
                f"asset-type-{asset_type}"
            )
        except (NoMatches, OptionDoesNotExist):
            pass

        if asset_type == "instruction":
            instruction_grid.display = True
            skill_grid.display = False
            command_grid.display = False
            pi_grid.display = False
            agent_grid.display = False
            mcp_grid.display = False
            scope_toggle.display = True
        elif asset_type == "skill":
            instruction_grid.display = False
            skill_grid.display = True
            command_grid.display = False
            pi_grid.display = False
            agent_grid.display = False
            mcp_grid.display = False
            scope_toggle.display = True
        elif asset_type == "command":
            instruction_grid.display = False
            skill_grid.display = False
            command_grid.display = True
            pi_grid.display = False
            agent_grid.display = False
            mcp_grid.display = False
            scope_toggle.display = True
        elif asset_type == "pi-extension":
            instruction_grid.display = False
            skill_grid.display = False
            command_grid.display = False
            pi_grid.display = True
            agent_grid.display = False
            mcp_grid.display = False
            scope_toggle.display = True
        elif asset_type == "agent":
            instruction_grid.display = False
            skill_grid.display = False
            command_grid.display = False
            pi_grid.display = False
            agent_grid.display = True
            mcp_grid.display = False
            scope_toggle.display = True
        else:  # "mcp"
            instruction_grid.display = False
            skill_grid.display = False
            command_grid.display = False
            pi_grid.display = False
            agent_grid.display = False
            mcp_grid.display = True
            scope_toggle.display = True

    def on_option_list_option_selected(
        self, event: SidebarOptionList.OptionSelected
    ) -> None:
        """Handle sidebar asset-type selection."""
        if event.option_list.id != "asset-types-list":
            return
        opt_id = event.option.id
        # Guard against separator or unknown options.
        if opt_id is None or opt_id.startswith("asset-type-separator"):
            return
        if opt_id == "asset-type-instruction":
            self.action_asset_type("instruction")
        elif opt_id == "asset-type-skill":
            self.action_asset_type("skill")
        elif opt_id == "asset-type-command":
            self.action_asset_type("command")
        elif opt_id == "asset-type-pi-extension":
            self.action_asset_type("pi-extension")
        elif opt_id == "asset-type-agent":
            self.action_asset_type("agent")
        elif opt_id == "asset-type-mcp":
            self.action_asset_type("mcp")

    def action_asset_type(self, asset_type: str) -> None:
        if asset_type not in (
            "instruction",
            "skill",
            "command",
            "pi-extension",
            "agent",
            "mcp",
        ):
            return
        if asset_type == self._active_asset_type:
            # Re-selecting the tab you are already on still puts the caret in
            # its filter (#477 R3). Skip the expensive refresh; that is what
            # this branch has always existed to do.
            self._focus_filter(asset_type)  # type: ignore[arg-type]
            return
        self._active_asset_type = asset_type  # type: ignore[assignment]
        self._show_asset_type(asset_type)  # type: ignore[arg-type]
        grid = self._active_grid()
        saved = grid.pending_entries() if grid is not None else {}
        self._refresh_active_view()
        if grid is not None and saved:
            grid.restore_pending(saved)  # type: ignore[arg-type]
        self._refresh_content_header()
        self._refresh_pending_label()
        self._refresh_status_bar()
        # LAST, and after _show_asset_type: a hidden Input cannot take focus,
        # and the refusal is silent (#477 R2 ordering constraint).
        self._focus_filter(asset_type)  # type: ignore[arg-type]

    # ----- instruction-view --------------------------------------------------

    def _scope_to_roots(
        self, scope: str | None = None
    ) -> tuple[str, Path | None, Path | None]:
        if (self._scope if scope is None else scope) == "global":
            return "global", Path.home(), None
        return "project", Path.home(), Path.cwd()

    def _skill_project_root(self) -> Path:
        """Project root for the Skills pane, folding a Paperclip company
        descendant to its company root. Skills-only: other asset panes keep
        their literal CWD project root."""
        from agent_toolkit_cli.paperclip_paths import normalize_skill_project_root

        return normalize_skill_project_root(Path.cwd())

    def _active_grid(
        self,
    ) -> (
        InstructionGrid | SkillGrid | CommandGrid | PiGrid | AgentGrid | McpGrid | None
    ):
        selector: str
        if self._active_asset_type == "instruction":
            selector = "#instruction-grid"
        elif self._active_asset_type == "skill":
            selector = "#skill-grid"
        elif self._active_asset_type == "command":
            selector = "#command-grid"
        elif self._active_asset_type == "pi-extension":
            selector = "#pi-grid"
        elif self._active_asset_type == "mcp":
            selector = "#mcp-grid"
        else:
            selector = "#agent-grid"
        try:
            return self.query_one(selector)  # type: ignore[return-value]
        except NoMatches:
            return None

    def _refresh_active_view(self) -> None:
        if getattr(self, "_catalog_scope", None) != self._scope:
            self._start_catalog_refresh()
        if self._active_asset_type == "instruction":
            self._refresh_instruction_view()
        elif self._active_asset_type == "skill":
            self._refresh_skill_view(reload_catalog=False)
        elif self._active_asset_type == "command":
            self._refresh_command_view()
        elif self._active_asset_type == "pi-extension":
            self._refresh_pi_view()
        elif self._active_asset_type == "mcp":
            self._refresh_mcp_view()
        else:
            self._refresh_agent_view()

    def _refresh_instruction_view(self) -> None:
        try:
            grid = self.query_one("#instruction-grid", InstructionGrid)
        except NoMatches:
            return
        scope, home, project = self._scope_to_roots()
        grid.set_harness_selection(self._tui_settings.harnesses)
        grid.set_scope(scope)  # type: ignore[arg-type]
        grid.set_rows(
            build_instruction_rows(
                scope=scope,
                home=home,
                project=project,
                selection=self._tui_settings.harnesses,
            )
        )  # type: ignore[arg-type]

    # ----- skill-view --------------------------------------------------------

    def _refresh_skill_view(self, *, reload_catalog: bool = True) -> None:
        if reload_catalog:
            self._start_catalog_refresh()
        try:
            grid = self.query_one("#skill-grid", SkillGrid)
        except NoMatches:
            return
        scope, home, _ = self._scope_to_roots()
        project = None if scope == "global" else self._skill_project_root()
        saved = grid.pending_entries()
        grid.set_harness_selection(self._tui_settings.harnesses)
        grid.set_scope(scope)
        grid.set_rows(
            build_skill_rows(
                scope=scope,
                home=home,
                project=project,
                selection=self._tui_settings.harnesses,
                catalog_snapshot=getattr(self, "_catalog_snapshot", None),
            )
        )
        grid.restore_pending(saved)

    def _set_catalog_status(self, status: str) -> None:
        if self._catalog_status_label is not None:
            self._catalog_status_label.update(f"Catalogue: {status}")

    def _start_catalog_refresh(self) -> None:
        self._catalog_snapshot = None
        self._catalog_scope = self._scope
        scope, home, _ = self._scope_to_roots()
        project = None if scope == "global" else self._skill_project_root()
        self._skill_catalog_generation = getattr(self, "_skill_catalog_generation", 0) + 1
        generation = self._skill_catalog_generation
        from agent_toolkit_cli.behavior import _read_config
        from agent_toolkit_cli.skill_catalog import read_catalog
        try:
            subscribed = _read_config(home).get("skillCatalog") is not None
        except (RuntimeError, OSError, ValueError):
            self._set_catalog_status("unavailable")
            self.notify("Invalid shared catalog subscription; local assets retained.", severity="warning")
            return
        if subscribed:
            self._set_catalog_status("refreshing…")
            def fetch():
                snapshot = read_catalog(home=home)
                try:
                    self.call_from_thread(self._finish_skill_catalog, generation, scope, home, project, snapshot)
                except RuntimeError:
                    pass  # App stopped while the bounded read was in flight.
            self.run_worker(fetch, thread=True, group="skill-catalog", exclusive=True)
        else:
            self._set_catalog_status("not subscribed")

    def _finish_skill_catalog(self, generation, scope, home, project, snapshot) -> None:
        if generation != getattr(self, "_skill_catalog_generation", 0):
            return
        if scope != self._scope:
            return
        self._catalog_snapshot = snapshot
        self._refresh_skill_view(reload_catalog=False)
        self._refresh_command_view()
        self._refresh_agent_view()
        self._refresh_pi_view()
        if snapshot is not None and snapshot.error:
            self._set_catalog_status("unavailable")
            self.notify(f"{snapshot.error}; catalog-only entries hidden.", title="Shared catalog", severity="warning")
        elif snapshot is not None:
            self._set_catalog_status(snapshot.version or "unversioned")
        else:
            self._set_catalog_status("not subscribed")
        self._refresh_pending_label()
        self._refresh_status_bar()

    # ----- command-view -----------------------------------------------------

    def _refresh_command_view(self) -> None:
        try:
            grid = self.query_one("#command-grid", CommandGrid)
        except NoMatches:
            return
        scope, home, project = self._scope_to_roots()
        saved = grid.pending_entries()
        grid.set_harness_selection(self._tui_settings.harnesses)
        grid.set_scope(scope)
        grid.set_rows(build_command_rows(scope=scope, home=home, project=project,
            selection=self._tui_settings.harnesses,
            catalog_snapshot=getattr(self, "_catalog_snapshot", None)))
        grid.restore_pending(saved)

    # ----- pi-view -----------------------------------------------------------

    def _refresh_pi_view(self) -> None:
        try:
            grid = self.query_one("#pi-grid", PiGrid)
        except NoMatches:
            return
        from agent_toolkit_cli._pi_settings import PiSettingsError

        pending = grid.pending_entries()
        local_targets = grid.pending_local_targets()
        npm_snapshots = grid.pending_npm_snapshots()
        # Scope follows the visible application toggle even if rebuilding fails.
        grid.set_scope(self._scope)  # type: ignore[arg-type]
        try:
            rows = build_pi_rows(home=Path.home(), project=Path.cwd(),
                catalog_snapshot=getattr(self, "_catalog_snapshot", None))
        except (PiSettingsError, OSError, ValueError) as exc:
            grid.restore_pending(pending, local_targets=local_targets, npm_snapshots=npm_snapshots)
            self.notify(str(exc), title="Pi refresh failed", severity="error", timeout=12)
            return
        grid.set_rows(rows)
        grid.restore_pending(pending, local_targets=local_targets, npm_snapshots=npm_snapshots)

    # ----- agent-view --------------------------------------------------------

    def _refresh_agent_view(self) -> None:
        try:
            grid = self.query_one("#agent-grid", AgentGrid)
        except NoMatches:
            return
        scope, home, project = self._scope_to_roots()
        saved = grid.pending_entries()
        grid.set_harness_selection(self._tui_settings.harnesses)
        grid.set_scope(scope)
        grid.set_rows(build_agent_rows(scope=scope, home=home, project=project,
            selection=self._tui_settings.harnesses,
            catalog_snapshot=getattr(self, "_catalog_snapshot", None)))
        grid.restore_pending(saved)

    # ----- mcp-view ----------------------------------------------------------

    def _refresh_mcp_view(self) -> None:
        try:
            grid = self.query_one("#mcp-grid", McpGrid)
        except NoMatches:
            return
        scope, home, project = self._scope_to_roots()
        grid.set_harness_selection(self._tui_settings.harnesses)
        grid.set_scope(scope)  # type: ignore[arg-type]
        grid.set_rows(
            build_mcp_rows(
                scope=scope,
                home=home,
                project=project,
                selection=self._tui_settings.harnesses,
            )
        )  # type: ignore[arg-type]

    def _set_grid_harness_selection(self, selection: tuple[str, ...]) -> None:
        """Set the selection on every harness grid, including hidden tabs."""
        grids = (
            ("#instruction-grid", InstructionGrid),
            ("#skill-grid", SkillGrid),
            ("#command-grid", CommandGrid),
            ("#agent-grid", AgentGrid),
            ("#mcp-grid", McpGrid),
        )
        for selector, grid_type in grids:
            try:
                self.query_one(selector, grid_type).set_harness_selection(selection)
            except NoMatches:
                pass

    def _refresh_all_views(self) -> None:
        """Rebuild every asset grid after a committed harness change."""
        self._refresh_instruction_view()
        self._refresh_skill_view()
        self._refresh_command_view()
        self._refresh_pi_view()
        self._refresh_agent_view()
        self._refresh_mcp_view()

    # ----- messages ----------------------------------------------------------

    def on_instruction_grid_pending_changed(
        self, event: InstructionGrid.PendingChanged
    ) -> None:
        """Live-update footer + status bar when the instruction grid's pending set changes."""
        self._refresh_pending_label()
        self._refresh_status_bar()

    def on_skill_grid_pending_changed(self, event: SkillGrid.PendingChanged) -> None:
        """Live-update footer + status bar when the skill grid's pending set changes."""
        self._refresh_pending_label()
        self._refresh_status_bar()

    def on_command_grid_pending_changed(
        self, event: CommandGrid.PendingChanged
    ) -> None:
        """Live-update footer + status bar when command grid pending changes."""
        self._refresh_pending_label()
        self._refresh_status_bar()

    def on_pi_grid_pending_changed(self, event: PiGrid.PendingChanged) -> None:
        """Live-update footer + status bar when the pi grid's pending set changes."""
        self._refresh_pending_label()
        self._refresh_status_bar()

    def on_agent_grid_pending_changed(self, event: AgentGrid.PendingChanged) -> None:
        """Live-update footer + status bar when the agent grid's pending set changes."""
        self._refresh_pending_label()
        self._refresh_status_bar()

    def on_mcp_grid_pending_changed(self, event: McpGrid.PendingChanged) -> None:
        """Live-update footer + status bar when the MCP grid's pending set changes."""
        self._refresh_pending_label()
        self._refresh_status_bar()

    # ----- actions -----------------------------------------------------------

    def _all_grids(self) -> list[Any]:
        """Collect all mounted grid widgets across the six asset types."""
        grids: list[Any] = []
        for selector in (
            "#instruction-grid",
            "#skill-grid",
            "#command-grid",
            "#pi-grid",
            "#agent-grid",
            "#mcp-grid",
        ):
            try:
                grids.append(self.query_one(selector))
            except Exception:
                pass
        return grids

    def _get_all_pending_edits(self) -> dict[tuple[str, ...], str]:
        """Namespace pending keys by grid, retaining scope as the first field."""
        pending: dict[tuple[str, ...], str] = {}
        for selector in (
            "#instruction-grid",
            "#skill-grid",
            "#command-grid",
            "#pi-grid",
            "#agent-grid",
            "#mcp-grid",
        ):
            try:
                grid = self.query_one(selector)
                pending.update(
                    {(*key, selector): op for key, op in grid.pending_entries().items()}
                )
            except Exception:
                pass
        return pending

    def _get_pending_asset_types(self) -> set[str]:
        """Return the set of asset types that currently have queued pending edits."""
        pending_types: set[str] = set()
        type_selectors = (
            ("instruction", "#instruction-grid"),
            ("command", "#command-grid"),
            ("skill", "#skill-grid"),
            ("pi-extension", "#pi-grid"),
            ("agent", "#agent-grid"),
            ("mcp", "#mcp-grid"),
        )
        for asset_type, selector in type_selectors:
            try:
                grid = self.query_one(selector)
                if grid.pending_entries():
                    pending_types.add(asset_type)
            except Exception:
                pass
        return pending_types

    def action_double_ctrl_c_quit(self) -> None:
        now = monotonic()
        last = self._last_ctrl_c_quit_at
        if last is not None and now - last <= _DOUBLE_CTRL_C_QUIT_SECONDS:
            self._last_ctrl_c_quit_at = None
            self.action_quit()
            return

        self._last_ctrl_c_quit_at = now
        self.notify("Press ctrl+c again to quit")

    def action_quit(self) -> None:
        n = len(self._get_all_pending_edits())
        if n == 0:
            self.exit()
            return

        def _on_close(discard: bool | None) -> None:
            if discard:
                self.exit()

        self.push_screen(ConfirmDiscardScreen(n), _on_close)

    def action_scope(self, scope: str) -> None:
        if scope not in ("global", "project") or scope == self._scope:
            return
        self._scope = scope
        try:
            self.query_one("#scope-toggle", ScopeToggle).set_active(scope)
        except NoMatches:
            pass
        # Preserve pending across the toggle (#349): set_scope/set_rows clear
        # by contract, so save the active grid's queue and put it back. One
        # app-side site — no per-grid preservation logic.
        grid = self._active_grid()
        saved = grid.pending_entries() if grid is not None else {}
        self._refresh_active_view()
        if grid is not None and saved:
            grid.restore_pending(saved)  # type: ignore[arg-type]
        self._refresh_content_header()
        self._refresh_pending_label()
        self._refresh_status_bar()

    def action_scope_toggle(self) -> None:
        self.action_scope("global" if self._scope == "project" else "project")

    def action_focus_sidebar(self) -> None:
        """Focus the sidebar OptionList."""
        try:
            self.query_one("#asset-types-list").focus()
        except Exception:
            pass

    def _focus_filter(self, asset_type: AssetType) -> None:
        """Focus `asset_type`'s filter input. No-op if it is not mounted.

        Non-destructive by contract (#477): it must not touch filter text,
        pending queues, scope, or cursor coordinate.
        """
        selector = _FILTER_SELECTORS.get(asset_type)
        if selector is None:
            return
        try:
            self.query_one(selector, Input).focus()
        except NoMatches:
            return

    def action_focus_filter(self) -> None:
        """`/` or Escape re-focuses the active asset pane's filter box."""
        self._focus_filter(self._active_asset_type)

    def action_info_pass(self) -> None:
        """Delegate `i` to the active grid widget."""
        grid = self._active_grid()
        if grid is not None:
            grid.action_info()

    def search_themes(self) -> None:
        from textual.command import CommandPalette

        self.push_screen(
            CommandPalette(
                providers=[PersistentThemeProvider],
                placeholder="Search for themes…",
            )
        )

    def action_main_harnesses(self) -> None:
        self.search_main_harnesses()

    def search_main_harnesses(self) -> None:
        display_names = {
            key: (config.display_name if (config := AGENTS.get(key)) else key)
            for key in MAIN_HARNESS_CANDIDATES
        }

        def _on_close(result: tuple[str, ...] | None) -> None:
            if result is not None:
                self._commit_harness_selection(result)

        self.push_screen(
            MainHarnessSelectScreen(
                candidates=MAIN_HARNESS_CANDIDATES,
                display_names=display_names,
                selected=self._tui_settings.harnesses,
            ),
            _on_close,
        )

    def _commit_harness_selection(self, new_selection: tuple[str, ...]) -> None:
        """Apply a harness selection, prompting once if pending edits exist."""
        if new_selection == self._tui_settings.harnesses:
            return

        n_pending = len(self._get_all_pending_edits())
        if n_pending == 0:
            self.apply_harness_settings(new_selection)
            return

        def _on_confirm(discard: bool | None) -> None:
            if discard:
                self.apply_harness_settings(new_selection)

        msg = f"Discard {n_pending} pending change(s) and update main harnesses?"
        self.push_screen(ConfirmDiscardScreen(n_pending, message=msg), _on_confirm)

    def toggle_main_harness(self, harness: str) -> None:
        """Toggle a single main harness, prompting if pending edits exist."""
        current = self._tui_settings.harnesses
        if harness in current:
            new_selection = tuple(h for h in current if h != harness)
        else:
            new_set = set(current) | {harness}
            new_selection = tuple(h for h in MAIN_HARNESS_CANDIDATES if h in new_set)
        self._commit_harness_selection(new_selection)

    def apply_theme_setting(self, theme: str) -> bool:
        """Atomically persist and then apply a theme, preserving harness state."""
        if theme not in self.available_themes:
            self.notify(
                f"Theme {theme!r} is not available.",
                title="Settings not saved",
                severity="error",
            )
            return False
        if theme == self._tui_settings.theme:
            return True

        updated = replace(self._tui_settings, theme=theme, retained_theme=None)
        try:
            save_settings(updated)
        except (OSError, SettingsPathError, SettingsWriteError) as exc:
            self.notify(
                str(exc),
                title="Settings not saved",
                severity="error",
            )
            return False

        self._tui_settings = updated
        self.theme = theme
        return True

    def apply_harness_settings(self, harnesses: tuple[str, ...]) -> bool:
        """Persist harness drafts, rebuild every grid, and keep constants intact."""
        updated = replace(self._tui_settings, harnesses=harnesses)
        try:
            save_settings(updated)
        except (OSError, SettingsPathError, SettingsWriteError) as exc:
            self.notify(
                str(exc),
                title="Settings not saved",
                severity="error",
            )
            return False

        self._tui_settings = updated
        self._set_grid_harness_selection(harnesses)
        for grid in self._all_grids():
            grid.clear_pending()
        # set_rows clears pending queues by the existing grid contract. This is
        # intentionally disclosed in the PR rather than hidden behind new v1
        # persistence semantics (#480 plan Task 3 Step 5).
        self._refresh_all_views()
        self._refresh_content_header()
        self._refresh_pending_label()
        self._refresh_status_bar()
        return True

    def action_refresh(self) -> None:
        self._start_catalog_refresh()
        # Drop previous live listings across all four grids while the new read runs.
        self._refresh_skill_view(reload_catalog=False)
        self._refresh_command_view()
        self._refresh_agent_view()
        self._refresh_pi_view()
        grid = self._active_grid()
        # Local Pi intents carry a target snapshot. Keep those only; other
        # assets retain their existing refresh-discard behavior.
        if isinstance(grid, PiGrid):
            targets = grid.pending_local_targets()
            npm_snapshots = grid.pending_npm_snapshots()
            native_pending = {key: op for key, op in grid.pending_entries().items() if key in targets or key in npm_snapshots}
            grid.clear_pending()
            grid.restore_pending(native_pending, local_targets=targets, npm_snapshots=npm_snapshots)
        elif grid is not None:
            grid.clear_pending()
        self._refresh_active_view()
        self._refresh_proj_path()
        self._refresh_pending_label()
        self._refresh_content_header()
        self._refresh_status_bar()

    def action_revert(self) -> None:
        # ctrl+z clears the pending queue across all asset types and both scopes (#349, #517).
        all_pending = self._get_all_pending_edits()
        keys = list(all_pending.keys())
        n = len(keys)
        for grid in self._all_grids():
            try:
                grid.clear_pending()
            except Exception:
                pass
        self._refresh_pending_label()
        self.query_one("#footer-pending", Static).update(
            f"reverted: {n} pending cleared{_scope_tag(keys)}"
        )

    def action_diff(self) -> None:
        pending = self._get_all_pending_edits()
        n_link = sum(1 for op in pending.values() if op == "link")
        n_unlink = sum(1 for op in pending.values() if op == "unlink")
        n_reset = sum(1 for op in pending.values() if op == "reset")
        resets = f", {n_reset} would-reset" if n_reset else ""
        self.query_one("#footer-pending", Static).update(
            f"diff: {n_link} would-link, {n_unlink} would-unlink{resets}{_scope_tag(pending.keys())}"
        )

    def _apply_for_asset_type(self, asset_type: str) -> ApplyResult | None:
        """Dispatch apply for a specific asset type."""
        if asset_type == "instruction":
            return self._apply_instruction_pending()
        if asset_type == "command":
            return self._apply_command_pending()
        if asset_type == "skill":
            return self._apply_skill_pending()
        if asset_type == "pi-extension":
            return self._apply_pi_pending()
        if asset_type == "mcp":
            return self._apply_mcp_pending()
        if asset_type == "agent":
            return self._apply_agent_pending()
        return None

    def action_apply(self) -> None:
        from agent_toolkit_cli.pi_npm import settings_path as pi_settings_path
        from agent_toolkit_tui.screens.pi_project_blocks import PiProjectBlocksScreen

        if isinstance(self.screen, PiProjectBlocksScreen):
            return
        try:
            grid = self.query_one("#pi-grid", PiGrid)
        except NoMatches:
            grid = None
        blocks = grid.pending_project_blocks() if grid is not None else ()
        if not blocks:
            self._apply_pending_edits()
            return

        # Consent covers this exact batch and target, never edits made while
        # the modal is open. Native Apply still enforces settings freshness.
        pending = self._get_all_pending_edits()
        snapshots = grid.pending_npm_snapshots()
        project = Path.cwd()

        def on_review(confirmed: bool) -> None:
            if not confirmed:
                return
            if (pending != self._get_all_pending_edits()
                    or snapshots != grid.pending_npm_snapshots()
                    or project != Path.cwd()):
                self.notify("Pending changes or project changed; press Ctrl+S to review again.", severity="warning")
                return
            self._apply_pending_edits()

        self.push_screen(PiProjectBlocksScreen(
            packages=blocks, project=project,
            settings=pi_settings_path(scope="project", home=Path.home(), project=project),
            pending_count=len(pending),
            asset_types=tuple(sorted(_asset_type_label(kind, plural=True)
                                     for kind in self._get_pending_asset_types())),
        ), on_review)

    def _apply_pending_edits(self) -> None:
        pending_types = self._get_pending_asset_types()
        if not pending_types:
            # Preserve dispatch when nothing is pending (tests / no-op)
            if self._active_asset_type == "instruction":
                self._apply_instruction_pending()
            elif self._active_asset_type == "skill":
                self._apply_skill_pending()
            elif self._active_asset_type == "command":
                self._apply_command_pending()
            elif self._active_asset_type == "pi-extension":
                self._apply_pi_pending()
            elif self._active_asset_type == "mcp":
                self._apply_mcp_pending()
            else:
                self._apply_agent_pending()
            return

        order = ("instruction", "command", "skill", "agent", "mcp", "pi-extension")
        results: list[ApplyResult] = []
        from agent_toolkit_cli.skill_catalog import read_catalog
        needs_catalog = any(getattr(grid, "pending_catalog_entries", lambda: {})() for grid in self._all_grids())
        self._catalog_apply_snapshot = read_catalog() if needs_catalog else None
        try:
            for asset_type in order:
                if asset_type in pending_types:
                    res = self._apply_for_asset_type(asset_type)
                    if isinstance(res, ApplyResult):
                        results.append(res)
        finally:
            del self._catalog_apply_snapshot

        if len(results) > 1:
            total_ok = sum(r.ok for r in results)
            total_failed = sum(r.failed for r in results)
            all_errors = [e for r in results for e in r.errors]
            all_keys = [k for r in results for k in r.keys]
            tag = _scope_tag(all_keys)
            self._refresh_pending_label()
            self._refresh_status_bar()
            if all_errors:
                first = " ".join(all_errors[0].split())
                extra = f" (+{len(all_errors) - 1} more)" if len(all_errors) > 1 else ""
                self.query_one("#footer-pending", Static).update(
                    f"[red]apply failed[/] — {first}{extra}{tag}"
                )
                self.notify(
                    "\n\n".join(all_errors),
                    title=f"Apply: {total_ok} ok, {total_failed} failed",
                    severity="error",
                    timeout=12,
                )
            else:
                self.query_one("#footer-pending", Static).update(
                    f"applied: {total_ok} ok, {total_failed} failed{tag}"
                )

    def _apply_instruction_pending(self) -> ApplyResult | None:
        """Apply explicit pointer intents; inventory remains the installation truth."""
        from agent_toolkit_cli import instructions_install
        from agent_toolkit_cli.instructions_adapters.symlink import canonical_usable, inspect_pointer
        from agent_toolkit_tui.instruction_state import pointer_path_for

        try:
            grid = self.query_one("#instruction-grid", InstructionGrid)
        except NoMatches:
            return None
        pending = grid.pending_entries()
        if not pending:
            return None
        tag = _scope_tag(pending)
        batches = {}
        errors: list[str] = []
        try:
            # Guard every scope before writes, including canonical-chain protection.
            for scope, _, _ in pending:
                if scope in batches:
                    continue
                project = Path.cwd() if scope == "project" else None
                home = Path.home() if scope == "global" else None
                adds = [h for (s, h, slug), op in pending.items() if s == scope and op == "link"]
                removes = [h for (s, h, slug), op in pending.items() if s == scope and op == "unlink"]
                if any(slug != "AGENTS.md" for s, h, slug in pending if s == scope):
                    raise ValueError("Instructions only supports AGENTS.md")
                instructions_install.plan(
                    scope=scope, project_root=project, home=home,
                    add_harnesses=adds, remove_harnesses=removes,
                )
                batches[scope] = (project, home, adds, removes)
        except (OSError, RuntimeError, ValueError, KeyError) as exc:
            errors.append(str(exc))
        if not errors:
            for scope, (project, home, adds, removes) in batches.items():
                try:
                    instructions_install.apply(
                        scope=scope, project_root=project, home=home,
                        add_harnesses=adds, remove_harnesses=removes,
                    )
                except (OSError, RuntimeError, ValueError, KeyError) as exc:
                    errors.append(f"{scope}: {exc}")

        remaining = {}
        for key, op in pending.items():
            scope, harness, slug = key
            project = Path.cwd() if scope == "project" else None
            home = Path.home() if scope == "global" else None
            try:
                canonical = instructions_install._resolve_canonical(scope, project)
                pointer = pointer_path_for(harness, scope=scope, home=home, project=project)
                if pointer is None:
                    remaining[key] = op
                    continue
                state = inspect_pointer(pointer, canonical)
                satisfied = (
                    state.linked and canonical_usable(canonical) if op == "link"
                    else not state.linked and not state.conflict
                )
                if not satisfied:
                    remaining[key] = op
            except (OSError, RuntimeError, ValueError, KeyError):
                remaining[key] = op
        failed = len(remaining)
        ok = len(pending) - failed
        grid.clear_pending()
        self._refresh_instruction_view()
        if remaining:
            grid.restore_pending(remaining)
        self._refresh_pending_label()
        self._refresh_status_bar()
        if failed and not errors:
            errors.append("Some pointer intents remain unsatisfied; inspect conflicts before retrying.")
        if errors:
            first = " ".join(errors[0].split())
            extra = f" (+{len(errors) - 1} more)" if len(errors) > 1 else ""
            self.query_one("#footer-pending", Static).update(
                f"[red]apply failed[/] — {first}{extra}{tag}"
            )
            self.notify(
                "\n\n".join(errors), title=f"Apply: {ok} ok, {failed} failed",
                severity="error", timeout=12,
            )
        else:
            self.query_one("#footer-pending", Static).update(
                f"applied: {ok} ok, {failed} failed{tag}"
            )
        return ApplyResult(
            ok=ok, failed=failed, errors=errors, keys=list(pending.keys())
        )

    def _apply_command_pending(self) -> ApplyResult | None:
        """Apply pending Commands Standard/Pi/Gemini toggles via the facade."""
        from agent_toolkit_cli._install_core import InstallError, InstallPlan
        from agent_toolkit_cli import command_install

        try:
            grid = self.query_one("#command-grid", CommandGrid)
        except NoMatches:
            return None
        pending = grid.pending_entries()
        if not pending:
            return None
        tag = _scope_tag(pending)
        by_slug: dict[tuple[str, str], tuple[set[str], set[str]]] = defaultdict(
            lambda: (set(), set())
        )
        for (scope, harness, slug), op in pending.items():
            adds, removes = by_slug[(scope, slug)]
            (adds if op == "link" else removes).add(harness)

        ok = failed = 0
        errors: list[str] = []
        failed_groups: set[tuple[str, str]] = set()
        from agent_toolkit_tui.catalog_apply import prepare_entry, snapshot_for
        catalog_pending = grid.pending_catalog_entries()
        snapshot = snapshot_for(self, catalog_pending)
        for (scope, slug), (adds, removes) in by_slug.items():
            n_writes = len(adds) + len(removes)
            _, apply_home, project = self._scope_to_roots(scope)
            p = InstallPlan(
                slug=slug,
                scope=scope,  # type: ignore[arg-type]
                source=None,
                ref=None,
                add_agents=tuple(sorted(adds)),
                remove_agents=tuple(sorted(removes)),
            )
            try:
                if adds:
                    prepare_entry("command", slug, intents=catalog_pending, snapshot=snapshot,
                        targets=adds, scope=scope, home=apply_home or Path.home(), project=project)
                result = command_install.apply(p, home=apply_home, project=project)
                ok += len(result.created) + len(result.removed)
            except (InstallError, ValueError) as exc:
                errors.append(f"{slug}: {exc}")
                failed += n_writes
                failed_groups.add((scope, slug))

        saved = (
            {
                k: v
                for k, v in grid.pending_entries().items()
                if (k[0], k[2]) in failed_groups
            }
            if failed
            else {}
        )
        grid.clear_pending()
        self._refresh_command_view()
        if saved:
            grid.restore_pending(saved)
        grid.restore_catalog_pending(catalog_pending)
        self._refresh_pending_label()
        self._refresh_status_bar()
        if errors:
            first = " ".join(errors[0].split())
            extra = f" (+{len(errors) - 1} more)" if len(errors) > 1 else ""
            self.query_one("#footer-pending", Static).update(
                f"[red]apply failed[/] — {first}{extra}{tag}"
            )
            self.notify(
                "\n\n".join(errors),
                title=f"Apply: {ok} ok, {failed} failed",
                severity="error",
                timeout=12,
            )
        else:
            self.query_one("#footer-pending", Static).update(
                f"applied: {ok} ok, {failed} failed{tag}"
            )
        return ApplyResult(
            ok=ok, failed=failed, errors=errors, keys=list(pending.keys())
        )

    def _apply_skill_pending(self) -> ApplyResult | None:
        from agent_toolkit_cli.skill_install import (
            InstallError,
            InstallPlan,
            apply as engine_apply,
            validate_projection_context,
        )
        from agent_toolkit_cli.skill_paths import library_lock_path

        try:
            grid = self.query_one("#skill-grid", SkillGrid)
        except NoMatches:
            return None
        pending = grid.pending_entries()
        if not pending:
            return None
        tag = _scope_tag(pending)
        from agent_toolkit_cli.skill_collections import catalog, exposed
        from agent_toolkit_cli.skill_install import apply_collection_selection as apply_selection
        handled: set[tuple[str, str, str]] = set()
        failed_keys: set[tuple[str, str, str]] = set()
        ok = failed = 0
        errors: list[str] = []
        failed_groups: set[tuple[str, str]] = set()
        # Only remote-only selections need catalog connectivity. Local operations
        # remain usable even if the catalog is offline or no longer subscribed.
        from agent_toolkit_tui.skill_catalog_apply import prepare_catalog_acquisitions
        catalog_pending = grid.pending_catalog_entries()
        intents = grid.pending_skill_intents()
        prepared = prepare_catalog_acquisitions(
            pending, intents, home=Path.home(),
            project=self._skill_project_root() if any(k[0] == 'project' for k in pending) else None,
            **({"snapshot": self._catalog_apply_snapshot} if hasattr(self, "_catalog_apply_snapshot") else {}),
        )
        failed_keys.update(prepared.blocked)
        failed += len(prepared.blocked)
        errors.extend(prepared.errors)
        pending = {key: op for key, op in pending.items() if key not in failed_keys}
        for scope in {k[0] for k in pending}:
            home = Path.home()
            project = None if scope == "global" else self._skill_project_root()
            try:
                groups = catalog(scope=scope, home=home, project=project)
            except (InstallError, OSError) as exc:
                keys = {k for k in pending if k[0] == scope}
                handled.update(keys)
                failed_keys.update(keys)
                failed += len(keys)
                errors.append(str(exc))
                continue
            from agent_toolkit_cli.skill_lock import read_lock
            from agent_toolkit_cli.skill_paths import lock_file_path
            records = {**read_lock(library_lock_path()).skills,
                       **read_lock(lock_file_path(scope=scope, home=home, project=project)).skills}
            # One registered child still needs a transaction spanning all requested
            # harnesses; display-only advertised siblings must never enter it.
            from agent_toolkit_cli.skill_collections import Collection, Child
            from agent_toolkit_cli.skill_paths import canonical_skill_dir
            from agent_toolkit_cli.skill_catalog_ops import skill_identity
            covered = {n for group in groups for n in group.children}
            covered.update(n for group in groups for n in (*group.containers, *group.container_conflicts, group.wrapper) if n is not None)
            for slug, entry in records.items():
                identity = skill_identity(entry)[:2]
                has_nested = any(e.parent_url is not None and skill_identity(e)[:2] == identity for e in records.values())
                requested = any(k[0] == scope and k[2] in records and skill_identity(records[k[2]])[:2] == identity for k in pending)
                if slug in covered or not requested or (entry.parent_url is None and not has_nested):
                    continue
                group = next((g for g in groups if g.wrapper is None and all(skill_identity(c.entry)[:2] == identity for c in g.children.values())), None)
                if group is None:
                    group = Collection(entry.source, entry.ref)
                    groups.append(group)
                group.children[slug] = Child(slug, entry, canonical_skill_dir(slug, scope=scope, home=home, project=project).resolve())
                covered.add(slug)
            owners = {n: skill_identity(e)[:2] for n, e in records.items()}
            for group in groups:
                for name, child in group.children.items():
                    owners.setdefault(name, skill_identity(child.entry)[:2])
            for group in groups:
                identity = skill_identity(next(iter(group.children.values())).entry)[:2]
                agents = {k[1] for k in pending if k[0] == scope and k[2] in group.children and owners.get(k[2]) == identity}
                keys = {k for k in pending if k[0] == scope and k[1] in agents and k[2] in group.children and owners.get(k[2]) == identity}
                if not keys:
                    continue
                handled.update(keys)
                selections = {}
                for agent in agents:
                    selected = {n for n, c in group.children.items() if exposed(
                        c, group, agent, scope=scope, home=home, project=project)}
                    for key in keys:
                        if key[1] == agent:
                            if pending[key] == "link": selected.add(key[2])
                            else: selected.discard(key[2])
                    selections[agent] = selected
                try:
                    apply_selection(group, selections, scope=scope, home=home, project=project)
                    ok += len(keys)
                except (InstallError, OSError) as exc:
                    failed_keys.update(keys)
                    failed += len(keys)
                    errors.append(f"{group.label}: {exc}")
        by_slug: dict[tuple[str, str], tuple[set[str], set[str]]] = defaultdict(
            lambda: (set(), set())
        )
        for (scope, agent, slug), op in pending.items():
            if (scope, agent, slug) in handled:
                continue
            adds, removes = by_slug[(scope, slug)]
            (adds if op == "link" else removes).add(agent)
        for (scope, slug), (adds, removes) in by_slug.items():
            n_writes = len(adds) + len(removes)
            home = Path.home() if scope == "global" else None
            project = None if scope == "global" else self._skill_project_root()
            if scope == "project":
                try:
                    # Fail loudly on an invalid Paperclip projection before any
                    # canonical materialization or lock write.
                    validate_projection_context(
                        slug=slug,
                        target_agents=(*adds, *removes),
                        scope=scope,
                        home=home,
                        project=project,
                    )
                except InstallError as exc:
                    errors.append(f"{slug}: {exc}")
                    failed += n_writes
                    failed_groups.add((scope, slug))
                    continue
            p = InstallPlan(
                slug=slug,
                scope=scope,
                source=None,
                ref=None,
                add_agents=tuple(sorted(adds)),
                remove_agents=tuple(sorted(removes)),
            )
            try:
                result = engine_apply(p, home=home, project=project, env=None)
                ok += len(result.created) + len(result.removed)
                if scope == "project" and not adds:
                    self._drop_project_entry_if_unlisted_and_unlinked(
                        slug=slug,
                        project=project,  # type: ignore[arg-type]
                    )
            except InstallError as exc:
                errors.append(f"{slug}: {exc}")
                failed += n_writes
                failed_groups.add((scope, slug))
        # Restore only the ops of FAILED (scope, slug) groups (#360 G1).
        # Successfully applied ops must never be re-queued: replaying a full
        # unlisted uninstall (entry dropped, row gone) would fail with
        # "not in global library" on every subsequent Apply, holding the
        # genuinely-failed group's retry hostage.
        saved = (
            {
                k: v
                for k, v in grid.pending_entries().items()
                if k in failed_keys or (k[0], k[2]) in failed_groups
            }
            if failed
            else {}
        )
        saved_catalog = {key: value for key, value in catalog_pending.items() if key in saved}
        saved_intents = {key: value for key, value in intents.items() if key in saved}
        if failed and prepared.acquired:
            errors.append('Retained in library: ' + ', '.join(prepared.acquired))
        grid.clear_pending()
        self._refresh_skill_view()
        if saved:
            grid.restore_pending(saved, intents=saved_intents)
            grid._catalog_pending.update(saved_catalog)
        self._refresh_pending_label()
        self._refresh_status_bar()
        if errors:
            first = " ".join(errors[0].split())
            extra = f" (+{len(errors) - 1} more)" if len(errors) > 1 else ""
            self.query_one("#footer-pending", Static).update(
                f"[red]apply failed[/] — {first}{extra}{tag}"
            )
            self.notify(
                "\n\n".join(errors),
                title=f"Apply: {ok} ok, {failed} failed",
                severity="error",
                timeout=12,
            )
        else:
            self.query_one("#footer-pending", Static).update(
                f"applied: {ok} ok, {failed} failed{tag}"
            )
        return ApplyResult(
            ok=ok, failed=failed, errors=errors, keys=list(pending.keys())
        )

    def _drop_project_entry_if_unlisted_and_unlinked(
        self,
        *,
        slug: str,
        project: Path,
    ) -> None:
        """Forget only an unlinked CENTRAL projection registration.

        Private provenance is backing ownership, not activation state. Keep it
        even when unlisted, so detach/status/re-registration/reinstall works
        without adopting an unrecorded directory or enabling new isolation.
        """
        from agent_toolkit_cli.skill_agents import AGENTS
        from agent_toolkit_cli.skill_lock import read_lock, remove_entry, write_lock
        from agent_toolkit_cli.skill_paths import (
            library_lock_path, lock_file_path, canonical_skill_dir, library_skill_path,
        )
        from agent_toolkit_tui.skill_state import _cell_for

        if canonical_skill_dir(slug, scope="project", project=project) != library_skill_path(slug):
            return  # retained private backing needs its recorded identity
        if slug in read_lock(library_lock_path()).skills:
            return  # listed — out of scope for the drop rule
        # Probe the FULL agent universe, not just the rendered columns: a
        # long-tail projection installed via the CLI must block the drop,
        # otherwise the entry vanishes while a live symlink remains and
        # doctor then offers destructive cleanup of a functional install.
        # Mirrors skill_doctor._scan_stray_symlinks' universe.
        probe = ("standard", *(a for a in AGENTS if not AGENTS[a].is_standard))
        for agent in probe:
            cell = _cell_for(slug, agent, scope="project", home=None, project=project)
            if cell.skipped:
                continue  # skipped cells report linked=canonical-exists, not a symlink
            if cell.linked or cell.drift:
                return  # a projection remains — not a full uninstall
        lpath = lock_file_path(scope="project", project=project)
        lock = read_lock(lpath)
        if slug in lock.skills:
            write_lock(lpath, remove_entry(lock, slug))

    def _apply_pi_pending(self) -> ApplyResult | None:
        from agent_toolkit_cli import (
            _pi_settings,
            pi_extension_install,
            pi_extension_ops,
        )
        from agent_toolkit_cli.pi_local_extensions import set_local_extension_enabled
        from agent_toolkit_cli.pi_npm import set_npm_enabled, reset_npm_override
        from agent_toolkit_cli.pi_extension_lock import read_lock
        from agent_toolkit_cli.pi_extension_paths import library_lock_path

        try:
            grid = self.query_one("#pi-grid", PiGrid)
        except NoMatches:
            return None
        pending = grid.pending_entries()
        if not pending:
            return None
        tag = _scope_tag(pending)

        home = Path.home()
        ok = failed = 0
        errors: list[str] = []

        local_targets = grid.pending_local_targets()
        npm_snapshots = grid.pending_npm_snapshots()
        catalog_pending = grid.pending_catalog_entries()
        from agent_toolkit_tui.catalog_apply import prepare_entry, snapshot_for
        snapshot = snapshot_for(self, catalog_pending)
        remaining = {}
        glob_lock = None
        _Scope = Literal["global", "project"]
        operations = list(pending.items())
        # Project snapshots bind inherited global filters. Apply those intents
        # first rather than weakening freshness checks for our own global edit.
        for index, (key, _op) in enumerate(operations):
            if key[0] == "global" and key in npm_snapshots:
                project_key = ("project", key[1])
                other = next((i for i, (candidate, _) in enumerate(operations) if candidate == project_key), -1)
                if other > index and project_key in npm_snapshots:
                    operations[index], operations[other] = operations[other], operations[index]
        for (scope_str, slug), op in operations:
            scope = cast(_Scope, scope_str)
            key = (scope_str, slug)
            try:
                if key in npm_snapshots:
                    if op == "reset":
                        reset_npm_override(identity=slug, scope=scope, home=home, project=Path.cwd(), expected_snapshot=npm_snapshots[key])
                    else:
                        set_npm_enabled(identity=slug, enabled=op == "link", scope=scope, home=home, project=Path.cwd(), expected_snapshot=npm_snapshots[key])
                elif key in local_targets:
                    # Local configuration has no dependency on a Toolkit lock.
                    set_local_extension_enabled(
                        slug=slug, scope=scope, enabled=op == "link",
                        home=home, project=Path.cwd(),
                        expected_paths=local_targets[key],
                    )
                else:
                    if key in catalog_pending:
                        prepare_entry("pi-extension", slug, intents=catalog_pending, snapshot=snapshot,
                            targets=("pi",), scope=scope, home=home,
                            project=Path.cwd() if scope == "project" else None)
                        glob_lock = None  # Acquisition may have added a new library record.
                    if glob_lock is None:
                        try:
                            glob_lock = read_lock(library_lock_path(env={}))
                        except Exception as exc:
                            raise _pi_settings.PiSettingsError(f"global lock: {exc}") from exc
                    if slug not in glob_lock.skills or glob_lock.skills[slug].source_type == "npm":
                        raise _pi_settings.PiSettingsError(
                            f"{slug}: no longer registered or missing local target snapshot; refresh and queue again"
                        )
                    project = Path.cwd() if scope == "project" else None
                    if op == "link":
                        pi_extension_ops.install(slug=slug, scope=scope, home=home, project=project, git_only=True)
                    else:
                        pi_extension_ops.uninstall(slug=slug, scope=scope, home=home, project=project, git_only=True)
                ok += 1
            except (
                pi_extension_install.InstallError,
                _pi_settings.PiSettingsError, ValueError, RuntimeError,
            ) as exc:
                errors.append(f"{slug}: {exc}")
                failed += 1
                remaining[key] = op

        grid.clear_pending()
        grid.restore_pending(remaining, local_targets=local_targets, npm_snapshots=npm_snapshots)
        grid.restore_catalog_pending(catalog_pending)
        self._refresh_pi_view()
        self._refresh_pending_label()
        self._refresh_status_bar()

        if errors:
            first = " ".join(errors[0].split())
            extra = f" (+{len(errors) - 1} more)" if len(errors) > 1 else ""
            self.query_one("#footer-pending", Static).update(
                f"[red]apply failed[/] — {first}{extra}{tag}"
            )
            self.notify(
                "\n\n".join(errors),
                title=f"Apply: {ok} ok, {failed} failed",
                severity="error",
                timeout=12,
            )
        else:
            self.query_one("#footer-pending", Static).update(
                f"applied: {ok} ok, {failed} failed{tag}"
            )
        return ApplyResult(
            ok=ok, failed=failed, errors=errors, keys=list(pending.keys())
        )

    def _apply_agent_pending(self) -> ApplyResult | None:
        from agent_toolkit_cli import agent_install
        from agent_toolkit_cli._install_core import InstallError, InstallPlan

        try:
            grid = self.query_one("#agent-grid", AgentGrid)
        except NoMatches:
            return None
        pending = grid.pending_entries()
        if not pending:
            return None
        tag = _scope_tag(pending)

        # Group by (scope, slug) → (adds set, removes set) of harnesses.
        by_slug: dict[tuple[str, str], tuple[set[str], set[str]]] = defaultdict(
            lambda: (set(), set())
        )
        for (scope, harness, slug), op in pending.items():
            adds, removes = by_slug[(scope, slug)]
            (adds if op == "link" else removes).add(harness)

        ok = failed = 0
        errors: list[str] = []
        refusal_msgs: list[str] = []
        agent_failed_keys = set()
        catalog_pending = grid.pending_catalog_entries()
        from agent_toolkit_tui.catalog_apply import prepare_entry, snapshot_for
        snapshot = snapshot_for(self, catalog_pending)

        for (scope, slug), (adds, removes) in by_slug.items():
            # Global scope MUST pass home=Path.home() so adapters' {HOME}
            # templates don't raise ValueError.
            effective_home = Path.home() if scope == "global" else None
            project = None if scope == "global" else Path.cwd()

            if adds:
                try:
                    prepare_entry("agent", slug, intents=catalog_pending, snapshot=snapshot,
                        targets=adds, scope=scope, home=Path.home(), project=project)
                except (ValueError, RuntimeError, OSError) as exc:
                    errors.append(f"{slug}: {exc}")
                    failed += len(adds)
                    agent_failed_keys.update((scope, harness, slug) for harness in adds)
                    adds = set()
            # Adds → agent_install.apply()
            if adds:
                p = InstallPlan(
                    slug=slug,
                    scope=scope,  # type: ignore[arg-type]
                    source=None,
                    ref=None,
                    add_agents=tuple(sorted(adds)),
                    remove_agents=(),
                )
                try:
                    result = agent_install.apply(
                        p, home=effective_home, project=project
                    )
                    skipped = tuple(getattr(result, "skipped", ()))
                    if skipped:
                        self.notify(
                            f"{slug}: skipped unsupported agent projection: {', '.join(skipped)}",
                            title="Agent projection not supported", severity="warning", timeout=12,
                        )
                    ok += len(result.created)
                except InstallError as exc:
                    # #373: the facade seam already prefixed the slug — do not
                    # double it ("my-agent: my-agent: ...").
                    errors.append(str(exc))
                    failed += len(adds)
                    agent_failed_keys.update((scope, harness, slug) for harness in adds)
                except ValueError as exc:
                    # A ValueError NOT routed through the seam (e.g. a bad
                    # scope/home arg) carries no slug — prefix it ourselves.
                    errors.append(f"{slug}: {exc}")
                    failed += len(adds)
                    agent_failed_keys.update((scope, harness, slug) for harness in adds)

            # Removes → agent_install.uninstall() DIRECTLY.
            # Do NOT use apply().removed — it is ALWAYS EMPTY (the #268-class gap).
            # Calling uninstall() directly avoids orphaning projected files.
            if removes:
                try:
                    # uninstall() returns structured refusals (PM review F5):
                    # the standard adapter leaves a non-owned (sentinel-less,
                    # content-divergent) slot file in place — surface each
                    # instead of silently counting it as removed. The re-scan
                    # below keeps the cell linked (truthful grid state).
                    refusals = (
                        agent_install.uninstall(
                            slug=slug,
                            scope=scope,  # type: ignore[arg-type]
                            home=effective_home,
                            project=project,
                            harnesses=tuple(sorted(removes)),
                        )
                        or ()
                    )
                    for harness, dest in refusals:
                        refusal_msgs.append(
                            f"{slug} ({harness}): {dest} is not managed by "
                            "this tool (no ownership sentinel, content "
                            "differs) — left in place"
                        )
                    ok += len(removes)
                except InstallError as exc:
                    # #373: seam already prefixed the slug — do not double it.
                    errors.append(str(exc))
                    failed += len(removes)
                    agent_failed_keys.update((scope, harness, slug) for harness in removes)
                except ValueError as exc:
                    # ValueError bypasses the seam — prefix the slug ourselves.
                    errors.append(f"{slug}: {exc}")
                    failed += len(removes)
                    agent_failed_keys.update((scope, harness, slug) for harness in removes)

        saved = {key: op for key, op in pending.items() if key in agent_failed_keys}
        grid.clear_pending()
        self._refresh_agent_view()
        if saved:
            grid.restore_pending(saved)
        grid.restore_catalog_pending(catalog_pending)
        self._refresh_pending_label()
        self._refresh_status_bar()
        if refusal_msgs:
            self.notify(
                "\n\n".join(refusal_msgs),
                title="Apply: some files left in place",
                severity="warning",
                timeout=12,
            )
        if errors:
            first = " ".join(errors[0].split())
            extra = f" (+{len(errors) - 1} more)" if len(errors) > 1 else ""
            self.query_one("#footer-pending", Static).update(
                f"[red]apply failed[/] — {first}{extra}{tag}"
            )
            self.notify(
                "\n\n".join(errors),
                title=f"Apply: {ok} ok, {failed} failed",
                severity="error",
                timeout=12,
            )
        else:
            self.query_one("#footer-pending", Static).update(
                f"applied: {ok} ok, {failed} failed{tag}"
            )
        return ApplyResult(
            ok=ok, failed=failed, errors=errors, keys=list(pending.keys())
        )

    def _apply_mcp_pending(self) -> ApplyResult | None:
        from agent_toolkit_cli import mcp_install
        from agent_toolkit_cli._install_core import InstallError
        from agent_toolkit_cli.mcp_library import library_root

        try:
            grid = self.query_one("#mcp-grid", McpGrid)
        except NoMatches:
            return None
        pending = grid.pending_entries()
        if not pending:
            return None
        tag = _scope_tag(pending)

        # Group by (scope, slug) → (adds set, removes set) of harnesses.
        by_slug: dict[tuple[str, str], tuple[set[str], set[str]]] = defaultdict(
            lambda: (set(), set())
        )
        for (scope, harness, slug), op in pending.items():
            adds, removes = by_slug[(scope, slug)]
            (adds if op == "link" else removes).add(harness)

        ok = failed = 0
        errors: list[str] = []
        for (scope, slug), (adds, removes) in by_slug.items():
            _, home, project = self._scope_to_roots(scope)
            # MCP adapters require a home for sentinel checks in both scopes.
            assert home is not None
            lib_root = library_root(home)
            if adds:
                try:
                    result = mcp_install.apply(
                        slug=slug,
                        harnesses=sorted(adds),
                        scope=scope,
                        library_root=lib_root,
                        home=home,
                        project=project,
                    )
                    ok += len(result.installed)
                except InstallError as exc:
                    errors.append(f"{slug}: {exc}")
                    failed += len(adds)
                except ValueError as exc:
                    errors.append(f"{slug}: {exc}")
                    failed += len(adds)
            if removes:
                try:
                    mcp_install.uninstall(
                        slug=slug,
                        harnesses=sorted(removes),
                        scope=scope,
                        library_root=lib_root,
                        home=home,
                        project=project,
                    )
                    ok += len(removes)
                except InstallError as exc:
                    errors.append(f"{slug}: {exc}")
                    failed += len(removes)
                except ValueError as exc:
                    errors.append(f"{slug}: {exc}")
                    failed += len(removes)

        saved = grid.pending_entries() if failed else {}
        if failed == 0:
            grid.clear_pending()
        self._refresh_mcp_view()
        if saved:
            grid.restore_pending(saved)
        self._refresh_pending_label()
        self._refresh_status_bar()
        if errors:
            first = " ".join(errors[0].split())
            extra = f" (+{len(errors) - 1} more)" if len(errors) > 1 else ""
            self.query_one("#footer-pending", Static).update(
                f"[red]apply failed[/] — {first}{extra}{tag}"
            )
            self.notify(
                "\n\n".join(errors),
                title=f"Apply: {ok} ok, {failed} failed",
                severity="error",
                timeout=12,
            )
        else:
            self.query_one("#footer-pending", Static).update(
                f"applied: {ok} ok, {failed} failed{tag}"
            )
        return ApplyResult(
            ok=ok, failed=failed, errors=errors, keys=list(pending.keys())
        )

    # ----- header + status ---------------------------------------------------

    def _build_content_header(self) -> str:
        label = _asset_type_label(self._active_asset_type, plural=True)
        if self._active_asset_type == "instruction":
            try:
                n = self.query_one("#instruction-grid", InstructionGrid).row_count
            except (NoMatches, Exception):
                n = 0
        elif self._active_asset_type == "skill":
            try:
                skills = self.query_one("#skill-grid", SkillGrid)
                n = skills.row_count
                if skills.collection_count:
                    count = skills.collection_count
                    return f"  [b]{label}[/]   [dim]·[/]   {n} skills in {count} collection{'s' if count != 1 else ''}"
            except (NoMatches, Exception):
                n = 0
        elif self._active_asset_type == "command":
            try:
                n = self.query_one("#command-grid", CommandGrid).row_count
            except NoMatches:
                n = 0
        elif self._active_asset_type == "pi-extension":
            try:
                n = self.query_one("#pi-grid", PiGrid).row_count
            except (NoMatches, Exception):
                n = 0
        elif self._active_asset_type == "mcp":
            try:
                n = self.query_one("#mcp-grid", McpGrid).row_count
            except (NoMatches, Exception):
                n = 0
        else:
            try:
                n = self.query_one("#agent-grid", AgentGrid).row_count
            except (NoMatches, Exception):
                n = 0
        return f"  [b]{label}[/]   [dim]·[/]   {n} items"

    def _refresh_content_header(self) -> None:
        try:
            self.query_one("#content-header", Static).update(
                self._build_content_header()
            )
        except Exception:
            pass

    def _build_proj_path_markup(self, cwd: Path | str | None = None) -> str:
        if cwd is None:
            cwd = getattr(self, "_cwd_override", None) or Path.cwd()
        else:
            cwd = Path(cwd)
        from agent_toolkit_cli.skill_git import is_git_repo

        path = str(cwd)
        final = Path(cwd).name or path
        parent = path[:-len(final)]
        formatted = f"[bold]REPO:[/bold]{escape(parent)}[bold]{escape(final)}[/bold]"
        if not is_git_repo(cwd):
            return f"[red]⚠️  {formatted}[/]"
        return formatted

    def _refresh_proj_path(self, cwd: Path | str | None = None) -> None:
        try:
            self.query_one("#proj-path", Static).update(
                self._build_proj_path_markup(cwd)
            )
        except Exception:
            pass

    def _refresh_pending_label(self) -> None:
        try:
            footer = self.query_one("#footer-pending", Static)
            if "apply failed" in str(footer.render()):
                return
            grid = self.query_one("#pi-grid", PiGrid)
            blocks = grid.pending_project_blocks()
            footer.update(Text(
                f"{len(blocks)} Pi project block(s) pending — Ctrl+S to review; Ctrl+Z to discard"
                if blocks else ""
            ))
        except Exception:
            pass

    def _refresh_status_bar(self) -> None:
        """Roll up active grid rows into status counts."""
        active = getattr(self, "_active_asset_type", "skill")
        if active == "instruction":
            linked = 0
            try:
                grid_instr = self.query_one("#instruction-grid", InstructionGrid)
            except (NoMatches, Exception):
                grid_instr = None
            if grid_instr is not None:
                scope = self._scope_to_roots()[0]
                for instr_row in grid_instr._rows:
                    for (harness, sc), icell in instr_row.cells.items():
                        if sc != scope:
                            continue
                        if icell.linked:
                            linked += 1
                pending = len(grid_instr.pending_entries())
            else:
                pending = 0
            text = f"  [b green]{linked}[/] linked   [b yellow]{pending}[/] pending"
        elif active == "skill":
            linked = drifted = stray = broken = 0
            try:
                grid = self.query_one("#skill-grid", SkillGrid)
            except (NoMatches, Exception):
                grid = None
            if grid is not None:
                scope = self._scope_to_roots()[0]
                for row in grid._rows:
                    if row.state in ("missing", "copy"):
                        broken += 1
                    for (agent, sc), cell in row.cells.items():
                        if sc != scope:
                            continue
                        if cell.drift:
                            drifted += 1
                        elif cell.stray:
                            stray += 1
                        elif cell.linked:
                            linked += 1
                pending = len(grid.pending_entries())
            else:
                pending = 0
            text = (
                f"  [b green]{linked}[/] linked   "
                f"[b yellow]{pending}[/] pending   "
                f"[b orange3]{drifted}[/] drifted   "
                f"[b yellow]{stray}[/] stray   "
                f"[b red]{broken}[/] broken"
            )
        elif active == "pi-extension":
            enabled = linked = mixed = 0
            try:
                grid_pi = self.query_one("#pi-grid", PiGrid)
            except (NoMatches, Exception):
                grid_pi = None
            if grid_pi is not None:
                scope = self._scope_to_roots()[0]
                for pi_row in grid_pi._rows:
                    if pi_row.npm_state and pi_row.npm_state.for_scope(scope).mixed:
                        mixed += 1
                    if pi_row.local_state and (pi_row.local_state.global_package_paths if scope == "global" else pi_row.local_state.project_package_paths):
                        continue  # Count its package reference, not a duplicate loose cell.
                    selected = (
                        pi_row.global_cell.global_loaded if scope == "global"
                        else pi_row.project_cell.project_loaded
                    )
                    if selected:
                        if pi_row.origin == "store-owned":
                            linked += 1
                        else:
                            enabled += 1
                pending = len(grid_pi.pending_entries())
            else:
                pending = 0
            connections = f"   [b green]{linked}[/] linked" if linked else ""
            partial = f"   [b yellow]{mixed}[/] mixed" if mixed else ""
            text = f"  [b green]{enabled}[/] enabled{connections}{partial}   [b yellow]{pending}[/] pending"
        elif active == "mcp":
            linked = 0
            try:
                grid_mcp = self.query_one("#mcp-grid", McpGrid)
            except (NoMatches, Exception):
                grid_mcp = None
            if grid_mcp is not None:
                scope = self._scope_to_roots()[0]
                for mcp_row in grid_mcp._rows:
                    for (harness, sc), mcell in mcp_row.cells.items():
                        if sc != scope:
                            continue
                        if mcell.linked:
                            linked += 1
                pending = len(grid_mcp.pending_entries())
            else:
                pending = 0
            text = f"  [b green]{linked}[/] linked   [b yellow]{pending}[/] pending"
        else:  # "agent"
            linked = 0
            try:
                grid_agent = self.query_one("#agent-grid", AgentGrid)
            except (NoMatches, Exception):
                grid_agent = None
            if grid_agent is not None:
                scope = self._scope_to_roots()[0]
                for agent_row in grid_agent._rows:
                    for (harness, sc), acell in agent_row.cells.items():
                        if sc != scope:
                            continue
                        if acell.linked:
                            linked += 1
                pending = len(grid_agent.pending_entries())
            else:
                pending = 0
            text = f"  [b green]{linked}[/] linked   [b yellow]{pending}[/] pending"
        settings_diagnostics = getattr(self, "_settings_diagnostics", ())
        if settings_diagnostics:
            diagnostic = " | ".join(settings_diagnostics)
            text = f"  [b yellow]Settings:[/] {escape(diagnostic)}   {text.strip()}"
        try:
            self.query_one("#status-bar", Static).update(text)
        except Exception:
            pass


def main() -> int:
    from agent_toolkit_tui.launcher import main as launch
    return launch()


if __name__ == "__main__":
    raise SystemExit(main())
