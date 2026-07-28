# Column Info Affordances Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clicking a column header explains the *column* for this asset type; pressing `i` explains the *asset* on the current row. Every rendered `ⓘ` resolves to real content.

**Architecture:** Replace `column_info.COLUMN_INFO` (2 keys) with a registry keyed by `(column, asset_type)` whose values are factories resolved at call time. Add a `DataTable.HeaderSelected` handler to each grid that maps a column index to a registry key and opens `ColumnInfoModal`. Repoint every grid's `action_info()` at a single asset-scoped panel. Fix `app.action_info_pass()`'s dead Commands branch. Glyph the State/Origin headers that lack `ⓘ`.

**Spec:** `docs/superpowers/specs/2026-07-28-479-column-info-affordances.md` — the authored copy matrix is spec R5 and is the source of truth for all wording.

**Depends on #478.** #478 introduces `standard_column_header()` and settles which columns exist and lead. Landing #479 first means writing header-index mapping against a layout that is about to change, and #478's spec R2a explicitly delegates "what does `Standard (39)` vs `Standard (2)` mean" to this issue's panels. Do #478 first.

**Tech Stack:** Python 3.13-compatible, Textual `DataTable` (`HeaderSelected`), `ModalScreen`, pytest + pytest-asyncio pilots.

---

## Implementation Units

- Rewrite `src/agent_toolkit_tui/column_info.py`: `(column, asset_type)` registry, per-harness factories, per-asset State/Origin factories.
- Modify all six grids: `on_data_table_header_selected`, header-index → registry-key mapping, `ⓘ` on State/Origin, `action_info()` → asset panel.
- Modify `src/agent_toolkit_tui/screens/cell_info.py` or add an asset panel screen.
- Modify `src/agent_toolkit_tui/app.py`: fix the Commands `action_info_pass` branch.
- Tests: registry coverage invariant, header-click behaviour, `i` behaviour, and the both-ways glyph invariant.

## Task 0: Confirm the dependency and the premise

- [x] **Step 1: Verify #478 has landed**

```bash
git log --oneline -20 | rg -i "standard column|478" || echo "NOT LANDED"
uv run python -c "from agent_toolkit_tui.display_names import standard_column_header; print(standard_column_header('skill','global'))"
```

Expected: prints `Standard (13)`. If it raises `ImportError`, **stop** — #478 is
a hard prerequisite. Park and report.

- [x] **Step 2: Re-derive the rendered column set**

```bash
uv run python - <<'PY'
from agent_toolkit_tui.skill_state import INTERACTIVE_AGENTS
from agent_toolkit_tui.agent_state import INTERACTIVE_HARNESSES as AG
from agent_toolkit_tui.composition import instructions_nonstandard_main, mcp_nonstandard_main
from agent_toolkit_cli.command_adapters import DEFAULT_HARNESSES
print("skills", INTERACTIVE_AGENTS)
print("instr ", ("standard",)+instructions_nonstandard_main())
print("agents", AG)
print("mcp g ", mcp_nonstandard_main("global"))
print("mcp p ", ("standard",)+mcp_nonstandard_main("project"))
print("cmd   ", DEFAULT_HARNESSES)
PY
```

Compare against the spec's table. If any row differs, the copy matrix in spec
R5 has a gap — author the missing sentence from the adapter before continuing,
and note the addition in the PR body. Do **not** ship a column with no panel.

## Task 1: The coverage invariant, written first

**Files:**
- Create: `tests/test_tui/test_column_info_coverage.py`

- [x] **Step 1: Write the both-ways invariant**

Create `tests/test_tui/test_column_info_coverage.py`:

