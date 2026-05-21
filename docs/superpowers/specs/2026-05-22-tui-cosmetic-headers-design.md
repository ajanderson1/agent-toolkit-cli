# TUI SkillGrid header polish + State info popup — design

**Status:** Spec — drafted for issue #179.
**Date:** 2026-05-22.
**Scope:** Cosmetic-only. No behaviour change to skill state detection, badge semantics, link/unlink machinery, or the `INTERACTIVE_AGENTS` set.

## TL;DR

- Rename three column headers in `SkillGrid`: `slug → SKILL`, `(i) universal → Universal (i)` (info glyph moves to the right, base capitalised), `state → State (i)`.
- Register a `state` entry in `COLUMN_INFO` so pressing `i` while the cursor sits on a `State` cell opens `ColumnInfoModal` with a badge legend.
- Extend `_agent_for_column` (or the routing inside `action_open_column_info`) so the `state` column can resolve to a `COLUMN_INFO` key — today it returns `None` for col 0 and col N+1, which would silently swallow the `i` keypress.

## Why now

The grid lands in front of every new user the first time they open the TUI. Three small frictions:

1. `slug` and `state` use lowercase identifiers where every other column uses display case (`Claude Code`, `Pi`). Identifiers leak into user-facing chrome.
2. `(i) universal` places the affordance glyph on the wrong side — readers scan label-first, affordance-after. `Universal (i)` matches the future `State (i)` pattern.
3. Five state badges (`clean`/`dirty`/`missing`/`copy`/`library`) have meaning a new user must guess at. We already have a `ColumnInfoModal` and a registered `i` keystroke — adding a `state` entry is the cheapest possible discoverability win.

## Current state (code anchors)

- Column build: `src/agent_toolkit_tui/widgets/skill_grid.py::SkillGrid._rebuild` — lines ~237-247. Adds `"slug"` (col 0), one column per `INTERACTIVE_AGENTS` (cols 1..N), then `"state"` (col N+1).
- Info-glyph composition: same function, line ~245: `label = f"{_INFO_GLYPH} {base}" if agent in COLUMN_INFO else base`. The glyph is always prepended.
- Info registry: `src/agent_toolkit_tui/column_info.py::COLUMN_INFO` — currently `{"universal": _universal_info}`.
- `i` keystroke wiring: `action_open_column_info` (line 178). Resolves column → agent via `_agent_for_column`, which returns `None` for cols 0 and N+1. **This is the routing gap to close.**
- Badge source of truth: `_STATE_MARKUP` (lines 27-35) + inline comment above the `"library"` entry.

## Header rename mapping

| Old | New | Notes |
|---|---|---|
| `slug` | `SKILL` | Uppercased identifier-as-label. No info popup. |
| `(i) universal` | `Universal (i)` | Base capitalised; glyph suffixed not prefixed; only emitted when `"universal" in COLUMN_INFO` (matches current conditional). |
| `claude-code` display_name `Claude Code` | unchanged | Per-agent, comes from `AGENTS["claude-code"].display_name`. |
| `pi` display_name `Pi` | unchanged | Same. |
| `state` | `State (i)` | Capitalised; glyph suffixed; emitted iff `"state" in COLUMN_INFO`. |

The "(i) suffixed not prefixed" decision applies to **every** column that has a `COLUMN_INFO` entry — there is one composition rule, not per-column branches. Today only `universal` and (new) `state` qualify, but the rule is uniform so a future `slug` info entry would just work.

## State info-popup content

Register `"state"` in `COLUMN_INFO` with a factory that returns:

- **Title:** `State badges`
- **Lines:** one bullet per badge, in this order (matches `_STATE_MARKUP` declaration order plus `library` from its comment):
  - `• clean — installed and matches the library canonical`
  - `• dirty — installed but the on-disk copy diverges from the library`
  - `• missing — in the library, not installed in this scope`
  - `• copy — installed as a real copy (symlink fallback — e.g. Windows)`
  - `• library — in the library, not yet installed in this project (project scope only — normal pre-install state)`

Rationale: text duplicates the issue body verbatim so the spec, issue, and popup say the same thing. Source-of-truth note in `column_info.py` references `_STATE_MARKUP` so a future badge addition has one obvious home.

## Routing extension

`action_open_column_info` currently:

```python
col = table.cursor_coordinate.column
agent = self._agent_for_column(col)
if agent is None:
    return
info = get_column_info(agent)
```

The `state` column needs a path through. Two equally simple options:

1. **Extend `_agent_for_column`** to return `"state"` when `col == 1 + len(INTERACTIVE_AGENTS)`. Pro: one function knows all column→key mappings. Con: the name `_agent_for_column` becomes slightly misleading.
2. **Branch inside `action_open_column_info`**: if `col == 1 + len(INTERACTIVE_AGENTS)` and `"state" in COLUMN_INFO`, push the modal directly. Pro: keeps `_agent_for_column` strictly about agents. Con: routing logic is split.

**Decision: option 1.** Rename the helper to `_column_key_for_index` (or similar) and have it return one of `None | "state" | <agent_name>`. The companion `_column_index(agent_name)` is only called from the `a` keystroke (toggle column); `state` is not togglable, so that call site does not need to change.

This keeps a single column-resolution function, which is what the `_rebuild` layout comment already promises: `[0]=slug, [1..N]=INTERACTIVE_AGENTS, [N+1]=state`.

## Test surface

Existing tests to update (string assertions):

- `tests/test_tui/test_skill_grid_*.py` — any header-string assertions (`"slug"`, `"state"`, `"ⓘ universal"`).
- `tests/test_tui/test_column_info.py` — currently covers the universal entry; add a `state` entry test mirroring it.
- `tests/test_tui/test_skill_grid_column_info.py` — currently tests `i` on the universal column; add a sibling test for `i` on the state column opening `ColumnInfoModal`.

New behaviour to assert:

- `COLUMN_INFO["state"]()` returns a `ColumnInfo` with `title == "State badges"` and 5 lines beginning with the badges in the order above.
- `_column_key_for_index(0)` → `None`; for each agent index → that agent; for `len(INTERACTIVE_AGENTS) + 1` → `"state"`.
- Pressing `i` with the cursor in the State column pushes a `ColumnInfoModal` (test via direct call to `action_open_column_info` after setting `table.cursor_coordinate.column = len(INTERACTIVE_AGENTS) + 1`).

## Out of scope

- No changes to `_STATE_MARKUP` colours or badge semantics.
- No changes to which states render dim vs coloured.
- No new columns; no changes to `INTERACTIVE_AGENTS`.
- No accessibility/keybinding additions (e.g. a separate `?` key) — the `i` keystroke continues to be the single info affordance.
- No CLI changes — this is TUI chrome only.

## Definition of done

1. Headers render exactly: `SKILL`, `Universal (i)`, `Claude Code`, `Pi`, `State (i)`.
2. Pressing `i` with the cursor on any `State` column cell opens `ColumnInfoModal` with the five-badge legend.
3. Pressing `i` on the `Universal` column still works (regression).
4. `uv run pytest` passes.
5. No behaviour change to skill state detection, badge rendering, or link/unlink machinery.

## Risk

Negligible. All changes are display strings + one new dict entry + one helper rename. The single non-trivial decision (routing extension) has a one-line implementation in either of the two options. No persisted state touched; no on-disk format changes.
