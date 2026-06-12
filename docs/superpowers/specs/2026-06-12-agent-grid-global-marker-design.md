# Agent grid 🌐 global marker at project scope — design

**Issue:** #374
**Date:** 2026-06-12
**Tier:** standard

## Problem

On the TUI agents tab at project scope, an agent that is also installed at
global scope shows a plain cell with no 🌐 marker. The skills tab (#188) and
pi-extensions tab (#349) render the marker in exactly this situation so the
user knows a project install may be redundant; the agents tab silently omits
it. Both halves are missing:

1. **State layer** — `agent_state.build_agent_rows` only probes cells for the
   active scope (`agent_state.py:122-125`). Contrast
   `skill_state.py:227-234`, which at project scope additionally probes
   global cells precisely so the grid can render the indicator.
2. **Grid layer** — `agent_grid._cell_glyph` (`agent_grid.py:382-393`) has no
   🌐 branch. Contrast `skill_grid._cell_glyph` (`skill_grid.py:623-632`) and
   `pi_grid._cell_glyph` (`pi_grid.py:350-351`).

## Decisions (brainstorm, 2026-06-12)

1. **Semantics: parity with skills/pi.** The marker means "also installed
   globally (linked)" — pure presence, no redundancy/shadowing claim. No
   per-harness provenance audit; the harness-matrix doc already records
   per-harness paths. Project-only harnesses (e.g. devin) self-suppress: they
   never produce a global cell, so no marker.
2. **Row universe: probe all rows**, including `unlisted`/`library` (#360
   badges). The probe is a lock-independent filesystem check
   (`adapter.destination(...)` + `exists()`); the skills tab already shows 🌐
   on unlisted rows with no state-based guard.
3. **Instructions: out of scope, by design.** Each scope has its own
   canonical AGENTS.md (no library union, no cross-scope concept), so the
   marker does not apply. The stale "skills-only — instructions has no
   global-marker concept" comment in `column_info.py:45-47` is rewritten to
   state the real rule.
4. **Info panel: extend to agents.** The 🌐 explainer block currently gated
   `asset_type == "skills"` widens to skills + agents, and
   `agent_grid._context_for` passes `global_linked` for the focused row.

## Design

Approach: extend the existing flat `cells` dict pattern from `skill_state`
(AgentRow.cells is already keyed `(harness, scope)`). The pi-style
restructure (precombined `global_cell`/`project_cell` attributes) was
rejected as needless churn.

### 1. State layer — `src/agent_toolkit_tui/agent_state.py`

In `build_agent_rows`, after the active-scope probe loop: when
`scope == "project"` and `home is not None`, additionally probe
`cells[(harness, "global")] = _cell_for(slug, harness, scope="global",
home=home, project=None)` for every harness in `INTERACTIVE_HARNESSES`, for
every row in the universe (installed, unlisted, library). Mirrors
`skill_state.py:227-234` including the "skipped when home is None" escape for
callers that don't care. `AgentCell` only carries `linked` (no
drift/stray/skipped), so no model change.

### 2. Grid layer — `src/agent_toolkit_tui/widgets/agent_grid.py`

- Add `_GLOBAL_GLYPH = "🌐"` (same constant as `skill_grid.py:55`,
  `pi_grid.py:45`).
- Restructure `_cell_glyph` to compute `base` first — including the
  not-applicable `[dim]—[/]` case — then, at project scope only, append
  ` 🌐` when `row.cells.get((harness, "global"))` exists and is `linked`.
  The gate is simpler than skill_grid's because `AgentCell` has no
  drift/stray/skipped states. A globally-linked harness whose project slot
  is not applicable renders `— 🌐`, matching skills-tab semantics (marker
  appends to whatever the base is).

### 3. Info panel — `src/agent_toolkit_tui/column_info.py` + agent_grid

- Widen the `show_marker` gate (`column_info.py:48`) from
  `asset_type == "skills"` to `asset_type in ("skills", "agents")`.
- Rewrite the stale comment: the marker applies to skills and agents;
  instructions is excluded by design (per-scope canonical AGENTS.md, no
  cross-scope concept).
- `agent_grid._context_for` gains row-awareness (currently takes only `key`;
  skill_grid's takes `row_index` — `skill_grid.py:484-498`) and adds
  `global_linked` from the focused row's `("standard", "global")` cell to
  the standard-key context it already builds.

### Error handling

`home is None` → global probe skipped, no global cells, no marker, no crash
(explicit test). No new failure modes: `_cell_for` already handles
`UnsupportedMechanismError`/missing-slot cases by returning `None`.

## Test surface

New `tests/test_tui/test_agent_grid_global_indicator.py` mirroring
`test_skill_grid_global_indicator.py`:

- project scope + globally-linked cell → marker shown
- global scope → never shown
- global cell absent or unlinked → not shown
- per-harness independence (marker on one column, not another)
- `home=None` / no global cells in row → no crash, no marker
- unlisted row with global install → marker shown

Plus: `agent_state` test asserting the project-scope global probe populates
`(harness, "global")` cells (and does not at global scope / `home=None`);
`column_info` test asserting the agents panel renders the 🌐 explainer when
`global_linked` is true and omits it when false.

## Out of scope

- Instructions-tab marker (absence is by design; comment fix only).
- Per-harness provenance/shadowing audit or matrix assertions.
- Pi modal/column-info work (pi doesn't use the column-info framework).
- Redundancy-claiming copy ("you may not need this") — copy stays
  presence-neutral.