```python
"""Every rendered ⓘ resolves, and every explainable column carries ⓘ (#479 R2)."""
from __future__ import annotations

import pytest

from agent_toolkit_tui.column_info import get_column_info, registered_pairs

# (asset_type, scope) -> the harness/meta columns the grid renders.
# Derived, not hardcoded, in Task 0 Step 2; pinned here so a composition
# change breaks this test loudly rather than silently dropping a panel.
EXPECTED = {
    ("skill", "global"): ("standard", "claude-code", "pi", "hermes-agent", "paperclip", "state"),
    ("skill", "project"): ("standard", "claude-code", "pi", "hermes-agent", "paperclip", "state"),
    ("instruction", "global"): ("standard", "claude-code", "gemini-cli"),
    ("instruction", "project"): ("standard", "claude-code", "gemini-cli"),
    ("agent", "global"): ("standard", "gemini-cli", "opencode", "pi", "state"),
    ("agent", "project"): ("standard", "gemini-cli", "opencode", "pi", "state"),
    ("mcp", "global"): ("claude-code", "codex", "opencode", "pi", "state"),
    ("mcp", "project"): ("standard", "codex", "opencode", "state"),
    ("command", "global"): ("claude-code", "pi", "gemini-cli", "state"),
    ("command", "project"): ("claude-code", "pi", "gemini-cli", "state"),
    ("pi-extension", "global"): ("pi", "origin"),
    ("pi-extension", "project"): ("pi", "origin"),
}


@pytest.mark.parametrize(("key", "columns"), sorted(EXPECTED.items()))
def test_every_rendered_column_has_info(key, columns):
    asset_type, scope = key
    for column in columns:
        info = get_column_info(column, asset_type=asset_type, context={"scope": scope})
        assert info is not None, f"{asset_type}/{scope}: no info for {column!r}"
        assert info.title.strip(), f"{asset_type}/{scope}/{column}: empty title"
        assert info.lines, f"{asset_type}/{scope}/{column}: empty body"


def test_unregistered_pair_is_loud():
    """A new column must fail loudly, not silently render a dead ⓘ (#479 R4)."""
    with pytest.raises(KeyError):
        get_column_info("nonsense", asset_type="skill", context={"scope": "global"})


def test_no_orphan_registry_entries():
    """Every registered pair is actually rendered somewhere (#193's lesson:
    orphan info machinery outlived its columns and had to be swept)."""
    rendered = {(a, c) for (a, s), cols in EXPECTED.items() for c in cols}
    orphans = {(a, c) for (a, c) in registered_pairs() if (a, c) not in rendered}
    assert not orphans, f"registry has entries no grid renders: {sorted(orphans)}"
```

- [x] **Step 2: Confirm the red**

```bash
uv run pytest tests/test_tui/test_column_info_coverage.py -q
```

Expected: `ImportError` on `registered_pairs`, or failures for every non-
`standard`/`state` column. Both are the correct red.

## Task 2: Rebuild the registry

**Files:**
- Modify: `src/agent_toolkit_tui/column_info.py`
- Modify: `tests/test_tui/test_column_info.py`

- [x] **Step 1: Restructure the registry key**

Rewrite `COLUMN_INFO` as `dict[tuple[str, str], Callable[..., ColumnInfo]]`
keyed by `(asset_type, column)`. Change the accessor to:

```python
def get_column_info(column: str, *, asset_type: str, context: dict | None = None) -> ColumnInfo:
    """Fresh ColumnInfo for (asset_type, column). Raises KeyError if unregistered.

    Factories, not prebuilt objects, so harness lists and counts always reflect
    the live SSOT rather than an import-time snapshot (#479 R4).
    """
    factory = COLUMN_INFO[(asset_type, column)]
    return factory(context or {})


def registered_pairs() -> frozenset[tuple[str, str]]:
    """(asset_type, column) pairs the registry knows. Used by the coverage test."""
    return frozenset(COLUMN_INFO)
```

**Behaviour change:** `get_column_info` now **raises** on an unknown pair
instead of returning `None`. Every caller currently branches on `None` — update
them in Task 3 rather than leaving a silent fallback.

- [x] **Step 2: Port the Standard factories**

Keep `_standard_info`'s substance but split the `if asset_type == ...` chains
into four small factories (`_standard_skills`, `_standard_instructions`,
`_standard_agents`, `_standard_mcp`), each producing: the covered-harness
bullet list, then the **one sentence** from spec R5.

Carry across **verbatim**:

- the `🌐` marker block for skills / agents / instructions, gated on
  `context.get("global_linked", True)` and project scope;
- the instructions wording ("also loads a global AGENTS.md, merged with (not
  replaced by) the project one") — this is a deliberate correction from #388,
  **do not** re-generalise it to the skills "you may not need it" phrasing;
- the agents `devin` project-scope-only note supplied via `extra_lines`.

Re-read `column_info.py:29-95` before deleting anything; the comments there
record why each clause exists.

- [x] **Step 3: Add the harness factories**

Add one factory per `(asset_type, harness)` pair in spec R5 — 17 pairs. Each
returns a title (`f"{harness_label(h)} — {asset_type_label(asset_type)}"`) and a
one-sentence body, plus a destination-path line where the adapter exposes one
cheaply.

Do **not** paraphrase spec R5. Copy the sentences. Where a sentence names a
path, add a comment pinning it to its source, e.g.:

```python
# path source: command_adapters/markdown.py DESTINATIONS["pi"]
```

- [x] **Step 4: Add the State and Origin factories**

Four State factories (skills keeps today's six-badge legend verbatim from
`_state_info`; agents/commands/mcp share the three-badge legend from spec R5)
and one Origin factory for Pi Extensions.

Do not collapse the four State panels into one — the vocabularies genuinely
differ (spec Non-goals).

- [x] **Step 5: Green the coverage test**

```bash
uv run pytest tests/test_tui/test_column_info_coverage.py tests/test_tui/test_column_info.py -q
```

