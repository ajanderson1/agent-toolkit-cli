"""The Textual App + main() entry point for agent-toolkit-tui.

Skill-only cockpit over the v2.3 `agent-toolkit-cli skill` surface. Reads the
library lock + project filesystem directly via `agent_toolkit_cli.*` modules;
applies pending toggles by calling `skill_install.apply` in-process.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Header, Label, Static

from agent_toolkit_tui import __version__
from agent_toolkit_tui.skill_state import build_skill_rows
from agent_toolkit_tui.widgets import ScopeToggle, SkillGrid


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

    def __init__(self, n_pending: int) -> None:
        super().__init__()
        self._n_pending = n_pending

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"Discard {self._n_pending} pending change(s)?")
            with Horizontal(id="buttons"):
                yield Button("Discard", variant="warning", id="discard")
                yield Button("Cancel", variant="primary", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "discard")

    def action_discard(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


class TUIApp(App):
    """agent-toolkit-tui — Textual cockpit over `agent-toolkit-cli skill`."""

    CSS_PATH = "css/app.tcss"
    TITLE = "agent-toolkit-tui"

    BINDINGS = [
        Binding("ctrl+s", "apply", "Apply", priority=True),
        Binding("ctrl+d", "diff", "Diff", priority=True),
        Binding("ctrl+r", "refresh", "Refresh", priority=True),
        Binding("ctrl+z", "revert", "Revert", priority=True),
        Binding("s", "scope_toggle", "toggle scope"),
        Binding("i", "info_pass", "Info"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._scope: str = "project"
        self.sub_title = f"v{__version__}"

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="content"):
            with Horizontal(id="content-header-row"):
                yield Static(self._build_content_header(), id="content-header")
                yield ScopeToggle(active=self._scope, id="scope-toggle")
            yield SkillGrid([], id="skill-grid")
        yield Static("", id="status-bar")
        yield Static("", id="footer-pending")
        yield Footer()

    def on_mount(self) -> None:
        try:
            self.theme = "gruvbox"
        except Exception:
            pass
        self._refresh_skill_view()
        self._refresh_content_header()
        self._refresh_pending_label()
        self._refresh_status_bar()
        try:
            self.query_one("#skill-table", DataTable).focus()
        except Exception:
            pass

    # ----- skill-view ----------------------------------------------------
    def _scope_to_roots(self) -> tuple[str, Path | None, Path | None]:
        if self._scope == "global":
            return "global", Path.home(), None
        return "project", None, Path.cwd()

    def _refresh_skill_view(self) -> None:
        try:
            grid = self.query_one("#skill-grid", SkillGrid)
        except NoMatches:
            return
        scope, home, project = self._scope_to_roots()
        grid.set_scope(scope)
        grid.set_rows(build_skill_rows(scope=scope, home=home, project=project))

    # ----- actions --------------------------------------------------------
    def action_quit(self) -> None:
        n = 0
        try:
            n = len(self.query_one("#skill-grid", SkillGrid).pending_entries())
        except NoMatches:
            pass
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
        self._refresh_skill_view()
        self._refresh_content_header()
        self._refresh_status_bar()

    def action_scope_toggle(self) -> None:
        self.action_scope("global" if self._scope == "project" else "project")

    def action_info_pass(self) -> None:
        """Delegate `i` to the SkillGrid widget (visible in Footer hints)."""
        try:
            grid = self.query_one("#skill-grid", SkillGrid)
        except NoMatches:
            return
        grid.action_info()

    def action_refresh(self) -> None:
        self._refresh_skill_view()
        self._refresh_pending_label()
        self._refresh_content_header()
        self._refresh_status_bar()

    def action_revert(self) -> None:
        try:
            grid = self.query_one("#skill-grid", SkillGrid)
        except NoMatches:
            return
        n = len(grid.pending_entries())
        grid.clear_pending()
        self._refresh_pending_label()
        self.query_one("#footer-pending", Static).update(
            f"reverted: {n} pending cleared"
        )

    def action_diff(self) -> None:
        try:
            grid = self.query_one("#skill-grid", SkillGrid)
        except NoMatches:
            return
        pending = grid.pending_entries()
        n_link = sum(1 for op in pending.values() if op == "link")
        n_unlink = sum(1 for op in pending.values() if op == "unlink")
        self.query_one("#footer-pending", Static).update(
            f"diff: {n_link} would-link, {n_unlink} would-unlink"
        )

    def action_apply(self) -> None:
        self._apply_skill_pending()

    def _apply_skill_pending(self) -> None:
        from agent_toolkit_cli.skill_install import (
            InstallError, InstallPlan, apply as engine_apply,
            ensure_project_canonical,
        )
        from agent_toolkit_cli.skill_paths import library_lock_path

        try:
            grid = self.query_one("#skill-grid", SkillGrid)
        except NoMatches:
            return
        pending = grid.pending_entries()
        if not pending:
            return
        by_slug: dict[tuple[str, str], tuple[set[str], set[str]]] = defaultdict(
            lambda: (set(), set())
        )
        for (scope, agent, slug), op in pending.items():
            adds, removes = by_slug[(scope, slug)]
            (adds if op == "link" else removes).add(agent)
        ok = failed = 0
        for (scope, slug), (adds, removes) in by_slug.items():
            home = Path.home() if scope == "global" else None
            project = None if scope == "global" else Path.cwd()
            if scope == "project":
                try:
                    ensure_project_canonical(
                        slug=slug,
                        project=project,
                        global_lock_path=library_lock_path(),
                        env=None,
                    )
                except InstallError as exc:
                    self.query_one("#footer-pending", Static).update(
                        f"apply error ({slug}): {exc}"
                    )
                    failed += 1
                    continue
            p = InstallPlan(
                slug=slug, scope=scope, source=None, ref=None,
                add_agents=tuple(sorted(adds)),
                remove_agents=tuple(sorted(removes)),
            )
            try:
                engine_apply(p, home=home, project=project, env=None)
                ok += 1
            except InstallError as exc:
                self.query_one("#footer-pending", Static).update(
                    f"apply error ({slug}): {exc}"
                )
                failed += 1
        saved = grid.pending_entries() if failed else {}
        if failed == 0:
            grid.clear_pending()
        self._refresh_skill_view()
        if saved:
            grid.restore_pending(saved)
        self._refresh_pending_label()
        self._refresh_status_bar()
        self.query_one("#footer-pending", Static).update(
            f"applied: {ok} ok, {failed} failed"
        )

    # ----- header + status -----------------------------------------------
    def _build_content_header(self) -> str:
        try:
            n = self.query_one("#skill-grid", SkillGrid).row_count
        except (NoMatches, Exception):
            n = 0
        return f"  [b]Skill[/]   [dim]·[/]   {n} items"

    def _refresh_content_header(self) -> None:
        try:
            self.query_one("#content-header", Static).update(
                self._build_content_header()
            )
        except Exception:
            pass

    def _refresh_pending_label(self) -> None:
        n = 0
        try:
            n = len(self.query_one("#skill-grid", SkillGrid).pending_entries())
        except Exception:
            pass
        try:
            self.query_one("#footer-pending", Static).update(f"Pending: {n}")
        except Exception:
            pass

    def _refresh_status_bar(self) -> None:
        """Roll up SkillGrid rows into linked / pending / drifted / broken counts."""
        linked = drifted = broken = 0
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
                    elif cell.linked:
                        linked += 1
            pending = len(grid.pending_entries())
        else:
            pending = 0
        text = (
            f"  [b green]{linked}[/] linked   "
            f"[b yellow]{pending}[/] pending   "
            f"[b orange3]{drifted}[/] drifted   "
            f"[b red]{broken}[/] broken"
        )
        try:
            self.query_one("#status-bar", Static).update(text)
        except Exception:
            pass


def main() -> int:
    TUIApp().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
