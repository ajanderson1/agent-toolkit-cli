# Pi-grid scope toggle (#349) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The pi-extensions grid shows one scope column and follows the app-wide ctrl+g scope toggle; pending ops survive the toggle in all four grids via a single app-side save/restore site; summaries are scope-tagged.

**Architecture:** `PiGrid` adopts the same `set_scope` contract as the other grids (single scope column, clears pending — uniform widget semantics). Preservation is purely orchestration in `TUIApp.action_scope`: save the active grid's `pending_entries()`, refresh (which clears), then `restore_pending()`. A module-level `_scope_tag()` helper formats `(N global, M project)` attributions; `key[0]` is the scope in every grid's pending-key shape.

**Tech Stack:** Python 3.13, Textual (headless pilot tests), pytest + pytest-asyncio. Spec: `docs/superpowers/specs/2026-06-10-pi-grid-scope-toggle-design.md`.

**Conventions:** run tests with `uv run pytest`. Commits use conventional prefixes and carry a `Device: $(hostname -s)` trailer. The repo pre-commit schema-check hook is known-broken (aborts on a removed `--toolkit-repo` option); `--no-verify` is sanctioned for that failure only.

---

### Task 1: `_scope_tag` helper

**Files:**
- Modify: `src/agent_toolkit_tui/app.py` (module level, below the `_KIND_LABELS` dict)
- Test: `tests/test_tui/test_scope_tag.py` (create)

- [ ] **Step 1: Write the failing tests**

```python
"""Unit tests for app._scope_tag — scope attribution for pending summaries."""
from __future__ import annotations

from agent_toolkit_tui.app import _scope_tag


def test_scope_tag_empty():
    assert _scope_tag([]) == ""


def test_scope_tag_single_scope_global():
    keys = [("global", "a"), ("global", "claude", "b")]
    assert _scope_tag(keys) == ""


def test_scope_tag_single_scope_project():
    keys = [("project", "a")]
    assert _scope_tag(keys) == ""


def test_scope_tag_spanning_scopes():
    keys = [("global", "a"), ("project", "b"), ("global", "claude", "c")]
    assert _scope_tag(keys) == " (2 global, 1 project)"


def test_scope_tag_accepts_dict():
    pending = {("global", "a"): "link", ("project", "b"): "unlink"}
    assert _scope_tag(pending) == " (1 global, 1 project)"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tui/test_scope_tag.py -v`
Expected: FAIL — `ImportError: cannot import name '_scope_tag'`

- [ ] **Step 3: Implement**

In `src/agent_toolkit_tui/app.py`, add `Iterable` to the `typing` import line, then below `_KIND_LABELS`:

```python
def _scope_tag(keys: Iterable[tuple[str, ...]]) -> str:
    """Return ' (N global, M project)' when pending ops span both scopes.

    Every grid's pending key starts with the scope string — (scope, slug)
    for pi, (scope, harness, slug) for the rest — so key[0] is the scope in
    all four shapes. Iterating a pending dict yields its keys, so both dicts
    and key lists are accepted. Empty or single-scope input returns ''.
    """
    ks = list(keys)
    n_global = sum(1 for k in ks if k[0] == "global")
    n_project = len(ks) - n_global
    if n_global and n_project:
        return f" ({n_global} global, {n_project} project)"
    return ""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tui/test_scope_tag.py -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/app.py tests/test_tui/test_scope_tag.py
git commit --no-verify -m "feat(tui): _scope_tag helper for scope-spanning pending summaries (#349)

Device: $(hostname -s)"
```

---

### Task 2: PiGrid goes single-column with `set_scope`

**Files:**
- Modify: `src/agent_toolkit_tui/widgets/pi_grid.py`
- Test: `tests/test_tui/test_pi_grid.py` (amend existing + add)

- [ ] **Step 1: Write/adjust the widget tests**

In `tests/test_tui/test_pi_grid.py`, REPLACE `test_pi_grid_mounts_with_correct_columns` with:

