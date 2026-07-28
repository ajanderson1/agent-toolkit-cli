# Spec: full-catalog main-harness chooser in the command palette

Issue: #491

## Problem

`agent-toolkit-tui` puts two lightweight preferences behind a bespoke Settings
modal: its Textual colour theme and the harnesses that receive standalone grid
columns. The modal is a second interaction model inside a command-palette TUI,
and its harness checklist is limited to the eight names in
`MAIN_HARNESSES`. A user who treats a long-tail catalog harness as primary
cannot select it, even when the relevant asset grid can render it.

The toolkit already has a native command-palette theme flow: Textual's
`Theme` system command opens a nested searchable chooser. Main-harness choice
should use that same pattern. The result must remain a presentation preference:
it changes only TUI columns, never CLI installs or output.

## Goal

Replace the Settings modal with direct, persisted command-palette choices:

- selecting a theme in the native-style theme chooser persists it; and
- selecting a real catalog harness in a nested **Main harnesses** chooser
  immediately adds or removes it from the user's main set, then renders it on
  every asset type and scope where it is supported.

A fresh installation keeps today's eight selected harnesses, so opening the
TUI without a settings file does not suddenly make every grid wide.

## Current facts

- `TUIApp.get_system_commands()` inherits Textual's **Theme** entry.
  `App.action_change_theme()` calls the overridable `search_themes()`, whose
  stock `ThemeProvider` sets `app.theme` but does not persist it.
- #480 added `SettingsCommandProvider`, `SettingsScreen`, and the split
  commit behaviour: a theme writes immediately; checkbox changes wait for
  Save. `SettingsScreen` is the UI to remove, but `settings.py` remains the
  versioned, atomic persistence boundary.
- `AGENTS` is the catalog source. It contains real harnesses plus the three
  synthetic projection tokens `standard`, `standard-skill`, and
  `standard-agent`; those synthetic entries have `show_in_standard_list=False`.
  Every real catalog harness is a chooser candidate; no synthetic token is.
- `MAIN_HARNESSES` currently conflates two concepts: the eight-name fresh
  default and the complete candidate universe. `effective_main_harnesses()`
  therefore rejects every long-tail selection while the per-asset composition
  helpers iterate only that tuple.
- Skills can use the catalog directly; instructions, agents, MCPs, and
  commands each have narrower support sets. Commands currently use
  `DEFAULT_HARNESSES`, even though `SUPPORTED_HARNESSES` additionally includes
  Codex.
- All six grids can hold pending edits. A settings-driven rebuild calls
  `set_rows()` and clears queues. Existing aggregate paths are inconsistent:
  `action_quit()` omits MCP pending edits and `_refresh_pending_label()` omits
  Command pending edits. A main-harness change must not silently throw away
  any pending edit.
- `tui-settings.json` schema v1 already retains unknown names and unavailable
  themes across unrelated saves, reports bad input, and is deliberately unread
  by `agent_toolkit_cli`.

## Requirements

### R1 — no Settings modal

Delete `src/agent_toolkit_tui/screens/settings.py`, remove
`SettingsCommandProvider`, `action_settings`, and their screen-specific tests.
The main command palette has no **Settings** entry and there is no new
keybinding. The existing `Theme` system command remains available.

A confirmation prompt used only to protect queued edits is permitted; it is not
a settings surface.

### R2 — persist the native-style theme chooser

`TUIApp.search_themes()` uses a persistence-aware provider instead of Textual's
stock `ThemeProvider`. It lists exactly `app.available_themes`, as Textual does.
Choosing a theme calls the existing atomic `apply_theme_setting()` path, so the
visible theme and `tui-settings.json` change together only after a successful
write. Invalid or unwritable settings preserve the current theme and surface
the existing named error notification.

This retains #480's persistence guarantee while restoring the palette UX:
`ctrl+p` → **Theme** → searchable theme list → select one.

### R3 — full-catalog Main harnesses chooser

`TUIApp.get_system_commands()` adds **Main harnesses** beside inherited system
commands. Its action opens a nested Textual command palette, analogous to
`search_themes()`, backed by a dynamic provider.

The provider derives candidates at runtime from `AGENTS`, retaining each entry
whose `show_in_standard_list` is true. It must:

- list every real catalog harness and no synthetic Standard token;
- display the human-facing harness label and a selected/unselected marker;
- search by both the display label and canonical harness key; and
- execute one direct toggle per selected result — no intermediate draft,
  Save, or Cancel state.

A toggle changes `TuiSettings.harnesses`, preserves retained unknown values and
an unavailable retained theme, atomically saves, applies the selection, and
rebuilds every grid. Re-selecting the same command later toggles it back. The
stored known selection is canonical catalog order, not palette-search order.
An empty selection remains valid.

