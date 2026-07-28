# Spec: Standard column first, always labelled `Standard (N)`

Issue: #478

## Problem

The TUI renders, for each asset type, a `Standard` column — the
convention-driven slot that covers several harnesses with one installed
artifact — followed by the main harnesses that slot does *not* cover
(#351). Two properties are supposed to hold everywhere:

1. `Standard` is the **first** column after the slug column.
2. Its header carries the **live covered-harness count**, as `Standard (N)`.

They hold on four asset types and not on the other two, and the rule that makes
them hold is copy-pasted rather than shared, so the next asset type will drift
again.

## Current facts

| Asset type | Standard first? | `(N)` in header? | Evidence |
|---|---|---|---|
| Skills | yes | yes | `skill_state.py:48` — `INTERACTIVE_AGENTS = ("standard",) + skills_nonstandard_main()`; header via `standard_label(len(get_standard_agents()))` at `skill_grid.py:592` |
| Instructions | yes | yes | `instruction_grid.py:480-482` — `standard_label(_standard_count())` |
| Agents | yes | yes | `agent_state.py:37` — `("standard",) + agents_nonstandard_main("global")`; header via `standard_label(len(agents_standard_covered(scope)))` at `agent_grid.py:423-429` |
| MCPs | yes, project scope only | yes | `mcp_grid.py:432`; `mcp_standard_covered("global")` raises `KeyError` by design (`composition.py:58-71`) |
| **Commands** | **no** | **no** | `command_grid.py:404-405` iterates `INTERACTIVE_HARNESSES` (= `DEFAULT_HARNESSES` = `("claude-code", "pi", "gemini-cli")`) and uses the **raw catalog key** as the header |
| **Pi Extensions** | n/a | n/a | `pi_grid.py:415-421` — `<EXTENSION> \| Pi \| Origin \| Source`; single-harness asset type |

Four further facts matter:

- `standard_label(count)` (`display_names.py`) already produces `Standard (N)`;
  four grids each re-derive the count and call it behind their own
  `if harness == "standard":` special case.
- The Commands grid's headers bypass `harness_label()`, so they read
  `claude-code` / `gemini-cli` rather than `Claude` / `Gemini` — an escapee
  from the #448 terminology sweep.
- The Commands grid contains **dead code that assumes a standard slot exists**:
  `_column_key_for_index` tests for `"standard"` (`command_grid.py:357-361`) and
  `_context_for`'s docstring claims to enumerate `.claude/commands` readers,
  but `"standard"` never appears in its column list. The module docstring at
  `command_grid.py:3` advertises a layout the code does not implement.
- There is **no** `command_adapters/standard.py` and no
  `commands_standard_covered()`. `SUPPORTED_HARNESSES` /`DEFAULT_HARNESSES` in
  `command_adapters/__init__.py` contain no `standard` entry.

## Goal

Make "Standard is first and says how many it covers" a single shared rule that
every asset type either satisfies or documents an explicit exception to — and
stop the Commands grid lying about a slot it does not have.

## Scope decision (load-bearing)

**This issue is display consistency only.** Giving Commands a *real* Standard
column requires a new convergence projection — reader research, an adapter, a
per-scope SSOT, install/uninstall fan-out, and lockfile entries. That is the
same risk class as #361 (agents) and #399 (MCP), both of which were their own
issues. It is spun out as **#482** and is explicitly **not** delivered here.

Attempting both in one change would turn a contained TUI tidy-up into a
lockfile-schema change.

## Requirements

### R1 — One owner for the standard column header

A single shared helper produces the standard column's header text from the
asset type and scope, e.g.:

```python
def standard_column_header(asset_type: str, scope: str) -> str | None
```

It returns `Standard (N)` with the live covered count, or `None` when the asset
type has no standard slot at that scope. Every grid calls it; no grid keeps its
own `if harness == "standard": standard_label(...)` branch.

The count is resolved **at call time** from the existing SSOTs
(`get_standard_agents()`, `agents_standard_covered(scope)`,
`mcp_standard_covered(scope)`, the instructions canonical set) — never an
import-time snapshot, never a literal.

### R2 — Standard leads, on every asset type that has one

For Skills, Instructions, Agents, and MCPs the standard column is the first
column after the slug column, and its header matches `^Standard \(\d+\)$`.
This is asserted by test, not by convention.

### R2a — What `N` counts, and the fact that it differs

Measured today, the four live counts are **13 / 39 / 5–6 / 2**:

| Asset type | N | SSOT | What `N` actually counts |
|---|---|---|---|
| Skills | 13 | `get_standard_agents()` | harnesses in the standard skills bundle |
| Instructions | 39 | `instructions_matrix_rows()` where `verdict == "native"` | every catalogued harness that reads `AGENTS.md` natively |
| Agents | 5 global / 6 project | `agents_standard_covered(scope)` | harnesses reading `.claude/agents/` at that scope |
| MCPs | 2 (project) | `mcp_standard_covered("project")` | harnesses reading the project `.mcp.json` |

The **format** is uniform; the **denominator is not**. Instructions counts the
whole catalogue (39), skills counts a curated bundle (13). Both are correct for
their asset type, and neither should be normalised to the other — clamping
instructions to the main-harness set would understate reality, and expanding
skills to the catalogue would misdescribe the bundle.

This issue therefore fixes the *shape* (`Standard (N)`, first column) and
delegates the *meaning* to the per-asset-type info panel, which #479 is
rewriting: each Standard panel must state, in its one sentence, what "covered"
means for that asset type. Without that, `Standard (39)` next to `Standard (2)`
invites a false comparison.

### R3 — Scope changes update the count

Toggling scope re-derives the header. The Agents count already differs by scope
(`STANDARD_AGENT_READERS` has `devin` at project scope only), so a stale header
is a live defect, not a hypothetical.

### R4 — MCPs at global scope keep no Standard column

**Decision (agent, recorded for AJ):** at global scope the MCP grid renders no
Standard column, as today — not `Standard (0)`.

Rationale: the standard MCP projection *is* the project `.mcp.json` file. There
is no global equivalent, so a `Standard (0)` column would offer a header, an
info panel, and a toggle target for an artifact that cannot exist. The
`KeyError` from `mcp_standard_covered("global")` is deliberate fail-loud design
(`composition.py:58-71`) and stays. R1's helper returns `None` for this case,
which is why its return type is optional.

### R5 — Pi Extensions keeps its single `Pi` column

**Decision (agent, recorded for AJ):** Pi Extensions gets no Standard column.

Rationale: "Standard" names a *convergence slot* — one artifact read by several
harnesses. Pi extensions are consumed only by Pi, and there is no shared
directory. Rendering `Standard (1)` would assert a convention that does not
exist and would make the count meaningless (`(1)` reading as "one harness
converges here" when nothing converges).

The consistency the user asked for is delivered instead as a **rule with a
stated exception**: the first harness column is `Standard (N)` wherever a
standard slot exists; where none exists, the single harness column leads and
its header info (#479) says why there is no Standard slot for this asset type.

This decision is cheap to reverse — it is one branch in R1's helper.

### R6 — Commands headers stop lying

Within this issue's display-only scope:

- Commands harness headers render through `harness_label()`: `Claude`, `Pi`,
  `Gemini` — not `claude-code`, `pi`, `gemini-cli`.
- The module docstring (`command_grid.py:3`) and the inline comment
  (`command_grid.py:400-403`) are corrected to describe the layout that exists,
  with a pointer to #482 for the layout that is intended.
- The `_context_for` docstring stops claiming to enumerate `.claude/commands`
  readers.
- The unreachable `"standard"` branch in `_column_key_for_index` is **kept**,
  annotated as dormant-until-#482. Removing and re-adding it churns the file
  twice for no behavioural gain, and #479 rewrites this dispatch anyway.

### R7 — Regression protection

`tests/test_tui/test_composition.py` gains a rule-level test that, for every
asset type and both scopes, asserts either "column 1 header matches
`^Standard \(\d+\)$`" or "this asset type is on the documented exception list"
— so a new asset type cannot silently drift.

Per-grid tests assert the Commands headers are display labels, and that the
Agents standard count changes across the scope toggle.

## Non-goals

- Adding a real standard projection for Commands — that is **#482**.
- Changing which harnesses are "main" — that is **#480**.
- Changing the *content* of any info panel — that is **#479**.
- Changing column widths, truncation, or ellipsis behaviour (#459).
- Reintroducing the long-tail harness columns removed in #351.
- Changing `agent_state.INTERACTIVE_HARNESSES`'s import-time
  `agents_nonstandard_main("global")` snapshot. It is a latent per-scope
  inconsistency, but it governs *which* columns exist, not the standard
  header rule; note it and leave it.

## Open decisions

None. R4 and R5 are the two product choices; both are recorded above with
rationale and both are one-line reversible.
