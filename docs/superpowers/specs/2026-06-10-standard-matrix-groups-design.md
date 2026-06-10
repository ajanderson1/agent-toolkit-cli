# TUI matrix Standard / Non-standard column groups — design

**Issue:** #351 · **Tier:** standard · **Date:** 2026-06-10 · **Depends on:** #350 (standard rename)

## Problem

The TUI grids give every rendered harness an undifferentiated column: there is no
visual grouping of convention-compliant ("standard") vs special-cased harnesses,
the standard column's ⓘ panel does not say which harnesses it covers, and the
long tail of non-standard harnesses is simply absent (not even reachable).
Restructure the matrix presentation into **Standard / Non-standard column
groups** with an exhaustive standard-coverage info panel and an expandable
long-tail column set.

## Decisions (approved by AJ, 2026-06-10)

1. **Kinds in scope: skills + instructions grids only.** The agents kind has no
   standard projection today (`standard-agent` is synthetic,
   `subagent_mechanism="none"`, never rendered) — it gets **no Standard column**
   until a real standard agents projection exists. Pi-extensions is pi-only;
   "standard" has no meaning there. Both grids are untouched.
2. **Collapse state is session-only**, in-memory per kind, collapsed on every
   launch — matching every existing TUI state (scope, filter, scroll). No new
   state file (keeps the issue at standard tier).
3. **TUI-only.** Plain-CLI `render_table()` output is row-oriented, not a column
   matrix; it is not restructured. The issue title's "CLI" is satisfied by the
   #350 token rename.
4. **Header approach: group-tagged two-line column labels** inside the native
   DataTable header — NOT a separate spanning widget (manual width-alignment and
   scroll-sync make that fragile). Each column label carries a dim group tag on
   line 1 and the column name on line 2.

## Design

### Column model (per grid)

```
[slug] | STANDARD group | NON-STANDARD group           | trailing columns
        standard ⓘ      big-five cols … [… +N ⓘ]       (State/Source — ungrouped)
```

- **Standard group**: exactly one column — the standard column (post-#350 name).
  Standard-compliant harnesses get NO individual columns; they are enumerated
  only in the standard column's ⓘ panel.
- **Non-standard group**: of the big five (claude-code, pi, codex, gemini-cli,
  opencode), those non-compliant *for that kind* get individual columns; all
  other non-compliant-but-installable harnesses fold into the collapsed set.
- **Trailing columns** (State, Source) belong to neither group and carry no
  group tag.

Composition is **derived from the catalog at rebuild time**, not hardcoded:

- **Skills**: standard set = `get_standard_agents()` (14 today). Non-standard
  big five = claude-code, pi (codex/gemini-cli/opencode ARE standard for
  skills). Long tail = the remaining non-compliant catalog harnesses (40 today).
- **Instructions**: standard column = the existing read-only canonical-status
  column (40 native AGENTS.md readers). Non-standard big five = claude-code,
  gemini-cli (symlink verdict). Long tail = the remaining symlink-verdict
  harnesses (augment, codebuddy, iflow-cli, replit, tabnine-cli today).
  Gap/unknown-verdict harnesses are excluded — there is nothing to toggle.

The current hardcoded `INTERACTIVE_AGENTS` / instruction harness tuples are
replaced by per-kind derivation helpers so composition tracks the catalog.

### Two-line header labels

Column labels become Rich `Text` with two lines: dim group tag + column name,
e.g. `STANDARD\nstandard ⓘ`, `NON-STD\nclaude-code ⓘ`, `NON-STD\n… +40 ⓘ`.
Trailing columns keep single-line labels (DataTable pads them). Alignment is
native; nothing to sync on scroll or resize.

### Collapsed long-tail column set

- Collapsed (default): one pseudo-column labeled `… +N ⓘ` after the big-five
  non-standard columns. N = long-tail count for that kind. Cells under it render
  a dim placeholder (`·`).
- Activating it (cursor on the pseudo-column + the existing info/activate
  action) expands in place: `_rebuild()` runs with the long-tail toggle columns
  included and the pseudo-column relabeled `… collapse`. Activating again
  collapses.
- Expanded long-tail columns behave exactly like the big-five columns (same
  toggle/apply semantics for skills; same install semantics for instructions).
- State: one boolean per grid instance (`_longtail_expanded`), session-only.
  Rebuild preserves scroll via the existing #321 save/restore idiom.
- The pseudo-column's ⓘ panel lists the collapsed harness names so they are
  discoverable without expanding.

### Standard-column ⓘ info panel

The standard column's `ColumnInfo` factory enumerates the compliant set
**exhaustively and dynamically**: name + count for the kind (skills: the 14 from
`get_standard_agents()`; instructions: the native list from the instructions
SSOT). Wording: "Covered by the standard convention for <kind> (N): …". Counts
and membership stay correct as the catalog grows.

### Interaction & accessibility

- Existing bindings unchanged (scope ctrl+g, filter, info). Expand/collapse is
  reachable via the cursor + activate on the pseudo-column; no new global
  keybinding unless the plan finds activation awkward in practice (then a
  per-grid `e` binding, documented in the footer).
- Headless tests must cover: default collapsed composition per kind, expand →
  columns appear in place + scroll preserved, collapse → restored, group tags
  present in header labels, standard ⓘ panel lists the full set with correct
  count, pseudo-column ⓘ lists collapsed names, pi/agents grids unchanged.

## Out of scope

- Agents-kind Standard column (no standard projection exists; revisit when one
  does).
- Pi-extensions grid changes.
- CLI table restructuring.
- Persisted TUI state file.
- Any token/terminology renames (#350 owns those).

## Acceptance criteria

1. Skills grid: header shows STANDARD group (1 col) + NON-STD group
   (claude-code, pi, `… +N ⓘ`); trailing State/Source untagged.
2. Instructions grid: same structure with its own composition (standard
   read-only col; claude-code, gemini-cli; `… +N ⓘ` for the remaining symlink
   harnesses).
3. Standard ⓘ panel enumerates the compliant set exhaustively with count,
   derived from the catalog/SSOT at open time.
4. Long-tail set expands/collapses in place; per-kind session-only state;
   scroll preserved; expanded columns fully functional (toggle + apply round-trip
   on at least one long-tail harness in tests).
5. Agents + pi-extensions grids byte-identical in behavior (regression-guarded).
6. Composition derived from the catalog — adding a compliant harness upstream
   changes the ⓘ panel and counts without touching grid code.
7. Full suite green; headless TUI tests per the interaction list above.
