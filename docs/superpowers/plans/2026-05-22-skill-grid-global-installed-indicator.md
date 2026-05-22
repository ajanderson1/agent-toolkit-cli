# SkillGrid Global-Installed Indicator (Project Scope) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the TUI Skill tab is in Project scope, suffix a `🌐` glyph onto each interactive-agent cell whose skill is also installed at global scope, so the operator can see at a glance "this is already covered globally."

**Architecture:** Two-level change. (1) Data — extend `build_skill_rows` to populate `(agent, "global")` cells alongside `(agent, "project")` cells when called in project scope with a `home` path, and update `app._scope_to_roots` to provide that `home`. (2) Render — `SkillGrid._cell_glyph` suffixes ` 🌐` when in project scope and the row's global cell is a clean linked symlink (linked, no drift, not skipped). Indicator is per-`(agent)`, not per-row; column-info popup for `Universal` gets a one-paragraph note.

**Tech Stack:** Python 3.x, Textual (DataTable / async pilot tests), pytest. Existing helpers (`_cell_for`, `SkillCell`, `INTERACTIVE_AGENTS`, `_GLOBAL_GLYPH` constant we'll add) carry the work.

**Spec:** `docs/superpowers/specs/2026-05-22-skill-grid-global-installed-indicator-design.md`
**Issue:** [#188](https://github.com/ajanderson1/agent-toolkit-cli/issues/188)

---

### Task 1: Extend `build_skill_rows` to populate global cells in project scope

**Files:**
- Modify: `src/agent_toolkit_tui/skill_state.py:137-173` (`build_skill_rows`)
- Test: `tests/test_tui/test_skill_state.py` (append new tests)

The current `build_skill_rows` loops `INTERACTIVE_AGENTS` once and writes `cells[(agent, scope)]`. We extend it: when `scope == "project"` and `home is not None`, write a second pass that calls `_cell_for(..., scope="global", home=home, project=None)` and stores under `(agent, "global")`. Global-scope behaviour is unchanged.

- [ ] **Step 1: Write the first failing test — project scope with home populates global cells**

Append to `tests/test_tui/test_skill_state.py`:

```python
# ---------------------------------------------------------------------------
# Global-cell population when in project scope (#188)
# ---------------------------------------------------------------------------


def _install_demo_globally(runner, project, library_root, *, universal: bool = True):
    """Install demo at global scope. Caller already added it to the library."""
    args = [
        "skill", "install", "demo",
        "--scope", "global",
    ]
    if universal:
        args.extend(["--agents", "universal"])
    return runner.invoke(main, args)


def test_build_skill_rows_project_scope_populates_global_cells(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    """In project scope, when home is provided, each row carries both
    (agent, 'project') and (agent, 'global') cells so the SkillGrid can
    render the globally-installed indicator (#188)."""
    project = tmp_path / "proj"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    monkeypatch.setenv("HOME", str(home))

    runner = CliRunner()
    r = _add_demo_project(runner, git_sandbox.upstream, project, library_root)
    assert r.exit_code == 0, r.output

    rows = build_skill_rows(scope="project", home=home, project=project)
    demo = next(r for r in rows if r.slug == "demo")
    # Project cells still present (existing behaviour).
    for agent in INTERACTIVE_AGENTS:
        assert (agent, "project") in demo.cells, (
            f"project cell missing for agent {agent!r}: {demo.cells.keys()}"
        )
    # Global cells now also present (new behaviour).
    for agent in INTERACTIVE_AGENTS:
        assert (agent, "global") in demo.cells, (
            f"global cell missing for agent {agent!r}: {demo.cells.keys()}"
        )


def test_build_skill_rows_project_scope_without_home_skips_global_cells(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    """Backwards-compatible path: home=None in project scope omits global
    cells. The indicator simply won't render — no exception."""
    project = tmp_path / "proj"
    project.mkdir()
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    r = _add_demo_project(runner, git_sandbox.upstream, project, library_root)
    assert r.exit_code == 0, r.output

    rows = build_skill_rows(scope="project", home=None, project=project)
    demo = next(r for r in rows if r.slug == "demo")
    for agent in INTERACTIVE_AGENTS:
        assert (agent, "project") in demo.cells
        assert (agent, "global") not in demo.cells, (
            f"unexpected global cell when home=None: {demo.cells.keys()}"
        )


def test_build_skill_rows_global_scope_unchanged(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    """Global-scope behaviour is unchanged: no project cells get populated."""
    home = tmp_path / "home"
    home.mkdir()
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    monkeypatch.setenv("HOME", str(home))

    runner = CliRunner()
    r = runner.invoke(main, [
        "skill", "add", str(git_sandbox.upstream), "--slug", "demo",
    ])
    assert r.exit_code == 0, r.output

    rows = build_skill_rows(scope="global", home=home, project=None)
    demo = next(r for r in rows if r.slug == "demo")
    for agent in INTERACTIVE_AGENTS:
        assert (agent, "global") in demo.cells
        assert (agent, "project") not in demo.cells, (
            f"unexpected project cell at global scope: {demo.cells.keys()}"
        )
```

The `INTERACTIVE_AGENTS` import is already present at the top of the file (used by the existing universal-cell tests); confirm it is imported. If not, add `INTERACTIVE_AGENTS` to the existing `from agent_toolkit_tui.skill_state import …` line.

- [ ] **Step 2: Run the new tests to confirm they fail**

```bash
uv run pytest tests/test_tui/test_skill_state.py::test_build_skill_rows_project_scope_populates_global_cells \
              tests/test_tui/test_skill_state.py::test_build_skill_rows_project_scope_without_home_skips_global_cells \
              tests/test_tui/test_skill_state.py::test_build_skill_rows_global_scope_unchanged \
              -v
```

Expected: the first test fails (`(universal, "global") not in demo.cells`). The other two should pass (they assert current behaviour) — if either fails, stop and inspect before changing the code.

- [ ] **Step 3: Implement the data-population change**

Modify `src/agent_toolkit_tui/skill_state.py`, in `build_skill_rows`, replace the existing per-row cell loop:

```python
        cells: dict[tuple[str, str], SkillCell] = {}
        for agent in INTERACTIVE_AGENTS:
            cells[(agent, scope)] = _cell_for(
                slug, agent, scope=scope, home=home, project=project,
            )
```

with:

```python
        cells: dict[tuple[str, str], SkillCell] = {}
        for agent in INTERACTIVE_AGENTS:
            cells[(agent, scope)] = _cell_for(
                slug, agent, scope=scope, home=home, project=project,
            )
        # In project scope, also probe global so the SkillGrid can render
        # the globally-installed indicator (#188). Skipped when home is
        # None (callers that don't care about the indicator).
        if scope == "project" and home is not None:
            for agent in INTERACTIVE_AGENTS:
                cells[(agent, "global")] = _cell_for(
                    slug, agent, scope="global", home=home, project=None,
                )
```

- [ ] **Step 4: Run the new tests to confirm they pass**

```bash
uv run pytest tests/test_tui/test_skill_state.py::test_build_skill_rows_project_scope_populates_global_cells \
              tests/test_tui/test_skill_state.py::test_build_skill_rows_project_scope_without_home_skips_global_cells \
              tests/test_tui/test_skill_state.py::test_build_skill_rows_global_scope_unchanged \
              -v
```

Expected: PASS, PASS, PASS.

- [ ] **Step 5: Run the full skill-state test module to confirm no regression**

```bash
uv run pytest tests/test_tui/test_skill_state.py -v
```

Expected: All pre-existing tests still pass (the change is additive when `scope == "project"` and `home is not None`; otherwise a no-op).

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_tui/skill_state.py tests/test_tui/test_skill_state.py
git commit -m "feat(tui): populate global cells in project scope for indicator (#188)"
```

---

### Task 2: Pass `Path.home()` from `app._scope_to_roots` in project mode

**Files:**
- Modify: `src/agent_toolkit_tui/app.py:128-131` (`_scope_to_roots`)
- Test: `tests/test_tui/test_scope_toggle.py` (append)

Today `_scope_to_roots()` returns `(scope, None, Path.cwd())` for project mode. After Task 1, that `None` means the indicator data never gets populated. Switch to `(scope, Path.home(), Path.cwd())` so the new code path is exercised in the live app.

- [ ] **Step 1: Look at the existing test file shape**

Read `tests/test_tui/test_scope_toggle.py` (one read, no edit). The plan needs to see the existing imports + fixture style to mirror them.

```bash
sed -n '1,40p' tests/test_tui/test_scope_toggle.py
```

If the file already imports the App under test, reuse those imports. If it does not exist yet, create it.

- [ ] **Step 2: Write the failing test**

Append (or create) in `tests/test_tui/test_scope_toggle.py`:

```python
from pathlib import Path

from agent_toolkit_tui.app import AgentToolkitTUI


def test_scope_to_roots_project_mode_passes_home():
    """In project scope the TUI must pass Path.home() so build_skill_rows
    can populate (agent, 'global') cells for the indicator (#188)."""
    app = AgentToolkitTUI()
    app._scope = "project"  # type: ignore[attr-defined]
    scope, home, project = app._scope_to_roots()  # type: ignore[attr-defined]
    assert scope == "project"
    assert home == Path.home(), f"expected Path.home(), got {home!r}"
    assert project == Path.cwd(), f"expected Path.cwd(), got {project!r}"


def test_scope_to_roots_global_mode_unchanged():
    app = AgentToolkitTUI()
    app._scope = "global"  # type: ignore[attr-defined]
    scope, home, project = app._scope_to_roots()  # type: ignore[attr-defined]
    assert scope == "global"
    assert home == Path.home()
    assert project is None
```

If `AgentToolkitTUI` is the wrong class name (the app entrypoint class), substitute the actual class from `agent_toolkit_tui/app.py`. Inspect the file once if unsure: `grep -n '^class ' src/agent_toolkit_tui/app.py`.

- [ ] **Step 3: Run the new tests to confirm they fail**

```bash
uv run pytest tests/test_tui/test_scope_toggle.py::test_scope_to_roots_project_mode_passes_home \
              tests/test_tui/test_scope_toggle.py::test_scope_to_roots_global_mode_unchanged \
              -v
```

Expected: the project-mode test fails (`home is None`); the global-mode test passes.

- [ ] **Step 4: Implement the change**

In `src/agent_toolkit_tui/app.py`, modify `_scope_to_roots`:

```python
    def _scope_to_roots(self) -> tuple[str, Path | None, Path | None]:
        if self._scope == "global":
            return "global", Path.home(), None
        return "project", Path.home(), Path.cwd()
```

(The only edit is `None` → `Path.home()` on the project branch.)

- [ ] **Step 5: Run the new tests to confirm they pass**

```bash
uv run pytest tests/test_tui/test_scope_toggle.py::test_scope_to_roots_project_mode_passes_home \
              tests/test_tui/test_scope_toggle.py::test_scope_to_roots_global_mode_unchanged \
              -v
```

Expected: PASS, PASS.

- [ ] **Step 6: Run the full scope-toggle module to confirm no regression**

```bash
uv run pytest tests/test_tui/test_scope_toggle.py -v
```

Expected: All tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/agent_toolkit_tui/app.py tests/test_tui/test_scope_toggle.py
git commit -m "feat(tui): pass Path.home() in project scope so global cells populate (#188)"
```

---

### Task 3: Add `_GLOBAL_GLYPH` constant + suffix logic in `SkillGrid._cell_glyph`

**Files:**
- Modify: `src/agent_toolkit_tui/widgets/skill_grid.py` (add `_GLOBAL_GLYPH` constant near other glyphs at l.39-45; extend `_cell_glyph` at l.286-299)
- Create: `tests/test_tui/test_skill_grid_global_indicator.py`

The grid widget now has access to global cells via `row.cells.get((agent, "global"))`. After computing the existing project glyph, when `self._scope == "project"` and the global cell is a clean linked symlink, append `" 🌐"` to the returned string.

- [ ] **Step 1: Write the first failing test — project scope, global-linked claude-code cell shows the marker**

Create `tests/test_tui/test_skill_grid_global_indicator.py`:

```python
"""Render tests for the globally-installed indicator in the project view (#188)."""
from __future__ import annotations

import pytest
from rich.text import Text
from textual.app import App
from textual.widgets import DataTable

from agent_toolkit_tui.skill_state import INTERACTIVE_AGENTS, SkillCell, SkillRow
from agent_toolkit_tui.widgets.skill_grid import SkillGrid


def _linked() -> SkillCell:
    return SkillCell(linked=True, drift=False, skipped=False)


def _unlinked() -> SkillCell:
    return SkillCell(linked=False, drift=False, skipped=False)


def _drifted() -> SkillCell:
    return SkillCell(linked=False, drift=True, skipped=False)


def _skipped() -> SkillCell:
    return SkillCell(linked=True, drift=False, skipped=True)


def _row_with(
    slug: str,
    *,
    project_cells: dict[str, SkillCell] | None = None,
    global_cells: dict[str, SkillCell] | None = None,
) -> SkillRow:
    cells: dict[tuple[str, str], SkillCell] = {}
    if project_cells:
        for agent, cell in project_cells.items():
            cells[(agent, "project")] = cell
    if global_cells:
        for agent, cell in global_cells.items():
            cells[(agent, "global")] = cell
    return SkillRow(
        slug=slug, source=f"x/{slug}", ref="main",
        state="library", cells=cells,
    )


def _cell_plain(table: DataTable, *, row_key: str, col_idx: int) -> str:
    """Return the rendered cell at (row_key, col_idx) with Rich markup stripped."""
    raw = table.get_cell(row_key, table.columns_at(col_idx)[0].key)  # type: ignore[attr-defined]
    return Text.from_markup(str(raw)).plain


def _claude_code_col_idx() -> int:
    # Layout: [0]=slug, [1]=description, [2]=universal, [3]=claude-code, [4]=pi
    return 2 + INTERACTIVE_AGENTS.index("claude-code")


def _pi_col_idx() -> int:
    return 2 + INTERACTIVE_AGENTS.index("pi")


@pytest.mark.asyncio
async def test_project_scope_globally_linked_cell_shows_marker():
    """In project scope, a row that is globally linked for claude-code
    shows the 🌐 suffix on the claude-code cell."""
    row = _row_with(
        "alpha",
        project_cells={agent: _unlinked() for agent in INTERACTIVE_AGENTS},
        global_cells={
            "universal": _unlinked(),
            "claude-code": _linked(),
            "pi": _unlinked(),
        },
    )

    class _A(App):
        def compose(self):
            grid = SkillGrid([row], id="g")
            yield grid

    a = _A()
    async with a.run_test() as pilot:
        g = a.query_one("#g", SkillGrid)
        g.set_scope("project")
        await pilot.pause()
        # Force a rebuild so the new scope is reflected.
        table = a.query_one("#skill-table", DataTable)
        g._rebuild(table)  # type: ignore[attr-defined]
        await pilot.pause()
        rendered_rows = list(table.rows.keys())
        assert rendered_rows, "no rows rendered"
        row_key = rendered_rows[0]
        # Pull each cell's raw value and convert to plain text.
        cc_col_key = list(table.columns.keys())[_claude_code_col_idx()]
        pi_col_key = list(table.columns.keys())[_pi_col_idx()]
        cc_plain = Text.from_markup(str(table.get_cell(row_key, cc_col_key))).plain
        pi_plain = Text.from_markup(str(table.get_cell(row_key, pi_col_key))).plain
        assert "🌐" in cc_plain, f"claude-code cell missing marker: {cc_plain!r}"
        assert "🌐" not in pi_plain, f"pi cell unexpectedly shows marker: {pi_plain!r}"
```

If `table.get_cell` or `table.columns` signatures don't match (Textual version drift), substitute the equivalent introspection — `table.get_row(row_key)` returning a list works too; pick whichever the existing tests in this directory already use (e.g. `test_skill_grid_column_info.py` uses `table.columns.values()` to read labels, which confirms `.columns` is a `dict`). The plan's intent is unambiguous: read the rendered text for the claude-code and pi cells of the only row, after a project-scope rebuild, and assert marker presence on one and absence on the other.

- [ ] **Step 2: Run the new test to confirm it fails**

```bash
uv run pytest tests/test_tui/test_skill_grid_global_indicator.py::test_project_scope_globally_linked_cell_shows_marker -v
```

Expected: FAIL — currently `_cell_glyph` ignores the global cell.

- [ ] **Step 3: Implement the suffix**

In `src/agent_toolkit_tui/widgets/skill_grid.py`:

a. Add the constant alongside the other glyphs (after `_INFO_GLYPH` at l.45):

```python
_GLOBAL_GLYPH   = "🌐"
```

b. Extend `_cell_glyph` (current implementation at l.286-299). Replace the existing method body with:

```python
    def _cell_glyph(self, *, row: SkillRow, agent: str) -> str:
        cell = row.cells.get((agent, self._scope))
        if cell is None:
            base = " "
        elif cell.skipped:
            base = _SKIPPED_GLYPH
        else:
            pending = self._pending.get((self._scope, agent, row.slug))
            if pending == "link":
                base = _PENDING_LINK
            elif pending == "unlink":
                base = _PENDING_UNLINK
            elif cell.drift:
                base = _DRIFT_GLYPH
            else:
                base = _LINKED_GLYPH if cell.linked else _UNLINKED_GLYPH
        if self._scope == "project":
            global_cell = row.cells.get((agent, "global"))
            if (
                global_cell is not None
                and global_cell.linked
                and not global_cell.drift
                and not global_cell.skipped
            ):
                return f"{base} {_GLOBAL_GLYPH}"
        return base
    ```

- [ ] **Step 4: Run the test to confirm it passes**

```bash
uv run pytest tests/test_tui/test_skill_grid_global_indicator.py::test_project_scope_globally_linked_cell_shows_marker -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/widgets/skill_grid.py tests/test_tui/test_skill_grid_global_indicator.py
git commit -m "feat(tui): suffix 🌐 in project-scope cells when globally linked (#188)"
```

---

### Task 4: Add render tests for the negative cases + per-agent independence

**Files:**
- Modify: `tests/test_tui/test_skill_grid_global_indicator.py`

The implementation passes the happy path. Add tests covering the rest of the DoD: global scope view doesn't show the marker; drift/skipped global cells don't trigger it; per-agent independence holds.

- [ ] **Step 1: Write the four additional failing-then-passing tests**

Append to `tests/test_tui/test_skill_grid_global_indicator.py`:

```python
@pytest.mark.asyncio
async def test_global_scope_view_does_not_show_marker():
    """In global scope, even a globally-linked row must not show 🌐.
    The marker is informative only when looking at the project view."""
    row = _row_with(
        "alpha",
        global_cells={
            "universal": _linked(),
            "claude-code": _linked(),
            "pi": _linked(),
        },
    )

    class _A(App):
        def compose(self):
            yield SkillGrid([row], id="g")

    a = _A()
    async with a.run_test() as pilot:
        g = a.query_one("#g", SkillGrid)
        g.set_scope("global")
        await pilot.pause()
        table = a.query_one("#skill-table", DataTable)
        g._rebuild(table)  # type: ignore[attr-defined]
        await pilot.pause()
        row_key = list(table.rows.keys())[0]
        for agent in INTERACTIVE_AGENTS:
            col_idx = 2 + INTERACTIVE_AGENTS.index(agent)
            col_key = list(table.columns.keys())[col_idx]
            plain = Text.from_markup(str(table.get_cell(row_key, col_key))).plain
            assert "🌐" not in plain, (
                f"global-scope {agent} cell unexpectedly has marker: {plain!r}"
            )


@pytest.mark.asyncio
async def test_drifted_global_cell_does_not_show_marker():
    """A drifted global symlink is NOT a clean global install — no marker."""
    row = _row_with(
        "alpha",
        project_cells={agent: _unlinked() for agent in INTERACTIVE_AGENTS},
        global_cells={
            "universal": _unlinked(),
            "claude-code": _drifted(),
            "pi": _unlinked(),
        },
    )

    class _A(App):
        def compose(self):
            yield SkillGrid([row], id="g")

    a = _A()
    async with a.run_test() as pilot:
        g = a.query_one("#g", SkillGrid)
        g.set_scope("project")
        await pilot.pause()
        table = a.query_one("#skill-table", DataTable)
        g._rebuild(table)  # type: ignore[attr-defined]
        await pilot.pause()
        row_key = list(table.rows.keys())[0]
        cc_col_key = list(table.columns.keys())[2 + INTERACTIVE_AGENTS.index("claude-code")]
        plain = Text.from_markup(str(table.get_cell(row_key, cc_col_key))).plain
        assert "🌐" not in plain, f"drifted global cell shows marker: {plain!r}"


@pytest.mark.asyncio
async def test_skipped_global_cell_does_not_show_marker():
    """A skipped global cell (canonical-IS-dir) is informational, not a
    clean per-agent global link — no marker."""
    row = _row_with(
        "alpha",
        project_cells={agent: _unlinked() for agent in INTERACTIVE_AGENTS},
        global_cells={
            "universal": _skipped(),
            "claude-code": _unlinked(),
            "pi": _unlinked(),
        },
    )

    class _A(App):
        def compose(self):
            yield SkillGrid([row], id="g")

    a = _A()
    async with a.run_test() as pilot:
        g = a.query_one("#g", SkillGrid)
        g.set_scope("project")
        await pilot.pause()
        table = a.query_one("#skill-table", DataTable)
        g._rebuild(table)  # type: ignore[attr-defined]
        await pilot.pause()
        row_key = list(table.rows.keys())[0]
        u_col_key = list(table.columns.keys())[2 + INTERACTIVE_AGENTS.index("universal")]
        plain = Text.from_markup(str(table.get_cell(row_key, u_col_key))).plain
        assert "🌐" not in plain, f"skipped global cell shows marker: {plain!r}"


@pytest.mark.asyncio
async def test_per_agent_independence():
    """A row that is globally linked for universal but not pi shows the
    marker only on the universal cell."""
    row = _row_with(
        "alpha",
        project_cells={agent: _unlinked() for agent in INTERACTIVE_AGENTS},
        global_cells={
            "universal": _linked(),
            "claude-code": _unlinked(),
            "pi": _unlinked(),
        },
    )

    class _A(App):
        def compose(self):
            yield SkillGrid([row], id="g")

    a = _A()
    async with a.run_test() as pilot:
        g = a.query_one("#g", SkillGrid)
        g.set_scope("project")
        await pilot.pause()
        table = a.query_one("#skill-table", DataTable)
        g._rebuild(table)  # type: ignore[attr-defined]
        await pilot.pause()
        row_key = list(table.rows.keys())[0]
        cols = list(table.columns.keys())
        u_plain = Text.from_markup(str(table.get_cell(
            row_key, cols[2 + INTERACTIVE_AGENTS.index("universal")]))).plain
        cc_plain = Text.from_markup(str(table.get_cell(
            row_key, cols[2 + INTERACTIVE_AGENTS.index("claude-code")]))).plain
        pi_plain = Text.from_markup(str(table.get_cell(
            row_key, cols[2 + INTERACTIVE_AGENTS.index("pi")]))).plain
        assert "🌐" in u_plain, f"universal cell missing marker: {u_plain!r}"
        assert "🌐" not in cc_plain, f"claude-code cell has marker: {cc_plain!r}"
        assert "🌐" not in pi_plain, f"pi cell has marker: {pi_plain!r}"
```

- [ ] **Step 2: Run the four new tests**

```bash
uv run pytest tests/test_tui/test_skill_grid_global_indicator.py -v
```

Expected: all five tests in the file pass (the Task-3 happy path plus the four added here).

- [ ] **Step 3: Commit**

```bash
git add tests/test_tui/test_skill_grid_global_indicator.py
git commit -m "test(tui): negative + per-agent cases for global-installed marker (#188)"
```

---

### Task 5: Update `Universal` column-info popup to mention the marker

**Files:**
- Modify: `src/agent_toolkit_tui/column_info.py:26-41` (`_universal_info`)
- Modify: `tests/test_tui/test_column_info.py` (append a small assertion)

The column-info popup for `Universal` is the most-asked-about column. Append a short paragraph explaining the 🌐 marker so it ships with its explanation.

- [ ] **Step 1: Read the current Universal info test for the assertion style**

```bash
sed -n '1,80p' tests/test_tui/test_column_info.py
```

Note whatever helper currently asserts on the `Universal` content (likely `from agent_toolkit_tui.column_info import get_column_info` + `assert ... in info.lines`). Reuse that pattern.

- [ ] **Step 2: Write the failing test**

Append to `tests/test_tui/test_column_info.py`:

```python
def test_universal_info_mentions_global_indicator():
    """The Universal column-info popup explains the 🌐 marker (#188)."""
    info = get_column_info("universal")
    assert info is not None
    joined = "\n".join(info.lines)
    assert "🌐" in joined, f"info missing global marker glyph: {info.lines}"
    assert "global" in joined.lower(), (
        f"info should explain the marker mentions global scope: {info.lines}"
    )
```

If `get_column_info` is already imported in the file, no import change needed. Otherwise add it.

- [ ] **Step 3: Run the test to confirm it fails**

```bash
uv run pytest tests/test_tui/test_column_info.py::test_universal_info_mentions_global_indicator -v
```

Expected: FAIL — info content currently doesn't mention 🌐.

- [ ] **Step 4: Update `_universal_info` to add the paragraph**

Modify `src/agent_toolkit_tui/column_info.py`, in `_universal_info`:

```python
def _universal_info() -> ColumnInfo:
    harness_names = get_universal_agents()
    description = [
        "Toggles link/unlink for every harness whose",
        "skillsDir is `.agents/skills`.",
        "",
        "Included harnesses:",
    ]
    bullets = [
        f"  • {name} — {AGENTS[name].display_name}"
        for name in harness_names
    ]
    indicator_note = [
        "",
        "🌐 marker (project scope only):",
        "  This skill is also installed globally,",
        "  so you may not need it at project scope too.",
    ]
    return ColumnInfo(
        title="Universal bundle",
        lines=description + bullets + indicator_note,
    )
```

- [ ] **Step 5: Run the new test + the full column-info module**

```bash
uv run pytest tests/test_tui/test_column_info.py -v
```

Expected: All tests pass, including the new one.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_tui/column_info.py tests/test_tui/test_column_info.py
git commit -m "docs(tui): explain 🌐 marker in Universal column info (#188)"
```

---

### Task 6: Final integration sweep — run all tests + lint, hand off to verify

**Files:** none (verification + safety net)

After the focused per-task tests pass, run the full pytest + lint + any pre-commit hooks once to catch interactions with neighbours that the per-task tests miss.

- [ ] **Step 1: Run full pytest**

```bash
uv run pytest -q
```

Expected: 0 failures. The pre-commit hook on `git commit` already ran this for each prior task, but rerunning here is the defensive backstop before pre-flight CI.

- [ ] **Step 2: Run lint**

```bash
uv run ruff check src tests
```

Expected: 0 issues. If ruff is configured via `pyproject.toml` with a different invocation, defer to that (e.g. `uv run ruff check .`).

- [ ] **Step 3: Run pre-commit if configured**

```bash
test -f .pre-commit-config.yaml && uv run pre-commit run --all-files || echo "no pre-commit configured"
```

Expected: PASS (or "no pre-commit configured").

- [ ] **Step 4: If anything fails, fix in a separate commit; otherwise no new commit needed**

If lint / pre-commit found something the per-task tests didn't catch: fix in-place, run the relevant per-task tests + lint again, commit:

```bash
git add -A
git commit -m "chore: fix lint/pre-commit findings after #188 build"
```

If everything is already clean, this task is a no-op — the prior six commits already cover the feature.

---

## Self-Review

**Spec coverage (each DoD bullet → task):**

| DoD bullet | Task |
|---|---|
| `build_skill_rows` populates both project + global cells when in project scope with `home` | Task 1 |
| `app._scope_to_roots()` returns `Path.home()` in project mode | Task 2 |
| `_cell_glyph` suffixes ` 🌐` when project-scope + global cell is clean linked | Task 3 |
| Per-agent independence (universal / claude-code / pi independent markers) | Task 4 |
| `Universal` column-info popup mentions the 🌐 marker | Task 5 |
| Tests: state-model both-cells populated | Task 1 |
| Tests: render-positive (project + linked) | Task 3 |
| Tests: render-negative (global scope, drift, skipped) | Task 4 |
| Tests: per-agent independence | Task 4 |
| Tests: app-wiring smoke (`_scope_to_roots`) | Task 2 |
| Pre-commit hooks pass; no test regresses | Task 6 |

**Placeholder scan:** No "TBD" / "implement appropriate" / "similar to Task N" — every code block is concrete. The one piece of plan-time discretion ("substitute the actual class from `agent_toolkit_tui/app.py`" in Task 2, "substitute the equivalent introspection" in Task 3) is bounded by a one-line inspection command and a clear intent statement; this is acceptable plan-time-fallback rather than a placeholder.

**Type consistency:** `SkillCell`, `SkillRow`, `INTERACTIVE_AGENTS`, `_cell_for`, `build_skill_rows` are all imported with their existing public signatures across all tasks. `_GLOBAL_GLYPH` is defined in Task 3 and not referenced elsewhere. `ColumnInfo` is used only in Task 5, matching the existing dataclass. No cross-task naming drift.

---

## Execution Handoff

This plan is for `/aj-workflow flow --auto` Step 5 → Step 6. The flow skill will dispatch `superpowers:subagent-driven-development` next.