```python
@pytest.mark.asyncio
async def test_pi_grid_mounts_with_single_scope_column():
    """Grid shows EXTENSION, Pi (<scope>), Origin, Source — 4 columns (#349)."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield PiGrid([_store_row("alpha")], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#pi-table", DataTable)
        labels = [str(c.label) for c in table.columns.values()]
        assert len(labels) == 4
        assert any("EXTENSION" in lbl for lbl in labels)
        assert any("Pi (global)" in lbl for lbl in labels)  # default scope
        assert not any("project" in lbl.lower() for lbl in labels)
        assert any("Origin" in lbl for lbl in labels)
        assert any("Source" in lbl for lbl in labels)


@pytest.mark.asyncio
async def test_pi_grid_set_scope_switches_column_and_clears_pending():
    """set_scope re-headers the scope column and clears pending (uniform
    widget contract — preservation is the app's job, #349)."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield PiGrid([_store_row("alpha")], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", PiGrid)
        table = app.query_one("#pi-table", DataTable)
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        assert g.pending_entries() == {("global", "alpha"): "link"}

        # Park the cursor on Origin (old project-column index) to prove the snap.
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=2)
        g.set_scope("project")
        g.set_rows([_store_row("alpha")])  # app always refreshes after set_scope
        await pilot.pause()
        labels = [str(c.label) for c in table.columns.values()]
        assert any("Pi (project)" in lbl for lbl in labels)
        assert g.pending_entries() == {}
        # Cursor snapped to the scope column — without the snap a cursor on the
        # removed project column lands on non-interactive Origin (#349 review).
        assert table.cursor_coordinate.column == 1
```

Then sweep the rest of the file: every existing test that toggles the
project scope via `column=2` must instead call `g.set_scope("project")`
(plus `g.set_rows(...)` re-seed) and toggle `column=1`. The existing
"toggles both scopes" test (queues global col 1 + project col 2 in one
sitting) loses its premise — rewrite it as two single-scope assertions
(queue in global → keys are global; set_scope("project") → cleared; queue
in project → keys are project). Apply-path tests that pre-seed
`grid._pending` with both-scope keys keep working unchanged (the dict shape
is untouched).

- [ ] **Step 2: Run to verify the new tests fail**

Run: `uv run pytest tests/test_tui/test_pi_grid.py -v`
Expected: new/amended tests FAIL (5 columns rendered, no `set_scope` attr)

- [ ] **Step 3: Implement in `pi_grid.py`**

Rewrite the module docstring opener:

```python
"""Interactive DataTable for the TUI's pi-extension tab.

Columns: EXTENSION | Pi (<active scope>) | Origin | Source.

One scope is visible at a time; the app's ctrl+g scope toggle flips it
app-wide (#349). set_scope() follows the same contract as the other grids
(sets scope, clears pending); pending preservation across the toggle is
orchestrated by the App, not the widget.
"""
```

(keep the existing `_render_*` warning and untracked-rows paragraphs.)

Replace the column-index block:

```python
# Column indices (single scope column; the active scope is self._scope).
_COL_EXTENSION = 0
_COL_SCOPE     = 1
_COL_ORIGIN    = 2
_COL_SOURCE    = 3
```

In `__init__`, after `self._rows = ...`:

```python
self._scope: Literal["global", "project"] = "global"
```

Add after `set_rows` (mirroring `instruction_grid.set_scope`, plus the
cursor snap — after a scope change the old column identities are
meaningless, and a cursor left on the removed project column would land on
non-interactive Origin):

```python
def set_scope(self, scope: Literal["global", "project"]) -> None:
    self._scope = scope
    self._pending.clear()
    # Snap the cursor to the single interactive scope column (same row).
    try:
        table = self.query_one("#pi-table", DataTable)
        table.cursor_coordinate = Coordinate(
            row=table.cursor_coordinate.row, column=_COL_SCOPE
        )
    except Exception:
        pass
```

`_rebuild` — replace the two scope `add_column` calls and the row-cells list:

