# Spec: split column info (header click) from asset info (`i`)

Issue: #479

## Problem

The TUI puts an `ⓘ` glyph in most grid column headers, but the glyph is
decorative and the `i` key means two different things depending on where the
cursor happens to be:

- In the `Standard` and `State` columns, `i` opens a **column-level**
  explanation (`ColumnInfoModal`, content from `column_info.py`).
- In every other glyphed column, `i` falls through to a **row/cell-level**
  panel (`CellInfoScreen`).

So the user cannot predict what `i` will show before pressing it, and there is
no way at all to ask "what does the *Claude* column mean for this asset type?"

## Current facts

- `column_info.COLUMN_INFO` registers exactly two keys: `standard` and `state`.
  Every harness column resolves to `None` from `get_column_info()`.
- Each grid re-implements the same dispatch: `_column_key_for_index()` returns
  `"standard"` or `None` (`skill_grid.py`, `instruction_grid.py:417-421`,
  `agent_grid.py:353-357`, `mcp_grid.py:370-374`, `command_grid.py:357-361`).
- **No header is clickable.** There is no `DataTable.HeaderSelected` handler
  anywhere in `src/agent_toolkit_tui/widgets/`. The `ⓘ` in the header is a lie
  about affordance.
- `_standard_info()` (`column_info.py:29-95`) is already asset-type-aware
  through a `context` dict (`asset_type`, `names`, `extra_lines`,
  `global_linked`), but the per-asset wording lives in `if asset_type == ...`
  chains inside one function, and there is no per-harness equivalent.
- `app.action_info_pass()` (`app.py:584-613`) forwards `i` to the active grid's
  `action_info()` for five asset types but, for `command`, merely calls
  `cgrid.focus()` — the Commands grid's `i` is dead.
- Both modals already close on `escape` / `i` (`ColumnInfoModal`,
  `CellInfoScreen`; the latter also on `q`).

### The rendered column set is small and knowable

Computed live from the composition SSOT:

