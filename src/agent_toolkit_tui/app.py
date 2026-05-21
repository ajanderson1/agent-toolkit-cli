"""The Textual App + main() entry point.

Owns the runner, the state, and the Apply path. Widgets only render and emit
messages; they don't know about the runner.
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, Static

from agent_toolkit_cli._repo_resolution import RepoNotFoundError, resolve_toolkit_root
from agent_toolkit_tui import __version__
from agent_toolkit_tui.messages import (
    AssetToggled,
    KindChanged,
    ScopeChanged,
)
from agent_toolkit_tui.runner import CLIRunner, PlanResult, RunnerError
from agent_toolkit_tui.state import InventoryState, build_state
from agent_toolkit_tui.skill_state import build_skill_rows
from agent_toolkit_tui.widgets import AssetGrid, KindsSidebar, ScopeToggle
from agent_toolkit_tui.widgets.pi_tab import PiTab
from agent_toolkit_tui.widgets.skill_grid import SkillGrid


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


class PiTabScreen(ModalScreen[None]):
    """Modal screen that hosts the Pi inventory view with u/p toggles.

    Press ``escape`` or ``q`` to dismiss. With a row highlighted, press
    ``u`` to toggle user-scope load state and ``p`` for project-scope.
    """

    DEFAULT_CSS = """
    PiTabScreen {
        align: center middle;
    }
    PiTabScreen > Vertical {
        background: $panel;
        border: thick $primary;
        padding: 1 2;
        width: 90%;
        height: 80%;
    }
    PiTabScreen Label {
        text-style: bold;
        margin-bottom: 1;
    }
    PiTabScreen #pi-tab-footer {
        margin-top: 1;
        color: $warning;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("q", "close", "Close"),
        Binding("u", "toggle_user", "User load/unload"),
        Binding("p", "toggle_project", "Project load/unload"),
    ]

    def __init__(self, records: list[dict], runner: "CLIRunner") -> None:
        super().__init__()
        self._records = records
        self._runner = runner

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"Pi extension inventory — {len(self._records)} record(s)")
            yield PiTab(records=self._records, id="pi-tab")
            yield Static("", id="pi-tab-footer")

    def action_close(self) -> None:
        self.dismiss(None)

    def action_toggle_user(self) -> None:
        self._toggle("user")

    def action_toggle_project(self) -> None:
        self._toggle("project")

    def _toggle(self, scope: str) -> None:
        try:
            table = self.query_one("#pi-tab-table", DataTable)
        except NoMatches:
            self._set_footer("no table to act on")
            return
        cursor = table.cursor_row
        if cursor < 0 or cursor >= len(self._records):
            self._set_footer("select a row first")
            return
        record = self._records[cursor]
        slug = record.get("slug", "")
        if not slug:
            self._set_footer("row has no slug")
            return
        flag = "user_loaded" if scope == "user" else "project_loaded"
        try:
            if record.get(flag):
                self._runner.pi_unload(slug, scope)
            else:
                self._runner.pi_load(slug, scope)
        except RunnerError as exc:
            # Show only the first line so multi-line stderr doesn't blow up the footer.
            msg = str(exc).splitlines()[0] if str(exc) else "unknown error"
            self._set_footer(f"pi {scope} toggle error: {msg}")
            return
        # Refresh inventory and rebuild the table in place.
        try:
            new_records = self._runner.pi_inventory()
        except RunnerError as exc:
            msg = str(exc).splitlines()[0] if str(exc) else "unknown error"
            self._set_footer(f"refresh error: {msg}")
            return
        self._records = new_records
        self._rebuild_table(table, prefer_slug=slug)
        self._set_footer("")

    def _rebuild_table(self, table: DataTable, prefer_slug: str) -> None:
        table.clear()
        new_cursor = 0
        for idx, r in enumerate(self._records):
            badge = "1P" if r.get("origin") == "first-party" else "3P"
            table.add_row(
                r.get("slug", ""),
                badge,
                "✓" if r.get("user_loaded") else " ",
                "✓" if r.get("project_loaded") else " ",
                r.get("toolkit_intent", ""),
                r.get("source", ""),
            )
            if r.get("slug") == prefer_slug:
                new_cursor = idx
        if self._records:
            table.move_cursor(row=new_cursor)

    def _set_footer(self, msg: str) -> None:
        try:
            self.query_one("#pi-tab-footer", Static).update(msg)
        except Exception:
            pass


