# Spec: TUI settings screen — theme + main-harness selection

Issue: #480

## Problem

The TUI has no settings surface. Two things a user plausibly wants to change
are frozen in source:

- **Theme** — pinned to `gruvbox` in `TUIApp.on_mount` (`app.py:212-215`),
  inside a bare `try/except`. No override, no persistence.
- **Which harnesses get their own column** — `MAIN_HARNESSES`
  (`composition.py:22-28`) is a module constant. A user who never touches
  Cursor or Paperclip still pays for their columns in horizontal space.

Changing either requires editing Python.

## Current facts

- `MAIN_HARNESSES = ("claude-code", "gemini-cli", "codex", "opencode", "pi",
  "cursor", "hermes-agent", "paperclip")` feeds `skills_nonstandard_main()`,
  `instructions_nonstandard_main()`, and `agents_nonstandard_main(scope)`,
  which feed `skill_state.INTERACTIVE_AGENTS` (`skill_state.py:48`),
  `agent_state.INTERACTIVE_HARNESSES` (`agent_state.py:37`), and each grid's
  column list.
- **"Which harnesses get a column" has three sources**, not one:
  `MAIN_HARNESSES` (skills, instructions, agents); `_MCP_HARNESSES =
  ("claude-code", "codex", "opencode", "pi")` (`composition.py:53-56`); and
  `DEFAULT_HARNESSES = ("claude-code", "pi", "gemini-cli")` in
  `command_adapters/__init__.py` (a **CLI** constant the TUI borrows).
- `tests/test_tui/test_composition.py` guards a coverage invariant: every
  `MAIN_HARNESSES` member is either standard-covered or has its own column, for
  every asset type it supports.
- There is **no** palette command registration and **no** user-preferences file
  anywhere in `src/agent_toolkit_tui/`.
- The toolkit already owns a user-level home: `~/.agent-toolkit/`, holding
  `skills-lock.json`, `agents-lock.json`, `instructions-lock.json`,
  `mcps-lock.json`, `pi-extensions-lock.json`, plus the per-asset library dirs.
  Roots resolve through `_paths_core.library_root_for_asset_type()`, with the
  `AGENT_TOOLKIT_SKILLS_ROOT` env override as the established testability
  precedent.
- `display_names.py` opens with "This module is intentionally TUI-only:
  persisted lock keys, adapter names, CLI arguments, and catalog identifiers
  stay unchanged." That boundary is the existing precedent for where a
  presentation preference may live.

## Goal

A Settings screen, opened from the command palette, that persists a theme
choice and a main-harness selection to a versioned user-level file, and applies
both live.

## Requirements

### R1 — Storage

**Decision (agent, recorded for AJ):** `~/.agent-toolkit/tui-settings.json`,
JSON, sibling to the existing `*-lock.json` files.

Rationale: the toolkit already owns `~/.agent-toolkit/` and already keeps its
user-level state there as JSON. Introducing a second home
(`~/.config/agent-toolkit/`) or a second format (TOML) would fragment state for
no gain. `tomlkit` is a dependency, but only because Codex's MCP config is TOML
— that is a *foreign* format the toolkit round-trips, not the toolkit's own.

- Env override `AGENT_TOOLKIT_TUI_SETTINGS` (absolute path) for tests and for
  parity with `AGENT_TOOLKIT_SKILLS_ROOT`.
- The file carries an explicit schema marker:
  `{"schema": "agent-toolkit-tui-settings/v1", …}`.
- **This is a new persisted schema this repo owns and must version.** An
  unknown or future `schema` value is not silently coerced — see R6.

### R2 — Palette entry

