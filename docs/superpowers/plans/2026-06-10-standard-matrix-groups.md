# Standard / Non-standard Matrix Groups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the skills and instructions TUI grids into Standard / Non-standard column groups: group-tagged two-line headers, an exhaustive standard-coverage ⓘ panel, and a collapsed-by-default expandable long-tail column set (session-only state, per kind).

**Architecture:** A new pure composition module derives per-kind column sets from the catalog/SSOT at rebuild time (no hardcoded tuples). Grids gain a `_longtail_expanded` boolean and a pseudo-column (`… +N ⓘ` / `… collapse`); expand/collapse is just another `_rebuild()` using the existing #321 scroll-preservation idiom. Group tags ride inside the native DataTable header as two-line Rich `Text` labels (`header_height=2`) — no spanning widget, nothing to sync. Agents and pi-extensions grids are untouched and regression-guarded.

**Tech Stack:** Python 3.12, Textual ≥0.79 (DataTable), Rich Text, pytest + Textual headless pilot. Run tests with `uv run pytest`.

**Preconditions / worker notes:**
- **Blocked by #350.** This plan is written against the POST-#350 codebase: tokens/identifiers are `standard`, `is_standard`, `get_standard_agents()`, `_standard_info`, registry key `"standard"`, `INTERACTIVE_AGENTS = ("standard", "claude-code", "pi")`. If any old name is still present, stop and rebase onto the #350 merge first.
- Spec: `docs/superpowers/specs/2026-06-10-standard-matrix-groups-design.md`.
- The pre-commit schema-check hook is known-broken; `--no-verify` is sanctioned when it is the only failure. `test_empty_machine_is_empty` fails locally only (green on CI). Every commit carries a `Device: <hostname -s>` trailer.
- Headless Textual scroll/expand tests need the container to actually overflow (#321 lesson): build fixtures with enough rows/columns.

---

### Task 1: Composition module (pure, TDD)

**Files:**
- Create: `src/agent_toolkit_tui/composition.py`
- Test: `tests/test_tui/test_composition.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Column composition for the Standard / Non-standard matrix groups (#351)."""
from agent_toolkit_cli.skill_agents import AGENTS
from agent_toolkit_tui.composition import (
    BIG_FIVE,
    LONGTAIL_KEY,
    instructions_longtail,
    instructions_nonstandard_big_five,
    skills_longtail,
    skills_nonstandard_big_five,
)


def test_big_five_members():
    assert BIG_FIVE == ("claude-code", "pi", "codex", "gemini-cli", "opencode")


def test_skills_nonstandard_big_five_today():
    # codex / gemini-cli / opencode read .agents/skills → standard for skills.
    assert skills_nonstandard_big_five() == ("claude-code", "pi")


def test_skills_longtail_properties():
    tail = skills_longtail()
    assert tail == tuple(sorted(tail))                      # deterministic order
    assert set(tail).isdisjoint(BIG_FIVE)                   # big five never in tail
    assert set(tail).isdisjoint({"standard", "standard-skill", "standard-agent"})
    for name in tail:
        assert not AGENTS[name].is_standard                 # tail is non-compliant only
    assert len(tail) > 10                                   # sanity: tail is the long tail


def test_skills_sets_partition_catalog():
    standard = {n for n, c in AGENTS.items() if c.is_standard and c.show_in_standard_list}
    cols = set(skills_nonstandard_big_five()) | set(skills_longtail())
    assert cols.isdisjoint(standard)


def test_instructions_composition_today():
    assert instructions_nonstandard_big_five() == ("claude-code", "gemini-cli")
    tail = instructions_longtail()
    assert tail == tuple(sorted(tail))
    assert set(tail) == {"augment", "codebuddy", "iflow-cli", "replit", "tabnine-cli"}


def test_longtail_key_is_not_a_catalog_name():
    assert LONGTAIL_KEY not in AGENTS
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tui/test_composition.py -q`
Expected: FAIL — `ModuleNotFoundError: agent_toolkit_tui.composition`.

- [ ] **Step 3: Implement**

```python
"""Per-kind column composition for the Standard / Non-standard groups (#351).

Derived from the catalog/SSOT at call time — never hardcoded — so adding a
compliant harness upstream changes the grids without touching grid code.
Kinds without a standard concept (agents, pi-extensions) have no entry here.
"""
from __future__ import annotations

from agent_toolkit_cli.instructions_adapters import SUPPORTED_HARNESSES
from agent_toolkit_cli.skill_agents import AGENTS

# Pseudo-column key for the collapsed long-tail set; never a catalog name.
LONGTAIL_KEY = "longtail"

BIG_FIVE: tuple[str, ...] = ("claude-code", "pi", "codex", "gemini-cli", "opencode")

_SYNTHETIC = frozenset({"standard", "standard-skill", "standard-agent"})


def skills_nonstandard_big_five() -> tuple[str, ...]:
    return tuple(n for n in BIG_FIVE if not AGENTS[n].is_standard)


def skills_longtail() -> tuple[str, ...]:
    return tuple(sorted(
        n for n, c in AGENTS.items()
        if not c.is_standard and n not in BIG_FIVE and n not in _SYNTHETIC
    ))


def instructions_nonstandard_big_five() -> tuple[str, ...]:
    return tuple(h for h in BIG_FIVE if h in SUPPORTED_HARNESSES)


def instructions_longtail() -> tuple[str, ...]:
    return tuple(sorted(
        h for h in SUPPORTED_HARNESSES if h not in BIG_FIVE
    ))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tui/test_composition.py -q`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/composition.py tests/test_tui/test_composition.py
git commit -m "feat(tui): per-kind column composition for standard/non-standard groups (#351)

Device: $(hostname -s)"
```

---

### Task 2: skill_state cells for the full composition

The loader currently probes cells only for the pinned 3-agent tuple
(`skill_state.py:194-203`); expanded long-tail columns need cell data too.

**Files:**
- Modify: `src/agent_toolkit_tui/skill_state.py:29-34,194-203`
- Test: `tests/test_tui/test_skill_state.py` (extend the existing module)

- [ ] **Step 1: Write the failing test** (append to the existing skill_state tests,
  reusing that module's fixture pattern for a fake home/project)

```python
def test_rows_carry_cells_for_longtail_agents(tmp_path, ...existing fixture args...):
    from agent_toolkit_tui.composition import skills_longtail
    rows = load_rows(...)  # same call shape as the existing tests in this module
    some_tail = skills_longtail()[0]
    assert (some_tail, "global") in rows[0].cells or (some_tail, "project") in rows[0].cells
```

(Adapt the fixture plumbing to whatever the module's existing tests use — the
assertion is the contract: every loaded row has cells for long-tail agents.)

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_tui/test_skill_state.py -q -k longtail`
Expected: FAIL — KeyError/assert (cells only exist for the pinned 3).

- [ ] **Step 3: Implement** — replace the pinned tuple as the cell-probe source.
  `skill_state.py:29-34` becomes:

```python
from agent_toolkit_tui.composition import skills_longtail, skills_nonstandard_big_five

# Column composition is derived per rebuild (#351). ALL_CELL_AGENTS is the
# probe set for the state loader: standard bundle + every potential column,
# so expanding the long tail never needs a reload.
def all_cell_agents() -> tuple[str, ...]:
    return ("standard",) + skills_nonstandard_big_five() + skills_longtail()
```

and the two loops at (old) lines 194-203 iterate `all_cell_agents()` instead of
`INTERACTIVE_AGENTS`. Keep `INTERACTIVE_AGENTS` temporarily as
`("standard",) + skills_nonstandard_big_five()` if other modules still import
it; Task 3 removes the remaining uses.

- [ ] **Step 4: Run the module's tests**

Run: `uv run pytest tests/test_tui/test_skill_state.py -q`
Expected: PASS. (A per-skill probe is a few `Path` stats × ~42 agents — if the
suite shows a noticeable slowdown, note it in the PR; do not optimize ahead of
evidence.)

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/skill_state.py tests/test_tui/test_skill_state.py
git commit -m "feat(tui): probe skill cells for the full column composition (#351)

Device: $(hostname -s)"
```

---

### Task 3: Skill grid — grouped header, dynamic columns, long-tail pseudo-column

**Files:**
- Modify: `src/agent_toolkit_tui/widgets/skill_grid.py` (`_rebuild` ~:543-589,
  `_column_index`/`_agent_for_column`/`_column_key_for_index` :514-541,
  `_toggle_at` :487-512, `action_open_column_info` :454-468)
- Test: `tests/test_tui/test_skill_grid_groups.py` (new)

- [ ] **Step 1: Spike test — two-line header renders** (write first; it pins the
  mechanism the whole task depends on)

```python
import pytest
from rich.text import Text
from textual.widgets import DataTable


@pytest.mark.asyncio
async def test_datatable_two_line_header_renders():
    from textual.app import App, ComposeResult

    class Probe(App):
        def compose(self) -> ComposeResult:
            yield DataTable(id="t")

        def on_mount(self) -> None:
            t = self.query_one("#t", DataTable)
            t.header_height = 2
            label = Text()
            label.append("NON-STD\n", style="dim")
            label.append("claude-code ⓘ")
            t.add_column(label, width=14)
            t.add_row("x")

    app = Probe()
    async with app.run_test() as pilot:
        t = app.query_one("#t", DataTable)
        assert t.header_height == 2
        # Both lines present in the rendered header region.
        text = "\n".join(str(strip) for strip in [t.render_line(0), t.render_line(1)])
        assert "NON-STD" in text and "claude-code" in text
```

Run: `uv run pytest tests/test_tui/test_skill_grid_groups.py -q -k two_line`
Expected: PASS. **If this FAILS** (Textual version quirk), fall back to
single-line labels with a bracketed group prefix (`[STD] standard ⓘ`,
`[NON] claude-code ⓘ`) and adapt the header assertions in the later steps —
record the fallback in the PR description. Do not build a spanning widget.

- [ ] **Step 2: Write the failing behavior tests** (same file; drive the real
  `SkillGrid` through the app harness the existing `test_skill_grid_*` tests use —
  copy their fixture/app plumbing)

```python
# Assertions (adapt plumbing from tests/test_tui/test_skill_grid_column_info.py):

async def test_default_columns_collapsed(...):
    labels = [str(c.label) for c in table.columns.values()]
    # slug + standard + claude-code + pi + pseudo + state + source
    assert any("standard" in l for l in labels)
    assert any("… +" in l for l in labels)
    from agent_toolkit_tui.composition import skills_longtail
    assert not any("codex" in l for l in labels)          # standard → no own column
    assert not any(skills_longtail()[0] in l for l in labels)  # tail collapsed
    assert sum("STANDARD" in l for l in labels) == 1
    assert sum("NON-STD" in l for l in labels) == 2 + 1   # big-five-nonstd + pseudo
    assert not any("STANDARD" in l or "NON-STD" in l
                   for l in labels if "State" in l or "Source" in l)

async def test_expand_collapse_in_place_preserves_scroll(...):
    # Move cursor onto the pseudo-column, trigger the toggle binding,
    # assert long-tail columns appear, pseudo label flips to "… collapse",
    # scroll_y unchanged (fixture must overflow the container — #321 lesson),
    # then toggle again → columns gone, "… +N ⓘ" back.

async def test_longtail_toggle_roundtrip(...):
    # Expand, move to a long-tail agent column, press the toggle key,
    # assert the cell shows a pending glyph and _pending got
    # (scope, <tail-agent>, slug) — identical semantics to a big-five column.
```

Run: `uv run pytest tests/test_tui/test_skill_grid_groups.py -q`
Expected: FAIL (no pseudo-column, no group tags yet).

- [ ] **Step 3: Implement in `skill_grid.py`**

(a) Composition + state:

```python
from agent_toolkit_tui.composition import (
    LONGTAIL_KEY, skills_longtail, skills_nonstandard_big_five,
)

# in __init__:
        self._longtail_expanded: bool = False  # session-only, per grid (#351)

    def _active_agents(self) -> tuple[str, ...]:
        cols = ("standard",) + skills_nonstandard_big_five()
        if self._longtail_expanded:
            cols += skills_longtail()
        return cols
```

(b) `_rebuild` — replace the column block (old :557-569). Layout becomes
`[0]=slug, [1..N]=_active_agents(), [N+1]=longtail pseudo, [N+2]=state, [N+3]=source`:

```python
        table.header_height = 2
        table.add_column(f"SKILL {_INFO_GLYPH}", width=20)
        active = self._active_agents()
        for agent in active:
            tag = "STANDARD" if agent == "standard" else "NON-STD"
            base = "Standard" if agent == "standard" else AGENTS[agent].display_name
            table.add_column(_grouped_label(tag, f"{base} {_INFO_GLYPH}"), width=14)
        tail_n = len(skills_longtail())
        pseudo = "… collapse" if self._longtail_expanded else f"… +{tail_n} {_INFO_GLYPH}"
        table.add_column(_grouped_label("NON-STD", pseudo), width=14)
        table.add_column(f"State {_INFO_GLYPH}", width=10)
        table.add_column("Source", width=30)
```

with the shared helper added to `composition.py` (both grids import it; add
`from rich.text import Text` there):

```python
def grouped_label(tag: str, name: str) -> Text:
    """Two-line DataTable header label: dim group tag over the column name."""
    label = Text()
    label.append(f"{tag}\n", style="dim")
    label.append(name)
    return label
```

(References to `_grouped_label(...)` in the snippets above and in Task 5 mean
this shared `grouped_label`.)

Row cells: iterate `active` for glyphs, then a dim `"·"` placeholder cell for
the pseudo-column, then state/source. Update the `max_col` math (old :581) to
`3 + len(active)`.

(c) Index math — all three helpers go instance-composition-based:

```python
    def _column_index(self, agent_name: str) -> int:
        try:
            return 1 + self._active_agents().index(agent_name)
        except ValueError:
            return -1

    def _agent_for_column(self, col: int) -> str | None:
        active = self._active_agents()
        if 1 <= col <= len(active):
            return active[col - 1]
        return None

    def _column_key_for_index(self, col: int) -> str | None:
        active = self._active_agents()
        n = len(active)
        if 1 <= col <= n:
            return active[col - 1]
        if col == n + 1:
            return LONGTAIL_KEY
        if col == n + 2:
            return "state"
        return None
```

(d) Toggle path — in `_toggle_at` (old :487), before the agent lookup:

```python
        if coord.column == 1 + len(self._active_agents()):
            self._longtail_expanded = not self._longtail_expanded
            self._rebuild(table)
            return
```

(e) `_context_for` (old :470-485): the standard-key branch keeps its behavior;
add a `LONGTAIL_KEY` branch returning
`{"names": skills_longtail(), "expanded": self._longtail_expanded}`.

- [ ] **Step 4: Run the new tests + the full TUI suite**

Run: `uv run pytest tests/test_tui/ -q`
Expected: PASS. Pre-existing skill-grid tests asserting old column counts/labels
will fail — update them to the new layout (they are layout assertions, not
behavior regressions; list each updated file in the commit body).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/widgets/skill_grid.py tests/test_tui/
git commit -m "feat(tui): standard/non-standard groups + long-tail expand on the skill grid (#351)

Device: $(hostname -s)"
```

---

### Task 4: Info panels — exhaustive standard coverage + long-tail listing

**Files:**
- Modify: `src/agent_toolkit_tui/column_info.py`
- Test: `tests/test_tui/test_column_info.py` (extend)

- [ ] **Step 1: Write the failing tests**

```python
def test_standard_info_is_exhaustive_with_count():
    from agent_toolkit_cli.skill_agents import get_standard_agents
    info = get_column_info("standard")
    names = get_standard_agents()
    assert f"({len(names)})" in " ".join(info.lines)
    for name in names:
        assert any(name in line for line in info.lines)


def test_longtail_info_lists_collapsed_names():
    from agent_toolkit_tui.composition import LONGTAIL_KEY, skills_longtail
    info = get_column_info(LONGTAIL_KEY, context={"names": skills_longtail(), "expanded": False})
    assert info is not None
    for name in skills_longtail()[:3]:
        assert any(name in line for line in info.lines)
    assert "expand" in info.title.lower() or any("expand" in l for l in info.lines)
```

Run: `uv run pytest tests/test_tui/test_column_info.py -q`
Expected: FAIL.

- [ ] **Step 2: Implement** — in `_standard_info` (post-#350 name of
  `_universal_info`, :26-52), change the description head to:

```python
    description = [
        f"Covered by the standard convention for skills ({len(harness_names)}):",
        "",
    ]
```

(keep the existing bullets + contextual 🌐 block), and register the long-tail
factory:

```python
def _longtail_info(context: dict | None = None) -> ColumnInfo:
    names = tuple((context or {}).get("names", ()))
    expanded = bool((context or {}).get("expanded", False))
    head = "Collapsed non-standard harnesses" if not expanded else "Expanded long tail"
    return ColumnInfo(
        title=f"{head} ({len(names)})",
        lines=[
            "Press enter on this column to expand/collapse in place.",
            "",
            *[f"  • {n}" for n in names],
        ],
    )


COLUMN_INFO: dict[str, Callable[..., ColumnInfo]] = {
    "standard": _standard_info,
    "state": _state_info,
    "longtail": _longtail_info,
}
```

(Import nothing from `composition` here — names arrive via context, keeping
this module kind-agnostic.)

- [ ] **Step 3: Run + commit**

Run: `uv run pytest tests/test_tui/test_column_info.py -q` → PASS.

```bash
git add src/agent_toolkit_tui/column_info.py tests/test_tui/test_column_info.py
git commit -m "feat(tui): exhaustive standard-coverage panel + long-tail info panel (#351)

Device: $(hostname -s)"
```

---

### Task 5: Instruction grid — same treatment

**Files:**
- Modify: `src/agent_toolkit_tui/widgets/instruction_grid.py` (`_rebuild`
  ~:326-370, `_HARNESS_COL_OFFSET` :38-43, index helpers, activate path)
- Modify: `src/agent_toolkit_tui/instruction_state.py:31` (`INTERACTIVE_HARNESSES`)
- Test: `tests/test_tui/test_instruction_grid_groups.py` (new)

- [ ] **Step 1: Write the failing tests** (mirror Task 3 Step 2's assertions with
  the instructions composition: standard read-only column tagged STANDARD;
  claude-code + gemini-cli + `… +5 ⓘ` tagged NON-STD; expand shows augment,
  codebuddy, iflow-cli, replit, tabnine-cli as installable columns; collapse
  restores; per-grid state independent of the skill grid's)

```python
async def test_collapse_state_is_per_kind(...):
    # Expand the instruction grid's tail; switch to the skills tab;
    # assert the skill grid is still collapsed.
```

Run: `uv run pytest tests/test_tui/test_instruction_grid_groups.py -q`
Expected: FAIL.

- [ ] **Step 2: Implement** — replace `INTERACTIVE_HARNESSES` consumption with:

```python
from agent_toolkit_tui.composition import (
    LONGTAIL_KEY, instructions_longtail, instructions_nonstandard_big_five,
)

# instruction_state.py:31 — derive instead of pinning:
INTERACTIVE_HARNESSES: tuple[str, ...] = instructions_nonstandard_big_five()
```

and in `instruction_grid.py` mirror Task 3 exactly, with the offsets shifted by
the read-only standard column (the existing `_HARNESS_COL_OFFSET = 2` becomes
the base; pseudo-column sits after the active harness columns). The standard
column's two-line label: `_grouped_label("STANDARD", f"standard {_INFO_GLYPH}")`.
The instruction state loader must probe pointer cells for
`instructions_nonstandard_big_five() + instructions_longtail()` (mirror Task 2's
change in `instruction_state.py`).

The instructions standard ⓘ panel needs the native-harness list: extract the
matrix-row parser from `commands/instructions/list_cmd.py` (the regex +
row-builder around :25-65) into a reusable helper
`instructions_matrix_rows()` in `src/agent_toolkit_cli/instructions_matrix.py`
(moved, not duplicated — list_cmd imports it back), and pass
`[r["harness"] for r in rows if r["verdict"] == "native"]` to the panel via the
grid's `_context_for`.

- [ ] **Step 3: Run + commit**

Run: `uv run pytest tests/test_tui/ tests/test_cli/test_instructions*.py -q` → PASS
(update pre-existing instruction-grid layout assertions as in Task 3 Step 4).

```bash
git add src/agent_toolkit_tui/ src/agent_toolkit_cli/instructions_matrix.py src/agent_toolkit_cli/commands/instructions/list_cmd.py tests/
git commit -m "feat(tui): standard/non-standard groups on the instruction grid (#351)

Device: $(hostname -s)"
```

---

### Task 6: Regression guards + final verification

**Files:**
- Test: `tests/test_tui/test_grid_group_regressions.py` (new)

- [ ] **Step 1: Write the guards**

```python
"""#351 must not touch the agents and pi-extensions grids."""


async def test_agent_grid_columns_unchanged(...):
    labels = [str(c.label) for c in agent_table.columns.values()]
    assert not any("STANDARD" in l or "NON-STD" in l or "… +" in l for l in labels)


async def test_pi_grid_columns_unchanged(...):
    labels = [str(c.label) for c in pi_table.columns.values()]
    assert not any("STANDARD" in l or "NON-STD" in l or "… +" in l for l in labels)
```

- [ ] **Step 2: Full suite + smoke**

Run: `uv run pytest -q`
Expected: PASS (modulo the known-local `test_empty_machine_is_empty`).

Smoke: `uv run agent-toolkit-cli tui` — eyeball: skills tab collapsed by
default, expand/collapse round-trip, standard ⓘ shows the full list with count,
instructions tab independent, agents/pi tabs unchanged.

- [ ] **Step 3: Commit + PR**

```bash
git add tests/test_tui/test_grid_group_regressions.py
git commit -m "test(tui): regression guards — agents/pi grids untouched by matrix groups (#351)

Device: $(hostname -s)"
```

The runner opens a PR per its own flow, conventional title
`feat(tui): standard/non-standard matrix column groups` so release-please cuts
a minor.