class TUIApp(App):
    """agent-toolkit-tui — Textual cockpit over bin/agent-toolkit."""

    CSS_PATH = "css/app.tcss"
    TITLE = "agent-toolkit-tui"

    BINDINGS = [
        Binding("ctrl+s", "apply", "Apply", priority=True),
        Binding("ctrl+d", "diff", "Diff", priority=True),
        Binding("ctrl+r", "refresh", "Refresh", priority=True),
        Binding("ctrl+z", "revert", "Revert", priority=True),
        Binding("slash", "focus_filter", "Filter", priority=True),
        Binding("s", "scope_toggle", "toggle scope"),
        Binding("1", "kind('skill')", "Skills", show=False),
        Binding("2", "kind('agent')", "Agents", show=False),
        Binding("3", "kind('command')", "Commands", show=False),
        Binding("4", "kind('hook')", "Hooks", show=False),
        Binding("5", "kind('plugin')", "Plugins", show=False),
        Binding("6", "kind('mcp')", "MCPs", show=False),
        Binding("7", "kind('pi-extension')", "Pi Ext", show=False),
        Binding("8", "show_pi_tab", "Pi", show=False),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, toolkit_root: Path, runner: CLIRunner | None = None) -> None:
        super().__init__()
        self.toolkit_root = toolkit_root
        self.runner = runner or CLIRunner(toolkit_root=toolkit_root)
        self.state: InventoryState = build_state(self.runner)
        self._scope: str = "project"
        self._kind: str = "skill"
        # AGENT_TOOLKIT_TUI_LEGACY=1 restores the seven-kind interface that
        # shipped in v1. Default is skills-only — see docs/agent-toolkit/
        # roadmap.md for what's coming back and when.
        self._legacy: bool = os.environ.get("AGENT_TOOLKIT_TUI_LEGACY") == "1"
        self.sub_title = f"v{__version__}"

    # ----- composition ----------------------------------------------------
    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            # KindsSidebar + AssetGrid still mount, but are hidden in
            # non-legacy mode. Keeps the existing query_one(#asset-grid, ...)
            # callers working without 14 try/NoMatches guards.
            yield KindsSidebar(self.state, id="kinds-sidebar")
            with Vertical(id="content"):
                with Horizontal(id="content-header-row"):
                    yield Static(self._build_content_header(), id="content-header")
                    yield ScopeToggle(active=self._scope, id="scope-toggle")
                yield AssetGrid(self.state, id="asset-grid")
                yield SkillGrid([], id="skill-grid")
        yield Static("", id="status-bar")
        yield Static("", id="footer-pending")
        yield Footer()

    # ----- skill-tab helpers ----------------------------------------------
    def _refresh_skill_view(self) -> None:
        """Show SkillGrid when kind == 'skill', otherwise show AssetGrid.

        Rebuilds SkillGrid rows in place whenever the skill tab is active.
        Other kinds continue to use AssetGrid.
        """
        is_skill = self._kind == "skill"
        try:
            asset_grid = self.query_one("#asset-grid", AssetGrid)
            asset_grid.display = not is_skill
        except NoMatches:
            pass
        try:
            skill_grid = self.query_one("#skill-grid", SkillGrid)
        except NoMatches:
            return
        skill_grid.display = is_skill
        if not is_skill:
            return

        if self._scope == "user":
            scope, home, project = "global", Path.home(), None
        else:
            scope, home, project = "project", None, Path.cwd()
        skill_grid.set_rows(
            build_skill_rows(scope=scope, home=home, project=project)
        )

    # ----- lifecycle ------------------------------------------------------
    def on_mount(self) -> None:
        try:
            self.theme = "gruvbox"
        except Exception:
            pass
        if not self._legacy:
            # Skill-only UI: hide legacy widgets, pin kind to skill.
            try:
                self.query_one("#kinds-sidebar", KindsSidebar).display = False
            except NoMatches:
                pass
            self._kind = "skill"
        self._refresh_pending_label()
        self._refresh_status_bar()
        self._refresh_skill_view()
        # Default focus on the data table, not the filter Input — `q` and other
        # bindings should fire as bindings, not as text input.
        try:
            self.query_one("#grid-table", DataTable).focus()
        except Exception:
            pass

    # ----- message handlers ------------------------------------------------
    def on_kind_changed(self, event: KindChanged) -> None:
        self._kind = event.kind
        self.query_one("#asset-grid", AssetGrid).set_kind(event.kind)
        self._refresh_skill_view()
        self._refresh_content_header()
        self._refresh_status_bar()

    def on_scope_changed(self, event: ScopeChanged) -> None:
        self._scope = event.scope
        self.query_one("#asset-grid", AssetGrid).set_scope(event.scope)
        self._refresh_skill_view()
        self._refresh_content_header()
        self._refresh_status_bar()

    def on_asset_toggled(self, event: AssetToggled) -> None:
        self._refresh_pending_label()
        self._refresh_status_bar()

    # ----- actions --------------------------------------------------------
    def action_quit(self) -> None:
        from agent_toolkit_tui.widgets.skill_grid import SkillGrid
        n_asset = n_skill = 0
        try:
            n_asset = len(self.query_one("#asset-grid", AssetGrid).pending_entries())
        except NoMatches:
            pass
        try:
            n_skill = len(self.query_one("#skill-grid", SkillGrid).pending_entries())
        except NoMatches:
            pass
        n = n_asset + n_skill
        if n == 0:
            self.exit()
            return

        def _on_close(discard: bool | None) -> None:
            if discard:
                self.exit()
        self.push_screen(ConfirmDiscardScreen(n), _on_close)

    def action_focus_filter(self) -> None:
        try:
            self.query_one("#grid-filter", Input).focus()
        except Exception:
            pass

    def action_scope(self, scope: str) -> None:
        if scope not in ("user", "project") or scope == self._scope:
            return
        self._scope = scope
        self.query_one("#asset-grid", AssetGrid).set_scope(scope)
        try:
            self.query_one("#scope-toggle", ScopeToggle).set_active(scope)
        except NoMatches:
            pass
        self._refresh_skill_view()
        self._refresh_content_header()
        self._refresh_status_bar()

    def action_scope_toggle(self) -> None:
        self.action_scope("user" if self._scope == "project" else "project")

    def action_kind(self, kind: str) -> None:
        if not self._legacy and kind != "skill":
            # In default mode the other kinds are hidden; ignore the keyboard
            # shortcut rather than triggering a half-rendered view.
            return
        if kind == self._kind:
            return
        self._kind = kind
        self.query_one("#kinds-sidebar", KindsSidebar).set_active(kind)
        self.query_one("#asset-grid", AssetGrid).set_kind(kind)
        self._refresh_skill_view()
        self._refresh_content_header()
        self._refresh_status_bar()

    def action_show_pi_tab(self) -> None:
        """Open the Pi extension inventory modal.

        Shells out to `agent-toolkit-cli pi inventory --format json` via the
        runner and displays the records in a `PiTab` widget. Press ``u``/``p``
        inside the modal to toggle user/project load state for the cursor row.
        """
        if not self._legacy:
            return
        try:
            records = self.runner.pi_inventory()
        except RunnerError as exc:
            self.query_one("#footer-pending", Static).update(f"pi inventory error: {exc}")
            return
        self.push_screen(PiTabScreen(records=records, runner=self.runner))

    def action_refresh(self) -> None:
        if self._kind == "skill":
            self._refresh_skill_view()
            self._refresh_pending_label()
            self._refresh_content_header()
            self._refresh_status_bar()
            return
        self.state = build_state(self.runner)
        self.query_one("#asset-grid", AssetGrid).update_state(self.state)
        self.query_one("#kinds-sidebar", KindsSidebar).update_state(self.state)
        self._refresh_pending_label()
        self._refresh_content_header()
        self._refresh_status_bar()

    def action_revert(self) -> None:
        if self._kind == "skill":
            from agent_toolkit_tui.widgets.skill_grid import SkillGrid
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
            return
        grid = self.query_one("#asset-grid", AssetGrid)
        n = len(grid.pending_entries())
        grid.clear_pending()
        self._refresh_pending_label()
        self._refresh_status_bar()
        self.query_one("#footer-pending", Static).update(
            f"reverted: {n} pending cleared"
        )

    def action_diff(self) -> None:
        if self._kind == "skill":
            from agent_toolkit_tui.widgets.skill_grid import SkillGrid
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
            return
        grid = self.query_one("#asset-grid", AssetGrid)
        results = self._apply_pending(dry_run=True, grid=grid)
        ok = sum(r.ok for r in results)
        failed = sum(r.failed for r in results)
        self.query_one("#footer-pending", Static).update(
            f"diff: {ok} would-link, {failed} errors"
        )

    def action_apply(self) -> None:
        if self._kind == "skill":
            self._apply_skill_pending()
            return
        grid = self.query_one("#asset-grid", AssetGrid)
        results = self._apply_pending(dry_run=False, grid=grid)
        self.state = build_state(self.runner)
        grid.update_state(self.state)
        ok = sum(r.ok for r in results)
        failed = sum(r.failed for r in results)
        if failed == 0:
            grid.clear_pending()
        self._refresh_pending_label()
        self._refresh_status_bar()
        self.query_one("#footer-pending", Static).update(
            f"applied: {ok} ok, {failed} failed"
        )

    def _apply_skill_pending(self) -> None:
        from collections import defaultdict
        from agent_toolkit_cli.skill_install import (
            InstallError, InstallPlan, apply as engine_apply,
        )
        from agent_toolkit_tui.widgets.skill_grid import SkillGrid
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
            p = InstallPlan(
                slug=slug, scope=scope, source=None, ref=None,
                add_agents=tuple(sorted(adds)),
                remove_agents=tuple(sorted(removes)),
            )
            home = Path.home() if scope == "global" else None
            project = None if scope == "global" else Path.cwd()
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
        self.query_one("#footer-pending", Static).update(
            f"applied: {ok} ok, {failed} failed"
        )

    # ----- internals ------------------------------------------------------
    def _apply_pending(self, *, dry_run: bool, grid: AssetGrid) -> list[PlanResult]:
        """Walk the pending queue, batch by (scope, harness, op), call runner once per batch."""
        pending = grid.pending_entries()
        # batches: (scope, harness, op) -> [(kind, slug), ...]
        batches: dict[tuple[str, str, str], list[tuple[str, str]]] = defaultdict(list)
        for (scope, harness, kind, slug), op in pending.items():
            batches[(scope, harness, op)].append((kind, slug))

        results: list[PlanResult] = []
        for (scope, harness, op), entries in sorted(batches.items()):
            try:
                if op == "link":
                    res = self.runner.link_plan(
                        scope=scope, harness=harness,
                        entries=entries, dry_run=dry_run,
                    )
                else:
                    res = self.runner.unlink_plan(
                        scope=scope, harness=harness,
                        entries=entries, dry_run=dry_run,
                    )
                results.append(res)
            except RunnerError as e:
                # Programmer bug — log to footer, leave queue untouched
                self.query_one("#footer-pending", Static).update(f"error: {e}")
                break
        return results

    def _refresh_pending_label(self) -> None:
        n_asset = n_skill = 0
        try:
            n_asset = len(self.query_one("#asset-grid", AssetGrid).pending_entries())
        except Exception:
            pass
        try:
            from agent_toolkit_tui.widgets.skill_grid import SkillGrid
            n_skill = len(self.query_one("#skill-grid", SkillGrid).pending_entries())
        except Exception:
            pass
        n = n_asset + n_skill
        self.query_one("#footer-pending", Static).update(f"Pending: {n}")

    # ----- content header + status bar ------------------------------------
    def _build_content_header(self) -> str:
        """Header at the top of the content pane — kind label and count only.

        Deliberately does NOT include a global 'harnesses: …' chip line —
        that was the V3 mistake; harness state lives in the grid columns.
        Scope toggle is a sibling widget (ScopeToggle), not Rich markup.
        """
        if self._kind == "skill":
            try:
                from agent_toolkit_tui.widgets.skill_grid import SkillGrid
                n = self.query_one("#skill-grid", SkillGrid).row_count
            except (NoMatches, Exception):
                n = 0
            return f"  [b]Skill[/]   [dim]·[/]   {n} items"
        if self._kind == "pi-extension":
            kind_label = "Pi Ext"
        else:
            kind_label = self._kind.replace("-", " ").title()
        n = sum(1 for r in self.state.rows if r.kind == self._kind)
        return f"  [b]{kind_label}[/]   [dim]·[/]   {n} items"

    def _refresh_content_header(self) -> None:
        try:
            self.query_one("#content-header", Static).update(
                self._build_content_header()
            )
        except Exception:
            pass

    def _refresh_status_bar(self) -> None:
        """Roll up state into linked / pending / drifted / broken counts."""
        linked = drifted = broken = 0
        for row in self.state.rows:
            for cell in row.cells.values():
                if cell.status in ("linked", "linked-matches"):
                    linked += 1
                elif cell.status == "linked-drifted":
                    drifted += 1
                elif cell.status == "broken":
                    broken += 1
        try:
            grid = self.query_one("#asset-grid", AssetGrid)
            pending = len(grid.pending_entries())
        except Exception:
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


