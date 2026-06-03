"""The Textual App + main() entry point for agent-toolkit-tui.

Skill + Pi-extension cockpit over the v3 `agent-toolkit-cli` surface. Reads
locks + filesystem directly via `agent_toolkit_cli.*` modules and applies
pending toggles by calling the shipped CLI facades in-process.

Layout (matches existing CSS scaffold in css/app.tcss):

  Header
  Horizontal#main
    Vertical#kinds-sidebar
      Static.rail-header
      OptionList#kinds-list  ("skill" / "pi-extension" / "agent")
    Vertical#content
      Horizontal#content-header-row
        Static#content-header
        [ScopeToggle — skill and agent kinds only]
      SkillGrid | PiGrid | AgentGrid   (swapped by action_kind)
  Static#status-bar
  Static#footer-pending
  Footer
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Literal, cast

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import (
    Button, Footer, Header, Input, Label, OptionList, Static,
)
from textual.widgets.option_list import Option

from agent_toolkit_tui import __version__
from agent_toolkit_tui.agent_state import build_agent_rows
from agent_toolkit_tui.instruction_state import build_instruction_rows
from agent_toolkit_tui.pi_extension_state import build_pi_rows
from agent_toolkit_tui.skill_state import build_skill_rows
from agent_toolkit_tui.widgets import AgentGrid, InstructionGrid, PiGrid, ScopeToggle, SkillGrid

Kind = Literal["skill", "pi-extension", "agent", "instruction"]

_KIND_LABELS: dict[str, str] = {
    "skill": "Skill",
    "pi-extension": "Pi Extension",
    "agent": "Agent",
    "instruction": "Instruction",
}


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
        Binding("s", "scope_toggle", "toggle scope"),
        Binding("i", "info_pass", "Info"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._scope: str = "project"
        self._active_kind: Kind = "skill"
        self.sub_title = f"v{__version__}"

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            with Vertical(id="kinds-sidebar"):
                yield Static("Kind", classes="rail-header")
                yield OptionList(
                    # Instruction renders FIRST — above all other kinds.
                    Option("Instruction", id="kind-instruction"),
                    None,  # visual separator between instruction and the rest
                    Option("skill", id="kind-skill"),
                    Option("pi-extension", id="kind-pi-extension"),
                    Option("agent", id="kind-agent"),
                    id="kinds-list",
                )
            with Vertical(id="content"):
                with Horizontal(id="content-header-row"):
                    yield Static(self._build_content_header(), id="content-header")
                    yield ScopeToggle(active=self._scope, id="scope-toggle")
                yield InstructionGrid([], id="instruction-grid")
                yield SkillGrid([], id="skill-grid")
                yield PiGrid([], id="pi-grid")
                yield AgentGrid([], id="agent-grid")
        yield Static("", id="status-bar")
        yield Static("", id="footer-pending")
        yield Footer()

    def on_mount(self) -> None:
        try:
            self.theme = "gruvbox"
        except Exception:
            pass
        # Start with skill kind active; hide instruction-grid, pi-grid and agent-grid initially.
        self._show_kind("skill")
        self._refresh_skill_view()
        self._refresh_content_header()
        self._refresh_pending_label()
        self._refresh_status_bar()
        # Focus the filter box on open (#249).
        try:
            self.query_one("#skill-filter", Input).focus()
        except Exception:
            pass

    # ----- kind switching ----------------------------------------------------

    def _show_kind(self, kind: Kind) -> None:
        """Show the active grid and hide the inactive ones."""
        try:
            instr_grid = self.query_one("#instruction-grid", InstructionGrid)
            skill_grid = self.query_one("#skill-grid", SkillGrid)
            pi_grid = self.query_one("#pi-grid", PiGrid)
            agent_grid = self.query_one("#agent-grid", AgentGrid)
            scope_toggle = self.query_one("#scope-toggle", ScopeToggle)
        except NoMatches:
            return

        if kind == "instruction":
            instr_grid.display = True
            skill_grid.display = False
            pi_grid.display = False
            agent_grid.display = False
            scope_toggle.display = False
        elif kind == "skill":
            instr_grid.display = False
            skill_grid.display = True
            pi_grid.display = False
            agent_grid.display = False
            scope_toggle.display = True
        elif kind == "pi-extension":
            instr_grid.display = False
            skill_grid.display = False
            pi_grid.display = True
            agent_grid.display = False
            scope_toggle.display = False
        else:  # "agent"
            instr_grid.display = False
            skill_grid.display = False
            pi_grid.display = False
            agent_grid.display = True
            scope_toggle.display = True

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        """Handle sidebar kind selection."""
        if event.option_list.id != "kinds-list":
            return
        opt_id = event.option.id
        if opt_id == "kind-instruction":
            self.action_kind("instruction")
        elif opt_id == "kind-skill":
            self.action_kind("skill")
        elif opt_id == "kind-pi-extension":
            self.action_kind("pi-extension")
        elif opt_id == "kind-agent":
            self.action_kind("agent")

    def action_kind(self, kind: str) -> None:
        if kind not in ("skill", "pi-extension", "agent", "instruction"):
            return
        if kind == self._active_kind:
            return
        self._active_kind = kind  # type: ignore[assignment]
        self._show_kind(kind)  # type: ignore[arg-type]
        if kind == "skill":
            self._refresh_skill_view()
        elif kind == "pi-extension":
            self._refresh_pi_view()
        elif kind == "instruction":
            self._refresh_instruction_view()
        else:
            self._refresh_agent_view()
        self._refresh_content_header()
        self._refresh_pending_label()
        self._refresh_status_bar()

    # ----- skill-view --------------------------------------------------------

    def _scope_to_roots(self) -> tuple[str, Path | None, Path | None]:
        if self._scope == "global":
            return "global", Path.home(), None
        return "project", Path.home(), Path.cwd()

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

    # ----- instruction-view --------------------------------------------------

    def _refresh_instruction_view(self) -> None:
        try:
            grid = self.query_one("#instruction-grid", InstructionGrid)
        except NoMatches:
            return
        grid.set_rows(build_instruction_rows(home=Path.home(), project=Path.cwd()))

    # ----- messages ----------------------------------------------------------

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

    def on_instruction_grid_pending_changed(
        self, event: InstructionGrid.PendingChanged
    ) -> None:
        """Live-update footer + status bar when the instruction grid's pending set changes."""
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
        if self._active_kind == "agent":
            self._refresh_agent_view()
        else:
            self._refresh_skill_view()
        self._refresh_content_header()
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
        if self._active_kind == "skill":
            try:
                sgrid = self.query_one("#skill-grid", SkillGrid)
            except NoMatches:
                return
            sgrid.action_info()
        elif self._active_kind == "pi-extension":
            try:
                pgrid = self.query_one("#pi-grid", PiGrid)
            except NoMatches:
                return
            pgrid.action_info()
        elif self._active_kind == "instruction":
            try:
                igrid = self.query_one("#instruction-grid", InstructionGrid)
            except NoMatches:
                return
            igrid.action_info()
        else:
            try:
                agrid = self.query_one("#agent-grid", AgentGrid)
            except NoMatches:
                return
            agrid.action_info()

    def action_refresh(self) -> None:
        if self._active_kind == "skill":
            self._refresh_skill_view()
        elif self._active_kind == "pi-extension":
            self._refresh_pi_view()
        elif self._active_kind == "instruction":
            self._refresh_instruction_view()
        else:
            self._refresh_agent_view()
        self._refresh_pending_label()
        self._refresh_content_header()
        self._refresh_status_bar()

    def action_revert(self) -> None:
        if self._active_kind == "skill":
            try:
                sgrid = self.query_one("#skill-grid", SkillGrid)
            except NoMatches:
                return
            n = len(sgrid.pending_entries())
            sgrid.clear_pending()
            self._refresh_pending_label()
            self.query_one("#footer-pending", Static).update(
                f"reverted: {n} pending cleared"
            )
        elif self._active_kind == "pi-extension":
            try:
                pgrid = self.query_one("#pi-grid", PiGrid)
            except NoMatches:
                return
            n = len(pgrid.pending_entries())
            pgrid.clear_pending()
            self._refresh_pending_label()
            self.query_one("#footer-pending", Static).update(
                f"reverted: {n} pending cleared"
            )
        elif self._active_kind == "instruction":
            try:
                igrid = self.query_one("#instruction-grid", InstructionGrid)
            except NoMatches:
                return
            n = len(igrid.pending_entries())
            igrid.clear_pending()
            self._refresh_pending_label()
            self.query_one("#footer-pending", Static).update(
                f"reverted: {n} pending cleared"
            )
        else:
            try:
                agrid = self.query_one("#agent-grid", AgentGrid)
            except NoMatches:
                return
            n = len(agrid.pending_entries())
            agrid.clear_pending()
            self._refresh_pending_label()
            self.query_one("#footer-pending", Static).update(
                f"reverted: {n} pending cleared"
            )

    def action_diff(self) -> None:
        if self._active_kind == "skill":
            try:
                sgrid = self.query_one("#skill-grid", SkillGrid)
            except NoMatches:
                return
            all_ops: list[str] = list(sgrid.pending_entries().values())
        elif self._active_kind == "pi-extension":
            try:
                pgrid = self.query_one("#pi-grid", PiGrid)
            except NoMatches:
                return
            all_ops = list(pgrid.pending_entries().values())
        elif self._active_kind == "instruction":
            try:
                igrid = self.query_one("#instruction-grid", InstructionGrid)
            except NoMatches:
                return
            all_ops = list(igrid.pending_entries().values())
        else:
            try:
                agrid = self.query_one("#agent-grid", AgentGrid)
            except NoMatches:
                return
            all_ops = list(agrid.pending_entries().values())
        n_link = sum(1 for op in all_ops if op == "link")
        n_unlink = sum(1 for op in all_ops if op == "unlink")
        self.query_one("#footer-pending", Static).update(
            f"diff: {n_link} would-link, {n_unlink} would-unlink"
        )

    def action_apply(self) -> None:
        if self._active_kind == "skill":
            self._apply_skill_pending()
        elif self._active_kind == "pi-extension":
            self._apply_pi_pending()
        elif self._active_kind == "instruction":
            self._apply_instruction_pending()
        else:
            self._apply_agent_pending()

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
        errors: list[str] = []
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
                    continue
            p = InstallPlan(
                slug=slug, scope=scope, source=None, ref=None,
                add_agents=tuple(sorted(adds)),
                remove_agents=tuple(sorted(removes)),
            )
            try:
                result = engine_apply(p, home=home, project=project, env=None)
                ok += len(result.created) + len(result.removed)
            except InstallError as exc:
                errors.append(f"{slug}: {exc}")
                failed += n_writes
        saved = grid.pending_entries() if failed else {}
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
                f"[red]apply failed[/] — {first}{extra}"
            )
            self.notify(
                "\n\n".join(errors),
                title=f"Apply: {ok} ok, {failed} failed",
                severity="error",
                timeout=12,
            )
        else:
            self.query_one("#footer-pending", Static).update(
                f"applied: {ok} ok, {failed} failed"
            )

    def _apply_pi_pending(self) -> None:
        from agent_toolkit_cli import _pi_settings, pi_extension_install
        from agent_toolkit_cli.pi_extension_lock import (
            LockEntry, add_entry, read_lock, remove_entry, write_lock,
        )
        from agent_toolkit_cli.pi_extension_paths import (
            library_lock_path, lock_file_path,
        )

        try:
            grid = self.query_one("#pi-grid", PiGrid)
        except NoMatches:
            return
        pending = grid.pending_entries()
        if not pending:
            return

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
            entry = glob_lock.skills.get(slug)
            if entry is None:
                # Untracked slug — no lock entry, skip (guard: should not
                # reach here because untracked rows are non-interactive).
                continue

            try:
                if entry.source_type == "npm":
                    # npm: add or remove from packages[] in settings.json.
                    if op == "link":
                        _pi_settings.add_package(
                            entry.source,
                            scope=scope,
                            home=home,
                            project=project,
                        )
                    else:
                        _pi_settings.remove_package(
                            entry.source,
                            scope=scope,
                            home=home,
                            project=project,
                        )
                    ok += 1
                else:
                    # store-owned: project the symlink, then update project lock.
                    action: pi_extension_install.Action = (
                        "install" if op == "link" else "uninstall"
                    )
                    p = pi_extension_install.plan(
                        slug=slug,
                        scope=scope,
                        action=action,
                        home=home,
                        project=project,
                    )
                    pi_extension_install.apply(p, home=home, project=project)
                    ok += 1

                    # Update project lock after a successful projection.
                    if scope == "project" and project is not None:
                        proj_lock_path = lock_file_path(
                            scope="project", project=project
                        )
                        proj_lock = read_lock(proj_lock_path)
                        if op == "link" and slug not in proj_lock.skills:
                            write_lock(
                                proj_lock_path,
                                add_entry(
                                    proj_lock,
                                    slug,
                                    LockEntry(
                                        source=entry.source,
                                        source_type=entry.source_type,
                                        ref=entry.ref,
                                        pi_extension_path=entry.pi_extension_path,
                                    ),
                                ),
                            )
                        elif op == "unlink" and slug in proj_lock.skills:
                            write_lock(
                                proj_lock_path,
                                remove_entry(proj_lock, slug),
                            )

            except (pi_extension_install.InstallError, _pi_settings.PiSettingsError) as exc:
                errors.append(f"{slug}: {exc}")
                failed += 1

        if failed == 0:
            grid.clear_pending()
        self._refresh_pi_view()
        self._refresh_pending_label()
        self._refresh_status_bar()

        if errors:
            first = " ".join(errors[0].split())
            extra = f" (+{len(errors) - 1} more)" if len(errors) > 1 else ""
            self.query_one("#footer-pending", Static).update(
                f"[red]apply failed[/] — {first}{extra}"
            )
            self.notify(
                "\n\n".join(errors),
                title=f"Apply: {ok} ok, {failed} failed",
                severity="error",
                timeout=12,
            )
        else:
            self.query_one("#footer-pending", Static).update(
                f"applied: {ok} ok, {failed} failed"
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
                except (InstallError, ValueError) as exc:
                    errors.append(f"{slug}: {exc}")
                    failed += len(adds)

            # Removes → agent_install.uninstall() DIRECTLY.
            # Do NOT use apply().removed — it is ALWAYS EMPTY (the #268-class gap).
            # Calling uninstall() directly avoids orphaning projected files.
            if removes:
                try:
                    agent_install.uninstall(
                        slug=slug,
                        scope=scope,  # type: ignore[arg-type]
                        home=effective_home,
                        project=project,
                        harnesses=tuple(sorted(removes)),
                    )
                    ok += len(removes)
                except (InstallError, ValueError) as exc:
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
        if errors:
            first = " ".join(errors[0].split())
            extra = f" (+{len(errors) - 1} more)" if len(errors) > 1 else ""
            self.query_one("#footer-pending", Static).update(
                f"[red]apply failed[/] — {first}{extra}"
            )
            self.notify(
                "\n\n".join(errors),
                title=f"Apply: {ok} ok, {failed} failed",
                severity="error",
                timeout=12,
            )
        else:
            self.query_one("#footer-pending", Static).update(
                f"applied: {ok} ok, {failed} failed"
            )

    def _apply_instruction_pending(self) -> None:
        from agent_toolkit_cli import instructions_install
        from agent_toolkit_cli.instructions_adapters.symlink import PointerConflictError

        try:
            grid = self.query_one("#instruction-grid", InstructionGrid)
        except NoMatches:
            return
        pending = grid.pending_entries()
        if not pending:
            return

        ok = failed = 0
        errors: list[str] = []

        # Collapse per-harness entries to distinct (scope, op) reconcile operations.
        # apply(scope=...) and uninstall(scope=...) reconcile the ENTIRE scope at
        # once, so calling them once per harness entry would double-count ok/failed
        # and issue redundant filesystem operations.
        reconcile_ops: set[tuple[str, str]] = {
            (scope, op) for (scope, _harness, _slug), op in pending.items()
        }

        for scope, op in sorted(reconcile_ops):
            effective_home = Path.home() if scope == "global" else None
            project = None if scope == "global" else Path.cwd()

            try:
                if op == "link":
                    instructions_install.apply(
                        scope=scope,  # type: ignore[arg-type]
                        project_root=project,
                        home=effective_home,
                    )
                    ok += 1
                else:  # "unlink"
                    instructions_install.uninstall(
                        scope=scope,  # type: ignore[arg-type]
                        project_root=project,
                        home=effective_home,
                    )
                    ok += 1
            except (PointerConflictError, instructions_install.CanonicalMissingError, ValueError) as exc:
                errors.append(f"{op} @ {scope}: {exc}")
                failed += 1

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
                f"[red]apply failed[/] — {first}{extra}"
            )
            self.notify(
                "\n\n".join(errors),
                title=f"Apply: {ok} ok, {failed} failed",
                severity="error",
                timeout=12,
            )
        else:
            self.query_one("#footer-pending", Static).update(
                f"applied: {ok} ok, {failed} failed"
            )

    # ----- header + status ---------------------------------------------------

    def _build_content_header(self) -> str:
        kind_label = _KIND_LABELS.get(self._active_kind, self._active_kind)
        if self._active_kind == "skill":
            try:
                n = self.query_one("#skill-grid", SkillGrid).row_count
            except (NoMatches, Exception):
                n = 0
        elif self._active_kind == "pi-extension":
            try:
                n = self.query_one("#pi-grid", PiGrid).row_count
            except (NoMatches, Exception):
                n = 0
        elif self._active_kind == "instruction":
            try:
                n = self.query_one("#instruction-grid", InstructionGrid).row_count
            except (NoMatches, Exception):
                n = 0
        else:
            try:
                n = self.query_one("#agent-grid", AgentGrid).row_count
            except (NoMatches, Exception):
                n = 0
        return f"  [b]{kind_label}[/]   [dim]·[/]   {n} items"

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
            n += len(self.query_one("#instruction-grid", InstructionGrid).pending_entries())
        except Exception:
            pass
        try:
            n += len(self.query_one("#skill-grid", SkillGrid).pending_entries())
        except Exception:
            pass
        try:
            n += len(self.query_one("#pi-grid", PiGrid).pending_entries())
        except Exception:
            pass
        try:
            n += len(self.query_one("#agent-grid", AgentGrid).pending_entries())
        except Exception:
            pass
        try:
            self.query_one("#footer-pending", Static).update(f"Pending: {n}")
        except Exception:
            pass

    def _refresh_status_bar(self) -> None:
        """Roll up active grid rows into status counts."""
        active = getattr(self, "_active_kind", "skill")
        if active == "skill":
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
            loaded_global = loaded_project = 0
            try:
                grid_pi = self.query_one("#pi-grid", PiGrid)
            except (NoMatches, Exception):
                grid_pi = None
            if grid_pi is not None:
                for pi_row in grid_pi._rows:
                    if pi_row.global_cell.global_loaded:
                        loaded_global += 1
                    if pi_row.project_cell.project_loaded:
                        loaded_project += 1
                pending = len(grid_pi.pending_entries())
            else:
                pending = 0
            text = (
                f"  [b green]{loaded_global}[/] global   "
                f"[b cyan]{loaded_project}[/] project   "
                f"[b yellow]{pending}[/] pending"
            )
        elif active == "instruction":
            linked_global = linked_project = 0
            try:
                grid_instr = self.query_one("#instruction-grid", InstructionGrid)
            except (NoMatches, Exception):
                grid_instr = None
            if grid_instr is not None:
                for instr_row in grid_instr._rows:
                    if instr_row.general_linked:
                        if instr_row.scope == "global":
                            linked_global += 1
                        else:
                            linked_project += 1
                pending = len(grid_instr.pending_entries())
            else:
                pending = 0
            text = (
                f"  [b green]{linked_global}[/] global   "
                f"[b cyan]{linked_project}[/] project   "
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