Expected: PASS. Existing `test_column_info.py` cases will need their call sites
updated for the new signature — that is a genuine API change, not a test to
weaken.

- [x] **Step 6: Commit**

```bash
git add src/agent_toolkit_tui/column_info.py tests/test_tui/test_column_info*.py
git commit -m "feat(tui): per-asset-type column info registry"
```

## Task 3: Header click opens column info

**Files:**
- Modify: all six grids in `src/agent_toolkit_tui/widgets/`
- Create: `tests/test_tui/test_header_click_info.py`

- [x] **Step 1: Write the failing header-click test**

Create `tests/test_tui/test_header_click_info.py` with, for each asset type, a
pilot test that posts a `DataTable.HeaderSelected` for each glyphed column and
asserts a `ColumnInfoModal` is pushed with the expected title. Use
`app.push_screen` inspection or `isinstance(app.screen, ColumnInfoModal)` after
`await pilot.pause()`.

Prefer posting the message directly over simulating a pixel click:

```python
    table = app.query_one("#skill-table", DataTable)
    grid = app.query_one("#skill-grid", SkillGrid)
    grid.post_message(
        DataTable.HeaderSelected(table, column_key=list(table.columns)[1],
                                 column_index=1, label=Text("Standard (13)"))
    )
    await pilot.pause()
    assert isinstance(app.screen, ColumnInfoModal)
```

Check `DataTable.HeaderSelected`'s constructor signature against the installed
Textual version before writing all six — it has changed across releases:

```bash
uv run python -c "import inspect, textual.widgets as w; print(inspect.signature(w.DataTable.HeaderSelected.__init__))"
```

Also assert the negative: posting `HeaderSelected` for the `Source` column
opens **no** modal.

```bash
uv run pytest tests/test_tui/test_header_click_info.py -q
```

Expected: FAIL — no handler exists.

- [x] **Step 2: Add the handler to each grid**

In each grid, add:

```python
    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        """Click a header -> that column's info (#479 R1). Mouse-only by design;
        `i` is reserved for the per-asset panel."""
        key = self._column_key_for_index(event.column_index)
        if key is None:
            return  # passive column (Source) — no panel, no glyph
        self.app.push_screen(
            ColumnInfoModal(
                get_column_info(key, asset_type=<ASSET_TYPE>, context=self._context_for_column(key))
            )
        )
```

Rework each grid's existing `_column_key_for_index` so it returns a key for
**every** glyphed column — the harness name for harness columns, `"state"` for
State, `"origin"` for Origin, `"standard"` for Standard — and `None` only for
the slug and Source columns.

Note: `DataTable.HeaderSelected` only fires when the table's header is
clickable. Confirm `show_header` is on (it is, by default) and that no grid
sets `header_height=0`.

- [x] **Step 3: Glyph the bare headers**

Add ` {_INFO_GLYPH}` to the `State` header in `agent_grid.py:431`,
`command_grid.py:407`, and `mcp_grid.py:437`, and to `Origin` in
`pi_grid.py:420`. Leave `Source` bare.

Widen the affected column constants by 2 if the glyph pushes the label to
truncate; check visually in Task 5 rather than guessing.

- [x] **Step 4: Green**

```bash
uv run pytest tests/test_tui/test_header_click_info.py -q
```

- [x] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/widgets tests/test_tui/test_header_click_info.py
git commit -m "feat(tui): click a column header for column info"
```

## Task 4: `i` always explains the asset

**Files:**
- Modify: all six grids' `action_info()`
- Modify: `src/agent_toolkit_tui/app.py`
- Modify/Create: the asset panel screen
- Create: `tests/test_tui/test_asset_info_key.py`

- [x] **Step 1: Write the failing test**

Create `tests/test_tui/test_asset_info_key.py`:

```python
@pytest.mark.asyncio
@pytest.mark.parametrize("column", [0, 1, 2])
async def test_i_shows_the_same_asset_panel_from_any_column(column):
    """`i` means 'explain this asset', not 'explain this column' (#479 R3)."""
    ...
    # move cursor to (row 0, column), press "i", assert the pushed screen is the
    # asset panel and its title contains the row's slug — identical for all
    # three columns, including Standard and State.


@pytest.mark.asyncio
async def test_i_works_on_the_command_grid():
    """app.action_info_pass() currently just refocuses the grid (app.py:596-601)."""


@pytest.mark.asyncio
async def test_i_with_no_description_says_so():
    """R3: say it plainly rather than rendering an empty section."""


@pytest.mark.asyncio
async def test_i_with_zero_visible_rows_is_a_noop():
    """Filter to no matches, press i, assert no screen was pushed."""
