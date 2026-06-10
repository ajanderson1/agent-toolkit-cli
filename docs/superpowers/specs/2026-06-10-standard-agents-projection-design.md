# Standard agents projection — `.claude/agents/` as the agents-kind convergence dir — design

**Issue:** #361 · **Tier:** deep (new installable harness-like cell) · **Date:** 2026-06-10 · **Depends on:** #351 (PR #359 — composition module, kind-agnostic info panels, pseudo-column machinery)

## Problem

The #351 matrix-groups work excluded the agents tab on the premise "no standard
agents projection exists". Fact-check during the demo showed the premise is
half-wrong: a de-facto shared folder exists — `~/.claude/agents/` /
`.claude/agents/` is read natively by multiple harnesses (Phase A matrix,
`harness-matrix.md` § Cross-harness convergence). What is missing is on our
side: the install machinery has no standard-agents projection (`standard-agent`
is synthetic, mechanism `none`), so the TUI has no cell state to show.

Make `standard` a real, installable projection for the agents kind and give the
agents tab its Standard column.

## Decisions (approved by AJ, 2026-06-10)

1. **`.claude/agents/` is the standard agents dir for now** — accepted over
   waiting for a neutral `.agents/agents/` convention. Revisit if/when a
   neutral convention emerges upstream.