# --------------------------------------------------------------------------
# Entry point — both the interactive TUI and the --headless mode used by
# Layer-3 bats smoke tests live here.
# --------------------------------------------------------------------------

def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="agent-toolkit-tui",
        description="Textual cockpit for agent-toolkit.",
    )
    p.add_argument("--toolkit-repo", dest="toolkit_repo", type=Path, default=None,
                   help="Path to the agent-toolkit repo "
                        "(default: $AGENT_TOOLKIT_REPO, walk-up .agent-toolkit-source, "
                        "or ~/GitHub/agent-toolkit/).")
    p.add_argument("--headless", action="store_true",
                   help="Don't launch the UI; apply --plan and exit.")
    p.add_argument("--plan", type=Path, default=None,
                   help="With --headless: path to a plan file (kind:slug per line) or '-' for stdin.")
    p.add_argument("--scope", choices=("user", "project"), default="user",
                   help="With --headless: scope to apply the plan under.")
    p.add_argument("--harness", default="claude",
                   help="With --headless: harness to apply the plan to.")
    p.add_argument("--op", choices=("link", "unlink"), default="link",
                   help="With --headless: operation to perform.")
    p.add_argument("--apply", action="store_true",
                   help="With --headless: actually apply (default would dry-run).")
    return p.parse_args(argv)


