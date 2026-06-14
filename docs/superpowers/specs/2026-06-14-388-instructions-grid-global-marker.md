# Spec — 🌐 global marker on the instructions grid (#388)

## Problem

In the TUI, the **instructions** asset-type grid is the only interactive grid
that does not render the 🌐 (globe) marker in project scope. The skills (#188),
agents (#374), and pi-extension (#349) grids all suffix a project-scope cell
with 🌐 when that harness's slot is *also* installed at global scope.
`instruction_grid` has neither the marker nor the shadow-cell data behind it.

## Decision: BUILD (parity) — reverses the #374 "excluded by design" note

The issue framed this as possibly-wontfix, hinging on one load-bearing question:
**do the instruction-grid harnesses load the global *and* project instruction
files cumulatively, or does the project file shadow (mask) the global one at
read-time?** If project shadows global, the marker would be misleading ("also
active globally" when it is actually masked) → wontfix. If both load, the marker
is a true signal → build.

The grid renders exactly two interactive harnesses
(`instructions_nonstandard_main()` → `claude-code`, `gemini-cli`). For **both**:

- **Claude Code** merges memory files from all scopes together — user
  (`~/.claude/CLAUDE.md`) + project (`./CLAUDE.md` or `./.claude/CLAUDE.md`) are
  concatenated, not shadowed. (code.claude.com/docs/en/configuration —
  "files from all scopes being merged together".)
- **Gemini CLI** concatenates the hierarchy of `GEMINI.md` files
  (`~/.gemini/GEMINI.md` global + project) and sends all found files with every
  prompt; more-specific files win *on conflict* but all load.
  (geminicli.com/docs/cli/gemini-md — "concatenates the contents of all found
  files".)

So when a project `CLAUDE.md → AGENTS.md` pointer **and** a global
`~/.claude/CLAUDE.md → ~/AGENTS.md` pointer both exist, the harness loads both
canonicals into context simultaneously — the same live-reader-in-both-scopes
situation skills and agents have. The 🌐 marker ("this harness slot is also
linked at global scope, so global instructions are also active") is therefore a
**true, useful signal**, consistent with the other three grids.

This reverses the comment #374 wrote into `column_info.py`:

> Instructions is excluded by design — each scope has its own canonical
> AGENTS.md, so there is no cross-scope install concept.

That note conflated two distinct facts: the *canonical file* is per-scope (true),
but the *harness reads both scopes* (also true). The cross-scope signal the 🌐
conveys — "both scopes' instructions are loaded at once" — holds for
instructions exactly as it does for skills/agents. The #374 note and its
`show_marker` gate are corrected as part of this work, not left to contradict
the new behaviour.

### Residual risk (premise is version-dependent)

The BUILD decision rests on the *current* documented behaviour of two external
products: Claude Code merges memory files across scopes, Gemini CLI concatenates
the `GEMINI.md` hierarchy. If either harness later switches to a
project-shadows-global model for its memory file, the marker would flip from
true-signal to misleading — the exact wontfix trigger the issue named. This is
true today and could expire; the toolkit does not control it. No in-repo
evidence anchor is added as part of this work (a follow-up could capture the two
precedence quotes into `docs/harnesses/claude-code.md` / `gemini-cli.md`).

## Scope

Display-only. **No** change to instruction install / uninstall behaviour, to
pointer precedence, or to what the harness actually loads — this surfaces an
existing truth that the grid currently hides.

## Design — parity-port of the agent-tab mechanism (#374)

Three mechanical edits mirroring the agents tab:

### 1. State layer — shadow cell (`instruction_state.py`)

`build_instruction_rows` currently populates only `(harness, scope)` cells. In
**project scope** (and only when `home is not None`), additionally probe the
`(harness, "global")` cell for every row, via the existing `_cell_for(...,
scope="global", home=home, project=None)`. This is a lock-independent filesystem
probe — it runs for every row in the universe, matching `agent_state.py:131-135`
and `skill_state.py:230-234`.

This applies to **both** row-construction branches: the empty-lock fresh-user
row (L152-166) and the locked-entry rows (L168-186). The global probe resolves
the global canonical (`global_canonical_agents_md()`), independent of the
project canonical already passed via `_canonical`, so the global `_cell_for`
call must **not** pass the project `_canonical` override (it computes the global
canonical itself when `scope="global"`).

### 2. Grid layer — globe branch + constant (`instruction_grid.py`)

Add `_GLOBAL_GLYPH = "🌐"` alongside the other glyph constants. In `_cell_glyph`,
after computing the base glyph, append ` 🌐` when `self._scope == "project"` and
the `(harness, "global")` cell is present and linked — mirroring
`agent_grid._cell_glyph:413-416`. `InstructionCell` has no drift/stray/skipped
states (it has `linked` + `conflict`), so `linked` is the whole gate, same as
`AgentCell`. The marker appends to any base, including the not-applicable
em-dash `—` (matching agent/skill semantics).

### 3. Info panel — extend the marker block to instructions (`column_info.py` + grid `_context_for`)

The `show_marker` gate in `column_info.py` (`asset_type in ("skills",
"agents")`) extends to include `"instructions"`, with instructions-appropriate
copy in the 🌐 explainer block. The "instructions excluded by design" comment is
rewritten to state the real rule (both scopes' instructions load; 🌐 = global
AGENTS.md also active).

`instruction_grid._context_for` already exists for the `standard` key only. It
gains the per-cell `global_linked` path so the CellInfoScreen / column-info
panel surfaces the global-linked state consistently with the other grids
(AC3). Follow the agent-grid shape (`agent_grid._context_for` + the
`global_linked` plumbing at `agent_grid.py:333-341`).

## Acceptance criteria

1. In project scope, an instruction cell whose `(harness, "global")` slot is
   linked renders a trailing 🌐, matching skills/agents/pi. (Global scope: no
   marker.)
2. `build_instruction_rows` populates the `(harness, "global")` shadow cell for
   project-scope rows — in **both** the empty-lock and locked-entry branches —
   gated on `home is not None`, mirroring `agent_state.py:131-135`.
3. The CellInfoScreen / column-info panel surfaces the global-linked state for
   instructions consistently with skills/agents (the `global_linked` 🌐 block).
4. The `column_info.py` `show_marker` gate includes `"instructions"`, and its
   stale "excluded by design" comment is corrected to the real precedence rule.
5. Global scope is unchanged (no shadow probe, no marker) and the existing
   instruction-grid tests stay green.

## Out of scope

- Any change to instruction install/uninstall, pointer precedence, or
  harness read order. Display-only.
- Pi-extension / skills / agents grids (already have the marker).
- The long-tail CLI-only harnesses (the grid renders only the two
  `instructions_nonstandard_main()` harnesses).