A `Settings` command appears in Textual's command palette (`ctrl+p`) and opens
the settings screen. Per the brief, the palette is the **only** route in: no
new keybinding, so no new key is consumed and no conflict with the filter boxes
(see #320, where a binding had to move off a letter for exactly this reason).

### R3 — Theme

- A picker lists the themes Textual actually offers (`app.available_themes`) —
  not a hardcoded list.
- Selecting one applies immediately and persists.
- `gruvbox` remains the default when nothing is persisted, so a fresh install
  is unchanged.
- The current `try/except Exception` around the theme assignment
  (`app.py:213-215`) is narrowed: an invalid *persisted* theme is handled by R6,
  and a genuine Textual failure is not swallowed.

### R4 — Main-harness selection

- A tickbox list whose candidates are **`MAIN_HARNESSES`**, not the full
  catalog.

  **Decision (agent):** the full `AGENTS` catalog is ~40 harnesses and the long
  tail is deliberately CLI-only (#351, post-demo decision). Offering it in a
  tickbox would reverse that decision by the back door and produce a list no
  one can scan. `MAIN_HARNESSES` stays the curated candidate set; growing it
  remains a code change, as it was for Hermes (#469).

- Ticking/unticking changes which harnesses render their own column, across
  every asset type, and persists.
- The selection **filters**; it cannot **add**. A harness still only gets a
  column for an asset type it actually supports — the selection intersects the
  existing per-asset-type support rules rather than bypassing them.
- The selection does **not** change the Standard column or its count. What the
  standard slot covers is a fact about the filesystem, not a preference.
  A harness that is standard-covered has no own column to hide, so unticking it
  is a visible no-op — the settings screen must say so rather than offering a
  tickbox that appears to do nothing.

### R5 — The three sources are reconciled

The setting applies to all three column sources, each within its own supported
set:

| Source | Applies to | Effect of the selection |
|---|---|---|
| `MAIN_HARNESSES` | skills, instructions, agents | filters the non-standard set |
| `_MCP_HARNESSES` | mcps | filters, within the four real MCP harnesses |
| `DEFAULT_HARNESSES` | commands | filters, within the three command harnesses |

**Decision (agent):** MCP and Command columns are **not** exempt. A user who
unticks Codex expects Codex gone everywhere, not gone from four tabs and
present on two.

`DEFAULT_HARNESSES` lives in `src/agent_toolkit_cli/command_adapters/` and is a
**CLI** constant. The TUI must filter its own view of it and must not mutate
it — see R7.

### R6 — Failure is loud, and forward-compatible

- Missing file → defaults, silently (a fresh install is not an error).
- Unreadable, malformed, or wrong-schema file → **defaults plus a visible
  status-bar notice** naming the file and the reason. Never a silent fallback,
  never a crash on launch.
- A persisted harness key that is no longer in `MAIN_HARNESSES` is **retained
  in the file** and ignored for rendering, with a notice. Dropping it would
  silently lose the user's choice if a harness is temporarily renamed or
  removed; retaining it makes the round-trip lossless.
- A persisted theme Textual no longer offers → fall back to `gruvbox` with a
  notice.
- Unticking **every** harness is legal and leaves a usable grid (slug +
  Standard + State + Source). It is not an error state.

### R7 — Scope boundary: the CLI does not read this

**Decision (agent):** `tui-settings.json` is read by `agent_toolkit_tui` only.

Rationale: CLI behaviour must stay deterministic in scripts and CI. If
`skill install` fanned out differently because of a GUI preference, the same
command would do different things on two machines — a *fail-loudly* violation
by way of invisible state. This mirrors the boundary `display_names.py` already
documents.

The TUI therefore filters a **copy**; it never mutates `MAIN_HARNESSES`,
`_MCP_HARNESSES`, or `DEFAULT_HARNESSES` at runtime.

### R8 — The coverage invariant survives

`tests/test_tui/test_composition.py`'s guard — every main harness is either
standard-covered or has its own column — is re-expressed against the
**effective** (user-selected) set, and re-run against a non-default selection.
The invariant must hold for any selection, including the empty one.

## Non-goals

- Per-project settings. This is a user-level preference; a project-scoped
  override is a separate issue if ever wanted.
- Any CLI flag, command, or output change.
- Adding harnesses to `MAIN_HARNESSES` — still a code change.
- Changing what the Standard slot covers.
- Column widths, ordering, or which columns exist beyond harness inclusion.
- Persisting scope, filter text, cursor position, or pending queues.
- A keybinding for the settings screen.

## Open decisions

None. R1, R4, R5, and R7 are the four product choices; each is recorded with
rationale above. R1 is the one that sizes the issue, and it is settled by
following the existing `~/.agent-toolkit/` precedent rather than inventing a
second home.
