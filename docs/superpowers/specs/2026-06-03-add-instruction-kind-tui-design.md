# Design — Add 'instruction' kind to TUI (#319)

**Mode:** `--auto` · **Issue:** [#319](https://github.com/ajanderson1/agent-toolkit-cli/issues/319) · **Date:** 2026-06-03

## Goal

The Textual TUI renders the `instruction` kind as a visually distinct section,
positioned **above** the other kinds (skill / pi-extension / agent) with a
separator. The `instruction` kind already exists in the CLI data model
(`instructions_lock.py`, `instructions_install.py`, `instructions_adapters/`)
but the TUI renderer does not yet surface it.

## Background (grounded in code)

- The instructions kind has its own lockfile model: `InstructionsLockEntry(scope,
  source, harnesses)` — no `source`/`ref`/`upstream_sha`, unlike skill `LockEntry`.
- Install/remove is by **symlink pointer**: each harness reads its own root file,
  and the adapter drops a same-name symlink → the canonical `AGENTS.md`.
  See `instructions_adapters/symlink.py` `CELLS` (7 harnesses, verified 2026-05-29):

  | harness | pointer file | scopes |
  |---|---|---|
  | augment | `CLAUDE.md` | global + project |
  | claude-code | `CLAUDE.md` | global + project |
  | codebuddy | `CODEBUDDY.md` | global + project |
  | gemini-cli | `GEMINI.md` | global + project |
  | iflow-cli | `IFLOW.md` | global + project |
  | replit | `replit.md` | **project-only** |
  | tabnine-cli | `TABNINE.md` | global + project |

- The adapter **already** enforces the no-clobber guarantee: `install()` raises
  `PointerConflictError` if a real file or a foreign symlink occupies the slot;
  `uninstall()` removes **only** our exact pointer and leaves real files / foreign
  symlinks untouched (`symlink.py:101–141`). The TUI must surface this error, not
  swallow it.

## Decisions

1. **Section order.** The instruction section renders **first** in the kind
   sidebar (`OptionList`), above skill / pi-extension / agent, with a visual
   separator. The default *active* kind stays `skill` (changing it would churn
   many existing tests and isn't required by the DoD) — only sidebar **order**
   and a separator change.

2. **Columns (user-confirmed 2026-06-03).** `general` first, then **claude-code**
   and **gemini-cli** — the two most common harnesses with distinct pointer
   files (`CLAUDE.md`, `GEMINI.md`). `general` represents the canonical
   `AGENTS.md` install state for the scope.

3. **Two-scope layout (PiGrid-shaped).** Like pi-extensions, instructions have a
   single logical slug (`AGENTS.md`) per scope rather than many slugs per
   harness, so the grid shows both scopes without a scope toggle. Pending key
   shape: `(scope, harness, slug)` to match the agent/skill convention.

4. **Cells that don't apply.** A harness with no slot for a scope (e.g. `replit`
   globally) yields a not-applicable cell — probe via `_pointer_path` wrapped in
   `try/except ValueError`, mirroring `agent_state._cell_for`.

5. **No `_render_*` method names** (Textual collision — documented in
   `agent_grid.py`). Use `_cell_glyph` / `_rebuild`.

## Out of scope

- No changes to non-TUI output paths (CLI JSON / plain text).
- No new instruction-editing features.
- No change to the symlink adapter or the install/remove CLI logic — the TUI
  consumes the existing `instructions_install.apply/uninstall`.

## Definition of done

- [ ] TUI displays `instruction` entries above all other kinds, with a separator.
- [ ] Instruction section shows `general`, `claude-code`, `gemini-cli` columns.
- [ ] Existing kinds (skill / pi-extension / agent) render unchanged.
- [ ] Toggling a cell queues a `link` / `unlink` pending op; apply calls
      `instructions_install.apply/uninstall`.
- [ ] Efficacy test confirms the symlink is **created** on apply and **removed**
      on uninstall for the instruction kind (pointer `.is_symlink()` and resolves
      to canonical `AGENTS.md`).
- [ ] `PointerConflictError` (real file at target) is surfaced as an error in the
      TUI, never swallowed — proving symlink handling does not clobber non-symlink
      files.
- [ ] `uv run pytest -q` green; existing TUI tests updated where they assert "three
      kinds".
