# Agent grid 🌐 global marker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** At project scope, agents-tab cells whose harness slot is also linked at global scope render the 🌐 suffix, with a matching info-panel explainer — parity with the skills (#188) and pi-extensions (#349) tabs.

**Architecture:** Port the skill-tab pattern: `build_agent_rows` gains an extra global-scope probe at project scope (flat `cells` dict already keyed `(harness, scope)`); `agent_grid._cell_glyph` appends `🌐` when the global cell is linked; `column_info._standard_info`'s marker gate widens from skills-only to skills + agents with presence-neutral agents copy. Instructions stays excluded by design (comment rewrite only).

**Tech Stack:** Python 3.12, Textual (TUI), pytest + pytest-asyncio (Textual `run_test()` pilot harness).

**Spec:** `docs/superpowers/specs/2026-06-12-agent-grid-global-marker-design.md` (issue #374).

**Process notes for the engineer:**
- Pre-commit runs the full pytest suite (~3 min). Two pre-existing HOME-isolation failures are known and whitelisted: `test_empty_machine_is_empty` and `test_build_instruction_rows_empty_lock_no_canonical`. If a commit's pre-commit run fails on EXACTLY those two and nothing else, re-commit with `--no-verify`. Any other failure is yours — fix it.
- This main checkout is shared with sibling issue-preps: stage with explicit paths only (never `git add -A` / `commit -a`), and leave the pre-existing `skills-lock.json` modification untouched.
- `INTERACTIVE_HARNESSES` (agent_state.py:37) is `("standard",) + agents_nonstandard_main("global")` — derived, so tests index into it rather than hard-coding non-standard harness names.

---

### Task 1: State layer — global-scope probe at project scope

**Files:**
- Modify: `src/agent_toolkit_tui/agent_state.py` (probe in `build_agent_rows`, lines ~121-125; stale key-order comments at lines 35-36 and 55)
- Test: `tests/test_tui/test_agent_state.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_tui/test_agent_state.py` (reuses the module's existing `_entry` / `_write_library` helpers):

```python
def test_project_scope_probes_global_cells(tmp_path: Path, monkeypatch):
    """#374: at project scope every row also carries (harness, 'global')
    cells so the grid can render the globally-installed indicator."""
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    _write_library({"reviewer": _entry("o/reviewer")})
    # Simulate a global install in the standard .claude/agents slot.
    slot = tmp_path / ".claude" / "agents"
    slot.mkdir(parents=True)
    (slot / "reviewer.md").write_text("# reviewer\n")

    rows = build_agent_rows(scope="project", home=tmp_path, project=project)
    cell = rows[0].cells.get(("standard", "global"))
    assert cell is not None and cell.linked


def test_project_scope_global_probe_runs_for_unlisted_rows(tmp_path: Path, monkeypatch):
    """#374: the probe is a lock-independent filesystem check — unlisted
    (project-lock-only) rows get global cells too, matching skill_state."""
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    _write_library({})
    proj_path = lock_file_path(scope="project", project=project)
    write_lock(proj_path, LockFile(version=1, skills={"reviewer": _entry("o/reviewer")}))
    slot = tmp_path / ".claude" / "agents"
    slot.mkdir(parents=True)
    (slot / "reviewer.md").write_text("# reviewer\n")

    rows = build_agent_rows(scope="project", home=tmp_path, project=project)
    assert rows[0].state == "unlisted"
    cell = rows[0].cells.get(("standard", "global"))
    assert cell is not None and cell.linked


def test_project_scope_home_none_skips_global_probe(tmp_path: Path, monkeypatch):
    """#374: callers that pass home=None don't care about the indicator —
    no (harness, 'global') cells, mirroring skill_state's escape hatch."""
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    _write_library({"reviewer": _entry("o/reviewer")})

    rows = build_agent_rows(scope="project", home=None, project=project)
    assert all(scope != "global" for (_, scope) in rows[0].cells)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_tui/test_agent_state.py -v`
Expected: the two probe tests FAIL (`cells.get(("standard", "global"))` is `None`); `test_project_scope_home_none_skips_global_probe` PASSES already (it pins current behavior — keep it as the regression guard).

- [ ] **Step 3: Implement the probe**

In `src/agent_toolkit_tui/agent_state.py`, replace the cell-probe block inside `build_agent_rows` (currently lines 121-125):

```python
        cells: dict[tuple[str, str], AgentCell] = {}
        for harness in INTERACTIVE_HARNESSES:
            cell = _cell_for(slug, harness, scope=scope, home=home, project=project)
            if cell is not None:
                cells[(harness, scope)] = cell
        # In project scope, also probe global so the AgentGrid can render
        # the globally-installed indicator (#374). Skipped when home is None
        # (callers that don't care about the indicator). Runs for every row
        # in the universe — the probe is a filesystem check, independent of
        # lock membership — matching skill_state (#188).
        if scope == "project" and home is not None:
            for harness in INTERACTIVE_HARNESSES:
                cell = _cell_for(slug, harness, scope="global", home=home, project=None)
                if cell is not None:
                    cells[(harness, "global")] = cell
```

- [ ] **Step 4: Fix the two stale key-order comments in the same file**

Both say `(scope, harness)` but the code keys `(harness, scope)`. Line 34-36 block comment — change the last sentence:

```python
# Rendered columns (#361): the standard slot first, then the non-covered
# main harnesses (derived per scope; the two scopes yield the same set
# today because devin is not a MAIN harness). Cells are still keyed by
# (harness, scope). The long tail is CLI-only.
```

Line 55 field comment on `AgentRow.cells`:

```python
    # Key: (harness_name, scope) → AgentCell
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_tui/test_agent_state.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_tui/agent_state.py tests/test_tui/test_agent_state.py
git commit --only src/agent_toolkit_tui/agent_state.py --only tests/test_tui/test_agent_state.py -m "feat(tui): probe global agent cells at project scope (#374)"
```

(If pre-commit fails on exactly the two whitelisted tests, re-run with `--no-verify`.)

---

### Task 2: Grid layer — 🌐 suffix in `_cell_glyph`

**Files:**
- Modify: `src/agent_toolkit_tui/widgets/agent_grid.py` (constant near line 38; `_cell_glyph` at lines 382-393)
- Create: `tests/test_tui/test_agent_grid_global_indicator.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_tui/test_agent_grid_global_indicator.py` (mirrors `test_skill_grid_global_indicator.py`; uses `INTERACTIVE_HARNESSES` indices because the non-standard harness set is derived):

```python
"""Render tests for the agents-tab globally-installed indicator (#374).

Mirrors test_skill_grid_global_indicator.py (#188). Harness names beyond
"standard" are derived (INTERACTIVE_HARNESSES), so tests index into the
tuple instead of hard-coding names.
"""
from __future__ import annotations

import pytest
from rich.text import Text
from textual.app import App
from textual.widgets import DataTable

from agent_toolkit_tui.agent_state import INTERACTIVE_HARNESSES, AgentCell, AgentRow
from agent_toolkit_tui.widgets.agent_grid import AgentGrid

_H0 = INTERACTIVE_HARNESSES[0]  # "standard"
_H1 = INTERACTIVE_HARNESSES[1]  # first non-standard main harness


def _row_with(
    slug: str,
    *,
    state: str = "installed",
    project_cells: dict[str, AgentCell] | None = None,
    global_cells: dict[str, AgentCell] | None = None,
) -> AgentRow:
    cells: dict[tuple[str, str], AgentCell] = {}
    for harness, cell in (project_cells or {}).items():
        cells[(harness, "project")] = cell
    for harness, cell in (global_cells or {}).items():
        cells[(harness, "global")] = cell
    return AgentRow(slug=slug, source=f"x/{slug}", ref="main", state=state, cells=cells)


async def _rendered_plain(app: App, pilot, harness: str) -> str:
    table = app.query_one("#agent-table", DataTable)
    grid = app.query_one("#g", AgentGrid)
    grid._rebuild(table)  # type: ignore[attr-defined]
    await pilot.pause()
    row_key = list(table.rows.keys())[0]
    col_key = list(table.columns.keys())[1 + list(INTERACTIVE_HARNESSES).index(harness)]
    return Text.from_markup(str(table.get_cell(row_key, col_key))).plain


@pytest.mark.asyncio
async def test_project_scope_globally_linked_cell_shows_marker():
    """In project scope, a cell whose harness is globally linked shows 🌐;
    a sibling harness without a global link does not."""
    row = _row_with(
        "alpha",
        project_cells={h: AgentCell(linked=False) for h in INTERACTIVE_HARNESSES},
        global_cells={_H0: AgentCell(linked=True), _H1: AgentCell(linked=False)},
    )

    class _A(App):
        def compose(self):
            yield AgentGrid([row], id="g")

    a = _A()
    async with a.run_test() as pilot:
        a.query_one("#g", AgentGrid).set_scope("project")
        await pilot.pause()
        assert "🌐" in await _rendered_plain(a, pilot, _H0)
        assert "🌐" not in await _rendered_plain(a, pilot, _H1)


@pytest.mark.asyncio
async def test_global_scope_view_does_not_show_marker():
    """In global scope, even a globally-linked cell must not show 🌐."""
    row = _row_with(
        "alpha",
        global_cells={h: AgentCell(linked=True) for h in INTERACTIVE_HARNESSES},
    )

    class _A(App):
        def compose(self):
            yield AgentGrid([row], id="g")

    a = _A()
    async with a.run_test() as pilot:
        a.query_one("#g", AgentGrid).set_scope("global")
        await pilot.pause()
        for harness in INTERACTIVE_HARNESSES:
            assert "🌐" not in await _rendered_plain(a, pilot, harness)


@pytest.mark.asyncio
async def test_not_applicable_project_cell_still_shows_marker():
    """A harness with no project cell (not applicable at project scope) but a
    linked global cell renders the marker next to the em-dash base — matching
    the skills tab, where the marker appends to whatever the base glyph is."""
    row = _row_with(
        "alpha",
        project_cells={},
        global_cells={_H0: AgentCell(linked=True)},
    )

    class _A(App):
        def compose(self):
            yield AgentGrid([row], id="g")

    a = _A()
    async with a.run_test() as pilot:
        a.query_one("#g", AgentGrid).set_scope("project")
        await pilot.pause()
        plain = await _rendered_plain(a, pilot, _H0)
        assert "—" in plain and "🌐" in plain


@pytest.mark.asyncio
async def test_unlisted_row_shows_marker():
    """#360 state badges and the marker are independent — an unlisted row
    with a globally-linked cell shows 🌐."""
    row = _row_with(
        "alpha",
        state="unlisted",
        project_cells={h: AgentCell(linked=True) for h in INTERACTIVE_HARNESSES},
        global_cells={_H0: AgentCell(linked=True)},
    )

    class _A(App):
        def compose(self):
            yield AgentGrid([row], id="g")

    a = _A()
    async with a.run_test() as pilot:
        a.query_one("#g", AgentGrid).set_scope("project")
        await pilot.pause()
        assert "🌐" in await _rendered_plain(a, pilot, _H0)


@pytest.mark.asyncio
async def test_no_global_cells_no_marker_no_crash():
    """Rows without any (harness, 'global') cells (e.g. home=None callers)
    simply render no marker — no KeyError, no crash."""
    row = _row_with(
        "alpha",
        project_cells={h: AgentCell(linked=True) for h in INTERACTIVE_HARNESSES},
    )

    class _A(App):
        def compose(self):
            yield AgentGrid([row], id="g")

    a = _A()
    async with a.run_test() as pilot:
        a.query_one("#g", AgentGrid).set_scope("project")
        await pilot.pause()
        for harness in INTERACTIVE_HARNESSES:
            assert "🌐" not in await _rendered_plain(a, pilot, harness)
```

- [ ] **Step 2: Run the tests to verify the marker tests fail**

Run: `uv run pytest tests/test_tui/test_agent_grid_global_indicator.py -v`
Expected: `test_project_scope_globally_linked_cell_shows_marker`, `test_not_applicable_project_cell_still_shows_marker`, `test_unlisted_row_shows_marker` FAIL (no 🌐 rendered); the two negative tests PASS (they pin behavior that must survive).

- [ ] **Step 3: Implement the glyph**

In `src/agent_toolkit_tui/widgets/agent_grid.py`, add the constant after `_INFO_GLYPH` (line 38):

```python
_GLOBAL_GLYPH   = "🌐"
```

Replace `_cell_glyph` (lines 382-393) with:

```python
    def _cell_glyph(self, *, row: AgentRow, harness: str) -> str:
        """Return the display glyph for a harness cell. Never named _render_*."""
        cell = row.cells.get((harness, self._scope))
        if cell is None:
            # Not applicable at this scope (e.g. dexto at project scope).
            base = "[dim]—[/]"
        else:
            pending = self._pending.get((self._scope, harness, row.slug))
            if pending == "link":
                base = _PENDING_LINK
            elif pending == "unlink":
                base = _PENDING_UNLINK
            else:
                base = _LINKED_GLYPH if cell.linked else _UNLINKED_GLYPH
        # In project scope, mark cells whose harness slot is also linked
        # globally — same indicator as skill_grid (#188) / pi_grid (#349).
        # AgentCell has no drift/stray/skipped states, so linked is the
        # whole gate (#374). Appends to any base, including the
        # not-applicable em-dash.
        if self._scope == "project":
            global_cell = row.cells.get((harness, "global"))
            if global_cell is not None and global_cell.linked:
                return f"{base} {_GLOBAL_GLYPH}"
        return base
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_tui/test_agent_grid_global_indicator.py tests/test_tui/test_agent_grid.py tests/test_tui/test_agent_grid_standard.py -v`
Expected: all PASS (the two existing agent-grid files prove no glyph regressions).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/widgets/agent_grid.py tests/test_tui/test_agent_grid_global_indicator.py
git commit --only src/agent_toolkit_tui/widgets/agent_grid.py --only tests/test_tui/test_agent_grid_global_indicator.py -m "feat(tui): render 🌐 global marker on agent grid at project scope (#374)"
```

---

### Task 3: Info panel — widen the marker gate to agents

**Files:**
- Modify: `src/agent_toolkit_tui/column_info.py` (`_standard_info` lines 44-56; `get_column_info` docstring line 98)
- Test: `tests/test_tui/test_column_info.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_tui/test_column_info.py`:

```python
def test_standard_info_agents_includes_marker_when_globally_linked():
    """#374: the agents panel gets the 🌐 explainer, with presence-neutral
    copy (no redundancy claim — per-harness precedence is not asserted)."""
    info = get_column_info(
        "standard", context={"asset_type": "agents", "global_linked": True},
    )
    joined = "\n".join(info.lines)
    assert "🌐" in joined
    assert "This agent is also installed globally." in joined
    assert "may not need" not in joined


def test_standard_info_agents_omits_marker_when_not_globally_linked():
    info = get_column_info(
        "standard", context={"asset_type": "agents", "global_linked": False},
    )
    assert "🌐" not in "\n".join(info.lines)


def test_standard_info_instructions_never_shows_marker():
    """Instructions is excluded by design: per-scope canonical AGENTS.md,
    no cross-scope install concept — even a (bogus) global_linked=True
    context must not render the block."""
    info = get_column_info(
        "standard", context={"asset_type": "instructions", "global_linked": True},
    )
    assert "🌐" not in "\n".join(info.lines)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_tui/test_column_info.py -v`
Expected: the first test FAILS (`asset_type == "skills"` gate suppresses the block); the other two PASS already (regression pins).

- [ ] **Step 3: Implement the widened gate**

In `src/agent_toolkit_tui/column_info.py`, replace lines 45-56 (the comment, `show_marker`, and `indicator_note`) with:

```python
    # The 🌐 marker block applies to the asset types whose grids render the
    # marker: skills (#188) and agents (#374). Instructions is excluded by
    # design — each scope has its own canonical AGENTS.md, so there is no
    # cross-scope install concept. The block is also contextual: it only
    # makes sense when the focused row IS installed globally, so omit it
    # when the caller says otherwise.
    show_marker = asset_type in ("skills", "agents") and (
        context is None or bool(ctx.get("global_linked", True))
    )
    indicator_note: list[str] = []
    if show_marker:
        indicator_note = ["", "🌐 marker (project scope only):"]
        if asset_type == "skills":
            indicator_note += [
                "  This skill is also installed globally,",
                "  so you may not need it at project scope too.",
            ]
        else:
            # Agents copy stays presence-neutral (#374): per-harness
            # project-vs-global precedence is not asserted.
            indicator_note += ["  This agent is also installed globally."]
```

In `get_column_info`'s docstring (line 98), change `global_linked` (skills-only 🌐 marker block)` to `global_linked` (skills/agents 🌐 marker block)`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_tui/test_column_info.py tests/test_tui/test_column_info_modal.py -v`
Expected: all PASS (including the pre-existing skills-copy tests — the skills wording is byte-identical).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/column_info.py tests/test_tui/test_column_info.py
git commit --only src/agent_toolkit_tui/column_info.py --only tests/test_tui/test_column_info.py -m "feat(tui): extend column-info 🌐 explainer to agents asset type (#374)"
```

---

### Task 4: Wire `global_linked` from the agent grid's focused row

**Files:**
- Modify: `src/agent_toolkit_tui/widgets/agent_grid.py` (`action_info` call site line 167; `_context_for` lines 307-331)
- Test: `tests/test_tui/test_agent_grid_global_indicator.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_tui/test_agent_grid_global_indicator.py`:

```python
@pytest.mark.asyncio
async def test_context_for_reports_global_linked_true():
    """#374: the standard-key context surfaces whether the focused row's
    standard slot is linked globally, mirroring skill_grid._context_for."""
    row = _row_with(
        "alpha",
        project_cells={_H0: AgentCell(linked=False)},
        global_cells={_H0: AgentCell(linked=True)},
    )

    class _A(App):
        def compose(self):
            yield AgentGrid([row], id="g")

    a = _A()
    async with a.run_test() as pilot:
        g = a.query_one("#g", AgentGrid)
        g.set_scope("project")
        await pilot.pause()
        ctx = g._context_for(key="standard", row_index=0)  # type: ignore[attr-defined]
        assert ctx is not None
        assert ctx["global_linked"] is True
        assert ctx["asset_type"] == "agents"


@pytest.mark.asyncio
async def test_context_for_reports_global_linked_false():
    """No global cell (or out-of-range row) → global_linked False."""
    row = _row_with("alpha", project_cells={_H0: AgentCell(linked=True)})

    class _A(App):
        def compose(self):
            yield AgentGrid([row], id="g")

    a = _A()
    async with a.run_test() as pilot:
        g = a.query_one("#g", AgentGrid)
        g.set_scope("project")
        await pilot.pause()
        ctx = g._context_for(key="standard", row_index=0)  # type: ignore[attr-defined]
        assert ctx is not None and ctx["global_linked"] is False
        oob = g._context_for(key="standard", row_index=99)  # type: ignore[attr-defined]
        assert oob is not None and oob["global_linked"] is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_tui/test_agent_grid_global_indicator.py -v`
Expected: both new tests FAIL with `TypeError: _context_for() got an unexpected keyword argument 'row_index'`.

- [ ] **Step 3: Implement row-aware context**

In `src/agent_toolkit_tui/widgets/agent_grid.py`, replace `_context_for` (lines 307-331) with:

```python
    def _context_for(self, *, key: str, row_index: int) -> dict | None:
        """Context for get_column_info(): the standard panel enumerates the
        native .claude/agents readers from the per-scope coverage SSOT (#361).

        At global scope the panel carries the devin note (devin reads the
        slot at project scope only, so it is absent from the global covered
        set); at project scope devin is simply covered and the note is gone.

        Also surfaces whether the focused row is installed globally so the
        modal can omit the 🌐 paragraph when it's not (#374) — mirrors
        skill_grid._context_for.
        """
        if key == "standard":
            from agent_toolkit_cli.agent_adapters.standard import (
                agents_standard_covered,
            )

            covered = sorted(agents_standard_covered(self._scope))
            extra_lines = (
                ["", "devin reads .claude/agents at project scope only."]
                if self._scope == "global"
                else []
            )
            global_linked = False
            if 0 <= row_index < len(self._rows):
                global_cell = self._rows[row_index].cells.get(("standard", "global"))
                global_linked = bool(global_cell and global_cell.linked)
            return {
                "asset_type": "agents",
                "names": tuple(covered),
                "extra_lines": extra_lines,
                "global_linked": global_linked,
            }
        return None
```

Update the call site in `action_info` (line 167):

```python
            info = get_column_info(
                key, context=self._context_for(key=key, row_index=coord.row),
            )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_tui/test_agent_grid_global_indicator.py tests/test_tui/test_agent_grid.py tests/test_tui/test_agent_grid_standard.py -v`
Expected: all PASS (the existing files cover `action_info` paths and prove the signature change is fully wired).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/widgets/agent_grid.py tests/test_tui/test_agent_grid_global_indicator.py
git commit --only src/agent_toolkit_tui/widgets/agent_grid.py --only tests/test_tui/test_agent_grid_global_indicator.py -m "feat(tui): surface global_linked in agent grid column-info context (#374)"
```

---

### Task 5: Full-suite verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full suite**

Run: `uv run pytest`
Expected: green except the two whitelisted HOME-isolation failures (`test_empty_machine_is_empty`, `test_build_instruction_rows_empty_lock_no_canonical`) — both reproduce on clean main; anything else is a regression to fix before opening the PR.

- [ ] **Step 2: Run the linters/type-checkers exactly as CI does**

Run: `uv run ruff check src tests && uv run mypy src`
Expected: no NEW errors relative to main (main has known pre-existing counts; compare with `git stash`-free baseline via `git show` if in doubt — never stash to peek).
