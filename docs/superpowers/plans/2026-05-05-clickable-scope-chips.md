# Clickable scope chips — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the project / user scope chips in the V1 Navigator content-header clickable with the mouse, so a click on the inactive chip flips `_scope` via the existing `action_scope`.

**Architecture:** Markup-only change inside `TUIApp._build_content_header`: wrap each chip span in Textual's `[@click=app.action_scope('<scope>')]…[/]`. The action already exists; the click goes to it.

**Tech Stack:** Python 3.13, Textual 8.2.5, pytest-asyncio, uv, lefthook (pre-commit runs full pytest).

---

## Task 1: Test + implementation + commit

**Files:**
- Test: `tests/test_tui/test_app.py` (append after the existing `test_content_header_renders_with_nonzero_height` block)
- Modify: `src/agent_toolkit_tui/app.py` (the `_build_content_header` method, around lines 290–301)

The plan is one TDD-style task: write a click-driven test, watch it fail, add the markup, watch it pass, run the full suite, commit.

- [ ] **Step 1: Write the failing test**

Append this test to `tests/test_tui/test_app.py`, immediately after `test_content_header_renders_with_nonzero_height`:

```python
async def test_scope_chip_click_switches_scope():
    """Regression for #59: clicking the inactive scope chip flips _scope.

    The chips render as Rich-markup spans inside #content-header. Wrapping
    each chip in [@click=app.action_scope(...)] makes the span a click target.
    Verifies via pilot.click('#content-header'); we don't pin the exact x-
    offset (rich-text regions are layout-sensitive) — instead we assert that
    invoking the click handler via the action route does what u/p does.
    """
    from agent_toolkit_tui.widgets import AssetGrid

    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        grid = app.query_one("#asset-grid", AssetGrid)
        assert app._scope == "project"
        assert grid._scope == "project"

        # The action wired to the chip's [@click=...] markup. Calling it
        # directly proves the dispatch path the click span will use.
        await app.run_action("scope('user')")
        await pilot.pause()
        assert app._scope == "user"
        assert grid._scope == "user"

        # And back — clicking the (now-inactive) project chip flips it back.
        await app.run_action("scope('project')")
        await pilot.pause()
        assert app._scope == "project"
        assert grid._scope == "project"


async def test_content_header_markup_contains_click_actions():
    """Regression for #59: the content-header markup wires both chips
    to action_scope via Rich [@click=...] spans, so a mouse click on the
    chip text dispatches the same action u / p do.

    Asserts the *rendered markup* contains the click directives. This is
    what makes the chips actually clickable in the running TUI; without
    these directives the visual chip is just dead text.
    """
    from textual.widgets import Static

    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        # _build_content_header is what update() is called with; assert the
        # raw markup string contains both click directives.
        markup = app._build_content_header()
        assert "@click=app.action_scope('project')" in markup, markup
        assert "@click=app.action_scope('user')" in markup, markup
```

Two assertions deliberately:
1. `test_scope_chip_click_switches_scope` proves the **dispatch path** (the action invocation works end-to-end via `run_action`, which is exactly the route a `[@click=app.action_scope(...)]` span takes).
2. `test_content_header_markup_contains_click_actions` proves the **markup wiring** is present — without the `[@click=...]` directive the click target doesn't exist, no matter how good the action is.

Together they catch both regression classes: action removed *and* markup removed.

- [ ] **Step 2: Run the new tests to verify they fail**

```bash
uv run pytest tests/test_tui/test_app.py::test_scope_chip_click_switches_scope tests/test_tui/test_app.py::test_content_header_markup_contains_click_actions -v
```

Expected:
- `test_scope_chip_click_switches_scope` — PASS already (the action exists, this test only proves the action dispatch path; it's a guardrail against later removal of the action).
- `test_content_header_markup_contains_click_actions` — **FAIL** with `assert "@click=app.action_scope('project')" in markup` because the markup currently has plain `[reverse] project [/]` / `[dim]project[/]` spans without click directives.

If both pass, the markup is already wired and there's nothing to do — stop here and confirm the spec was right about the gap.

- [ ] **Step 3: Add the click markup**

Open `src/agent_toolkit_tui/app.py`. Locate the `_build_content_header` method (around lines 280–301). Replace the chips loop:

```python
        chips = []
        for s in ("project", "user"):
            if s == self._scope:
                chips.append(f"[reverse] {s} [/]")
            else:
                chips.append(f" [dim]{s}[/] ")
```

with:

```python
        chips = []
        for s in ("project", "user"):
            if s == self._scope:
                chips.append(f"[@click=app.action_scope('{s}')][reverse] {s} [/][/]")
            else:
                chips.append(f"[@click=app.action_scope('{s}')] [dim]{s}[/] [/]")
```

That's the entire change: each chip span is wrapped in a `[@click=app.action_scope('<scope>')]…[/]` outer span. The visual styling (reverse / dim) and the trailing punctuation are unchanged.

- [ ] **Step 4: Re-run the new tests to verify they pass**

```bash
uv run pytest tests/test_tui/test_app.py::test_scope_chip_click_switches_scope tests/test_tui/test_app.py::test_content_header_markup_contains_click_actions -v
```

Expected: both **PASS**.

- [ ] **Step 5: Run the full suite**

```bash
uv run pytest -q
```

Expected: 549 tests pass (the 547 from PR #57 + the two new ones).

If anything fails, check for tests that asserted the *exact* content of the header markup string — those would need their assertions widened to allow the click prefixes. Most existing tests assert substrings like `"Skill"`, `"project"`, etc. so they should be unaffected.

- [ ] **Step 6: Commit**

```bash
git add tests/test_tui/test_app.py src/agent_toolkit_tui/app.py
git commit -m "feat(#59): make scope chips mouse-clickable

Wrap each project/user chip span in Textual's [@click=app.action_scope(...)]
markup so a left-click flips _scope via the existing action_scope handler.
Visual styling (reverse for active, dim for inactive) is unchanged. The
u/p keybindings still work — the click is purely an alternative input path.

Two new tests: one proves the action dispatch path works end-to-end via
run_action, one asserts the click markup is actually present in the
rendered header (the bit that makes the click target exist at all)."
```

The pre-commit hook runs the full suite. If it fails, do NOT `--amend` — fix and re-commit.

---

## Self-review checklist

**Spec coverage:**
- ✅ DoD #1 (clicking inactive chip flips `_scope`) → `test_scope_chip_click_switches_scope` covers via the action dispatch path.
- ✅ DoD #2 (active chip still reverse-rendered) → markup still contains `[reverse]` for active scope; existing `test_breadcrumb_reflects_current_kind_and_scope` covers.
- ✅ DoD #3 (`u`/`p` keybindings still work) → existing `test_u_p_keys_switch_scope` is unchanged and runs.
- ✅ DoD #4 (new pilot-based test) → `test_scope_chip_click_switches_scope` + `test_content_header_markup_contains_click_actions`.

**Out of scope, confirmed not introduced:**
- ✅ No new keybindings.
- ✅ No layout changes.
- ✅ No clickable kind label or count.
- ✅ No new widgets — Static stays.
- ✅ No CSS changes.

**Placeholders:** none.

**Type consistency:** `app.action_scope` — exists on `TUIApp` (line 184 of `app.py`), accepts a single `scope: str` argument. The markup `[@click=app.action_scope('project')]` matches.
