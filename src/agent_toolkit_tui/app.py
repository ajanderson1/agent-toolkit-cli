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
from textual.containers import Horizontal
from textual.widgets import Checkbox, Footer, Header, Static

from agent_toolkit_tui.messages import (
    AssetToggled,
    HarnessVisibilityChanged,
    KindChanged,
    ScopeChanged,
)
from agent_toolkit_tui.runner import CLIRunner, PlanResult, RunnerError
from agent_toolkit_tui.state import InventoryState, build_state
from agent_toolkit_tui.widgets import AssetGrid, HarnessPicker, KindsSidebar


class TUIApp(App):
    """agent-toolkit-tui — Textual cockpit over bin/agent-toolkit."""

    CSS_PATH = "css/app.tcss"
    TITLE = "agent-toolkit-tui"

    BINDINGS = [
        Binding("ctrl+s", "apply", "Apply", priority=True),
        Binding("ctrl+d", "diff", "Diff", priority=True),
        Binding("ctrl+r", "refresh", "Refresh", priority=True),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, repo_root: Path, runner: CLIRunner | None = None) -> None:
        super().__init__()
        self.repo_root = repo_root
        self.runner = runner or CLIRunner(repo_root=repo_root)
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

    def on_harness_visibility_changed(self, event: HarnessVisibilityChanged) -> None:
        grid = self.query_one("#asset-grid", AssetGrid)
        # Walk the picker's checkboxes to figure out the new set.
        visible = []
        for h in self.state.all_harnesses:
            cb = self.query_one(f"#hcb-{h}", Checkbox)
            if cb.value:
                visible.append(h)
        grid.set_visible_harnesses(visible)

    def on_asset_toggled(self, event: AssetToggled) -> None:
        self._refresh_pending_label()

    # ----- actions --------------------------------------------------------
    def action_refresh(self) -> None:
        self.state = build_state(self.runner)
        self.query_one("#asset-grid", AssetGrid).update_state(self.state)
        self.query_one("#kinds-sidebar", KindsSidebar).update_state(self.state)
        self._refresh_pending_label()

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
    p.add_argument("--repo-root", type=Path, default=Path.cwd(),
                   help="Repo root (default: current directory).")
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
    repo_root = args.repo_root.resolve()

    if args.headless:
        if args.plan is None:
            print("--headless requires --plan", file=sys.stderr)
            return 2
        runner = CLIRunner(repo_root=repo_root)
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

    TUIApp(repo_root=repo_root).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