def _read_plan(path: Path) -> list[tuple[str, str]]:
    if str(path) == "-":
        text = sys.stdin.read()
    else:
        text = path.read_text(encoding="utf-8")
    out: list[tuple[str, str]] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if ":" not in line:
            print(f"malformed plan line: {raw!r}", file=sys.stderr)
            continue
        kind, slug = line.split(":", 1)
        out.append((kind.strip(), slug.strip()))
    return out


def main() -> int:
    args = _parse_args(sys.argv[1:])
    try:
        toolkit_root = resolve_toolkit_root(args.toolkit_repo)
    except RepoNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.headless:
        if args.plan is None:
            print("--headless requires --plan", file=sys.stderr)
            return 2
        runner = CLIRunner(toolkit_root=toolkit_root)
        entries = _read_plan(args.plan)
        if args.op == "link":
            res = runner.link_plan(
                scope=args.scope, harness=args.harness,
                entries=entries, dry_run=not args.apply,
            )
        else:
            res = runner.unlink_plan(
                scope=args.scope, harness=args.harness,
                entries=entries, dry_run=not args.apply,
            )
        verb = "applied" if args.apply else "would apply"
        print(f"{verb}: {res.ok} ok, {res.failed} failed", file=sys.stderr)
        return 0 if res.failed == 0 else 1

    TUIApp(toolkit_root=toolkit_root).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
