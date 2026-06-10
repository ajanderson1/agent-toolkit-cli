# TUI row-universe union — unlisted project installs visible across kinds (#360)

**Issue:** [#360](https://github.com/ajanderson1/agent-toolkit-cli/issues/360)
**Tier:** standard
**Status:** approved (brainstorm 2026-06-10; design D1–D7 approved by PM on AJ's behalf)

## Problem

A skill installed at project scope but no longer present in the global library
lock has no TUI representation at all: `build_skill_rows`
(`src/agent_toolkit_tui/skill_state.py`) uses the **library lock as the row
universe at both scopes**, consulting the project lock only for per-row state,
never inclusion. After `skill remove <slug>` at global scope, a project that
still has the slug installed keeps working on disk (project installs are
independent clones in `~/.agent-toolkit/projects/<id>/skills/` — by design) and
is still listed by `skill list -p`, but becomes dark matter in the TUI: no row,
no cells, not even uninstallable from the grid.

The kinds also disagree on what the row universe IS (2026-06-10 audit):

| Kind | Row universe today | Consequence |
|---|---|---|
| skill | library lock, both scopes | project orphans invisible (the bug); has dim `library` state for available-not-installed |
| agent | scope lock only | orphans would show, but library agents not installed in the project never render as available (mirror gap); pre-#362 the project tab is simply empty |
| pi-extension | union already (both scope locks + loose dir discovery + settings packages) | closest to target semantic |
| instruction | scope lock (+ fresh-user canonical fallback) | no library concept (single AGENTS.md slug, per-scope canonical) — alignment N/A |

## Decision summary

1. **Row universe = union(library lock, scope lock)** for the skill and agent
   tabs. Pi-extension already complies (precedent, no change); instruction is a
   documented by-design exception.
2. New row state **`unlisted`** (installed at this scope, missing from the
   library lock), rendered with a **warning tint** — visually distinct from dim
   `library` (available-not-installed) and from error styling.
3. Doctor gains an **`unlisted` warning finding** with one inline fix-action
   (y/N/q, #337 pattern): **re-add to library** from the project entry's
   recorded source+ref. Decline leaves the functional install untouched.
4. Implementation is **inline per-kind** (~10 lines at each of the two sites;
   the lock types differ) — no shared helper. The canonical semantic statement
   lives in `skill_state.py`'s module docstring; the other three state modules
   cross-reference it.

## Design

### D1 — Canonical row-universe semantic

Universe = sorted union of library-lock slugs and scope-lock slugs.

- **Global scope:** the library lock IS the scope lock → behaviour unchanged.
- **Project scope:** three states:
  - lib-only → `library` (dim, available; preserved exactly as today — AC5),
  - both locks → existing installed states (clean/dirty/missing/copy for skill),
  - scope-only → `unlisted` (warning tint).

Applies to the skill and agent tabs. Pi-extension's inventory already unions
(cited as precedent, untouched). Instruction has no library concept; its module
docstring documents the exception.

### D2 — skill_state

- `State` literal gains `"unlisted"`.
- `build_skill_rows` reads the project lock alongside the library lock at
  project scope and iterates the union.
- Orphan (`unlisted`) rows take `source`/`ref` from the project lock entry.
- `unlisted` supersedes the git working-tree badge, exactly as `library` does
  today (one `state` field; the distinct state wins).
- Cells are probed by the existing `_cell_for` unchanged — the project
  canonical exists for an unlisted row, so probing works.
- Description read from the project canonical (the library copy is gone).

### D3 — agent_state

- `AgentRow` gains a `state` field: `Literal["installed", "library",
  "unlisted"]` (it has no state concept today).
- `build_agent_rows` unions the library lock with the scope lock.
- **#362 dependency (explicit):** `agent install -p` currently writes NO
  project lock entry (#362, open). The spec does NOT assume project-lock rows
  appear. Behaviour is defined both ways:
  - **Pre-#362:** the project lock is absent/empty → the union degenerates to
    library-lock rows, all state `library` (dim available). Today that tab is
    empty, so this is strictly additive — no regression.
  - **Post-#362:** project lock entries appear → `installed` rows, and
    `unlisted` becomes reachable when a slug is dropped from the library.
  - The `unlisted` code path ships now regardless (also reachable via
    hand-written project locks; tested that way).
- #360 does NOT fix #362 — separate issue, separate PR.
- `library` agent rows are actionable via the existing install toggles
  (skill-tab parity). This is the pre-existing `_apply_agent_pending` path —
  it seeds the project canonical by copy from the global canonical, then
  writes projections; #360 adds no new agent install code. Pre-#362 such an
  install lands on disk but writes no project lock entry — that gap is
  #362's to close, not this issue's.

### D4 — TUI actionability (AC2)

Unlisted skill rows are fully actionable: cells toggle, Apply detaches
projections and drops the project lock entry on full uninstall, mirroring the
CLI's non-destructive project posture and honouring the #319 Apply rollback
contract (write lock → apply → roll back prior on conflict). The plan must
verify the Apply/uninstall path derives its targets from the **scope lock**,
not the library (an Apply that consults the library would no-op on exactly the
rows this issue makes visible).

### D5 — Doctor finding (AC4)

New warning-severity finding `unlisted`: a project lock entry whose slug is
absent from the library lock. One inline fix-action on the Finding/fix_action
y/N/q loop (#337 precedent): re-add the slug to the library from the entry's
recorded source+ref (the mechanical equivalent of `skill add`). Decline leaves
the functional install untouched.

**Two separate activations:**

- `skill doctor -p`: **live immediately** — skill project locks exist today,
  so the finding can fire as soon as this ships.
- `agent doctor -p`: same finding shape, but **inert until #362 lands**
  (no project lock is ever written today, so the finding cannot fire); it
  ships now for forward-compatibility and is tested via a hand-written
  project lock.

Exclusions: pi-extension project projections are symlinks INTO the library, so
a library removal there produces a dangling projection — existing-doctor
territory (#314 family), not a functional orphan; no new finding. Instruction:
N/A (no library).

## Acceptance criteria (firm)

1. At project scope, a slug present in the project lock but absent from the
   library lock renders as a row with state `unlisted` (warning tint), for the
   skill tab now and the agent tab once #362 provides project lock entries
   (code path ships now, exercised in tests via hand-written locks).
2. Unlisted rows are actionable: TUI-driven uninstall works (cells toggle,
   Apply detaches projections + drops the project lock entry, #319 rollback
   contract preserved).
3. Row-inclusion semantics are documented and identical across kinds: union
   for skill/agent, pi-extension already-union noted as precedent, instruction
   documented as the by-design exception.
4. `skill doctor -p` gains the `unlisted` warning finding with the
   re-add-to-library fix-action (y/N/q); `agent doctor -p` gains the same
   finding shape (inert until #362).
5. Existing `library`-state (available-not-installed) rendering is preserved
   on the skill tab, and the agent tab gains it (dim available rows at project
   scope).

## Non-goals

- Fixing #362 (agent project lock write) — separate issue, separate PR.
- Lock format changes (no new fields; the union is computed, not stored).
- CLI `list` changes (`skill list -p` already reads the scope lock correctly).
- Pi-extension or instruction row-builder changes.
- Doctor findings for pi-extension/instruction (see D5 exclusions).

## Testing

- **Unit (skill_state):** project scope with a slug only in the project lock →
  `unlisted` row, source/ref from project entry, cells probed; slug in both →
  existing states; lib-only → `library` (AC5 regression); global scope
  unchanged.
- **Unit (agent_state):** no project lock → degenerate union (all `library`,
  no crash — pre-#362 case); hand-written project lock with an orphan slug →
  `unlisted`; both-locks slug → `installed`.
- **Doctor:** finding fires on an orphaned project entry; fix-action re-adds
  to the library from recorded source+ref; decline leaves lock + install
  untouched; agent variant exercised via hand-written project lock.
- **TUI:** headless-Textual apply round-trip for an unlisted skill row
  (toggle off → Apply → projections detached, project lock entry dropped).

## Deferred / Open Questions

### From 2026-06-10 review

- Should the TUI footer show a distinct message (e.g. "removed from project:
  <slug>") when a fully-uninstalled `unlisted` row vanishes from the grid
  after Apply, instead of only the standard "applied: N ok" counts? The row
  disappearing without comment may read as a refresh failure. (design-lens,
  deferred — UX decision, not blocking)

## Precedents / links

- #337 — doctor Finding/fix_action y/N/q loop + adopt rollback pattern.
- #319 — TUI Apply rollback contract.
- #314 — pi-extension doctor symlink blind-spot family (dangling projections).
- #351 — composition-derived TUI columns (the grids this lands in).
- #361 — standard agents projection (parallel agents-tab work; coordinate at
  plan level if both run concurrently).
- #362 — agent project lock gap (explicit dependency, out of scope here).