2. **Coverage is per-scope.** A harness counts as covered at a scope iff it
   reads `.claude/agents/` at that scope. Evidence today (re-verified by the
   plan's research step before the table is written):
   - global: `claude-code` (recursive), `kode`, `neovate`, `cortex` (or-path
     with `~/.snowflake/cortex/agents/`).
   - project: those four **plus `devin`** (reads `.claude/agents/*.md` at
     project scope only; its global path is a profile-dir `AGENT.md`).
3. **CLI token: `standard`** at the agent-kind `--harnesses` boundary — same
   bundle-token UX as the skills kind. `standard-agent` stays an internal
   synthetic name (post-#350 semantics unchanged).
4. **The Standard column absorbs claude-code's column** on the agents tab —
   mirror of the skills tab, where covered harnesses get no individual column.
5. **Accommodate as many harnesses as possible**: the covered set is derived
   from a declarative evidence table, and the plan includes a research step
   re-verifying every catalog harness for `.claude/agents/` compatibility
   (compat layers ship frequently; Phase A data is 2026-05 vintage).
6. **Pi is untouched**: discovery is `{PI_AGENT_DIR}/agents/<slug>.md` global
   (`$PI_CODING_AGENT_DIR` override, else `~/.pi/agent`) and
   `<project>/.pi/agents/<slug>.md`; the matrix warns the dual user-scope alias
   must be verified against the installed `@tintinweb/pi-subagents`, and
   project `.agents/` survives only as a legacy non-discovery fallback. Pi
   keeps its first-class column and adapter.

## Design

### Ground truth (verified 2026-06-10)

- The agents lock records **no harness tokens** — projections are detected
  from disk (`status_cmd._projected_harnesses`, adapter-aware
  `_current_linked_agents` scan). **No lock schema change.**
- The claude-code adapter already writes `{HOME}/.claude/agents/<slug>.md` /
  `{PROJECT}/.claude/agents/<slug>.md` (`agent_adapters/symlink.py` CELLS).
  The standard slot is **the same file** — one artifact, one name.

### Coverage table (new, declarative)

`agent_adapters/standard.py` (or a table in `symlink.py` — plan decides):

```python
# Harnesses that natively read the standard agents dir, per scope.
# Evidence: docs/agent-toolkit/research/subagent-fragments/ + re-verification
# (#361). Derived consumers: composition.agents_standard_covered(scope).
STANDARD_AGENT_READERS: dict[str, frozenset[str]] = {
    "global":  frozenset({"claude-code", "kode", "neovate", "cortex"}),
    "project": frozenset({"claude-code", "kode", "neovate", "cortex", "devin"}),
}
```

The TUI/composition layer consumes this via a new per-scope helper —
`composition.agents_standard_covered(scope)` — never hardcodes names.

### Installer

- `standard` accepted at the agent-kind `--harnesses` boundary
  (`_resolve_harnesses` / `_resolve_harnesses_for_uninstall`), resolved through
  the existing #350 alias/validation path. It maps to **one slot**: the
  `.claude/agents/<slug>.md` projection at the chosen scope.
- **Adopt-if-identical:** if the slot file already exists (e.g. a prior
  `--harnesses claude-code` install) and is byte-identical to the canonical
  content, installing `standard` succeeds as a no-op adoption. Different
  content → fail loud (conflict), same as the foreign-file guard today.
- **`claude-code` stays a valid explicit token** and writes the same slot
  (idempotent with `standard` on disk). Reporting (status/TUI) names the slot
  `standard`; the per-scope covered set explains who reads it.
- **Uninstall:** `--harnesses standard` removes the slot file (the usual
  non-destructive detach; canonical + lock untouched). Because `standard` and
  `claude-code` are one slot, uninstalling either token removes the same file.
- **Default fan-out** (`agent install` with no `--harnesses`): `standard` +
  the enabled harnesses **not** covered at that scope. Covered harnesses no
  longer receive individual default installs (they read the standard slot).
- The synthetic-name guard keeps rejecting `standard-agent` as a user token.

### TUI agents tab

Columns become:

```
AGENT ⓘ | Standard ⓘ | Cursor ⓘ | Pi ⓘ | Gemini CLI ⓘ | … +N ⓘ | State | Source
```

- Single-line headers (post-#351 demo decision — no group-tag row).
- The Standard cell shows the `.claude/agents/<slug>.md` slot state at the
  current scope (linked / unlinked / drift), via the same adapter-aware check
  the claude-code cell used.
- Standard ⓘ panel: reuses the kind-agnostic `_standard_info` with
  `{"kind": "agents", "names": agents_standard_covered(scope)}` — exhaustive,
  counted, derived at open time. At global scope it appends a note that
  `devin` is covered at project scope only.
- The long-tail pseudo-column (`… +N ⓘ`) and expand/collapse machinery from
  #351 are reused as-is; covered harnesses are excluded from both the big-five
  and tail sets per scope.
- Composition: agents-kind helpers added to `composition.py`
  (`agents_nonstandard_big_five(scope)`, `agents_longtail(scope)`), built from
  the catalog + adapter support minus `agents_standard_covered(scope)`.

### Doctor

The standard slot joins agent doctor's scan: drift (file differs from
canonical) and orphan (slot file with no lock entry) findings, named
`standard` in output.

### Research step (mandated)

Before the coverage table is committed, re-verify per harness against current
upstream docs/source:

1. The five known readers (paths + scopes still accurate).
2. A sweep of the remaining supported set (cursor, droid, qoder, pochi,
   augment, codebuddy, command-code, forgecode, junie, rovodev, mux, …) for
   `.claude/agents/` compat layers added since Phase A.
3. Findings recorded as fragment updates + matrix rows, with citations, in the
   same commit as the coverage table.

## Out of scope

- A neutral `.agents/agents/` convention (revisit on upstream movement).
- Pi adapter changes (kept as-is per decision 6).
- Translating the standard slot's frontmatter per harness (covered harnesses
  read the Claude format by definition; harnesses needing reshaping stay on
  their translate adapters).
- Skills/instructions tabs (done in #351); pi-extensions grid.
- Removing the `claude-code` token (one-cycle UX continuity; revisit at v4).

## Acceptance criteria

1. `agent install <slug> --harnesses standard` projects exactly
   `~/.claude/agents/<slug>.md` (global) / `<project>/.claude/agents/<slug>.md`
   (project); round-trips with uninstall; adopt-if-identical on existing
   claude-code installs; conflict on foreign content.
2. Default fan-out installs `standard` + non-covered harnesses only.
3. Agents tab shows the Standard column (absorbing claude-code's column);
   cells reflect slot state; ⓘ panel enumerates the per-scope covered set
   with count and the devin caveat at global scope.
4. Coverage is derived from `STANDARD_AGENT_READERS` (single source) — no
   hardcoded harness names in TUI or CLI paths.
5. Research step completed: every supported harness re-verified for
   `.claude/agents/` reading, fragments + matrix updated with citations.
6. Doctor reports drift/orphan on the standard slot.
7. `standard-agent` still rejected as a user token; #350 alias behavior
   unchanged; full suite green.
