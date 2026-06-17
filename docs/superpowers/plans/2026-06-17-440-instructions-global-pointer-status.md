# Instructions Global Pointer Status Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the instructions TUI show harness-specific global pointer status clearly, without the `standard` column pretending that canonical existence equals harness install success.

**Architecture:** Keep `InstructionCell(linked, conflict)` as the single source of truth for symlink-backed harness cells. Change only presentation semantics: neutralize the `standard` column glyph, expose pointer/canonical paths in cell info, and strengthen tests around global-scope and same-harness 🌐 behavior.

**Tech Stack:** Python 3.13, Textual `DataTable`, pytest, existing `agent_toolkit_cli.instructions_adapters.symlink` path table.

---

## File Structure

- Modify: `src/agent_toolkit_tui/instruction_state.py`
  - Add `pointer_path_for()` helper so UI text can name the exact pointer slot without duplicating adapter path logic.
- Modify: `src/agent_toolkit_tui/widgets/instruction_grid.py`
  - Change `_standard_glyph()` to neutral/missing rendering.
  - Add pointer path + canonical target to harness-cell info text.
- Modify: `tests/test_tui/test_instruction_state.py`
  - Cover `pointer_path_for()` for global, project, and unavailable global `replit` slot.
- Modify: `tests/test_tui/test_instruction_grid.py`
  - Cover neutral standard glyph and info text path output.
- Modify: `tests/test_tui/test_instruction_grid_global_indicator.py`
  - Strengthen same-harness global marker behavior.

## Task 1: Add pointer path helper

**Files:**
- Modify: `src/agent_toolkit_tui/instruction_state.py`
- Test: `tests/test_tui/test_instruction_state.py`

- [ ] **Step 1: Write failing tests for pointer path helper**

Add imports and tests to `tests/test_tui/test_instruction_state.py`:

```python
from agent_toolkit_tui.instruction_state import pointer_path_for


def test_pointer_path_for_global_claude_code(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()

    path = pointer_path_for(
        "claude-code", scope="global", home=home, project=None,
    )

    assert path == home / ".claude" / "CLAUDE.md"


def test_pointer_path_for_project_gemini_cli(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()

    path = pointer_path_for(
        "gemini-cli", scope="project", home=None, project=project,
    )

    assert path == project / "GEMINI.md"


def test_pointer_path_for_unavailable_scope_returns_none(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()

    path = pointer_path_for(
        "replit", scope="global", home=home, project=None,
    )

    assert path is None
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_tui/test_instruction_state.py::test_pointer_path_for_global_claude_code tests/test_tui/test_instruction_state.py::test_pointer_path_for_project_gemini_cli tests/test_tui/test_instruction_state.py::test_pointer_path_for_unavailable_scope_returns_none -q
```

Expected: FAIL with import error or missing `pointer_path_for`.

- [ ] **Step 3: Implement helper**

Add near `_cell_for()` in `src/agent_toolkit_tui/instruction_state.py`:

```python
def pointer_path_for(
    harness: str,
    *,
    scope: Scope,
    home: Path | None,
    project: Path | None,
) -> Path | None:
    """Return the instructions pointer path for UI display, or None.

    Uses the same adapter path table as `_cell_for()` so the grid explains the
    exact slot it already checks. Returns None when the harness/scope pair has
    no pointer slot.
    """
    try:
        return _pointer_path(harness, scope, project, home)  # noqa: PLW0212
    except (ValueError, KeyError):
        return None
```

The `# noqa: PLW0212` is intentional: `instruction_state.py` already imports the private adapter helper for status checks, and this helper centralizes that existing private-path dependency instead of duplicating path templates in the grid.

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
uv run pytest tests/test_tui/test_instruction_state.py::test_pointer_path_for_global_claude_code tests/test_tui/test_instruction_state.py::test_pointer_path_for_project_gemini_cli tests/test_tui/test_instruction_state.py::test_pointer_path_for_unavailable_scope_returns_none -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/instruction_state.py tests/test_tui/test_instruction_state.py
git commit -m "fix: expose instruction pointer paths for TUI status"
```

## Task 2: Neutralize standard column glyph

**Files:**
- Modify: `src/agent_toolkit_tui/widgets/instruction_grid.py`
- Test: `tests/test_tui/test_instruction_grid.py`

- [ ] **Step 1: Write failing glyph tests**

Add tests to `tests/test_tui/test_instruction_grid.py`:

```python
def test_standard_glyph_is_neutral_when_canonical_exists():
    row = InstructionRow(
        slug="AGENTS.md",
        source="AGENTS.md",
        canonical_exists=True,
        cells={},
    )
    grid = InstructionGrid([row])

    glyph = grid._standard_glyph(row)  # type: ignore[attr-defined]

    assert "✔" not in glyph
    assert "green" not in glyph
    assert "AGENTS.md" in glyph or "std" in glyph


