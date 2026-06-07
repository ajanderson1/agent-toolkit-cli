# Design — Add the `instruction` kind to the TUI (#319)

**Issue:** #319 · **Type:** feat · **Mode:** `--auto` · **Date:** 2026-06-07

## Problem

The `instruction` kind has a complete CLI surface (`instructions_lock.py`,
`instructions_adapters/symlink.py`, `instructions_install.py`,
`commands/instructions/*`) but the TUI (`src/agent_toolkit_tui/`) does not
render it. The TUI exposes only `skill`, `pi-extension`, and `agent`. A user
managing AGENTS.md pointer symlinks must drop to the CLI.

## Goal

Render `instruction` in the TUI as its own kind, **first** in the left-rail
kind picker, visually separated from the other three kinds. Selecting it swaps
in a new `InstructionGrid` (same switcher idiom as today — one grid visible at
a time). The grid lets the user toggle which harnesses get a pointer symlink to
the canonical `AGENTS.md`, and applies edits through the shipped
`instructions_install` facade.

## Layout decision (resolved with user)

The live TUI is a **kind switcher**: a left-rail `OptionList` (skill /
pi-extension / agent) swaps one grid into the content pane at a time. Kinds are
never stacked on-screen. The issue's "above the other kinds with a visual
separator" is honored *within the switcher idiom*:

- `instruction` is the **first** option in the `#kinds-list` OptionList.
- A visual **separator** (a non-selectable dim divider option) sits between
  `instruction` and `skill`.
- Selecting `instruction` shows `InstructionGrid` and hides the others.

(The rejected alternative — permanently stacking the instruction grid above the
active kind grid — was a much larger change to the switcher/status/scope wiring
for no extra user value. Recorded here so the decision is explicit.)

## Columns

The instruction kind has **7 symlink harnesses** (from
`instructions_adapters/symlink.py` `CELLS`): `augment`, `claude-code`,
`codebuddy`, `gemini-cli`, `iflow-cli`, `replit`, `tabnine-cli`. The 39 native
readers consume `AGENTS.md` directly and need no pointer.

Per the issue ("'general' first, followed by 2–3 of the most common harnesses
that require different symlinking"), the grid columns are:

| Column | Meaning | Interactive? |
|---|---|---|
| `INSTRUCTION ⓘ` | slug (always `AGENTS.md`) | no (info on `i`) |
| `general ⓘ` | the canonical `AGENTS.md` itself — native readers need no pointer | **no** (informational; always "present" when canonical exists) |
| `claude-code ⓘ` | `CLAUDE.md` pointer | yes |
| `gemini-cli ⓘ` | `GEMINI.md` pointer | yes |
| `Source` | the source filename (`AGENTS.md`) | no |

- `claude-code` (CLAUDE.md) and `gemini-cli` (GEMINI.md) are the two most
  common harnesses with **distinct** pointer filenames — the clearest examples
  of "require different symlinking." That is exactly 2 interactive harness
  columns + the non-interactive `general` column = the "general + 2–3" the issue
  asks for. The remaining 5 harnesses stay CLI-only (consistent with how the
  agent grid pins a 4-harness shortlist via `INTERACTIVE_HARNESSES`).
- `INTERACTIVE_HARNESSES` is the single knob in `instruction_state.py` to
  add/remove interactive columns later.

### The `general` column

`general` represents the canonical `AGENTS.md` (what every native reader and
every pointer ultimately resolves to). It is **informational, not toggleable**:
you cannot "turn off" the canonical from the grid. It shows ✔ when the canonical
`AGENTS.md` exists at the active scope, ☐ when it does not (in which case
pointer installs would be refused by `instructions_install.apply` —
`CanonicalMissingError`). This mirrors the agent grid's synthetic
`general-agent` being non-rendered, but here we *do* render it as a read-only
status column because it is the precondition for everything else.

## Cell state

```python
@dataclass(frozen=True)
class InstructionCell:
    linked: bool       # our pointer symlink exists and resolves to canonical ("ok")
    conflict: bool     # pointer slot occupied by a real file or foreign symlink
```

Mirrors `commands/instructions/status_cmd.py` verdicts: `ok` → `linked=True`;
`missing` → both False; `conflict` → `conflict=True`. Surfacing `conflict` in
the grid is what satisfies the DoD "symlink handling does not clobber
non-symlink files" — a conflicted cell is shown distinctly (e.g. `[red]![/]`)
and toggling it is a no-op queue that the adapter will refuse loudly, never a
silent overwrite.

`replit` is project-only; were it ever added to `INTERACTIVE_HARNESSES` its
cell would be `None` at global scope (handled exactly like the agent grid's
scope-mismatch `None` cells). For the pinned `general/claude-code/gemini-cli`
set this does not arise, but the code path is kept symmetric.

## Apply semantics (differs from skill/agent)

`instructions_install.apply(scope=...)` reconciles the **whole lock** to the
filesystem; it does not take per-harness add/remove like skill/agent apply. So
the instruction apply path is:

1. Group pending toggles by `(scope, slug)` → sets of harnesses to add / remove.
2. Read the scope's instructions lock. For the slug's entry, mutate its
   `harnesses` list: add the queued-on harnesses, remove the queued-off ones.
   (If no entry exists yet and the user is adding, create one with
   `source="AGENTS.md"`.)
3. `write_lock(...)`.
4. `instructions_install.apply(scope=scope, project_root=..., home=...)` to
   reconcile pointers (idempotent + pruning; the adapter guards conflicts).
5. On `CanonicalMissingError` → surface as an apply error (footer + notify),
   identical UX to the agent grid's error path.

The pending key shape stays the 3-tuple `(scope, harness, slug)` for
consistency with skill/agent grids.

## Scope

The instruction kind has both global and project scope. The grid uses the
existing `ScopeToggle` (visible for instruction, like skill/agent). `general`'s
✔/☐ reflects the canonical at the active scope.

## Out of scope

- No changes to non-TUI output paths (JSON, plain text, the CLI commands).
- No new instruction *editing* features (authoring AGENTS.md content).
- The other 5 symlink harnesses stay CLI-only.
- The "stacked, always-visible" layout interpretation (rejected above).

## Definition of done (from issue)

- [x] TUI displays `instruction` entries above all other kinds → first sidebar
  option + separator.
- [x] Visual separator distinguishes the instruction section.
- [x] Existing kinds render unchanged (skill/pi-extension/agent untouched).
- [x] Efficacy checks confirm symlinks are created/removed correctly for the
  instruction kind → apply path drives `instructions_install.apply`; tests
  assert pointer create/remove on disk.
- [x] Symlink handling does not clobber non-symlink files → `conflict` cell
  surfaced; adapter `PointerConflictError` path tested.

## Verification

- `ruff` + `mypy --strict` clean on new files.
- New `tests/test_tui/test_instruction_state.py` — `build_instruction_rows`
  against a live lock + filesystem (linked / missing / conflict).
- New `tests/test_tui/test_instruction_grid.py` — Pilot tests mirroring
  `test_agent_grid.py`: columns render, toggle queues link/unlink, sidebar
  lists instruction first + separator, switching shows InstructionGrid, apply
  routes to `_apply_instruction_pending`, apply create/remove drives the
  install facade, conflict cell is non-clobbering, canonical-missing surfaces an
  error.
- Manual: launch the TUI, confirm `instruction` is first with a separator and
  the grid renders.
