# Design — scope toggle: mouse-clickable + single `s` hotkey

**Issue:** [#85](https://github.com/ajanderson1/agent-toolkit-cli/issues/85)
**Branch:** `feat/85-scope-toggle-clickable`

## Goal

Make the project/user scope indicator in the TUI mouse-clickable and replace the separate `u` / `p` hotkeys with a single `s` toggle.

## Current state

`src/agent_toolkit_tui/app.py`:

- `BINDINGS` registers `u` → `action_scope('user')` and `p` → `action_scope('project')` (lines 101–102).
- `action_scope(scope: str)` is value-driven — it accepts the target scope and bails if it matches the current one (lines 186–192).
- `_build_content_header()` already emits Textual click-action markup on each chip — `[@click=app.action_scope('{s}')]…[/]` (lines 293–298). Whether those are actually wired up depends on the host widget; the chip text is rendered into `#content-header` (a `Static`), which by default does support markup-action callbacks.

So the click hooks exist on paper. The work is:

1. Verify chips really do click through to `action_scope` (or fix the wiring if not).
2. Replace the two-key binding with a single `s` toggle.
3. Strip the old `u` / `p` references from any help/footer/docs surface.

## Behaviour after change

- Pressing `s` flips the scope: `project` → `user` and back.
- Clicking either scope chip in `#content-header` selects that scope. Clicking the already-active chip is a no-op (matches existing `action_scope` guard).
- The footer hint that previously listed `u user scope` / `p project scope` now shows a single `s toggle scope` entry.
- `u` and `p` are no longer bound to scope (or anything else).

## Implementation outline

1. **`app.py` — BINDINGS:**
   - Remove the two `Binding("u", …)` / `Binding("p", …)` lines.
   - Add `Binding("s", "scope_toggle", "toggle scope")`.

2. **`app.py` — new action `action_scope_toggle()`:**
   - Computes the opposite scope from `self._scope` and delegates to `action_scope(other)`.
   - Keeps `action_scope` intact so the click-action markup keeps working.

3. **Chip click verification:**
   - In the current rendering path, `_build_content_header()` returns a string passed to `Static.update(...)`. Confirm that Textual's `[@click=…]` markup in a plain `Static` triggers actions (it does, for markup actions, as of Textual ≥ 0.50). If the wiring needs a `markup=True` hint or a switch to `Label` / explicit `on_click`, adjust accordingly.

4. **Docs / surface scrubs:**
   - Search the repo for `u user scope`, `p project scope`, "press u", "press p" in `docs/`, `README*`, and any TUI screenshot captions; update to `s`.

## Out of scope

- Visual restyling of the scope chips (colour, layout, animation).
- Restructuring the content header.
- Changing the underlying scope model (`Literal["user","project"]`) or `ScopeChanged` message.

## Definition of done

- `s` toggles the scope between `project` and `user`.
- Clicking either chip in the content header switches scope to that chip.
- No `u` or `p` binding remains in `BINDINGS`; no doc/help text mentions them as scope keys.
- `uv run pytest -q` is green.
- Manual smoke (recorded in verification artifacts): launch the TUI, press `s`, click the inactive chip; both transitions visible in the header.

## Risks / unknowns

- **Chip click may not currently fire.** The markup is present but I haven't verified it triggers `action_scope` in the running app. If it doesn't, the fix is either (a) ensure `Static` is rendering markup (it is by default), or (b) swap to a widget with explicit click handling. The plan accounts for verifying this with a manual click during smoke.
- No automated tests exercise `BINDINGS` directly today; smoke-test artifacts are the verification.
