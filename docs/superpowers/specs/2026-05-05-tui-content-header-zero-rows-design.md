# TUI content-header collapses to zero rows — design

**Issue:** [#52](https://github.com/ajanderson1/agent-toolkit-cli/issues/52)
**Type:** fix
**Mode:** `--auto`

## Goal

Restore the V1 content-header (kind label · item count · scope chips) above the
asset grid by fixing the height/padding/border math that collapsed it to zero
visible rows.

## Background

PR #50 shipped the V1 Navigator layout. Above the AssetGrid, the layout includes
a `Static#content-header` whose Rich-formatted text is built by
`TUIApp._build_content_header`:

```
  Skills   ·   47 items   ·   scope:  project   user
```

The active scope is rendered in `[reverse]`, the inactive scope in `[dim]`.
`u`/`p` keybindings call `action_scope` which mutates `self._scope` and re-renders
the header. Tests (`test_breadcrumb_reflects_current_kind_and_scope`) pass —
`Static.render()` returns the expected text.

But on a real terminal the line is invisible. The CSS for `#content-header` is:

```css
#content-header {
    height: 2;
    color: $text;
    padding: 0 0 1 0;
    border-bottom: tall $primary-darken-2;
    margin: 0 0 1 0;
}
```

Textual's box model: `height: 2` is the **outer** height. With `padding-bottom: 1`
(1 row) and `border-bottom: tall` (also 1 row), the **content area** collapses
to `2 - 1 - 1 = 0` rows. The Rich text is rendered into a zero-row content box
and clipped.

## Root cause

CSS arithmetic. The `Static.render()` test passes because it inspects the
renderable, not the rendered output. There's no live-render assertion that
catches the visual collapse.

## Fix

Two parts.

### Part A — CSS

Either grow `height` to absorb the chrome, or drop the chrome. Cleanest is to
keep the visual separator but give the header room: bump `height` to 3 (1 text
row + 1 padding-bottom + 1 border-bottom), or remove the explicit `height` and
let the box auto-size around its content + chrome.

**Decision:** set `height: auto` and keep the `padding-bottom: 1` and
`border-bottom: tall` styling. `auto` is robust against future content changes
(e.g. multi-line headers) and survives terminal width changes. The bottom
margin can stay or go — it's just airspace before the AssetGrid.

### Part B — Regression test

`test_breadcrumb_reflects_current_kind_and_scope` already asserts the
*renderable*. Add a **live-render** assertion that catches this regression
class. Use `pilot.app.console.capture()` or query the rendered region size,
whichever is supported by the current Textual version. Minimum bar: assert that
the rendered content area is **non-zero rows tall** when the app is mounted.

A pragmatic alternative if direct region inspection is awkward: assert that
`query_one("#content-header", Static).size.height >= 1` after `pilot.pause()`.
`Widget.size` reports the actual region the widget is allocated, post-CSS.
A zero-height region is exactly what's broken today, so this check fires the
moment the regression returns.

## Definition of done

- `#content-header` renders with `height >= 1` row visible (covered by test).
- The kind label, item count, and scope chips appear on screen in the default
  gruvbox theme — verified by `assets/verification/52/after.txt` capture.
- `u`/`p` toggle moves the highlight between project and user (covered by
  existing `test_breadcrumb_reflects_current_kind_and_scope`).
- All existing TUI tests still pass.

## Out of scope

- No layout redesign — V1 Navigator structure is final.
- No new keybindings.
- No new widgets — fix is contained to `app.tcss` + one test addition.
- No theme changes.
