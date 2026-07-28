# Tab-Switch Filter Focus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every asset-type switch in the TUI ends with the caret inside that tab's filter box, via one shared code path also used at startup.

**Architecture:** Hoist the `AssetType -> filter selector` map out of `action_focus_filter` into a module constant, add a private `_focus_filter(asset_type)` helper, and call it from `action_asset_type` (twice — see the ordering constraint below) and from `on_mount`.

**Ordering constraint — read before writing code:** Textual cannot focus a widget with `display = False`. Every non-active grid is hidden, so `_focus_filter` MUST run **after** `_show_asset_type()`. Focusing a hidden input fails *silently*, so a mis-ordered implementation looks like "the feature just doesn't work" with no error. This is why the helper has two call sites in `action_asset_type` rather than one hoisted call.

**Tech Stack:** Python 3.13-compatible, Textual `App`/`Input`, pytest + pytest-asyncio TUI pilot tests, existing `agent_toolkit_tui` patterns.

**Spec:** `docs/superpowers/specs/2026-07-28-477-tab-switch-filter-focus.md`

---

## Implementation Units

- Modify `src/agent_toolkit_tui/app.py`: module constant `_FILTER_SELECTORS`, helper `_focus_filter()`, call sites in `action_asset_type` and `on_mount`.
- Create `tests/test_tui/test_tab_switch_filter_focus.py`: pilot tests for all six tabs, both routes, re-select, and non-destructive properties.

## Task 1: Write the failing tests

**Files:**
- Create: `tests/test_tui/test_tab_switch_filter_focus.py`
- Read for idiom: `tests/test_tui/test_app_filter_focus.py`, `tests/test_tui/test_sidebar_highlight_sync.py`

- [ ] **Step 1: Create the test module**

Create `tests/test_tui/test_tab_switch_filter_focus.py`:

```python
from __future__ import annotations

import pytest

from agent_toolkit_tui.app import TUIApp

CASES = [
    ("instruction", "instruction-filter"),
    ("skill", "skill-filter"),
    ("command", "command-filter"),
    ("pi-extension", "pi-filter"),
    ("agent", "agent-filter"),
    ("mcp", "mcp-filter"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("asset_type", "filter_id"), CASES)
async def test_action_asset_type_focuses_that_tabs_filter(asset_type, filter_id):
    app = TUIApp()
    async with app.run_test() as pilot:
        app.action_asset_type(asset_type)
        await pilot.pause()
        assert app.focused is not None
        assert app.focused.id == filter_id


@pytest.mark.asyncio
async def test_startup_focuses_skill_filter():
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.focused is not None
        assert app.focused.id == "skill-filter"


@pytest.mark.asyncio
async def test_reselecting_active_tab_refocuses_filter():
    app = TUIApp()
    async with app.run_test() as pilot:
        app.action_asset_type("agent")
        await pilot.pause()
        app.query_one("#asset-types-list").focus()
        await pilot.pause()
        assert app.focused.id == "asset-types-list"

        app.action_asset_type("agent")  # already active
        await pilot.pause()
        assert app.focused is not None
        assert app.focused.id == "agent-filter"


@pytest.mark.asyncio
async def test_number_key_route_focuses_filter():
    app = TUIApp()
    async with app.run_test() as pilot:
        app.query_one("#asset-types-list").focus()
        await pilot.pause()
        await pilot.press("4")  # agent
        await pilot.pause()
        assert app.focused is not None
        assert app.focused.id == "agent-filter"


@pytest.mark.asyncio
async def test_refocus_does_not_disturb_filter_text_or_pending():
    """R5 is a property of the focus call, not of a tab switch.

    A real switch runs `_refresh_active_view()` -> `set_rows()`, which clears
    pending BY EXISTING CONTRACT (app.py). So assert on the already-active
    (early-return) path, where no refresh runs. Asserting across a real switch
    would encode a false expectation and fail for a reason unrelated to #477.
    """
    from textual.widgets import Input

    app = TUIApp()
    async with app.run_test() as pilot:
        app.action_asset_type("agent")
        await pilot.pause()
        app.query_one("#agent-filter", Input).value = "zzz"
        await pilot.pause()
        grid = app.query_one("#agent-grid")
        pending_before = dict(grid.pending_entries())
        scope_before = grid._scope

        app.query_one("#asset-types-list").focus()
        await pilot.pause()
        app.action_asset_type("agent")  # re-select: focus only, no refresh
        await pilot.pause()

        assert app.focused.id == "agent-filter"
        assert app.query_one("#agent-filter", Input).value == "zzz"
        assert dict(grid.pending_entries()) == pending_before
        assert grid._scope == scope_before


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("asset_type", "filter_id", "table_id"),
    [
        ("instruction", "instruction-filter", "instruction-table"),
        ("skill", "skill-filter", "skill-table"),
        ("command", "command-filter", "command-table"),
        ("pi-extension", "pi-filter", "pi-table"),
        ("agent", "agent-filter", "agent-table"),
        ("mcp", "mcp-filter", "mcp-table"),
    ],
)
async def test_escape_hatch_from_filter_to_table(asset_type, filter_id, table_id):
    """R5a: the caret now starts in an Input on every tab, so Down/Tab/Enter
    must all reach the table, and `/` must come back."""
    app = TUIApp()
    async with app.run_test() as pilot:
        app.action_asset_type(asset_type)
        await pilot.pause()
        for key in ("down", "tab", "enter"):
            app.action_focus_filter()
            await pilot.pause()
            assert app.focused.id == filter_id
            await pilot.press(key)
            await pilot.pause()
            assert app.focused is not None, f"{key} lost focus entirely"
            assert app.focused.id == table_id, f"{key} did not reach the table"
        await pilot.press("slash")
        await pilot.pause()
        assert app.focused.id == filter_id
```

