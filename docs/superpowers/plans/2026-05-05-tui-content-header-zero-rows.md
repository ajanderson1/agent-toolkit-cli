# TUI content-header zero-rows fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the V1 Navigator content-header (kind · count · scope chips) actually visible above the AssetGrid by fixing the CSS so the content area isn't clipped to zero rows.

**Architecture:** One CSS rule change in `src/agent_toolkit_tui/css/app.tcss` (`#content-header { height: 2; padding-bottom: 1; border-bottom: tall; }` → `height: auto`). One TDD regression test in `tests/test_tui/test_app.py` asserting `query_one("#content-header").size.height >= 1` after mount, so the bug class can never silently come back.

**Tech Stack:** Python 3.13, Textual 8.2.5, pytest-asyncio, uv, lefthook (pre-commit runs full pytest).

---

## Task 1: Regression test + CSS fix

**Files:**
- Test: `tests/test_tui/test_app.py` (append after line 580 — right below the existing `test_breadcrumb_reflects_current_kind_and_scope`)
- Modify: `src/agent_toolkit_tui/css/app.tcss:62-68` (the `#content-header` block)

The existing breadcrumb test asserts the *renderable* string. The new test asserts the *rendered region size*. Together they catch both classes of regression: wrong content (existing) and clipped content (new).

- [ ] **Step 1: Add the failing test**

Open `tests/test_tui/test_app.py`. Find the existing `async def test_breadcrumb_reflects_current_kind_and_scope():` block (around line 559) and append this new test directly after the closing line of that test (after the final `assert "harnesses" not in text.lower()`):

```python
async def test_content_header_renders_with_nonzero_height():
    """Regression for #52: the content-header must occupy >= 1 row on screen.

    The string built by `_build_content_header` already passes a Static.render()
    test, but a CSS bug (height: 2 - padding-bottom 1 - border-bottom 1 = 0)
    silently clipped the content area to zero rows. This test fires the moment
    the box collapses again.
    """
    from textual.widgets import Static

    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        header = app.query_one("#content-header", Static)
        # `size.height` is the region Textual actually allocated for the widget
        # after CSS resolved. A zero-height region is the bug.
        assert header.size.height >= 1, (
            f"#content-header collapsed to height={header.size.height}; "
            f"chips and kind label would be invisible on screen."
        )
```

- [ ] **Step 2: Run the test to verify it fails**

Run from the worktree root:

```bash
uv run pytest tests/test_tui/test_app.py::test_content_header_renders_with_nonzero_height -v
```

Expected: **FAIL** with `AssertionError: #content-header collapsed to height=0; chips and kind label would be invisible on screen.`

If it passes here, stop — the bug isn't reproduced and the test is wrong; re-check the test before changing CSS.

- [ ] **Step 3: Apply the CSS fix**

Open `src/agent_toolkit_tui/css/app.tcss`. Replace the existing `#content-header` block (lines 62–68):

```css
#content-header {
    height: 2;
    color: $text;
    padding: 0 0 1 0;
    border-bottom: tall $primary-darken-2;
    margin: 0 0 1 0;
}
```

with:

```css
#content-header {
    height: auto;
    color: $text;
    padding: 0 0 1 0;
    border-bottom: tall $primary-darken-2;
    margin: 0 0 1 0;
}
```

The single change is `height: 2` → `height: auto`. `auto` lets Textual size the box around its content + the explicit `padding-bottom: 1` + `border-bottom: tall` (1 row), which gives exactly 1 row of visible text plus the visual chrome. The bottom margin and border are kept because they form the visual separator from the AssetGrid below.

- [ ] **Step 4: Run the new test to verify it passes**

```bash
uv run pytest tests/test_tui/test_app.py::test_content_header_renders_with_nonzero_height -v
```

Expected: **PASS** — `header.size.height` is now ≥ 1.

- [ ] **Step 5: Run the full test suite to confirm no regressions**

```bash
uv run pytest -q
```

Expected: all 547 tests pass (the prior 546 + this one new test).

If any TUI test now fails because of the CSS change, the most likely cause is a snapshot/region-size assertion elsewhere — read the failure, then revisit. The `height: auto` change widens the content-header by exactly one row, so layouts below it shift down by one row.

- [ ] **Step 6: Visual smoke check (manual, optional but valuable)**

This step is documentary — capture before/after for the verification artifacts. Skip if running as a pure subagent without TTY access; the controller will do it in flow Step 9.

```bash
uv run --extra tui agent-toolkit-tui --toolkit-repo /Users/ajanderson/GitHub/agent-toolkit
```

Look at the row above the filter input. You should now see something like:

```
  Skills   ·   47 items   ·   scope:   project   user
  ────────────────────────────────────────────────────
```

`q` to quit.

- [ ] **Step 7: Commit**

```bash
git add tests/test_tui/test_app.py src/agent_toolkit_tui/css/app.tcss
git commit -m "fix(#52): #content-header height auto so chips render visibly

The V1 Navigator content-header was set to height: 2 with padding-bottom: 1
and border-bottom: tall (1), leaving 0 rows for actual text. Static.render()
was correct so unit tests passed, but the rendered region was clipped and
the kind label, item count, and project/user scope chips never appeared.

Set height: auto so the box sizes around its content + chrome. Add a live-
render regression test asserting size.height >= 1 after mount, so this class
of bug fires loudly next time."
```

The pre-commit hook runs the full test suite — if it fails here, fix the underlying issue and create a *new* commit (do not `--amend`, since the previous commit didn't actually land).

---

## Self-review checklist

**Spec coverage:**

- ✅ Definition of done #1 (header renders with `height >= 1`) → Step 1's test asserts exactly this.
- ✅ Definition of done #2 (chips visible in default theme) → Step 6 visual smoke + the verify step in flow.
- ✅ Definition of done #3 (`u`/`p` toggles highlight) → already covered by `test_breadcrumb_reflects_current_kind_and_scope` and `test_u_p_keys_switch_scope`; the CSS change does not affect them.
- ✅ Definition of done #4 (all existing TUI tests still pass) → Step 5 enforces this.

**Out of scope, confirmed not introduced:**

- ✅ No layout redesign — only the `#content-header` block changes, and only `height` within it.
- ✅ No new keybindings.
- ✅ No new widgets.
- ✅ No theme changes.

**Placeholders:** none — every step has the actual code and the actual command.

**Type consistency:** all referenced symbols (`Static`, `TUIApp`, `FakeRunner`, `_doc`, `Path`, `query_one`, `pilot.pause`, `size.height`) exist in the test file or are imported in the module under test.
