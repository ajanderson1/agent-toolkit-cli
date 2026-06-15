"""The Textual App + main() entry point for agent-toolkit-tui.

Skill + Pi-extension cockpit over the v3 `agent-toolkit-cli` surface. Reads
locks + filesystem directly via `agent_toolkit_cli.*` modules and applies
pending toggles by calling the shipped CLI facades in-process.

Layout (matches existing CSS scaffold in css/app.tcss):

  Header
  Horizontal#main
    Vertical#asset-types-sidebar
      Static.rail-header
      OptionList#asset-types-list  ("instruction" / separator / "skill" / "pi-extension" / "agent")
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
from pathlib import Path
from typing import Iterable, Literal, cast

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import (
    Button, Footer, Header, Input, Label, OptionList, Static,
)
from textual.widgets.option_list import Option, OptionDoesNotExist

from agent_toolkit_tui import __version__
from agent_toolkit_tui.agent_state import build_agent_rows
from agent_toolkit_tui.instruction_state import build_instruction_rows
from agent_toolkit_tui.mcp_state import build_mcp_rows
from agent_toolkit_tui.pi_extension_state import build_pi_rows
from agent_toolkit_tui.skill_state import build_skill_rows
from agent_toolkit_tui.widgets import (
    AgentGrid,
    InstructionGrid,
    McpGrid,
    PiGrid,
    ScopeToggle,
    SkillGrid,
)

AssetType = Literal["instruction", "skill", "pi-extension", "agent", "mcp"]

_ASSET_TYPE_LABELS: dict[AssetType, str] = {
    "instruction": "Instruction",
    "skill": "Skill",
    "pi-extension": "Pi Extension",
    "agent": "Agent",
    "mcp": "MCP",
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
    """agent-toolkit-tui — Textual cockpit over `agent-toolkit-cli`."""

    CSS_PATH = "css/app.tcss"
    TITLE = "agent-toolkit-tui"

    BINDINGS = [
        Binding("ctrl+s", "apply", "Apply", priority=True),
        Binding("ctrl+d", "diff", "Diff", priority=True),
        Binding("ctrl+r", "refresh", "Refresh", priority=True),
        Binding("ctrl+z", "revert", "Revert", priority=True),
        Binding("slash", "focus_filter", "Filter", priority=True),
        Binding("ctrl+g", "scope_toggle", "toggle scope", priority=True),
        Binding("i", "info_pass", "Info"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._scope: str = "project"
        self._active_asset_type: AssetType = "skill"
        self.sub_title = f"v{__version__}"

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            with Vertical(id="asset-types-sidebar"):
                yield Static("Asset type", classes="rail-header")
                yield OptionList(
                    Option("instruction", id="asset-type-instruction"),
                    Option("─────────────", id="asset-type-separator", disabled=True),
                    Option("skill", id="asset-type-skill"),
                    Option("pi-extension", id="asset-type-pi-extension"),
                    Option("agent", id="asset-type-agent"),
                    Option("mcp", id="asset-type-mcp"),
                    id="asset-types-list",
                )
            with Vertical(id="content"):
                with Horizontal(id="content-header-row"):
                    yield Static(self._build_content_header(), id="content-header")
                    yield ScopeToggle(active=self._scope, id="scope-toggle")
                yield InstructionGrid([], id="instruction-grid")
                yield SkillGrid([], id="skill-grid")
                yield PiGrid([], id="pi-grid")
                yield AgentGrid([], id="agent-grid")
                yield McpGrid([], id="mcp-grid")
        yield Static("", id="status-bar")
        yield Static("", id="footer-pending")
        yield Footer()

    def on_mount(self) -> None:
        try:
            self.theme = "gruvbox"
        except Exception:
            pass
        # Start with the skill asset type active; hide others initially.
        self._show_asset_type("skill")
        self._refresh_skill_view()
        self._refresh_content_header()
        self._refresh_pending_label()
        self._refresh_status_bar()
        # Focus the filter box on open (#249).
        try:
            self.query_one("#skill-filter", Input).focus()
        except Exception:
            pass

    # ----- asset-type switching -----------------------------------------------------

    def _show_asset_type(self, asset_type: AssetType) -> None:
        """Show the active grid and hide the inactive ones."""
        try:
            instruction_grid = self.query_one("#instruction-grid", InstructionGrid)
            skill_grid = self.query_one("#skill-grid", SkillGrid)
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
            asset_types_list = self.query_one("#asset-types-list", OptionList)
            asset_types_list.highlighted = asset_types_list.get_option_index(f"asset-type-{asset_type}")
        except (NoMatches, OptionDoesNotExist):
            pass

        if asset_type == "instruction":
            instruction_grid.display = True
            skill_grid.display = False
            pi_grid.display = False
            agent_grid.display = False
            mcp_grid.display = False
            scope_toggle.display = True
        elif asset_type == "skill":
            instruction_grid.display = False
            skill_grid.display = True
            pi_grid.display = False
            agent_grid.display = False
            mcp_grid.display = False
            scope_toggle.display = True
        elif asset_type == "pi-extension":
            instruction_grid.display = False
            skill_grid.display = False
            pi_grid.display = True
            agent_grid.display = False
            mcp_grid.display = False
            scope_toggle.display = True
        elif asset_type == "agent":
            instruction_grid.display = False
            skill_grid.display = False
            pi_grid.display = False
            agent_grid.display = True
            mcp_grid.display = False
            scope_toggle.display = True
        else:  # "mcp"
            instruction_grid.display = False
            skill_grid.display = False
            pi_grid.display = False
            agent_grid.display = False
            mcp_grid.display = True
            scope_toggle.display = True

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        """Handle sidebar asset-type selection."""
        if event.option_list.id != "asset-types-list":
            return
        opt_id = event.option.id
        # Guard against separator or unknown options.
        if opt_id is None or opt_id == "asset-type-separator":
            return
        if opt_id == "asset-type-instruction":
            self.action_asset_type("instruction")
        elif opt_id == "asset-type-skill":
            self.action_asset_type("skill")
        elif opt_id == "asset-type-pi-extension":
            self.action_asset_type("pi-extension")
        elif opt_id == "asset-type-agent":
            self.action_asset_type("agent")
        elif opt_id == "asset-type-mcp":
            self.action_asset_type("mcp")

    def action_asset_type(self, asset_type: str) -> None:
        if asset_type not in ("instruction", "skill", "pi-extension", "agent", "mcp"):
            return
        if asset_type == self._active_asset_type:
            return
        self._active_asset_type = asset_type  # type: ignore[assignment]
        self._show_asset_type(asset_type)  # type: ignore[arg-type]
        self._refresh_active_view()
        self._refresh_content_header()
        self._refresh_pending_label()
        self._refresh_status_bar()

    # ----- instruction-view --------------------------------------------------

    def _scope_to_roots(self) -> tuple[str, Path | None, Path | None]:
        if self._scope == "global":
            return "global", Path.home(), None
        return "project", Path.home(), Path.cwd()

    def _active_grid(
        self,
    ) -> InstructionGrid | SkillGrid | PiGrid | AgentGrid | McpGrid | None:
        selector: str
        if self._active_asset_type == "instruction":
            selector = "#instruction-grid"
        elif self._active_asset_type == "skill":
            selector = "#skill-grid"
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
        if self._active_asset_type == "instruction":
            self._refresh_instruction_view()
        elif self._active_asset_type == "skill":
            self._refresh_skill_view()
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
        grid.set_scope(scope)  # type: ignore[arg-type]
        grid.set_rows(build_instruction_rows(scope=scope, home=home, project=project))  # type: ignore[arg-type]

    # ----- skill-view --------------------------------------------------------

    def _refresh_skill_view(self) -> None:
        try:
            grid = self.query_one("#skill-grid", SkillGrid)
        except NoMatches:
            return
        scope, home, project = self._scope_to_roots()
        grid.set_scope(scope)
        grid.set_rows(build_skill_rows(scope=scope, home=home, project=project))

    # ----- pi-view -----------------------------------------------------------

    def _refresh_pi_view(self) -> None:
        try:
            grid = self.query_one("#pi-grid", PiGrid)
        except NoMatches:
            return
        grid.set_scope(self._scope)  # type: ignore[arg-type]
        grid.set_rows(build_pi_rows(home=Path.home(), project=Path.cwd()))

    # ----- agent-view --------------------------------------------------------

    def _refresh_agent_view(self) -> None:
        try:
            grid = self.query_one("#agent-grid", AgentGrid)
        except NoMatches:
            return
        scope, home, project = self._scope_to_roots()
        grid.set_scope(scope)  # type: ignore[arg-type]
        grid.set_rows(build_agent_rows(scope=scope, home=home, project=project))  # type: ignore[arg-type]

    # ----- mcp-view ----------------------------------------------------------

    def _refresh_mcp_view(self) -> None:
        try:
            grid = self.query_one("#mcp-grid", McpGrid)
        except NoMatches:
            return
        scope, home, project = self._scope_to_roots()
        grid.set_scope(scope)  # type: ignore[arg-type]
        grid.set_rows(build_mcp_rows(scope=scope, home=home, project=project))  # type: ignore[arg-type]

    # ----- messages ----------------------------------------------------------

    def on_instruction_grid_pending_changed(
        self, event: InstructionGrid.PendingChanged
    ) -> None:
        """Live-update footer + status bar when the instruction grid's pending set changes."""
        self._refresh_pending_label()
        self._refresh_status_bar()

    def on_skill_grid_pending_changed(
        self, event: SkillGrid.PendingChanged
    ) -> None:
        """Live-update footer + status bar when the skill grid's pending set changes."""
        self._refresh_pending_label()
        self._refresh_status_bar()

    def on_pi_grid_pending_changed(
        self, event: PiGrid.PendingChanged
    ) -> None:
        """Live-update footer + status bar when the pi grid's pending set changes."""
        self._refresh_pending_label()
        self._refresh_status_bar()

    def on_agent_grid_pending_changed(
        self, event: AgentGrid.PendingChanged
    ) -> None:
        """Live-update footer + status bar when the agent grid's pending set changes."""
        self._refresh_pending_label()
        self._refresh_status_bar()

    def on_mcp_grid_pending_changed(
        self, event: McpGrid.PendingChanged
    ) -> None:
        """Live-update footer + status bar when the MCP grid's pending set changes."""
        self._refresh_pending_label()
        self._refresh_status_bar()

    # ----- actions -----------------------------------------------------------

    def action_quit(self) -> None:
        n = 0
        try:
            n += len(self.query_one("#instruction-grid", InstructionGrid).pending_entries())
        except NoMatches:
            pass
        try:
            n += len(self.query_one("#skill-grid", SkillGrid).pending_entries())
        except NoMatches:
            pass
        try:
            n += len(self.query_one("#pi-grid", PiGrid).pending_entries())
        except NoMatches:
            pass
        try:
            n += len(self.query_one("#agent-grid", AgentGrid).pending_entries())
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

    def action_focus_filter(self) -> None:
        """`/` re-focuses the filter box (restores v1 muscle memory, #249)."""
        try:
            self.query_one("#skill-filter", Input).focus()
        except NoMatches:
            pass

    def action_info_pass(self) -> None:
        """Delegate `i` to the active grid widget."""
        if self._active_asset_type == "instruction":
            try:
                igrid = self.query_one("#instruction-grid", InstructionGrid)
            except NoMatches:
                return
            igrid.action_info()
        elif self._active_asset_type == "skill":
            try:
                sgrid = self.query_one("#skill-grid", SkillGrid)
            except NoMatches:
                return
            sgrid.action_info()
        elif self._active_asset_type == "pi-extension":
            try:
                pgrid = self.query_one("#pi-grid", PiGrid)
            except NoMatches:
                return
            pgrid.action_info()
        else:
            try:
                agrid = self.query_one("#agent-grid", AgentGrid)
            except NoMatches:
                return
            agrid.action_info()

    def action_refresh(self) -> None:
        self._refresh_active_view()
        self._refresh_pending_label()
        self._refresh_content_header()
        self._refresh_status_bar()

    def action_revert(self) -> None:
        grid = self._active_grid()
        if grid is None:
            return
        # ctrl+z clears the active grid's WHOLE queue — both scopes, including
        # ops queued in the currently-invisible scope — and says so (#349).
        keys = list(grid.pending_entries().keys())
        n = len(keys)
        grid.clear_pending()
        self._refresh_pending_label()
        self.query_one("#footer-pending", Static).update(
            f"reverted: {n} pending cleared{_scope_tag(keys)}"
        )

    def action_diff(self) -> None:
        grid = self._active_grid()
        if grid is None:
            return
        pending = grid.pending_entries()
        n_link = sum(1 for op in pending.values() if op == "link")
        n_unlink = sum(1 for op in pending.values() if op == "unlink")
        self.query_one("#footer-pending", Static).update(
            f"diff: {n_link} would-link, {n_unlink} would-unlink{_scope_tag(pending)}"
        )

    def action_apply(self) -> None:
        if self._active_asset_type == "instruction":
            self._apply_instruction_pending()
        elif self._active_asset_type == "skill":
            self._apply_skill_pending()
        elif self._active_asset_type == "pi-extension":
            self._apply_pi_pending()
        elif self._active_asset_type == "mcp":
            self._apply_mcp_pending()
        else:
            self._apply_agent_pending()

    def _apply_instruction_pending(self) -> None:
        """Apply pending instruction pointer toggles.

        Apply semantics (different from skill/agent): instructions_install.apply
        reconciles the WHOLE scope lock to disk — it takes no per-harness
        add/remove. So per scope we:
          1. Mutate every pending slug entry's harnesses list (adds/removes);
             an entry left with no harnesses is pruned (matches the CLI's
             uninstall #312 contract — never leave an empty stub).
          2. write_lock(), then call apply() ONCE for the scope.
          3. On failure (CanonicalMissingError / PointerConflictError) roll the
             lock back to its prior state — apply() reads the lock from disk, so
             a failed reconcile would otherwise leave the lock lying about disk.
             Mirrors commands/instructions/install_cmd.py's rollback contract.
        """
        from agent_toolkit_cli import instructions_install
        from agent_toolkit_cli.instructions_adapters.symlink import (
            PointerConflictError,
        )
        from agent_toolkit_cli.instructions_lock import (
            InstructionsLockEntry, add_entry, read_lock, remove_entry,
            write_lock,
        )
        from agent_toolkit_cli.instructions_paths import lock_file_path

        try:
            grid = self.query_one("#instruction-grid", InstructionGrid)
        except NoMatches:
            return
        pending = grid.pending_entries()
        if not pending:
            return
        tag = _scope_tag(pending)

        # Group by scope → {slug: (adds set, removes set)}. apply() is
        # whole-lock, so all mutations for a scope are written before its single
        # apply() call — this also keeps ok/failed counts correct if the lock
        # ever holds more than one slug per scope (the keyed-by-slug shape the
        # lock model is forward-compatible with).
        by_scope: dict[str, dict[str, tuple[set[str], set[str]]]] = defaultdict(
            lambda: defaultdict(lambda: (set(), set()))
        )
        for (scope, harness, slug), op in pending.items():
            adds, removes = by_scope[scope][slug]
            (adds if op == "link" else removes).add(harness)

        ok = failed = 0
        errors: list[str] = []

        for scope, slugs in by_scope.items():
            home = Path.home() if scope == "global" else None
            project = None if scope == "global" else Path.cwd()
            n_writes = sum(len(a) + len(r) for a, r in slugs.values())

            lpath = lock_file_path(scope, project)  # type: ignore[arg-type]
            prior = read_lock(lpath)
            prior_existed = lpath.exists()

            # Apply every slug mutation onto a working copy of the lock.
            updated_lock = prior
            for slug, (adds, removes) in slugs.items():
                if slug in updated_lock.instructions:
                    entry = updated_lock.instructions[slug]
                    new_harnesses = list(entry.harnesses)
                    for h in adds:
                        if h not in new_harnesses:
                            new_harnesses.append(h)
                    for h in removes:
                        if h in new_harnesses:
                            new_harnesses.remove(h)
                    if new_harnesses:
                        updated_lock = add_entry(
                            updated_lock,
                            slug,
                            InstructionsLockEntry(
                                scope=entry.scope,
                                source=entry.source,
                                harnesses=new_harnesses,
                            ),
                        )
                    else:
                        # No harnesses left — prune the entry rather than
                        # writing an empty stub the CLI would never produce.
                        updated_lock = remove_entry(updated_lock, slug)
                elif adds:
                    updated_lock = add_entry(
                        updated_lock,
                        slug,
                        InstructionsLockEntry(
                            scope=scope,  # type: ignore[arg-type]
                            source="AGENTS.md",
                            harnesses=sorted(adds),
                        ),
                    )
                # else: only removes and no existing entry — nothing to do.

            # Write the mutated lock, reconcile once, roll back on failure.
            if updated_lock.instructions:
                write_lock(lpath, updated_lock)
            elif prior_existed:
                # Lock emptied entirely — delete it (#312), don't write `{}`.
                lpath.unlink()
            try:
                plan = instructions_install.apply(
                    scope=scope,  # type: ignore[arg-type]
                    project_root=project,
                    home=home,
                )
                created = sum(1 for a in plan.actions if a.action == "create")
                removed = sum(1 for a in plan.actions if a.action == "remove")
                ok += created + removed
            except (
                instructions_install.CanonicalMissingError,
                PointerConflictError,
            ) as exc:
                # Reconcile failed — restore the lock to its prior state so it
                # never claims an install that did not land on disk.
                if prior_existed:
                    write_lock(lpath, prior)
                else:
                    lpath.unlink(missing_ok=True)
                errors.append(f"{scope}: {exc}")
                failed += n_writes

        saved = grid.pending_entries() if failed else {}
        if failed == 0:
            grid.clear_pending()
        self._refresh_instruction_view()
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
        tag = _scope_tag(pending)
        by_slug: dict[tuple[str, str], tuple[set[str], set[str]]] = defaultdict(
            lambda: (set(), set())
        )
        for (scope, agent, slug), op in pending.items():
            adds, removes = by_slug[(scope, slug)]
            (adds if op == "link" else removes).add(agent)
        ok = failed = 0
        errors: list[str] = []
        failed_groups: set[tuple[str, str]] = set()
        for (scope, slug), (adds, removes) in by_slug.items():
            n_writes = len(adds) + len(removes)
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
                    errors.append(f"{slug}: {exc}")
                    failed += n_writes
                    failed_groups.add((scope, slug))
                    continue
            p = InstallPlan(
                slug=slug, scope=scope, source=None, ref=None,
                add_agents=tuple(sorted(adds)),
                remove_agents=tuple(sorted(removes)),
            )
            try:
                result = engine_apply(p, home=home, project=project, env=None)
                ok += len(result.created) + len(result.removed)
                if scope == "project" and not adds:
                    self._drop_project_entry_if_unlisted_and_unlinked(
                        slug=slug, project=project,  # type: ignore[arg-type]
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
        saved = {
            k: v
            for k, v in grid.pending_entries().items()
            if (k[0], k[2]) in failed_groups
        } if failed else {}
        if failed == 0:
            grid.clear_pending()
        self._refresh_skill_view()
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

    def _drop_project_entry_if_unlisted_and_unlinked(
        self, *, slug: str, project: Path,
    ) -> None:
        """#360 AC2: after a remove-only apply, drop the project lock entry of
        an UNLISTED slug once no projection symlink remains. Listed slugs keep
        today's behaviour (entry stays; the row remains visible via the
        library universe). Non-destructive: the external-store canonical is
        preserved; doctor's orphan sweep reclaims it if unreferenced."""
        from agent_toolkit_cli.skill_agents import AGENTS
        from agent_toolkit_cli.skill_lock import read_lock, remove_entry, write_lock
        from agent_toolkit_cli.skill_paths import library_lock_path, lock_file_path
        from agent_toolkit_tui.skill_state import _cell_for

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

    def _apply_pi_pending(self) -> None:
        from agent_toolkit_cli import (
            _pi_settings, pi_extension_install, pi_extension_ops,
        )
        from agent_toolkit_cli.pi_extension_lock import read_lock
        from agent_toolkit_cli.pi_extension_paths import library_lock_path

        try:
            grid = self.query_one("#pi-grid", PiGrid)
        except NoMatches:
            return
        pending = grid.pending_entries()
        if not pending:
            return
        tag = _scope_tag(pending)

        home = Path.home()
        ok = failed = 0
        errors: list[str] = []

        # Read the global library lock once — it is the universe of slugs.
        try:
            glob_lock = read_lock(library_lock_path(env={}))
        except Exception as exc:
            self.query_one("#footer-pending", Static).update(
                f"[red]apply failed[/] — could not read global lock: {exc}"
            )
            self.notify(
                str(exc),
                title="Apply: could not read global lock",
                severity="error",
                timeout=12,
            )
            return

        _Scope = Literal["global", "project"]
        for (scope_str, slug), op in pending.items():
            scope = cast(_Scope, scope_str)
            project = Path.cwd() if scope == "project" else None
            if slug not in glob_lock.skills:
                # Untracked slug — no lock entry, skip (untracked rows are
                # non-interactive; guard mirrors the old behaviour).
                continue
            try:
                if op == "link":
                    pi_extension_ops.install(
                        slug=slug, scope=scope, home=home, project=project
                    )
                else:
                    pi_extension_ops.uninstall(
                        slug=slug, scope=scope, home=home, project=project
                    )
                ok += 1
            except (pi_extension_install.InstallError, _pi_settings.PiSettingsError) as exc:
                errors.append(f"{slug}: {exc}")
                failed += 1

        saved = grid.pending_entries() if failed else {}
        if failed == 0:
            grid.clear_pending()
        self._refresh_pi_view()
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

    def _apply_agent_pending(self) -> None:
        import shutil

        from agent_toolkit_cli import agent_install
        from agent_toolkit_cli._install_core import InstallError, InstallPlan
        from agent_toolkit_cli.agent_paths import canonical_agent_dir

        try:
            grid = self.query_one("#agent-grid", AgentGrid)
        except NoMatches:
            return
        pending = grid.pending_entries()
        if not pending:
            return
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

        for (scope, slug), (adds, removes) in by_slug.items():
            # Global scope MUST pass home=Path.home() so adapters' {HOME}
            # templates don't raise ValueError.
            effective_home = Path.home() if scope == "global" else None
            project = None if scope == "global" else Path.cwd()

            # Project scope: seed canonical from global if not already present.
            if scope == "project" and project is not None:
                canonical = canonical_agent_dir(slug, scope="project", project=project)
                if not canonical.exists():
                    global_canonical = canonical_agent_dir(slug, scope="global")
                    if global_canonical.exists():
                        try:
                            canonical.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copytree(global_canonical, canonical)
                        except OSError as exc:
                            errors.append(f"{slug}: could not seed project canonical: {exc}")
                            failed += len(adds) + len(removes)
                            continue

            # Adds → agent_install.apply()
            if adds:
                p = InstallPlan(
                    slug=slug, scope=scope,  # type: ignore[arg-type]
                    source=None, ref=None,
                    add_agents=tuple(sorted(adds)),
                    remove_agents=(),
                )
                try:
                    result = agent_install.apply(p, home=effective_home, project=project)
                    ok += len(result.created)
                except InstallError as exc:
                    # #373: the facade seam already prefixed the slug — do not
                    # double it ("my-agent: my-agent: ...").
                    errors.append(str(exc))
                    failed += len(adds)
                except ValueError as exc:
                    # A ValueError NOT routed through the seam (e.g. a bad
                    # scope/home arg) carries no slug — prefix it ourselves.
                    errors.append(f"{slug}: {exc}")
                    failed += len(adds)

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
                    refusals = agent_install.uninstall(
                        slug=slug,
                        scope=scope,  # type: ignore[arg-type]
                        home=effective_home,
                        project=project,
                        harnesses=tuple(sorted(removes)),
                    ) or ()
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
                except ValueError as exc:
                    # ValueError bypasses the seam — prefix the slug ourselves.
                    errors.append(f"{slug}: {exc}")
                    failed += len(removes)

        saved = grid.pending_entries() if failed else {}
        if failed == 0:
            grid.clear_pending()
        self._refresh_agent_view()
        if saved:
            grid.restore_pending(saved)
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

    def _apply_mcp_pending(self) -> None:
        from agent_toolkit_cli import mcp_install
        from agent_toolkit_cli._install_core import InstallError
        from agent_toolkit_cli.mcp_library import library_root

        try:
            grid = self.query_one("#mcp-grid", McpGrid)
        except NoMatches:
            return
        pending = grid.pending_entries()
        if not pending:
            return
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
        # Derive roots from the SSOT the grid was built against (review F-cwd) —
        # NOT a fresh Path.cwd()/Path.home(), so the apply target is guaranteed
        # identical to the displayed grid (the project .mcp.json / project lock
        # are repo-root files; a cwd drift would mutate the wrong project).
        active_scope, home, active_project = self._scope_to_roots()
        # _scope_to_roots always returns Path.home() for home (both scopes); the
        # MCP adapters need a real home for sentinel checks even at project scope.
        # Fail loud rather than silently passing None into the facade.
        assert home is not None

        for (scope, slug), (adds, removes) in by_slug.items():
            # The pending key's scope wins per-entry, but home/project come from
            # the active roots; project is None at global, the active project root
            # otherwise. (Pending only ever carries the active scope today.)
            project = None if scope == "global" else active_project
            lib_root = library_root(home)
            if adds:
                try:
                    result = mcp_install.apply(
                        slug=slug, harnesses=sorted(adds), scope=scope,
                        library_root=lib_root, home=home, project=project,
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
                        slug=slug, harnesses=sorted(removes), scope=scope,
                        library_root=lib_root, home=home, project=project,
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

    # ----- header + status ---------------------------------------------------

    def _build_content_header(self) -> str:
        asset_type_label = _ASSET_TYPE_LABELS.get(self._active_asset_type, self._active_asset_type)
        if self._active_asset_type == "instruction":
            try:
                n = self.query_one("#instruction-grid", InstructionGrid).row_count
            except (NoMatches, Exception):
                n = 0
        elif self._active_asset_type == "skill":
            try:
                n = self.query_one("#skill-grid", SkillGrid).row_count
            except (NoMatches, Exception):
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
        return f"  [b]{asset_type_label}[/]   [dim]·[/]   {n} items"

    def _refresh_content_header(self) -> None:
        try:
            self.query_one("#content-header", Static).update(
                self._build_content_header()
            )
        except Exception:
            pass

    def _refresh_pending_label(self) -> None:
        keys: list[tuple[str, ...]] = []
        for selector in ("#instruction-grid", "#skill-grid", "#pi-grid", "#agent-grid", "#mcp-grid"):
            try:
                keys.extend(self.query_one(selector).pending_entries().keys())  # type: ignore[attr-defined]
            except Exception:
                pass
        try:
            self.query_one("#footer-pending", Static).update(
                f"Pending: {len(keys)}{_scope_tag(keys)}"
            )
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
            text = (
                f"  [b green]{linked}[/] linked   "
                f"[b yellow]{pending}[/] pending"
            )
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
            loaded = 0
            try:
                grid_pi = self.query_one("#pi-grid", PiGrid)
            except (NoMatches, Exception):
                grid_pi = None
            if grid_pi is not None:
                scope = self._scope_to_roots()[0]
                for pi_row in grid_pi._rows:
                    if scope == "global":
                        if pi_row.global_cell.global_loaded:
                            loaded += 1
                    elif pi_row.project_cell.project_loaded:
                        loaded += 1
                pending = len(grid_pi.pending_entries())
            else:
                pending = 0
            text = (
                f"  [b green]{loaded}[/] loaded   "
                f"[b yellow]{pending}[/] pending"
            )
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
            text = (
                f"  [b green]{linked}[/] linked   "
                f"[b yellow]{pending}[/] pending"
            )
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
            text = (
                f"  [b green]{linked}[/] linked   "
                f"[b yellow]{pending}[/] pending"
            )
        try:
            self.query_one("#status-bar", Static).update(text)
        except Exception:
            pass


def main() -> int:
    import sys

    argv = sys.argv[1:]
    if argv and argv[0] in ("--version", "-V"):
        print(f"agent-toolkit-tui, version {__version__}")
        return 0
    TUIApp().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