- [ ] **Step 2: Run and confirm the expected failures**

```bash
uv run pytest tests/test_tui/test_tab_switch_filter_focus.py -q
```

Expected: the six parametrised cases FAIL for every type except `skill` (which
passes only by startup accident), plus `test_reselecting_active_tab_refocuses_filter`,
`test_number_key_route_focuses_filter`, and
`test_refocus_does_not_disturb_filter_text_or_pending` FAIL.
`test_startup_focuses_skill_filter` PASSES already.

`test_escape_hatch_from_filter_to_table` is a **characterisation** test of
existing behaviour and should PASS before any change. If it fails on some tab
today, that tab's `GridFilterInput` wiring is already broken — record it, fix
it here (it is a direct blocker for this issue's premise), and note it in the
PR body.

If a case ERRORs instead of failing (e.g. a grid has no filter with the
expected id), stop — that is a different defect and belongs in #478/#458, not
here. Record it and escalate.

## Task 2: Hoist the selector map

**Files:**
- Modify: `src/agent_toolkit_tui/app.py`

- [ ] **Step 1: Add the module constant**

Near the other module-level constants in `src/agent_toolkit_tui/app.py` (above
`class TUIApp`), add:

```python
# Single owner of the AssetType -> filter-input selector map. Consumed by
# `/` (action_focus_filter), by every asset-type switch (action_asset_type),
# and by startup (on_mount) — so the three cannot drift (#477).
_FILTER_SELECTORS: dict[AssetType, str] = {
    "instruction": "#instruction-filter",
    "skill": "#skill-filter",
    "command": "#command-filter",
    "pi-extension": "#pi-filter",
    "agent": "#agent-filter",
    "mcp": "#mcp-filter",
}
```

Confirm `AssetType` is already defined/imported above this point in the file; if
it is declared *below*, place the constant after its declaration instead.

- [ ] **Step 2: Add the helper and rewrite `action_focus_filter`**

Replace the body of `action_focus_filter` and add a private helper beside it:

```python
    def _focus_filter(self, asset_type: AssetType) -> None:
        """Focus `asset_type`'s filter input. No-op if it is not mounted.

        Non-destructive by contract (#477): it must not touch filter text,
        pending queues, scope, or cursor coordinate.
        """
        selector = _FILTER_SELECTORS.get(asset_type)
        if selector is None:
            return
        try:
            self.query_one(selector, Input).focus()
        except NoMatches:
            return

    def action_focus_filter(self) -> None:
        """`/` re-focuses the active asset pane's filter box."""
        self._focus_filter(self._active_asset_type)
```

`NoMatches` is already imported in `app.py` (used by `_show_asset_type`);
confirm with `rg -n "from textual.css.query import" src/agent_toolkit_tui/app.py`.

- [ ] **Step 3: Run the `/` regression**

```bash
uv run pytest tests/test_tui/test_app_filter_focus.py -q
```

Expected: PASS (behaviour is unchanged; only the map moved).

## Task 3: Focus on switch and at startup

**Files:**
- Modify: `src/agent_toolkit_tui/app.py`
- Test: `tests/test_tui/test_tab_switch_filter_focus.py`

- [ ] **Step 1: Call the helper from `action_asset_type` (two sites)**

Rewrite `action_asset_type`. The focus call appears **twice** — once on the
early-return branch (that grid is already displayed) and once as the final
statement of the switch branch (after `_show_asset_type` has made the grid
visible). Do **not** collapse these into a single hoisted call at the top: the
target grid is `display = False` at that point and Textual will silently refuse
to focus it.

```python
    def action_asset_type(self, asset_type: str) -> None:
        if asset_type not in ("instruction", "skill", "command", "pi-extension", "agent", "mcp"):
            return
        if asset_type == self._active_asset_type:
            # Re-selecting the tab you are already on still puts the caret in
            # its filter (#477 R3). Skip the expensive refresh; that is what
            # this branch has always existed to do.
            self._focus_filter(asset_type)  # type: ignore[arg-type]
            return
        self._active_asset_type = asset_type  # type: ignore[assignment]
        self._show_asset_type(asset_type)  # type: ignore[arg-type]
        self._refresh_active_view()
        self._refresh_content_header()
        self._refresh_pending_label()
        self._refresh_status_bar()
        # LAST, and after _show_asset_type: a hidden Input cannot take focus,
        # and the refusal is silent (#477 R2 ordering constraint).
        self._focus_filter(asset_type)  # type: ignore[arg-type]
```

- [ ] **Step 2: Route startup through the same helper**

In `on_mount`, replace the hardcoded block:

```python
        # Focus the filter box on open (#249).
        try:
            self.query_one("#skill-filter", Input).focus()
        except Exception:
            pass
```

with:

```python
        # Focus the filter box on open (#249) via the same path as every
        # asset-type switch (#477), so startup and switch cannot drift.
        self._focus_filter(self._active_asset_type)
```

Leave the rest of `on_mount` (theme, `_show_asset_type("skill")`, the four
refresh calls) unchanged, and keep `_focus_filter` as the **last** statement so
no later refresh steals focus.

- [ ] **Step 3: Run the new suite**

```bash
uv run pytest tests/test_tui/test_tab_switch_filter_focus.py -q
```

Expected: PASS, all cases.

If `test_number_key_route_focuses_filter` still fails, the digit is being
consumed before `SidebarOptionList` sees it — assert the highlight moved
(`asset-types-list.highlighted`) to distinguish "binding never fired" from
"fired but focus not applied", and fix the focus path only.

If a parametrised case still fails with `app.focused` unchanged, the most
likely cause is the ordering constraint: confirm `_focus_filter` runs after
`_show_asset_type`, and temporarily assert
`app.query_one(selector).display is True` immediately before the focus call to
prove visibility.

- [ ] **Step 4: Commit**

```bash
git add src/agent_toolkit_tui/app.py tests/test_tui/test_tab_switch_filter_focus.py
git commit -m "fix(tui): focus the filter box on asset-type switch"
```

Include the `Device:` trailer required by `~/.conventions/conventions/git.md`.

## Task 4: Regression sweep and manual smoke

**Files:**
- Review: `src/agent_toolkit_tui/app.py`
- Review: `tests/test_tui/`

- [ ] **Step 1: Full TUI suite**

```bash
uv run pytest tests/test_tui -q
```

Expected: PASS. Pay attention to `test_sidebar_highlight_sync.py`,
`test_view_pane_preservation.py`, and `test_double_ctrl_c_quit.py` — all three
make focus-sensitive assertions.

- [ ] **Step 2: Full suite**

```bash
uv run pytest -q
```

Expected: PASS.

- [ ] **Step 3: Stale-copy scan**

```bash
rg -n "skill-filter|instruction-filter|command-filter|pi-filter|agent-filter|mcp-filter" src/agent_toolkit_tui
```

Expected: the six ids appear in `_FILTER_SELECTORS` and in each grid's
`compose()`/handlers only. No second selector map in `app.py`.

- [ ] **Step 4: Manual smoke**

```bash
uv run agent-toolkit-tui
```

Checks:

1. On open, type immediately — the Skills list narrows (no `/` needed).
2. Click each of the six sidebar tabs; after each, type a character and confirm
   that tab's list narrows.
3. Press `1`–`6`; same result.
4. Click the tab you are already on; caret returns to that filter.
5. Press `Down` from a filter; focus lands in the table. Press `/`; focus
   returns to the filter.
6. Click the tab you are already on after queuing a toggle with `space`; the
   pending count in the footer is unchanged and the filter text is preserved.
   (Switching *away* and back clears pending by existing contract — that is not
   a regression from this change.)
7. Confirm the accepted trade-off is real and tolerable: press `1`, then `2`.
   The `2` types into the filter rather than switching. Press `ctrl+w`, then
   `2` — it switches. Note both in the PR body.

Capture the terminal evidence (screenshot or asciinema) into
`assets/verification/issue-477/` and record a one-line visual verdict in the PR
body, per `~/.conventions/conventions/testing.md`.

- [ ] **Step 5: Final commit if the sweep changed anything**

```bash
git add src/agent_toolkit_tui tests/test_tui
git commit -m "test(tui): cover tab-switch filter focus"
```

## Risk controls

- Do not call `_refresh_active_view()` on the already-active path — it is the
  expensive branch the early return exists to skip.
- Do not hoist `_focus_filter` above `_show_asset_type`. It fails silently.
- Do not "fix" pending being cleared across a tab switch. That is existing
  `set_rows()` contract and belongs to a separate issue.
- Do not bind `1`–`6` at App level to preserve the digit chain — it would break
  digits inside every filter box (spec, § Accepted trade-off).
- Do not replace `NoMatches` with a bare `except Exception`; a broad catch here
  hides real mount errors (fail loudly).
- Do not touch `set_filter`, `clear_pending`, `restore_pending`, or scope state.
- Do not change grid `compose()` order — the filter must stay above the table.
- If focusing an `Input` is found to break a grid's `space`/`i`/`a` binding in a
  way that startup does not already exhibit, stop and escalate rather than
  special-casing one grid.

## Self-review checklist

- Spec coverage: R1 Task 2 Step 1; R2 (incl. ordering constraint) Task 3
  Step 1; R3 Task 3 Step 1 + re-select test; R4 Task 3 Step 2; R5
  `test_refocus_does_not_disturb_filter_text_or_pending`; R5a
  `test_escape_hatch_from_filter_to_table`; R6 `NoMatches` in Task 2 Step 2;
  R7 the whole of Task 1.
- Test-first: Task 1 lands failing tests before any `app.py` edit.
- Placeholder scan: no `TODO(...)` or `<...>` left in any step.
- Scope guard: no change to `/`, `ctrl+w`, filter semantics, or sidebar
  highlight sync.
