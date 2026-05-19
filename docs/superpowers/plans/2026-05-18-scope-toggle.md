# Plan — scope toggle: clickable chips + single `s` hotkey

**Spec:** `docs/superpowers/specs/2026-05-18-scope-toggle-design.md`
**Issue:** #85
**Branch:** `feat/85-scope-toggle-clickable`

## Tasks

### Task 1 — Replace `u`/`p` bindings with single `s` toggle

**File:** `src/agent_toolkit_tui/app.py`

**Changes:**

1. In `BINDINGS` (≈ line 95–111), remove:

   ```python
   Binding("u", "scope('user')", "user scope"),
   Binding("p", "scope('project')", "project scope"),
   ```

   Add in their place:

   ```python
   Binding("s", "scope_toggle", "toggle scope"),
   ```

2. Below `action_scope(self, scope: str)` (≈ line 186), add:

   ```python
   def action_scope_toggle(self) -> None:
       other = "user" if self._scope == "project" else "project"
       self.action_scope(other)
   ```

   `action_scope` already validates and short-circuits if the target equals the current scope — we delegate to it so chip clicks and `s` go through the same code path.

**Why no separate action:** the click markup `[@click=app.action_scope('{s}')]` is value-driven (`'user'` or `'project'` baked into the markup). The keyboard binding is toggle-driven (no value). Keeping `action_scope(scope)` as the canonical setter and adding `action_scope_toggle()` as a thin wrapper preserves both call patterns without overloading semantics.

### Task 2 — Verify chip clicks work; fix if not

**File:** `src/agent_toolkit_tui/app.py` (`_build_content_header()` and `#content-header`)

**Steps:**

1. Run the TUI manually.
2. Click the inactive scope chip.
3. If the scope flips → done, no code change.
4. If it does not flip:
   - The `#content-header` widget is a `Static` — `Static` does parse `[@click=…]` markup as action links by default in Textual.
   - If the markup isn't firing, the most likely cause is the `Static` not having markup enabled, or the action name being unresolvable. Investigate with the Textual devtools console (`textual console`) or by adding a debug `Notify` to the action.
   - Minimum fix: replace `Static(..., id="content-header")` rendering with a widget that explicitly handles `on_click`, mapping click position → scope. Avoid touching the message-passing structure; the existing `action_scope` is the right target.

**Important:** do not invent a new message type or add a new chip widget unless step-4 verification proves the markup-action path is broken. Default outcome here is "no code change, just verified."

### Task 3 — Scrub `u` / `p` references from docs and help text

**Search-and-update across:**

- `docs/**/*.md` (especially `docs/agent-toolkit-tui/` if it exists)
- `README.md` (root and any `tui/`-scoped readmes)
- `src/agent_toolkit_tui/**/*.py` docstrings
- Screenshot captions or example transcripts

**Find:**

```bash
grep -rn -E "\b[up]\b.*(scope|user|project)|press [up]|hotkey [up]|key [up]" docs/ README.md src/agent_toolkit_tui/ 2>/dev/null
```

Replace any hits that documented the old bindings. Anything in changelog or release-note files referring to historical state stays as-is.

### Task 4 — Update tests (only if any reference `u`/`p` bindings)

**Search:**

```bash
grep -rn -E "Binding\(\"[up]\"|action_scope.*'(user|project)'|\bpress_key.*[up]\b" tests/
```

If results: update to drive `s` (or `action_scope_toggle`). Currently no tests reference these bindings, so this task is expected to be a no-op.

### Task 5 — Manual smoke (verification artifacts)

Will be captured in flow Step 9. Recorded transitions:

1. Launch TUI: header shows `scope:  project   user`.
2. Press `s`: header shows `scope:  project   user` with `user` reversed (active).
3. Click `project`: header reverts to `project` active.
4. Verify `u` and `p` no longer flip the scope (they should now be no-ops, falling through to the default Textual binding or doing nothing).

## File-touch summary

| File | Lines | Nature |
|---|---|---|
| `src/agent_toolkit_tui/app.py` | ~5 lines added, ~2 removed | binding swap + new action |
| `docs/**` or `README*` | TBD by grep | text scrub |
| Tests | likely none | grep-conditional |

Total expected diff: < 30 lines.

## Verification

- `uv run pytest -q` (lint + tests via lefthook on commit, full suite manually).
- Manual smoke recorded in `assets/verification/85/`.

## Rollback

Single revert commit — no migrations, no persisted state involved.