### R4 — defaults and backward-compatible settings semantics

Split the current overloaded constant into:

- `DEFAULT_MAIN_HARNESSES`: today's eight entries, in today's order; and
- `MAIN_HARNESS_CANDIDATES`: all real `AGENTS` catalog harnesses, in catalog
  order.

`TuiSettings` defaults to `DEFAULT_MAIN_HARNESSES`. Loading a pre-existing v1
file containing only the old eight names yields the same effective selection;
no schema-version bump or migration is needed. Loading filters known values
against `MAIN_HARNESS_CANDIDATES`, not the old eight-name tuple. Unknown names
stay retained, ignored, and diagnostic as before.

### R5 — support-aware columns everywhere

A selected harness is a request for a standalone column, not a promise that
every asset type supports it. Composition returns the selected catalog set in
canonical order, intersected independently with each asset type's real support
set:

| Surface | Column eligibility |
|---|---|
| Skills | selected, non-standard catalog harnesses; Standard coverage remains unchanged |
| Instructions | selected harnesses supported by the instructions matrix; native readers remain Standard-covered |
| Agents | selected harnesses with a real agent mechanism, excluding scope-specific Standard coverage |
| MCPs | selected harnesses in the existing four real MCP harnesses, preserving project/global Standard asymmetry |
| Commands | selected harnesses in command `SUPPORTED_HARNESSES`, not merely `DEFAULT_HARNESSES` |

Thus selecting Codex makes it eligible for its supported Command column;
selecting a harness unsupported by, for example, MCP simply produces no MCP
column. The preference never mutates CLI-owned constants or changes Standard
counts, lockfiles, projections, or CLI behavior.

### R6 — protect pending edits before live rebuild

Before applying a main-harness toggle, enumerate all six grids' pending entries
through one app-level helper. If the count is zero, apply immediately. If it is
nonzero, show a context-accurate confirmation explaining that the harness
change will discard that many queued edits:

- **Cancel/Escape**: no settings write, no grid refresh, and every pending
  entry remains unchanged.
- **Discard and change**: write settings first; only after a successful write,
  update selection and refresh all grids, clearing the queued entries by their
  established `set_rows()` contract.
- **Save failure**: retain every pending entry and the current grid selection;
  show the existing failure notification.

Use the same all-grid enumeration for existing pending summaries and quit
confirmation so Command and MCP edits are no longer invisible to those safety
paths. This narrow repair is in scope because the new confirmation must mean
**any pending edit**, not only a subset.

### R7 — TUI-only storage and failure behaviour stay intact

Keep `~/.agent-toolkit/tui-settings.json`, its v1 schema marker,
`AGENT_TOOLKIT_TUI_SETTINGS` override, atomic writes, diagnostics, and
forward-compatible retained fields. Update user documentation to say that the
harness list is a full real-catalog selection and that palette toggles apply
immediately (or ask before discarding pending work). The CLI must not import
TUI code or read this file; its output remains byte-identical with and without
a non-default setting.

### R8 — regression protection and visual proof

Tests must cover:

1. inherited **Theme** and added **Main harnesses** system commands, with no
   Settings provider/route;
2. direct palette theme selection persists and applies live;
3. catalog completeness, synthetic exclusion, checked-state display, and key
   plus display-name search for main-harness commands;
4. toggle-on/toggle-off persistence, restart, empty selection, and old-eight
   fresh default;
5. full support-aware composition across Skills, Instructions, Agents, MCPs,
   and Commands — including selected Codex on Commands;
6. the pending confirmation's cancel, discard, and save-failure paths across
   every grid type; and
7. `tui-settings.json` retention/diagnostic behaviour and the CLI boundary.

Manual QA captures `ctrl+p` → **Theme**, `ctrl+p` → **Main harnesses**, a
long-tail harness toggle, a supported and unsupported asset-type view, and the
pending-discard confirmation under `assets/verification/issue-491/`. The PR
records a one-line visual verdict.

## Non-goals

- Per-project preferences, new CLI flags, or CLI behavior changes.
- Adding a modal/bulk checklist for main harnesses.
- Changing Standard projection coverage, column widths, column ordering, or
  adapter support.
- Automatically applying or preserving queued edits during a column rebuild.
- Changing the underlying `tui-settings.json` format or adding a dependency.
- Repairing unrelated grid behavior beyond the shared all-grid pending
  enumeration required by R6.

## Open decisions

None. AJ approved: all real catalog harnesses as candidates; today's eight as
the fresh default; direct immediate toggles; and confirmation before queued
edits are discarded.