```

Fill in the bodies using the `_visible_rows` / cursor idiom from
`tests/test_tui/test_asset_grid_filters.py`.

- [x] **Step 2: Repoint `action_info()`**

In every grid, delete the column branch from `action_info()`. It becomes:
resolve the row from `_visible_rows()` at `cursor_coordinate.row`, bail if out
of range, push the asset panel.

The panel body: slug, description (or the plain "no description" line), source,
ref, and per-scope state. Reuse `CellInfoScreen`'s chrome — it already closes on
`escape`/`q`/`i` — or add a sibling screen if the field set diverges enough to
make the reuse contorted. Do not keep two screens that differ only cosmetically.

- [x] **Step 3: Fix the Commands branch in `app.py`**

Replace the `cgrid.focus()` branch in `action_info_pass()` with
`cgrid.action_info()`. While there, collapse the six near-identical branches
into a lookup over `self._active_grid()` if it reads more clearly — but keep it
a pure refactor, tested by the same suite.

- [x] **Step 4: Green, then check nothing lost the State legend**

```bash
uv run pytest tests/test_tui/test_asset_info_key.py tests/test_tui -q
```

`tests/test_tui/test_skill_grid_column_info.py` and `test_cell_info.py` assert
the **old** `i` semantics. They must be rewritten to the new contract — header
click for column info, `i` for asset info — not deleted. Losing them loses the
regression net for the exact behaviour being changed.

- [x] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui tests/test_tui
git commit -m "feat(tui): i explains the asset, not the column"
```

## Task 5: Sweep and visual judgment

- [x] **Step 1: Full suite**

```bash
uv run pytest -q
```

- [x] **Step 2: Dead-affordance scan**

```bash
rg -n "_INFO_GLYPH" src/agent_toolkit_tui/widgets
```

Every glyphed `add_column` must have a matching registry entry (Task 1's test
proves it); every non-glyphed column must return `None` from
`_column_key_for_index`. Reconcile any mismatch.

```bash
rg -n "get_column_info|COLUMN_INFO" src/agent_toolkit_tui
```

No caller may still branch on a `None` return.

- [x] **Step 3: Manual visual check**

```bash
uv run agent-toolkit-tui
```

At **both** scopes, for **each** of the six asset types:

1. Click every header that shows `ⓘ`; a modal opens with a real title and body.
2. Click the `Source` header; nothing happens.
3. Read each Standard panel: does the harness list match the `(N)` in the
   header, and does the sentence explain what "covered" means *here*? This is
   the #478 R2a hand-off — `Standard (39)` beside `Standard (2)` must now be
   explicable.
4. Put the cursor in three different columns of the same row and press `i`
   three times: the same asset panel each time.
5. Find an asset with no description; confirm the plain "no description" line.
6. Filter to zero rows, press `i`: nothing happens.
7. Toggle scope on the Agents tab; re-open the Standard panel; the covered list
   changed (devin appears at project scope).

Capture one screenshot per asset type plus one of each Standard panel into
`assets/verification/issue-479/`, and write a one-line visual verdict in the PR
body per `~/.conventions/conventions/testing.md`.

- [x] **Step 4: Final commit**

```bash
git add src/agent_toolkit_tui tests/test_tui
git commit -m "test(tui): guard column-info coverage both ways"
```

## Risk controls

- Do not start before #478 lands (Task 0 Step 1 is a hard gate).
- Do not paraphrase spec R5. The sentences are grounded in named adapter lines;
  paraphrase drifts them into fiction.
- Do not re-generalise the instructions `🌐` wording. #388 corrected it
  deliberately; the skills phrasing is wrong for instructions.
- Do not let `get_column_info` fall back to `None` for an unknown pair. Silent
  fallback is how the current dead-`ⓘ` state arose.
- Do not delete `test_skill_grid_column_info.py` / `test_cell_info.py` — rewrite
  them to the new contract.
- Do not add a keyboard binding for column info; `i` is being reclaimed and a
  second binding re-creates the ambiguity this issue removes.
- If `DataTable.HeaderSelected`'s signature differs from the assumed one, adapt
  the tests to the installed Textual version — do not pin or upgrade Textual as
  part of this issue (that would be a new runtime dependency change).

## Self-review checklist

- Spec coverage: R1 Task 3; R2 Task 1 + Task 3 Step 3 + Task 5 Step 2; R3
  Task 4; R4 Task 2 Steps 1–4; R5 Task 2 Steps 3–4 (verbatim); R6 the
  path-source comments in Task 2 Step 3.
- Test-first: Tasks 1, 3, and 4 each land failing tests before implementation.
- Scope guard: no `src/agent_toolkit_cli/` file is modified; no column set
  changes (that is #478/#480).
- Placeholder scan: Task 4 Step 1's test bodies are the only stubs and are
  explicitly marked to be filled from a named existing idiom.