```python
table.add_column(f"EXTENSION {_INFO_GLYPH}", width=24)
table.add_column(f"Pi ({self._scope}) {_INFO_GLYPH}", width=14)
table.add_column("Origin", width=12)
table.add_column("Source", width=30)

for row in self._rows:
    cells = [
        row.slug,
        self._cell_glyph(row=row, scope=self._scope),
        self._origin_glyph(row.origin),
        row.source,
    ]
    table.add_row(*cells, key=f"pi:{row.slug}")
```

(`max_col = _COL_SOURCE` still works — it is now 3. The #321 viewport
save/restore stays untouched.)

`_toggle_at` — replace the column→scope mapping:

```python
if coord.column != _COL_SCOPE:
    return
scope = self._scope
```

`action_info` — replace the `_COL_GLOBAL`/`_COL_PROJECT` branches with one:

```python
elif col == _COL_SCOPE:
    scope = self._scope
    title = f"{row.slug} · Pi ({scope})"
    body = self._info_body(row=row, scope=scope)
```

and re-key the origin branch to `_COL_ORIGIN` (body unchanged).

- [ ] **Step 4: Run the file's tests**

Run: `uv run pytest tests/test_tui/test_pi_grid.py tests/test_tui/test_pi_apply_roundtrip.py tests/test_tui/test_cell_info.py -v`
Expected: PASS (fix any remaining column-index assertions these files encode)

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/widgets/pi_grid.py tests/test_tui/
git commit --no-verify -m "feat(tui): pi grid renders a single scope-following column (#349)

Device: $(hostname -s)"
```

---

### Task 3: kind-aware `action_scope` + ScopeToggle on the pi pane

**Files:**
- Modify: `src/agent_toolkit_tui/app.py`
- Test: `tests/test_tui/test_scope_toggle.py` (add)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_tui/test_scope_toggle.py`:

```python
@pytest.mark.asyncio
async def test_ctrl_g_on_pi_pane_refreshes_pi_not_skill():
    """Regression (#349): the old action_scope else-branch refreshed the
    HIDDEN skill grid when the pi pane was active, clearing its pending."""
    from agent_toolkit_tui.widgets import PiGrid, SkillGrid

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        skill_grid = app.query_one("#skill-grid", SkillGrid)
        skill_grid._pending[("global", "claude", "alpha")] = "link"

        app.action_kind("pi-extension")
        await pilot.pause()
        await pilot.press("ctrl+g")
        await pilot.pause()

        assert skill_grid.pending_entries() == {
            ("global", "claude", "alpha"): "link"
        }, "hidden skill grid's pending must survive ctrl+g on the pi pane"


@pytest.mark.asyncio
async def test_pi_pane_shows_scope_toggle_and_header_tracks_scope():
    """The pi pane joins the scope toggle: widget visible, column header
    flips with ctrl+g (#349)."""
    from textual.widgets import DataTable

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_kind("pi-extension")
        await pilot.pause()
        assert app.query_one("#scope-toggle", ScopeToggle).display is True

        table = app.query_one("#pi-table", DataTable)
        labels = [str(c.label) for c in table.columns.values()]
        assert any("Pi (project)" in lbl for lbl in labels)  # app starts project

        await pilot.press("ctrl+g")
        await pilot.pause()
        labels = [str(c.label) for c in table.columns.values()]
        assert any("Pi (global)" in lbl for lbl in labels)
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_tui/test_scope_toggle.py -v`
Expected: both new tests FAIL (skill pending wiped; `display is False`; header static)

- [ ] **Step 3: Implement in `app.py`**

`_show_kind` pi branch: change `scope_toggle.display = False` to `True`.

