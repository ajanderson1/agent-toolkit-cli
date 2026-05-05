# Plan — TUI Visual Refresh (#43)

Implements the spec at `docs/superpowers/specs/2026-05-05-tui-visual-refresh-design.md`. Worktree: `feat/43-tui-visual-refresh`. Reference mockup: `/tmp/atui-mockups/3/`.

## Sequence

Tasks are ordered for safe incremental commits — each task leaves the test suite green and the TUI runnable. No parallelism: the changes touch the same files, and the order is part of the design.

### Task 1 — Add new `KindsTabs` widget

Create `src/agent_toolkit_tui/widgets/kinds_tabs.py`:

- Mirrors `KindsSidebar`'s public surface: `__init__(state, *, id=None)`, `update_state(state)`, posts `KindChanged`.
- Renders as a single `Static` line of segments (active = `[reverse][b]`, others muted with `[dim]` count).
- Click handling: not required for V1 — the `1`–`6` keybindings on the App drive selection. Mouse can be added later if asked.
- Internally tracks `_active_kind` and re-renders on `update_state`.

Export from `src/agent_toolkit_tui/widgets/__init__.py` (add alongside the existing exports for now — old widgets are removed in Task 4).

**Test:** add `tests/test_tui/test_kinds_tabs.py` mirroring whatever coverage `test_app.py` had for `KindsSidebar` selection. Exercise `update_state` and verify `KindChanged` is posted.

**Commit:** `feat(tui): add KindsTabs widget for the dashboard layout (#43)`

### Task 2 — Rewrite `app.tcss`

Replace `src/agent_toolkit_tui/css/app.tcss` with the dashboard tcss adapted from `/tmp/atui-mockups/3/app.tcss`. Key adjustments:

- Replace mockup IDs (`#tabs`, `#breadcrumb`, `#status-bar`, `#grid-filter`, `#grid-table`) with the actual IDs we'll use in the App's `compose()` (Task 3).
- Drop the rules that referenced widgets we're deleting (`KindsSidebar`'s `border: round $primary`, `HarnessPicker`'s borders).
- Drop the `Footer { background: $primary 30%; }` line (per user choice).
- Keep tokyo-night palette tokens — the theme is set in Task 3.

**Test:** existing tests don't read tcss. Visual confirmation in Task 3.

**Commit:** `style(tui): replace app.tcss with tokyo-night dashboard styling (#43)`

### Task 3 — Rewrite `TUIApp.compose()` + lifecycle

Edit `src/agent_toolkit_tui/app.py`:

1. Imports: drop `HarnessPicker` and `KindsSidebar` imports. Add `KindsTabs` and `Static` (already imported).
2. `compose()`:
   - `yield Header()`
   - `yield Static("", id="kinds-tabs")` — backed by `KindsTabs(state)` widget OR rendered inline. **Decision:** use the new `KindsTabs` widget so the App stays slim.
   - `yield Static("", id="breadcrumb")` — populated by `_refresh_breadcrumb()`.
   - `yield Input(placeholder="…", id="grid-filter")` — was previously inside `AssetGrid`, now hoisted to App level so it sits between breadcrumb and table per the dashboard layout.
   - `yield AssetGrid(self.state, id="asset-grid")` — modified to accept the filter input being external (see sub-step below).
   - `yield Static("", id="status-bar")` — populated by `_refresh_status_bar()`.
   - `yield Footer()`.
3. **AssetGrid filter hoist** — the existing `AssetGrid.compose()` yields its own `Input`. Two options:
   - **(a) Keep filter inside AssetGrid**, but reposition via tcss. *Pro:* zero API change. *Con:* the dashboard layout has the filter outside the grid card visually.
   - **(b) Hoist filter into App, AssetGrid exposes a `set_filter(value: str)` method.** *Pro:* matches dashboard visual exactly. *Con:* small API addition.
   
   **Pick (a)** — it's the smaller change, no API delta, and the visual difference is cosmetic. The mockup had the filter outside because there was no AssetGrid widget; the real grid having an internal filter is fine.
4. Keybindings: add `1`–`6` for kinds, `u`/`p` for scope, `/` already exists (`focus_filter`). Update Footer to show new ones.
5. `on_mount`: set `self.theme = "tokyo-night"`. Call `_refresh_breadcrumb()` and `_refresh_status_bar()`.
6. New methods:
   - `_refresh_breadcrumb()` — renders `agent-toolkit › <KindLabel> · scope: [chip] · harnesses: <chips>`
   - `_refresh_status_bar()` — counts state by status, renders `linked / pending / drifted / broken` summary
7. Modify `on_kind_changed`, `on_scope_changed`, `on_asset_toggled` to also call `_refresh_breadcrumb()` / `_refresh_status_bar()` as appropriate.
8. `action_kind(name)` and `action_scope(name)` — wire `1-6` and `u/p` to the existing `KindChanged` / `ScopeChanged` flows.
9. `ConfirmDiscardScreen` — update inline `DEFAULT_CSS`: container border `thick $warning`, title bold accent on warning bg, button margins `0 2`. Keep the CSS inline.

**Test:** existing TUI tests must still pass. Add a test for the new `1-6` and `u/p` keybindings (presses key, asserts `KindChanged` / `ScopeChanged` was posted).

**Commit:** `feat(tui): dashboard layout with breadcrumb, tabs, status bar (#43)`

### Task 4 — Delete obsolete widgets

After Task 3 is green, the old widgets are unreferenced. Delete:

- `src/agent_toolkit_tui/widgets/kinds_sidebar.py`
- `src/agent_toolkit_tui/widgets/harness_picker.py`

Update `src/agent_toolkit_tui/widgets/__init__.py` to drop their exports.

Update any tests that still import them — likely `tests/test_tui/test_app.py` and friends. Replace assertions about `KindsSidebar` with `KindsTabs` equivalents.

**Test:** full suite green. Run `uv run pytest -q`.

**Commit:** `refactor(tui): delete obsolete KindsSidebar and HarnessPicker (#43)`

### Task 5 — Capture before/after screenshots

The verification recipe (Step 9 of `flow.md`) runs against `.claude/testing.md` if present, or the legacy menu otherwise. For this PR specifically, the DoD demands "before/after screenshots in PR" — that's the verification artefact.

- Use `claude-in-chrome` browser automation? No — TUI is in a terminal.
- Use tmux + capture-pane (per the textual-tui skill, Tier 2)? Yes — this is the right tool.
- Approach:
  1. Stash a copy of the current TUI screenshot from `main` (already captured during the brainstorming phase by inspecting current `app.tcss` — but no PNG exists). Instead: check out the parent commit, run TUI, screenshot via `tmux capture-pane -p > before.txt`, and convert to a styled PNG with `aha | wkhtmltoimage` OR commit the raw text + the new screenshot together.
  2. **Simplification:** capture *both* views as text (`tmux capture-pane -e` → ANSI-coded text), commit them as `assets/verification/43/before.ansi` and `assets/verification/43/after.ansi`, plus pre-rendered PNGs via `aha`.
  3. Attach both PNGs as PR comments via `superpowers:finishing-a-development-branch` (it has artefact-attach support).

Concretely, in Task 5:

```bash
# AFTER (current branch)
tmux new-session -d -s atui-after -x 160 -y 44
tmux send-keys -t atui-after "uv run agent-toolkit-tui --toolkit-repo $PWD" Enter
sleep 2
tmux capture-pane -t atui-after -p -e > assets/verification/43/after.ansi
tmux kill-session -t atui-after

# BEFORE (from main)
git stash || true
git checkout main -- src/agent_toolkit_tui/
tmux new-session -d -s atui-before -x 160 -y 44
tmux send-keys -t atui-before "uv run agent-toolkit-tui --toolkit-repo $PWD" Enter
sleep 2
tmux capture-pane -t atui-before -p -e > assets/verification/43/before.ansi
tmux kill-session -t atui-before
git checkout HEAD -- src/agent_toolkit_tui/   # restore branch state
git stash pop || true

# Convert to PNGs
aha < assets/verification/43/before.ansi > /tmp/before.html && wkhtmltoimage /tmp/before.html assets/verification/43/before.png
aha < assets/verification/43/after.ansi  > /tmp/after.html  && wkhtmltoimage /tmp/after.html  assets/verification/43/after.png
```

If `aha` / `wkhtmltoimage` aren't installed, fall back to committing only the `.ansi` text files. The PR body explains the format.

`assets/verification/` is in `.gitignore` (per the flow contract); the screenshots are attached as PR comments via the finishing skill, not committed to the repo.

**Commit:** none — verification artefacts are ephemeral, attached at PR-open time.

### Task 6 — Pre-flight CI

Run lint + tests in the worktree. The lefthook pre-commit already runs pytest; explicitly run it again with `uv run pytest -q` and capture to `assets/verification/43/preflight-pytest.log`. Run `uv run ruff check src tests` if ruff is configured (check `pyproject.toml`).

If anything fails → halt. The user fixes and re-runs.

### Task 7 — Self-review (Step 10 of flow)

Invoke `superpowers:requesting-code-review` against the branch diff vs `origin/main`. Capture verdict + findings to `assets/verification/43/review-1.md`. Per the spec mode (`--guided`):

- PASS → proceed to PR
- needs-changes → `AskUserQuestion`: apply fixes / open PR anyway / abort
- FAIL → `AskUserQuestion`: same options

Retry budget: 1.

### Task 8 — Open PR via `superpowers:finishing-a-development-branch`

Hand off with:
- branch: `feat/43-tui-visual-refresh`
- PR title: "Refresh TUI visual style, taking cues from claude-tui-tools"
- PR body: built from the spec + commits + verification artefact paths (template per `flow.md` Step 11)
- `--draft` (mode is `--guided`)
- `Closes #43`
- Image artefacts: `assets/verification/43/before.png` and `after.png` (attached as PR comments)

After the PR exists, `gh issue comment 43 --body "PR opened: <url>"`.

## Risks & mitigations

1. **Rebuilding the TUI breaks an existing test in subtle ways** — e.g., a test that calls `app.query_one(KindsSidebar)`. Mitigation: full grep for `KindsSidebar` and `HarnessPicker` in `tests/` before Task 4. Update any matches to `KindsTabs` / breadcrumb-equivalent.
2. **The new keybindings collide with `RadioSet`'s arrow-key navigation in `HarnessPicker`** — but `HarnessPicker` is gone, so this is moot.
3. **Screenshot tooling absent (`aha`, `wkhtmltoimage`)** — fall back to ANSI text artefacts, document in PR body.
4. **The headless mode (`--headless --plan`) is a separate code path** — verify nothing in this refactor touches it. Specifically `_parse_args`, `_read_plan`, and the `if args.headless:` branch in `main()` should be byte-for-byte unchanged. Add to the self-review checklist.

## Acceptance for this plan

Approve to proceed to Task 1. Each task ends with a green commit; if anything fails the flow halts at that task.