def test_standard_glyph_reports_missing_when_canonical_absent():
    row = InstructionRow(
        slug="AGENTS.md",
        source="AGENTS.md",
        canonical_exists=False,
        cells={},
    )
    grid = InstructionGrid([row])

    glyph = grid._standard_glyph(row)  # type: ignore[attr-defined]

    assert "missing" in glyph or "✘" in glyph
    assert "red" in glyph
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_tui/test_instruction_grid.py::test_standard_glyph_is_neutral_when_canonical_exists tests/test_tui/test_instruction_grid.py::test_standard_glyph_reports_missing_when_canonical_absent -q
```

Expected: first test FAILS because `_standard_glyph()` currently returns `[green]✔[/]`.

- [ ] **Step 3: Implement neutral glyph**

Change `_standard_glyph()` in `src/agent_toolkit_tui/widgets/instruction_grid.py`:

```python
def _standard_glyph(self, row: InstructionRow) -> str:
    """Return display glyph for the standard/native AGENTS.md column."""
    if row.canonical_exists:
        return "[dim]AGENTS.md[/]"
    return "[red]missing[/]"
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
uv run pytest tests/test_tui/test_instruction_grid.py::test_standard_glyph_is_neutral_when_canonical_exists tests/test_tui/test_instruction_grid.py::test_standard_glyph_reports_missing_when_canonical_absent -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/widgets/instruction_grid.py tests/test_tui/test_instruction_grid.py
git commit -m "fix: make instructions standard column informational"
```

## Task 3: Show pointer and target paths in harness cell info

**Files:**
- Modify: `src/agent_toolkit_tui/widgets/instruction_grid.py`
- Test: `tests/test_tui/test_instruction_grid.py`

- [ ] **Step 1: Write failing info-screen test**

Add this test to `tests/test_tui/test_instruction_grid.py`:

```python
@pytest.mark.asyncio
async def test_harness_info_shows_pointer_and_canonical_paths(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    agent_toolkit_dir = home / ".agent-toolkit"
    agent_toolkit_dir.mkdir()
    canonical = agent_toolkit_dir / "AGENTS.md"
    canonical.write_text("# AGENTS\n")

    monkeypatch.setattr(
        "agent_toolkit_cli.instructions_paths.library_root",
        lambda: agent_toolkit_dir / "instructions",
    )
    monkeypatch.setenv("HOME", str(home))

    row = InstructionRow(
        slug="AGENTS.md",
        source="AGENTS.md",
        canonical_exists=True,
        cells={
            ("claude-code", "global"): InstructionCell(linked=False, conflict=False),
        },
    )

    class _A(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid([row], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", InstructionGrid)
        g.set_scope("global")
        table = app.query_one("#instruction-table", DataTable)
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=2)
        table.focus()
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()

        from agent_toolkit_tui.screens.cell_info import CellInfoScreen

        assert isinstance(app.screen, CellInfoScreen)
        body = str(app.screen.query_one("#cell-info-body").render())
        assert str(home / ".claude" / "CLAUDE.md") in body
        assert str(canonical) in body
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
uv run pytest tests/test_tui/test_instruction_grid.py::test_harness_info_shows_pointer_and_canonical_paths -q
```

Expected: FAIL because current info text does not include pointer and canonical paths.

- [ ] **Step 3: Import path helpers in action_info**

Inside the harness-cell branch of `InstructionGrid.action_info()`, import:

```python
from pathlib import Path

from agent_toolkit_cli import instructions_paths
from agent_toolkit_tui.instruction_state import pointer_path_for
```

Compute paths before the pending/cell branches:

```python
project_root = Path.cwd() if self._scope == "project" else None
home_root = Path.home()
pointer_path = pointer_path_for(
    harness,
    scope=self._scope,
    home=home_root,
    project=project_root,
)
canonical_path = (
    instructions_paths.global_canonical_agents_md()
    if self._scope == "global"
    else instructions_paths.project_canonical_agents_md(Path.cwd())
)
path_lines = ""
if pointer_path is not None:
    path_lines = (
        f"\n\nPointer slot:\n  {pointer_path}"
        f"\n\nExpected target:\n  {canonical_path}"
    )
```

Append `path_lines` to pending, conflict, linked, and unlinked body strings. Example linked branch:

```python
elif cell.linked:
    body = (
        f"Installed. Pointer for {harness} @ {self._scope} is active."
        f"{path_lines}\n\n"
        f"CLI: [b]agent-toolkit-cli instructions uninstall {scope_flag}[/]"
    )
```

- [ ] **Step 4: Run test to verify pass**

Run:

```bash
uv run pytest tests/test_tui/test_instruction_grid.py::test_harness_info_shows_pointer_and_canonical_paths -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/widgets/instruction_grid.py tests/test_tui/test_instruction_grid.py
git commit -m "fix: show instruction pointer paths in TUI info"
```

## Task 4: Strengthen same-harness global marker tests

R2's basic `☐` / `✔` / `!` harness glyph behavior already exists in `_cell_glyph()` and `_cell_for()`; this task pins the remaining regression risk: the project-scope 🌐 marker must stay same-harness scoped.

**Files:**
- Modify: `tests/test_tui/test_instruction_grid_global_indicator.py`

- [ ] **Step 1: Add same-harness marker regression test**

Add a test that creates a project row with global Claude linked and global Gemini unlinked:

```python
@pytest.mark.asyncio
async def test_project_global_marker_is_same_harness_scoped():
    row = InstructionRow(
        slug="AGENTS.md",
        source="AGENTS.md",
        canonical_exists=True,
        cells={
            ("claude-code", "project"): InstructionCell(linked=True, conflict=False),
            ("claude-code", "global"): InstructionCell(linked=True, conflict=False),
            ("gemini-cli", "project"): InstructionCell(linked=False, conflict=False),
            ("gemini-cli", "global"): InstructionCell(linked=False, conflict=False),
        },
    )

    class _A(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid([row], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#g", InstructionGrid)
        grid.set_scope("project")

        assert "🌐" in grid._cell_glyph(row=row, harness="claude-code")  # type: ignore[attr-defined]
        assert "🌐" not in grid._cell_glyph(row=row, harness="gemini-cli")  # type: ignore[attr-defined]
```

- [ ] **Step 2: Run test**

Run:

```bash
uv run pytest tests/test_tui/test_instruction_grid_global_indicator.py::test_project_global_marker_is_same_harness_scoped -q
```

Expected: PASS if existing implementation is correct; FAIL if marker currently leaks across harnesses.

- [ ] **Step 3: Fix only if needed**

If the test fails, change `_cell_glyph()` in `src/agent_toolkit_tui/widgets/instruction_grid.py` so the global probe uses the same harness key only:

```python
if self._scope == "project":
    global_cell = row.cells.get((harness, "global"))
    if global_cell is not None and global_cell.linked:
        return f"{base} {_GLOBAL_GLYPH}"
```

- [ ] **Step 4: Commit**

```bash
git add src/agent_toolkit_tui/widgets/instruction_grid.py tests/test_tui/test_instruction_grid_global_indicator.py
git commit -m "test: pin same-harness instruction global marker"
```

## Task 5: Run targeted and full verification

**Files:**
- No source edits unless tests expose failures.

- [ ] **Step 1: Run targeted TUI tests**

```bash
uv run pytest tests/test_tui/test_instruction_state.py tests/test_tui/test_instruction_grid.py tests/test_tui/test_instruction_grid_global_indicator.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full test suite**

```bash
uv run pytest -q
```

Expected: PASS.

- [ ] **Step 3: Final commit if verification fixes were needed**

If Step 1 or Step 2 required additional fixes:

```bash
git add src/agent_toolkit_tui tests/test_tui
git commit -m "fix: finish instructions global pointer status"
```

## Acceptance Checklist

- [ ] `standard` column no longer shows green ✔ for canonical existence alone.
- [ ] Global symlink-backed harness cells remain the source of truth for pointer status.
- [ ] Harness info text names both pointer slot and expected canonical target.
- [ ] Project-scope 🌐 marker is same-harness scoped.
- [ ] Targeted TUI tests pass.
- [ ] Full test suite passes.
