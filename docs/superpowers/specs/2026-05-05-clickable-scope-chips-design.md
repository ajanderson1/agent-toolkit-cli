# Clickable scope chips — design

**Issue:** [#59](https://github.com/ajanderson1/agent-toolkit-cli/issues/59)
**Type:** feat
**Mode:** `--ship-it`

## Goal

Make the project / user scope chips in the V1 Navigator content-header
clickable with the mouse so users do not need to remember the `u` / `p`
keybindings to switch scope.

## Background

`TUIApp._build_content_header` in `src/agent_toolkit_tui/app.py` produces a
single Rich-formatted string that goes into a single `Static#content-header`
widget. The chips are rendered as plain text with `[reverse]` for the active
scope and `[dim]` for the inactive scope. They look interactive but are not —
clicking does nothing.

Textual supports per-region click handlers in Rich markup via the
`[@click=action_name(args)]…[/]` syntax. Inside that span, mouse clicks fire
the named action on the active screen / app. Existing
`TUIApp.action_scope(self, scope: str)` already does the right thing
(idempotent, no-op when scope unchanged, refreshes header + status bar).

## Approach

Wrap each chip in `[@click=app.action_scope('<scope>')]…[/]` so a left-click
on the chip text calls the existing action. Active chip stays `[reverse]`;
inactive stays `[dim]`. No layout changes, no new widgets, no new
keybindings.

## Behaviour

- Clicking the inactive chip → calls `action_scope('user')` (or `'project'`).
  `_scope` flips, content-header re-renders, `[reverse]` moves to the
  newly-active chip.
- Clicking the active chip → calls `action_scope` with the current scope;
  the action's early-return (`scope == self._scope`) means no-op, no flicker.
- Clicking outside any chip's region → nothing (existing behaviour).
- `u` / `p` keybindings → still work, untouched.

## Definition of done

1. Clicking the inactive scope chip with the mouse flips `_scope`.
2. Active chip continues to render with reverse video.
3. `u` / `p` keybindings still work (existing test passes unchanged).
4. New `pilot.click("#content-header", offset=…)` test asserts the click
   behaviour. Falls back to a direct `pilot.app.action_scope(...)` call if
   precise offset clicking on rich-text regions is brittle in test pilot.

## Out of scope

- No new keybindings.
- No layout changes.
- No clickable kind label or count — scope only.
- No new widgets — stay on the single `Static`.
- No CSS changes.
