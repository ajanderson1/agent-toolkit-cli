# TUI Label Consistency Design

## Issue

GitHub: https://github.com/ajanderson1/agent-toolkit-cli/issues/448

## Problem

The Textual TUI uses inconsistent visible labels across its asset panes. The sidebar uses lowercase singular asset names, Pi extension origin text still says `store`, headers mix all-caps, lowercase, and title case, and some harness columns expose internal catalog names (`Claude Code`, `Gemini CLI`) instead of the product-facing short names used elsewhere.

This makes the TUI feel internally inconsistent and forces users to translate between old implementation terms and the current application vocabulary.

## Goals

- Replace user-facing `store` terminology in the TUI with `library` where it means the agent-toolkit managed asset library.
- Capitalize and pluralize the left sidebar asset type tabs.
- Render asset-pane table headers in title case with consistent asset type names across panes.
- Use short harness display names for visible TUI labels: `Claude`, not `Claude Code`; `Gemini`, not `Gemini CLI`.
- Make every Standard column label include a covered-count suffix: `Standard (N)`.
- Cover visible labels with tests so future panes do not regress.

## Non-goals

- Rename CLI commands, lockfile keys, adapter keys, Python type names, or persisted harness identifiers.
- Change install/apply behavior, row state semantics, scope behavior, or pending-operation behavior.
- Redesign the TUI layout beyond copy normalization.
- Change documentation outside tests/spec/plan unless implementation discovers directly stale TUI copy docs.

## Terminology policy

Internal identifiers stay stable:

- Asset type keys remain `instruction`, `skill`, `pi-extension`, `agent`, `mcp`.
- Harness keys remain `claude-code`, `gemini-cli`, `codex`, `opencode`, `pi`, `cursor`, `standard`.
- Pi extension origins may keep internal enum values such as `store-owned`.

Visible TUI copy should use display helpers rather than raw keys:

| Internal value | Visible label |
|---|---|
| `instruction` | `Instructions` |
| `skill` | `Skills` |
| `pi-extension` | `Pi Extensions` |
| `agent` | `Agents` |
| `mcp` | `MCPs` |
| `claude-code` | `Claude` |
| `gemini-cli` | `Gemini` |
| `store-owned` | `library` / `library-owned` depending sentence shape |
| `standard` column | `Standard (N)` |

Existing product names that are already concise (`Codex`, `OpenCode`, `Pi`, `Cursor`) should remain as-is except for title case where a raw key currently leaks (`codex` → `Codex`, `opencode` → `OpenCode`).

## Acceptance criteria

1. Sidebar header reads `Asset Types` and entries read `Instructions`, `Skills`, `Pi Extensions`, `Agents`, `MCPs`.
2. Main content header uses plural asset labels, e.g. `Pi Extensions · 18 items`, `MCPs · 2 items`.
3. Asset slug columns are title case and plural-aware where appropriate:
   - `Instruction ⓘ` or `Instructions ⓘ` must be consistent with the chosen existing row-label convention.
   - `Skill ⓘ`, `Pi Extension ⓘ`, `Agent ⓘ`, `MCP ⓘ` are title case, not all-caps.
4. Harness headers and TUI prose use product-facing names: `Claude`, `Gemini`, `Codex`, `OpenCode`, `Pi`, `Cursor`; no visible display label says `Claude Code`, `Gemini CLI`, `claude-code`, `gemini-cli`, `codex`, or `opencode`. Exact CLI command snippets may still contain raw harness flags where needed for copy/paste correctness.
5. Every Standard column includes covered count as `Standard (N)`, including skills, instructions, agents, and MCPs where Standard appears.
6. Pi extension origin display uses `library`, not `store`; info text says library-owned/agent-toolkit library, shows `Library path:`, and does not show `Store path:` or `store-owned`.
7. Column info modal copy still explains what Standard covers and includes count; titles remain meaningful and do not reintroduce old harness or store wording.
8. Tests assert the exact visible labels for sidebar, content header, grid headers, Standard counts, harness display names, cell-info prose, and Pi extension origin/info copy.

## Implementation notes

- Prefer central helpers for visible names to avoid five grids reimplementing the mapping.
- Keep helper functions in TUI code, not CLI data model code, unless an existing CLI-facing display helper is already appropriate.
- Do not mutate `AGENTS["claude-code"].display_name` unless all CLI outputs should also change; this issue targets TUI copy only.
- Standard counts should come from existing standard coverage single sources of truth:
  - skills: `get_standard_agents()`
  - instructions: native rows from `instructions_matrix_rows()`
  - agents: `agents_standard_covered(scope)`
  - MCPs: `mcp_standard_covered("project")` when the Standard column is present
- Tests should prefer widget/app rendered labels over implementation internals where practical.

## Test surface

- `tests/test_tui/test_app_labels.py` or existing app/sidebar tests for sidebar/content header labels.
- Existing grid tests for header labels:
  - `tests/test_tui/test_skill_grid_new_columns.py`
  - `tests/test_tui/test_instruction_grid.py`
  - `tests/test_tui/test_agent_grid.py`
  - `tests/test_tui/test_mcp_grid.py`
  - `tests/test_tui/test_pi_grid.py`
- `tests/test_tui/test_column_info.py` for Standard info text/count and display-name mapping.

## Open questions resolved

- Scope is all user-facing TUI copy in the affected panes, not only screenshot-visible labels.
- Implementation should centralize label mapping enough to prevent drift, but should not rename persisted identifiers.
