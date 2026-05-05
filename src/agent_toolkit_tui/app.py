"""The Textual App + main() entry point.

Owns the runner, the state, and the Apply path. Widgets only render and emit
messages; they don't know about the runner.
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Label, Static

from agent_toolkit_tui.messages import (
    AssetToggled,
    KindChanged,
    ScopeChanged,
)
from agent_toolkit_tui.runner import CLIRunner, PlanResult, RunnerError
from agent_toolkit_tui.state import InventoryState, build_state
from agent_toolkit_tui.widgets import AssetGrid, HarnessPicker, KindsSidebar


class ConfirmDiscardScreen(ModalScreen[bool]):
    """Yes/No prompt shown when quitting with unapplied pending edits."""

    DEFAULT_CSS = """
    ConfirmDiscardScreen {
        align: center middle;
    }
    ConfirmDiscardScreen > Vertical {
        background: $panel;
        border: round $warning;
        padding: 1 2;
        width: 50;
        height: auto;
    }
    ConfirmDiscardScreen Label {
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }
    ConfirmDiscardScreen #buttons {
        layout: horizontal;
        height: auto;
        align: center middle;
    }
    ConfirmDiscardScreen Button {
        margin: 0 1;
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
    """agent-toolkit-tui — Textual cockpit over bin/agent-toolkit."""

    CSS_PATH = "css/app.tcss"
    TITLE = "agent-toolkit-tui"

    BINDINGS = [
        Binding("ctrl+s", "apply", "Apply", priority=True),
        Binding("ctrl+d", "diff", "Diff", priority=True),
        Binding("ctrl+r", "refresh", "Refresh", priority=True),
        Binding("ctrl+z", "revert", "Revert", priority=True),
        Binding("slash", "focus_filter", "Filter", priority=True),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, toolkit_root: Path, runner: CLIRunner | None = None) -> None:
        super().__init__()
        self.toolkit_root = toolkit_root
        self.runner = runner or CLIRunner(toolkit_root=toolkit_root)
        self.state: InventoryState = build_state(self.runner)

    # ----- composition ----------------------------------------------------
    def compose(self) -> ComposeResult:
        yield Header()
        yield HarnessPicker(self.state, id="harness-picker")
        with Horizontal(id="main-row"):
            yield KindsSidebar(self.state, id="kinds-sidebar")
            yield AssetGrid(self.state, id="asset-grid")
        yield Static("", id="footer-pending")
        yield Footer()

    # ----- lifecycle ------------------------------------------------------
    def on_mount(self) -> None:
        # Initialize the footer label so it shows "Pending: 0" from startup.
        self._refresh_pending_label()

    # ----- message handlers ------------------------------------------------
    def on_kind_changed(self, event: KindChanged) -> None:
        self.query_one("#asset-grid", AssetGrid).set_kind(event.kind)

    def on_scope_changed(self, event: ScopeChanged) -> None:
        self.query_one("#asset-grid", AssetGrid).set_scope(event.scope)

    def on_asset_toggled(self, event: AssetToggled) -> None:
        self._refresh_pending_label()

    # ----- actions --------------------------------------------------------
    def action_quit(self) -> None:
        grid = self.query_one("#asset-grid", AssetGrid)
        n = len(grid.pending_entries())
        if n == 0:
            self.exit()
            return

        def _on_close(discard: bool | None) -> None:
            if discard:
                self.exit()

        self.push_screen(ConfirmDiscardScreen(n), _on_close)

    def action_focus_filter(self) -> None:
        from textual.widgets import Input
        try:
            self.query_one("#grid-filter", Input).focus()
        except Exception:
            pass

    def action_refresh(self) -> None:
        self.state = build_state(self.runner)
        self.query_one("#asset-grid", AssetGrid).update_state(self.state)
        self.query_one("#kinds-sidebar", KindsSidebar).update_state(self.state)
        self._refresh_pending_label()

    def action_revert(self) -> None:
        grid = self.query_one("#asset-grid", AssetGrid)
        n = len(grid.pending_entries())
        grid.clear_pending()
        self._refresh_pending_label()
        self.query_one("#footer-pending", Static).update(
            f"reverted: {n} pending cleared"
        )

    def action_diff(self) -> None:
        # Diff = run pending through --dry-run and surface counts in the footer.
        grid = self.query_one("#asset-grid", AssetGrid)
        results = self._apply_pending(dry_run=True, grid=grid)
        ok = sum(r.ok for r in results)
        failed = sum(r.failed for r in results)
        self.query_one("#footer-pending", Static).update(
            f"diff: {ok} would-link, {failed} errors"
        )

    def action_apply(self) -> None:
        grid = self.query_one("#asset-grid", AssetGrid)
        results = self._apply_pending(dry_run=False, grid=grid)
        # Refresh state after apply (per spec: always reconcile)
        self.state = build_state(self.runner)
        grid.update_state(self.state)
        ok = sum(r.ok for r in results)
        failed = sum(r.failed for r in results)
        if failed == 0:
            grid.clear_pending()
        self._refresh_pending_label()
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
        n = len(self.query_one("#asset-grid", AssetGrid).pending_entries())
        self.query_one("#footer-pending", Static).update(f"Pending: {n}")


# --------------------------------------------------------------------------
# Entry point — both the interactive TUI and the --headless mode used by
# Layer-3 bats smoke tests live here.
# --------------------------------------------------------------------------

def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="agent-toolkit-tui",
        description="Textual cockpit for agent-toolkit.",
    )
    p.add_argument("--toolkit-repo", dest="toolkit_repo", type=Path, default=Path.cwd(),
                   help="Path to the agent-toolkit repo (default: current directory).")
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
    toolkit_root = args.toolkit_repo.resolve()

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
