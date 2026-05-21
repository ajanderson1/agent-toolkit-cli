# TUI column-header info affordance — design

Issue: [#167](https://github.com/ajanderson1/agent-toolkit-cli/issues/167) — *Add hover-over (i) info boxes to TUI column headers (start with Universal)*.

## Goal

Make the TUI's `SkillGrid` column headers self-documenting. A user landing on the **Universal** column should be able to discover, without leaving the TUI, exactly which agent harnesses are bundled under that column. The same pattern must extend to other columns later with minimal new code.

## Context

- `SkillGrid` (`src/agent_toolkit_tui/widgets/skill_grid.py`) is a Textual `DataTable`. It currently shows three interactive columns from `INTERACTIVE_AGENTS = ("universal", "claude-code", "pi")` plus `slug` and `state`.
- The "Universal" column is a **bundle**: toggling it queues link/unlink for every harness returned by `get_universal_agents()` in `src/agent_toolkit_cli/skill_agents.py` (currently Claude Code, Pi, Cursor, Windsurf, Aider, Codex, Continue, … — the catalog source of truth).
- The column label today is just `"universal"`. There is no in-TUI way to discover what that bundle expands to — users have to read source.
- Project memory: in Textual, methods named `_render_*` collide with internal flags; do not use that prefix for any helper added here.
- Project memory: the universal-vs-additional model treats universals as a **group toggle**, not locked-on. The TUI grid layout is `universal` + `claude-code` + `pi` + a collapsible long-tail. That model stays unchanged.

## Approach

**Discovery in two layers, keyboard-first:**

1. **Glyph in the column label.** Append a small marker (default `ⓘ`, fallback `(i)` on terminals without the glyph) to any column whose header has registered info content. Visible at-a-glance, zero interaction needed.
2. **Info panel on demand.** Bind a key (proposed: `i`) that, when the cursor is on a cell in a column with registered info, opens a small `ModalScreen` listing the column's info content. `esc` closes. The footer reflects the binding so it's discoverable.

**Why not pure hover.** Textual mouse-hover tooltips exist on widgets, but `DataTable` column headers are not first-class widgets — there is no public API to attach a tooltip to a single column header cell across the supported Textual versions (≥0.79). The keyboard-first path is portable, testable with `Pilot`, and aligns with how every other action in this TUI works.

**Reusable shape.** A small data structure — `ColumnInfo(title: str, lines: list[str])` — and a registry mapping `column_name -> ColumnInfo`. The first registration is `"universal"` and pulls its lines from `get_universal_agents()` at render time so the panel never goes stale.

## Out of scope

- Other column headers (`claude-code`, `pi`, `slug`, `state`). The plumbing must support them; populating them is a separate issue.
- Cell-level tooltips, row-level info affordances, or any redesign of the universal-vs-additional model itself.
- True mouse-hover behavior across all terminals. The keyboard binding is the canonical path; if Textual exposes header-tooltips later, we can layer them on without changing the data shape.

## User-facing behavior

```
slug                  ⓘ universal     claude-code   pi          state
─────────────────────────────────────────────────────────────────────
brainstorming         ✔               ✔             ☐           clean
…
```

- Cursor on any cell in the `universal` column → footer hints `i Info`.
- Press `i` → modal:
  ```
   Universal bundle
  ─────────────────
   Toggles link/unlink for every harness whose
   skillsDir is `.agents/skills`.

   Included harnesses:
     • claude-code
     • pi
     • cursor
     • windsurf
     • aider
     • codex
     • continue
     • …
  ```
- `esc` or `i` again closes.
- If the cursor is on a column without registered info, `i` is a no-op (or surfaces a one-line footer message — TBD in plan).

## Definition of done

- `ⓘ` glyph renders next to the `universal` column header in the TUI.
- Pressing `i` while focused on the `universal` column opens a modal listing every harness returned by `get_universal_agents()` in catalog order.
- The implementation introduces a `ColumnInfo` data shape + registry so a future PR can add `claude-code` info by adding one entry — no new widget code.
- Pilot test (`tests/test_tui/test_column_info.py`) asserts: glyph present in the universal column label; pressing `i` on the universal column opens the modal; modal text contains every harness from `get_universal_agents()`; pressing `esc` closes it.
- No regression in existing `tests/test_tui/test_skill_grid_apply.py` or other suites.

## Risks / open questions

- **Key collision.** `i` is currently unbound on `SkillGrid` / `SkillApp` — confirmed via grep. If a future binding takes it, the registry pattern makes rebinding trivial.
- **Glyph rendering on legacy terminals.** Fall back to `(i)` if `ⓘ` is not in the active font. Detection is unreliable; safer to make the glyph configurable via a module-level constant and default to `ⓘ`. Plan to lock in.
- **Modal vs inline panel.** Modal is the Textual default for this kind of disclosure. Inline panel inside `SkillGrid` would crowd the grid. The plan should pick modal unless there's a strong reason otherwise.

## References

- `src/agent_toolkit_tui/widgets/skill_grid.py` — column rendering site.
- `src/agent_toolkit_cli/skill_agents.py::get_universal_agents` — bundle source of truth.
- `src/agent_toolkit_tui/skill_state.py::INTERACTIVE_AGENTS` — interactive column order.
- `tests/test_tui/test_skill_grid_apply.py` — Pilot test patterns to follow.
