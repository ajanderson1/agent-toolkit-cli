# Issue 440 — Instructions Global Pointer Status Spec

## Summary

The TUI instructions pane currently shows a green ✔ in the `standard` column whenever the canonical `AGENTS.md` file exists. That reads like an install/status success, but it is not tied to any particular harness. The pane must make the harness-specific truth obvious: for each symlink-backed instructions harness, the cell should show whether that harness's default global instruction file is linked to canonical `AGENTS.md`.

## Problem statement

Instructions have two different concepts that the grid currently blends visually:

1. **Standard/native coverage** — many harnesses read `AGENTS.md` directly. The `standard` column is an informational bucket listing those native readers.
2. **Pointer symlink state** — non-native harnesses such as Claude Code and Gemini CLI read own-name files (`CLAUDE.md`, `GEMINI.md`). Their cells must show whether those pointer files exist and resolve to canonical `AGENTS.md` at the active scope.

`InstructionGrid._standard_glyph()` currently returns `[green]✔[/]` when `InstructionRow.canonical_exists` is true. In practice this makes a row look “installed” even when a specific harness pointer is absent. Example from current state: the global canonical exists, `claude-code` is linked, `gemini-cli` is unlinked, yet `standard` still shows a green ✔. That green glyph does not answer the user’s question: “does this harness have its global default pointer set up?”

## Goals

- Make per-harness symlink status the visible source of truth for symlink-backed instruction harnesses.
- Ensure global scope cells answer: “is this harness’s default global instruction file linked to canonical `AGENTS.md`?”
- Ensure project scope cells keep the existing 🌐 marker, but only for the same harness when its global pointer is linked.
- Stop the `standard` column from looking like a per-harness install success.
- Keep the native-reader list available through the `i` info panel.

## Non-goals

- Do not add adapters for native harnesses.
- Do not create symlinks for native harnesses that already read `AGENTS.md`.
- Do not add long-tail instructions columns beyond the existing main harness set.
- Do not change the CLI install/uninstall semantics.
- Do not infer global support for harnesses whose matrix row has no documented global instruction-file path.

## Requirements

### R1 — Neutral standard column status

The `standard` column must not render a green success glyph solely because `canonical_exists` is true. It should render as informational/neutral when canonical exists and as a missing/error state when canonical is absent.

Acceptance:

- Given `InstructionRow(canonical_exists=True)`, `_standard_glyph()` returns a neutral glyph such as `[dim]AGENTS.md[/]`, `[dim]std[/]`, or another non-green/non-check status.
- Given `InstructionRow(canonical_exists=False)`, `_standard_glyph()` still clearly signals the canonical file is missing.
- `i` on the `standard` column still opens the native-reader info modal.

### R2 — Global harness cells show real pointer state

At global scope, each rendered symlink-backed harness column must reflect the filesystem state of that harness’s documented global pointer path:

- `claude-code` → `~/.claude/CLAUDE.md`
- `gemini-cli` → `~/.gemini/GEMINI.md`
- Other rendered symlink-backed main harnesses if `instructions_nonstandard_main()` expands later.

Acceptance:

- Absent pointer slot → `☐`
- Pointer symlink resolving to canonical global `AGENTS.md` → green `✔`
- Real file or foreign/broken symlink in pointer slot → red `!`
- Tests prove `build_instruction_rows(scope="global", ...)` and `InstructionGrid` agree on those states.

### R3 — Project cells show same-harness global marker only

At project scope, a harness cell may append 🌐 only when the same harness is linked at global scope. A global link for Claude Code must not mark Gemini CLI, and vice versa.

Acceptance:

- Project `claude-code` cell renders `✔ 🌐` only when `row.cells[("claude-code", "global")].linked` is true.
- Project `gemini-cli` cell does not render 🌐 when only `claude-code` is linked globally.
- Existing global-indicator tests stay green or get strengthened.

### R4 — Cell info names concrete paths

Pressing `i` on a symlink-backed harness cell should explain which pointer slot is being checked and what it should point to. This makes the UI self-auditing instead of glyph-only.

Acceptance:

- Global `claude-code` info includes `~/.claude/CLAUDE.md` (or the expanded fake-home path in tests) and canonical global `AGENTS.md` target.
- Global `gemini-cli` info includes `~/.gemini/GEMINI.md` and canonical global `AGENTS.md` target.
- Project-scope info similarly names project pointer path and project canonical target.

## Design

### Data model

Keep `InstructionCell(linked, conflict)` as the core status. It already models the exact state needed by the harness columns. Extend only if path display needs a non-invasive helper.

Add a public or private helper in `instruction_state.py`, wrapping the existing `_pointer_path()` adapter helper, to return the pointer path for UI explanations:

```python
def pointer_path_for(
    harness: str,
    *,
    scope: Scope,
    home: Path | None,
    project: Path | None,
) -> Path | None:
    try:
        return _pointer_path(harness, scope, project, home)
    except (ValueError, KeyError):
        return None
```

The grid can use this for info text. Status computation remains in `_cell_for()`.

### Grid rendering

Change `_standard_glyph()` so canonical existence is not shown as green install success. Recommended rendering:

```python
def _standard_glyph(self, row: InstructionRow) -> str:
    if row.canonical_exists:
        return "[dim]AGENTS.md[/]"
    return "[red]missing[/]"
```

This keeps the column useful as an informational “native AGENTS.md coverage exists” cue while preventing the green check from implying per-harness pointer success.

Keep `_cell_glyph()` as the harness status source of truth. Add or strengthen tests that assert the global marker is same-harness scoped.

### Info text

Update `InstructionGrid.action_info()` for harness cells to include:

- Pointer path
- Canonical target path
- Current state summary
- CLI command

Example global unlinked body:

```text
Not installed. The claude-code global pointer slot is:
  /tmp/home/.claude/CLAUDE.md

It should point to:
  /tmp/home/.agent-toolkit/AGENTS.md

Press space to queue install, or run:
  agent-toolkit-cli instructions install -g
```

The project branch should use the project pointer/canonical paths.

## Test plan

- `tests/test_tui/test_instruction_grid.py`
  - Add a unit test for neutral standard glyph when `canonical_exists=True`.
  - Keep/adjust missing canonical assertion if one exists.
  - Add info-screen assertions for pointer path and canonical target.
- `tests/test_tui/test_instruction_grid_global_indicator.py`
  - Strengthen same-harness 🌐 behavior.
- `tests/test_tui/test_instruction_state.py`
  - Add helper/path tests if `pointer_path_for()` is introduced.
- Targeted verification:
  - `uv run pytest tests/test_tui/test_instruction_state.py tests/test_tui/test_instruction_grid.py tests/test_tui/test_instruction_grid_global_indicator.py -q`
- Full verification:
  - `uv run pytest -q`

## Open decisions resolved

- **Do not convert `standard` into a multi-harness status column.** A single cell cannot accurately display 39 native harness states without hiding detail. Native readers remain documented in the info modal.
- **Do not make native harnesses symlink-managed.** That would contradict the harness matrix vocabulary: native means no pointer needed.
- **Use neutral standard rendering instead of removing the column.** The column still communicates native AGENTS.md coverage and keeps the `i` discovery path.