`_refresh_pi_view` becomes scope-aware (rows still carry both scopes — the
inventory call is unchanged; only the widget's visible scope is set):

```python
def _refresh_pi_view(self) -> None:
    try:
        grid = self.query_one("#pi-grid", PiGrid)
    except NoMatches:
        return
    grid.set_scope(self._scope)  # type: ignore[arg-type]
    grid.set_rows(build_pi_rows(home=Path.home(), project=Path.cwd()))
```

Add two dispatch helpers next to `_scope_to_roots` (shape mirrors
`action_refresh`):

```python
def _active_grid(self) -> InstructionGrid | SkillGrid | PiGrid | AgentGrid | None:
    selector: str
    if self._active_kind == "instruction":
        selector = "#instruction-grid"
    elif self._active_kind == "skill":
        selector = "#skill-grid"
    elif self._active_kind == "pi-extension":
        selector = "#pi-grid"
    else:
        selector = "#agent-grid"
    try:
        return self.query_one(selector)  # type: ignore[return-value]
    except NoMatches:
        return None

def _refresh_active_view(self) -> None:
    if self._active_kind == "instruction":
        self._refresh_instruction_view()
    elif self._active_kind == "skill":
        self._refresh_skill_view()
    elif self._active_kind == "pi-extension":
        self._refresh_pi_view()
    else:
        self._refresh_agent_view()
```

`action_scope` — replace the per-kind if/elif/else refresh block with:

```python
self._refresh_active_view()
```

(Optionally refactor `action_refresh` and `action_kind`'s dispatch to call
`_refresh_active_view()` too — same shape, less duplication.)

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_tui/test_scope_toggle.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/app.py tests/test_tui/test_scope_toggle.py
git commit --no-verify -m "feat(tui): pi pane joins the app-wide scope toggle; kind-aware action_scope (#349)

Device: $(hostname -s)"
```

---

### Task 4: pending preserved across ctrl+g — single app-side site

**Files:**
- Modify: `src/agent_toolkit_tui/app.py` (`action_scope` only)
- Test: `tests/test_tui/test_scope_toggle.py` (add)

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.asyncio
async def test_pending_survives_scope_round_trip_pi(monkeypatch):
    """Queue pi ops → ctrl+g away and back → ops still queued AND still
    RENDERED (#349). The glyph assertion is load-bearing: restore_pending
    swallows rebuild failures in try/except, so dict equality alone cannot
    catch ops that were restored but never re-rendered."""
    from textual.coordinate import Coordinate
    from textual.widgets import DataTable
    from agent_toolkit_tui.pi_extension_state import PiCell, PiExtensionRow
    from agent_toolkit_tui.widgets import PiGrid

    def _row(slug):
        cell = PiCell(global_loaded=False, project_loaded=False, origin="store-owned")
        return PiExtensionRow(slug=slug, origin="store-owned",
                              source=f"git@github.com:x/{slug}",
                              global_cell=cell, project_cell=cell)

    monkeypatch.setattr(
        "agent_toolkit_tui.app.build_pi_rows",
        lambda **kwargs: [_row("alpha"), _row("beta")],
    )
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_kind("pi-extension")
        await pilot.pause()
        pi_grid = app.query_one("#pi-grid", PiGrid)
        pi_grid._pending[("project", "alpha")] = "link"
        pi_grid._pending[("global", "beta")] = "unlink"

        await pilot.press("ctrl+g")
        await pilot.pause()
        await pilot.press("ctrl+g")
        await pilot.pause()

        assert pi_grid.pending_entries() == {
            ("project", "alpha"): "link",
            ("global", "beta"): "unlink",
        }
        # Back in project scope: row 0 (alpha) must RENDER its pending '+'.
        table = app.query_one("#pi-table", DataTable)
        assert "+" in str(table.get_cell_at(Coordinate(0, 1)))


@pytest.mark.asyncio
async def test_pending_survives_scope_round_trip_skill():
    """Same single mechanism covers the harness-keyed grids (#349)."""
    from agent_toolkit_tui.widgets import SkillGrid

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()  # skill pane is active on load
        skill_grid = app.query_one("#skill-grid", SkillGrid)
        skill_grid._pending[("project", "claude", "alpha")] = "link"

        await pilot.press("ctrl+g")
        await pilot.pause()
        assert skill_grid.pending_entries() == {
            ("project", "claude", "alpha"): "link"
        }, "pending must survive the toggle away"


@pytest.mark.asyncio
async def test_ctrl_r_still_clears_pending():
    """Explicit refresh keeps its clearing semantics (#349 out-of-scope guard)."""
    from agent_toolkit_tui.widgets import SkillGrid

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        skill_grid = app.query_one("#skill-grid", SkillGrid)
        skill_grid._pending[("project", "claude", "alpha")] = "link"
        await pilot.press("ctrl+r")
        await pilot.pause()
        assert skill_grid.pending_entries() == {}
```

- [ ] **Step 2: Run to verify the round-trip tests fail**

Run: `uv run pytest tests/test_tui/test_scope_toggle.py -v`
Expected: both round-trip tests FAIL (pending empty after toggle); the
ctrl+r test already PASSES (guard for the semantics we must not change)

- [ ] **Step 3: Implement — wrap the refresh in `action_scope`**

```python
def action_scope(self, scope: str) -> None:
    if scope not in ("global", "project") or scope == self._scope:
        return
    self._scope = scope
    try:
        self.query_one("#scope-toggle", ScopeToggle).set_active(scope)
    except NoMatches:
        pass
    # Preserve pending across the toggle (#349): set_scope/set_rows clear
    # by contract, so save the active grid's queue and put it back. One
    # app-side site — no per-grid preservation logic.
    grid = self._active_grid()
    saved = grid.pending_entries() if grid is not None else {}
    self._refresh_active_view()
    if grid is not None and saved:
        grid.restore_pending(saved)  # type: ignore[arg-type]
    self._refresh_content_header()
    self._refresh_pending_label()
    self._refresh_status_bar()
```

(The `type: ignore` is the union-narrowing cost of the kind-generic helper;
each grid round-trips its own dict shape.)

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_tui/test_scope_toggle.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/app.py tests/test_tui/test_scope_toggle.py
git commit --no-verify -m "feat(tui): pending ops survive the scope toggle — single app-side save/restore (#349)

Device: $(hostname -s)"
```

---

### Task 5: scope-tagged summaries (footer, diff, apply, revert)

**Files:**
- Modify: `src/agent_toolkit_tui/app.py` (`_refresh_pending_label`, `action_diff`, all four `_apply_*_pending` footer lines, all four `action_revert` branches)
- Test: `tests/test_tui/test_scope_toggle.py` (add)

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_footer_pending_label_scope_tagged_when_spanning():
    from textual.widgets import Static
    from agent_toolkit_tui.widgets import PiGrid

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_kind("pi-extension")
        await pilot.pause()
        pi_grid = app.query_one("#pi-grid", PiGrid)
        pi_grid._pending[("project", "alpha")] = "link"
        pi_grid._pending[("global", "beta")] = "link"
        pi_grid._pending[("global", "gamma")] = "unlink"
        app._refresh_pending_label()
        label = str(app.query_one("#footer-pending", Static).renderable)
        assert "Pending: 3 (2 global, 1 project)" in label


@pytest.mark.asyncio
async def test_footer_pending_label_plain_when_single_scope():
    from textual.widgets import Static
    from agent_toolkit_tui.widgets import PiGrid

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        pi_grid = app.query_one("#pi-grid", PiGrid)
        pi_grid._pending[("global", "beta")] = "link"
        app._refresh_pending_label()
        label = str(app.query_one("#footer-pending", Static).renderable)
        assert "Pending: 1" in label
        assert "(" not in label.split("Pending: 1")[1][:2]


@pytest.mark.asyncio
async def test_diff_scope_tagged_when_spanning():
    """ctrl+d output attributes ops when they span scopes (#349)."""
    from textual.widgets import Static
    from agent_toolkit_tui.widgets import PiGrid

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_kind("pi-extension")
        await pilot.pause()
        pi_grid = app.query_one("#pi-grid", PiGrid)
        pi_grid._pending[("project", "alpha")] = "link"
        pi_grid._pending[("global", "beta")] = "unlink"
        app.action_diff()
        label = str(app.query_one("#footer-pending", Static).renderable)
        assert "diff: 1 would-link, 1 would-unlink (1 global, 1 project)" in label


@pytest.mark.asyncio
async def test_revert_clears_both_scopes_and_is_scope_tagged():
    """ctrl+z is the one destructive surface that can consume invisible
    other-scope ops — it clears the whole grid dict and says so (#349)."""
    from textual.widgets import Static
    from agent_toolkit_tui.widgets import PiGrid

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_kind("pi-extension")
        await pilot.pause()
        pi_grid = app.query_one("#pi-grid", PiGrid)
        pi_grid._pending[("project", "alpha")] = "link"
        pi_grid._pending[("global", "beta")] = "unlink"
        pi_grid._pending[("global", "gamma")] = "link"
        app.action_revert()
        await pilot.pause()
        assert pi_grid.pending_entries() == {}
        label = str(app.query_one("#footer-pending", Static).renderable)
        assert "reverted: 3 pending cleared (2 global, 1 project)" in label
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_tui/test_scope_toggle.py -k footer -v`
Expected: spanning test FAIL (plain `Pending: 3`)

- [ ] **Step 3: Implement**

`_refresh_pending_label` — collect keys instead of bare counts:

```python
def _refresh_pending_label(self) -> None:
    keys: list[tuple[str, ...]] = []
    for selector in ("#instruction-grid", "#skill-grid", "#pi-grid", "#agent-grid"):
        try:
            keys.extend(self.query_one(selector).pending_entries().keys())  # type: ignore[attr-defined]
        except Exception:
            pass
    try:
        self.query_one("#footer-pending", Static).update(
            f"Pending: {len(keys)}{_scope_tag(keys)}"
        )
    except Exception:
        pass
```

`action_diff` — keep the per-kind `pending = grid.pending_entries()`
retrieval (one variable instead of `all_ops`), then:

```python
n_link = sum(1 for op in pending.values() if op == "link")
n_unlink = sum(1 for op in pending.values() if op == "unlink")
self.query_one("#footer-pending", Static).update(
    f"diff: {n_link} would-link, {n_unlink} would-unlink{_scope_tag(pending)}"
)
```

Each of the four `_apply_*_pending`: right after `pending = grid.pending_entries()`
/ the early-return guard, capture `tag = _scope_tag(pending)`; append `{tag}`
to the two footer lines (`applied: {ok} ok, {failed} failed{tag}` and
`[red]apply failed[/] — {first}{extra}{tag}`).

Each of the four `action_revert` branches: capture the keys before clearing
and tag the message (mechanical copy per branch):

```python
keys = list(grid.pending_entries().keys())
n = len(keys)
grid.clear_pending()
self._refresh_pending_label()
self.query_one("#footer-pending", Static).update(
    f"reverted: {n} pending cleared{_scope_tag(keys)}"
)
```

- [ ] **Step 4: Run the TUI suite**

Run: `uv run pytest tests/test_tui -v`
Expected: PASS (existing apply tests assert substring matches like
`"applied:"` — single-scope pending produces an empty tag, so they hold)

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/app.py tests/test_tui/test_scope_toggle.py
git commit --no-verify -m "feat(tui): scope-tagged pending/diff/apply summaries (#349)

Device: $(hostname -s)"
```

---

### Task 6: pi apply-failure restore parity (latent bug)

**Files:**
- Modify: `src/agent_toolkit_tui/app.py` (`_apply_pi_pending`)
- Test: `tests/test_tui/test_pi_grid.py` (add)

- [ ] **Step 1: Write the failing test (proves the latent bug RED)**

Model it on the existing `test_apply_*` monkeypatch pattern in
`test_pi_grid.py` (same fakes/locks), with `pi_extension_ops.install`
raising `pi_extension_install.InstallError("boom")`:

```python
@pytest.mark.asyncio
async def test_apply_failure_preserves_pending(monkeypatch):
    """Latent bug (#349 spec §5): on failure _apply_pi_pending skipped
    clear_pending() but _refresh_pi_view()'s set_rows cleared anyway."""
    from agent_toolkit_tui.app import TUIApp
    from agent_toolkit_cli import pi_extension_install as _pi_install
    from agent_toolkit_cli import pi_extension_ops as _ops
    from agent_toolkit_cli import pi_extension_lock as _lock

    entry = MagicMock()
    fake_lock = MagicMock()
    fake_lock.skills = {"alpha": entry}
    monkeypatch.setattr(_lock, "read_lock", lambda path: fake_lock)
    monkeypatch.setattr(
        "agent_toolkit_cli.pi_extension_paths.library_lock_path",
        lambda env=None: Path("/fake/lock"),
    )

    def _boom(**kwargs: Any) -> None:
        raise _pi_install.InstallError("boom")

    monkeypatch.setattr(_ops, "install", _boom)
    monkeypatch.setattr(
        "agent_toolkit_tui.app.build_pi_rows",
        lambda **kwargs: [_store_row("alpha")],
    )

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_kind("pi-extension")
        await pilot.pause()
        grid = app.query_one("#pi-grid", PiGrid)
        grid._pending[("global", "alpha")] = "link"

        app.action_apply()
        await pilot.pause()

        assert grid.pending_entries() == {("global", "alpha"): "link"}, (
            "failed ops must stay queued for retry, like the other grids"
        )
```

(Adjust the `read_lock` patch target to match how the neighbouring apply
tests patch it — they patch the symbol the app imports.)

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_tui/test_pi_grid.py::test_apply_failure_preserves_pending -v`
Expected: FAIL — pending is `{}` after the failed apply

- [ ] **Step 3: Implement — adopt the other apply paths' wrap**

In `_apply_pi_pending`, replace:

```python
        if failed == 0:
            grid.clear_pending()
        self._refresh_pi_view()
```

with:

```python
        saved = grid.pending_entries() if failed else {}
        if failed == 0:
            grid.clear_pending()
        self._refresh_pi_view()
        if saved:
            grid.restore_pending(saved)
```

- [ ] **Step 4: Add the multi-scope apply-tag test (same fakes, success path)**

In the same file, duplicate the Step 1 scaffolding but with `_ops.install` /
`_ops.uninstall` monkeypatched to no-op successes, seed
`grid._pending = {("global", "alpha"): "link", ("project", "alpha"): "unlink"}`,
run `app.action_apply()`, and assert the footer reads
`applied: 2 ok, 0 failed (1 global, 1 project)`. This is the only test shape
that can catch a missing apply tag — single-scope pending yields an empty
tag, so the existing apply tests stay green even if the tag is never wired.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_tui/test_pi_grid.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_tui/app.py tests/test_tui/test_pi_grid.py
git commit --no-verify -m "fix(tui): pi apply failure no longer drops pending ops (#349)

Device: $(hostname -s)"
```

---

### Task 7: pi status bar shows the active scope

**Files:**
- Modify: `src/agent_toolkit_tui/app.py` (`_refresh_status_bar` pi branch)
- Test: `tests/test_tui/test_status_counters.py` (add — NO pi case exists in
  this file today; it is SkillGrid-only)

- [ ] **Step 1: Write a NEW failing test for the pi status bar**

Append to `tests/test_tui/test_status_counters.py`:

```python
@pytest.mark.asyncio
async def test_pi_status_bar_shows_active_scope_only(monkeypatch):
    """Pi status bar reports the ACTIVE scope's loaded count + pending (#349)
    instead of 'N global · M project'. New test — no prior pi case existed."""
    from textual.widgets import Static

    from agent_toolkit_tui.app import TUIApp
    from agent_toolkit_tui.pi_extension_state import PiCell, PiExtensionRow

    def _row(slug: str, *, g: bool, p: bool) -> PiExtensionRow:
        cell = PiCell(global_loaded=g, project_loaded=p, origin="store-owned")
        return PiExtensionRow(slug=slug, origin="store-owned",
                              source=f"git@github.com:x/{slug}",
                              global_cell=cell, project_cell=cell)

    monkeypatch.setattr(
        "agent_toolkit_tui.app.build_pi_rows",
        lambda **kwargs: [_row("a", g=True, p=False), _row("b", g=True, p=True)],
    )
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_kind("pi-extension")
        await pilot.pause()
        bar = str(app.query_one("#status-bar", Static).renderable)
        # project scope is active on load: exactly one project-loaded row.
        assert "1" in bar and "loaded" in bar and "pending" in bar
        assert "global" not in bar

        await pilot.press("ctrl+g")
        await pilot.pause()
        bar = str(app.query_one("#status-bar", Static).renderable)
        assert "2" in bar and "loaded" in bar
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_tui/test_status_counters.py -v`
Expected: FAIL — the bar still renders the old `2 global   1 project` form,
so `"global" not in bar` is False (and `"loaded"` never appears)

- [ ] **Step 3: Implement — replace the pi branch text block**

```python
        elif active == "pi-extension":
            loaded = 0
            try:
                grid_pi = self.query_one("#pi-grid", PiGrid)
            except (NoMatches, Exception):
                grid_pi = None
            if grid_pi is not None:
                scope = self._scope_to_roots()[0]
                for pi_row in grid_pi._rows:
                    if scope == "global":
                        if pi_row.global_cell.global_loaded:
                            loaded += 1
                    elif pi_row.project_cell.project_loaded:
                        loaded += 1
                pending = len(grid_pi.pending_entries())
            else:
                pending = 0
            text = (
                f"  [b green]{loaded}[/] loaded   "
                f"[b yellow]{pending}[/] pending"
            )
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_tui/test_status_counters.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/app.py tests/test_tui/test_status_counters.py
git commit --no-verify -m "feat(tui): pi status bar reports the active scope only (#349)

Device: $(hostname -s)"
```

---

### Task 8: full-suite sweep + docs

**Files:**
- Possibly modify: any test still encoding the 5-column pi layout; `docs/agent-toolkit/cli.md` if it describes the pi tab's two columns

- [ ] **Step 1: Sweep for stale layout references**

Run: `grep -rn "Pi (global)\|Pi (project)\|column=2" tests/ docs/ --include="*.py" --include="*.md" | grep -v superpowers`
Fix any hits that assume the side-by-side layout (tests → active-scope
assertions; docs → describe the single scope-following column + ctrl+g).

- [ ] **Step 2: Full test suite**

Run: `uv run pytest`
Expected: PASS. Known local-only failure `test_empty_machine_is_empty`
(global pi inventory ignores `home=`) is pre-existing and green on CI —
ignore it if it is the ONLY failure.

- [ ] **Step 3: Re-run the full suite after sweep fixes**

Run: `uv run pytest`
Expected: PASS (this repo's only verification gate is pytest — ruff/mypy are
NOT installed or configured here; do not add them as part of #349)

- [ ] **Step 4: Commit any sweep fixes**

```bash
git add -A tests docs/agent-toolkit
git commit --no-verify -m "test(tui): sweep remaining 5-column pi-grid assumptions (#349)

Device: $(hostname -s)"
```

---

## Verification checklist (maps to spec § Test surface)

| Spec item | Covered by |
|---|---|
| 1. 4 columns, header tracks scope | Task 2 step 1, Task 3 step 1 |
| 2. Round-trip preserved (pi + skill) | Task 4 step 1 |
| 3. Both-scope apply + tagged summary | Task 6 step 4 (multi-scope apply-tag test) + Task 5 (diff tag test) |
| 4. Apply-failure pending survives (RED first) | Task 6 |
| 5. ctrl+r clears | Task 4 step 1 |
| 6. Kind-aware action_scope regression | Task 3 step 1 |
| 7. Untracked non-interactive | existing `test_untracked_row_is_non_interactive` (column 1 unchanged) |
| 8. Info pane active scope | Task 2 (action_info re-key) + existing cell-info tests amended |
| 9. `_scope_tag` units | Task 1 |
| 10. Revert clears both scopes + tagged message | Task 5 step 1 (revert test) |
| 11. Falsifiable round-trip/tag assertions | Task 4 (glyph assertion), Task 5 (diff), Task 6 step 4 (apply tag) |