| Asset type | Rendered harness columns |
|---|---|
| Skills | `standard` (13), claude-code, pi, hermes-agent, paperclip |
| Instructions | `standard` (39), claude-code, gemini-cli |
| Agents | `standard` (5 global / 6 project), gemini-cli, opencode, pi |
| MCPs — project | `standard` (2), codex, opencode |
| MCPs — global | claude-code, codex, opencode, pi (no standard slot) |
| Commands | claude-code, pi, gemini-cli (no standard slot — #482) |
| Pi Extensions | pi |

That is **17 distinct (harness, asset type) pairs plus 4 Standard panels** —
a bounded authoring job, not the open-ended 6 × 8 matrix the issue first feared.

## Goal

Two affordances, two meanings, no overlap:

- **Click a column header** → what this *column* means for this asset type.
- **Press `i`** → what this *asset* (the row, e.g. `ceo-board`) is and where it
  stands.

Every rendered `ⓘ` must resolve to real content, so no header click is a dead
end.

## Requirements

### R1 — Header click opens column info

`DataTable.HeaderSelected` is handled in every grid. Clicking a header opens
`ColumnInfoModal` with that column's content:

- **Standard** — lists the harnesses the slot covers at the active scope, then
  **one sentence** on how the slot works for this asset type.
- **A harness column** — **one sentence** on how that harness consumes this
  asset type (what file, where, by what mechanism).
- **State** — a badge legend for **that asset type's** state vocabulary.
- **Origin** (Pi Extensions) — a legend for `library` / `npm` / `untracked`.
- **Source** — passive. It carries no `ⓘ` and its header does not open a
  modal. (Chosen over a "no info here" modal: a glyph-free header is already
  the honest signal, and a modal that says nothing is worse than none.)

The keyboard is **not** a route to column info (see R3 and § Accessibility).

### R2 — Every rendered `ⓘ` resolves, and every explainable column has one

For every asset type and both scopes, each column whose header carries `ⓘ`
must return non-`None` content, **and** every column that has content must
carry `ⓘ`. The invariant runs both ways; it is what makes the affordance
trustworthy.

This fixes a live inconsistency: only `skill_grid.py:595` glyphs its `State`
header. `agent_grid.py:431`, `command_grid.py:407`, and `mcp_grid.py:437` all
add a bare `"State"`, so those three State columns are silently unexplained
today. Pi Extensions' `Origin` column (`pi_grid.py:420`) is likewise bare.

### R3 — `i` always means "explain this asset"

Pressing `i` anywhere in a grid opens the asset-scoped panel for the row under
the cursor, regardless of column. It no longer opens column info from the
Standard or State columns.

The panel shows the asset's slug, its description when the library has one, its
source and ref, and its per-scope state. When no description is available it
says so plainly (`no description in SKILL.md` and equivalents) rather than
rendering an empty section.

`i` on a grid with zero visible rows (an over-narrow filter) is a no-op, as it
is today.

The Commands grid honours `i` like every other grid —
`app.action_info_pass()`'s `cgrid.focus()` branch is a bug and is fixed.

### R4 — One registry, keyed by (column, asset type)

Column content resolves through one registry keyed by column identity **and**
asset type, replacing both `COLUMN_INFO`'s two-key dict and the per-grid
`if asset_type == ...` chains inside `_standard_info`.

Requirements on the registry:

- Harness lists and counts resolve from the SSOT **at call time** — no
  import-time snapshot. (This is why today's factories are callables; keep
  that.)
- Copy shape is uniform: Standard panels are `harness list → one sentence`;
  harness panels are `one sentence`, optionally plus a destination path line.
- The existing `🌐` marker block (skills / agents / instructions) and the
  agents `devin` project-scope-only note survive the move, with their current
  wording intact — the instructions wording in particular is a deliberate
  correction from #388 and must not be re-generalised.
- An unregistered `(column, asset_type)` pair raises rather than returning
  `None`, so R2's invariant test fails loudly on a new column.

### R5 — The content matrix

Grounded in the adapters, not invented. One sentence each.

**Standard panels** (harness list first, then the sentence):

| Asset type | Sentence |
|---|---|
| Skills | One skill directory at `.agents/skills/<slug>/` that every harness in this list reads natively, so a single install serves all of them. |
| Instructions | These harnesses read the repo's top-level `AGENTS.md` directly, so no per-harness pointer file is written for them. |
| Agents | One file at `.claude/agents/<slug>.md` — the de-facto convergence directory these harnesses read, so the slot is a single artifact, not a bundle. |
| MCPs | One `mcpServers` entry in the project's `.mcp.json`, which these harnesses read as a shared project-level server list. |

**Harness panels**, by asset type:

*Skills*
- Claude — Reads skills from `~/.claude/skills/`, its own directory rather than the shared `.agents/skills` slot, so it needs a separate install.
- Pi — Reads skills from `~/.pi/agent/skills/`, its own directory rather than the shared `.agents/skills` slot.
- Hermes — Reads skills from `~/.hermes/skills/`, its own directory outside the standard slot.
- Paperclip — Projects the skill into a Paperclip **company** library rather than a harness home, so its scope is the company, not the machine or the repo.

*Instructions*
- Claude — Reads `CLAUDE.md`, not `AGENTS.md`, so the toolkit writes a pointer file that references the canonical instructions.
- Gemini — Reads `GEMINI.md`, so the toolkit writes a pointer file; at project scope Gemini merges the global and project files rather than replacing one with the other.

*Agents*
- Gemini — Gets a translated agent file at `.gemini/agents/<slug>.md`; the toolkit rewrites the frontmatter into Gemini's shape rather than symlinking.
- OpenCode — Gets a translated agent file at `.opencode/agents/<slug>.md` (project) or the XDG config equivalent (global).
- Pi — Gets a symlinked agent file at `.pi/agents/<slug>.md`, so edits to the library copy are picked up immediately.

*MCPs*
- Claude — Reads `mcpServers` from a JSON config; at project scope it is covered by the shared `.mcp.json` slot instead of its own entry.
- Codex — Reads `[mcp_servers.<name>]` from a TOML config, so its entry is written and round-tripped separately from the JSON readers.
- OpenCode — Reads `mcpServers` from its own JSON config, which is not the shared project `.mcp.json`.
- Pi — Reads `mcpServers` from a JSON config; at project scope it is covered by the shared `.mcp.json` slot.

*Commands*
- Claude — Reads command markdown from `.claude/commands/`.
- Pi — Reads command markdown from `.pi/prompts/` (project) or `.pi/agent/prompts/` (global).
- Gemini — Needs a TOML command file at `.gemini/commands/<slug>.toml`, so the markdown is converted rather than copied.

*Pi Extensions*
- Pi — Extensions are Pi-only; there is no shared slot and no other harness consumes them, which is why this asset type has no Standard column.

**State panels.** The state vocabulary is **not** shared, so one legend cannot
serve all four grids:

| Asset type | Badges (source) | Panel content |
|---|---|---|
| Skills | `clean`, `dirty`, `missing`, `copy`, `library`, `unlisted` (`skill_grid._STATE_MARKUP`) | today's legend, kept verbatim |
| Agents | `installed`, `library`, `unlisted` (`agent_grid.py:54-58`) | new: three-badge legend |
| Commands | `installed`, `library`, `unlisted` (`command_grid.py:59-63`) | new: three-badge legend |
| MCPs | `installed`, `library`, `unlisted` (`mcp_grid.py:60-64`) | new: three-badge legend |

The three-badge legend reads: `installed` — tracked by the library and present
in this scope; `library` — in the library but not installed here; `unlisted` —
present in this scope but no longer tracked by the library lock (re-add via the
matching `doctor` command).

**Origin panel** (Pi Extensions), from `display_names._PI_EXTENSION_ORIGINS`:
`library` — owned by the toolkit store; `npm` — installed as an npm package;
`untracked` — present in Pi but not managed by the toolkit.

Codex's commands-global-only constraint (`markdown.py:29`) is noted here for the
author's benefit; Codex is not currently a rendered Commands column.

### R6 — Verified, not assumed

Every sentence in R5 must be checkable against a named source in the codebase.
The plan pins each one to its adapter/catalog line. If an adapter later moves a
path, the sentence is wrong — so destination paths shown in a panel are read
from the adapter where one is cheaply reachable, and hardcoded only where they
are genuinely static prose.

## Accessibility note

Header click is mouse-only, as briefed. This is a deliberate accessibility
regression risk and is accepted **only** because the information is
supplementary: no action, state, or asset data is reachable *exclusively*
through a column header. The per-asset `i` panel remains fully keyboard-driven.

Textual's `DataTable` with `cursor_type="cell"` cannot place the cursor on the
header row, so a keyboard route would need a new binding — which the brief
explicitly excludes, since `i` is being reclaimed for the asset panel. If a
keyboard route is later wanted, `shift+i` on a column is the natural spelling;
that is a follow-up, not this issue.

## Non-goals

- Adding a Standard column where none exists (#478 fixes the rule; #482 adds
  the Commands projection).
- Changing which harnesses render a column (#480).
- Changing column widths or truncation (#459).
- Hover-on-mouseover tooltips. "Hover-over" in the braindump means the popup
  panel; Textual has no hover-tooltip primitive here, and a click is the
  discoverable, testable gesture.
- Reworking `CellInfoScreen`'s per-cell state explanations into the asset panel
  wholesale — the asset panel is about the row; per-cell state stays reachable
  where it already is.
- Unifying the three asset types' state vocabularies with the skills one. They
  differ for real reasons (skills track working-tree drift; the others do not);
  four legends is the honest answer, not a defect to normalise.

## Open decisions

None. The three original `needs:` are resolved: the matrix is authored in R5,
the keyboard question in § Accessibility, and the missing-description fallback
in R3.
