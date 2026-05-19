# Spec: scope toggle — paired styling + working mouse click

**Issue:** #99
**Type:** fix(tui)
**Date:** 2026-05-19

## Goal

Make the `scope:` control in the TUI content header read clearly as a single two-state toggle between `project` and `user`, and make a mouse click on either label switch the active scope (same behaviour as pressing `s`).

## Background

`_build_content_header` in `src/agent_toolkit_tui/app.py:283-304` renders the scope chips with asymmetric Rich markup:

- Active scope → `[@click=app.action_scope('<s>')][reverse] <s> [/][/]` — inverted block.
- Inactive scope → `[@click=app.action_scope('<s>')] [dim]<s>[/] [/]` — dim text.

The result is two visually unrelated elements: a solid inverted block next to dim text that reads as an underline. It does not communicate "pick one of these two." The keyboard binding `s` (`Binding("s", "scope_toggle", "toggle scope")` at line 101, dispatching `action_scope_toggle` at line 193) works correctly. Mouse clicks via the `[@click=…]` action-link markup do **not** flip the scope in practice, even though the markup is structurally well-formed.

Recent history: commit `7bcc07a` (PR #88) added the single-key `s` toggle and claimed the chip clicks were already wired. The chips are now confirmed broken for mouse interaction, contradicting that claim — so the click pathway needs a real fix, not just a styling change.

## Scope

**In scope**

1. Replace the asymmetric `[reverse]` / `[dim]` markup with a single paired-toggle visual that:
   - Makes both options look like members of the same toggle group (same shape, same border treatment, same padding).
   - Distinguishes active from inactive via a consistent affordance (e.g. both options bracketed in a pill-style group with the active one highlighted in `$accent` or `[b]`, and the inactive one in the normal foreground colour — **not** dim/underline).
   - Removes the "ugly underlying thing" — no `[dim]` on the inactive label.
2. Restore working mouse click on either scope label so clicking switches the active scope. The exact mechanism (Rich `[@click=…]` action links vs. a dedicated clickable widget vs. `on_click` event handler with hit-test) is an implementation choice for the plan; the **behaviour requirement** is: clicking the inactive scope flips the active scope, and clicking the active scope is a no-op (matches `action_scope` guard at line 186).
3. Keep the keyboard `s` toggle working (regression guard).

**Out of scope**

- Adding new scope values beyond `project` / `user`.
- Restyling the rest of the content header (kind label, item count, separators).
- Touching the kinds sidebar, asset grid, or status bar.

## Approach (sketch — final shape decided in plan)

Two viable directions; the plan should pick one based on which produces the simplest working code:

**A. Stay in Rich markup, fix the click wiring.**
If `[@click=…]` action links in a `Static` are actually working in Textual ≥ current pinned version, the bug may be that the `Static` widget is not receiving click events at all (e.g. it's not the deepest hit-tested widget, or markup is being re-parsed in a way that strips the action). Investigation step: bench a minimal reproduction. If clicks fire, fix; if not, fall back to B.

**B. Replace the `Static` chip block with a small dedicated widget.**
A `Horizontal` containing two `Label`s (or two single-line `Static`s) each with its own `on_click` handler that calls `self.app.action_scope("project" | "user")`. This is the bulletproof Textual pattern — explicit widget click event handlers, no Rich-action-link plumbing. Cost: a small new widget class (or two `Label` instances with bound classes) and a CSS rule per state.

Approach B is the safer default because it removes the ambiguity of Rich action-link behaviour. The plan can confirm by trying A first if it appears trivially fixable.

## Constraints

- Textual conventions per memory `feedback_textual_render_methods`: do not name new methods `_render_*` — collides with Textual internals.
- Must remain a single line in the content header (no layout reflow).
- Must work in the default `gruvbox` theme set in `on_mount`.

## Definition of done

1. Active and inactive scope options share a single, consistent paired-toggle visual; no `[dim]`/underline-looking inactive state.
2. Clicking the inactive scope label with the mouse switches the active scope (verified by terminal-recorder artifact or manual eyeball).
3. Pressing `s` continues to toggle scope (regression).
4. `_build_content_header` (or its replacement) has no surprising side effects on the other header chips.
5. Pre-flight CI green; self-review PASS.

## Verification plan

- Unit / integration: if there is an existing TUI snapshot or `pytest` harness covering `_build_content_header`, update it; otherwise no new automated test gate — this is a visual + interaction fix.
- Manual / artifact: launch `agent-toolkit tui` in the verification step, capture a screenshot of the header in both scope states, capture a terminal recording that shows a click flipping the scope.
- Regression: confirm `s` keybinding still toggles in the same recording.
