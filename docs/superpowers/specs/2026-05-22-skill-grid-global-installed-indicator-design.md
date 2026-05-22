# Spec — Re-implement globally-installed indicator in SkillGrid Project scope (#188)

Date: 2026-05-22
Issue: [#188](https://github.com/ajanderson1/agent-toolkit-cli/issues/188)
Supersedes (for the SkillGrid surface): [`docs/superpowers/specs/2026-05-18-show-user-scope-indicator-design.md`](2026-05-18-show-user-scope-indicator-design.md)
Mode: `aj-workflow flow --auto`

## 1. Goal

When the TUI Skill tab is in **Project** scope, each interactive-agent cell of a skill that is also installed **globally** shows a clear glyph (🌐 by default). Read-only visual hint so the operator can see at a glance "this skill is already covered globally — I may not need to install it at project scope too." When in Global scope the indicator does not render.

## 2. Why now

The same affordance existed in the deprecated `AssetGrid` (shipped as #86 / PR #91, removed by `a52929b` during the v2.3 skill-only cutover). The user has now re-requested it for the v2.3 `SkillGrid`. The v2.3 architecture builds rows for a single scope at a time, so the data isn't yet available at render — we need a minimal, deliberate change to make it available.

## 3. Non-goals (out of scope)

- Reverse indicator (project-installed shown while viewing Global). Possible follow-up; not in this PR.
- Drift detection or "you should remove this" guidance — purely informational.
- Any change to `link` / `unlink` semantics, the `space`/`a` toggle behaviour, scope-switching, or the universal-project-unlink refusal in `_toggle_at`.
- CLI surfaces (`skill list`, `agent-toolkit doctor`, JSON output). The previous spec covered three surfaces — this issue and PR are scoped to the **SkillGrid widget only**.
- Hook/MCP correctness rework. SkillGrid renders skill projections via symlinks; this PR does not touch hook/MCP install state.

## 4. Background — code map

| Concern | Module:line |
|---|---|
| Cell data shape | `src/agent_toolkit_tui/skill_state.py:36` (`SkillCell`) |
| Row data shape — `cells: dict[(agent, scope), SkillCell]` | `src/agent_toolkit_tui/skill_state.py:43` (`SkillRow`) |
| Row builder — per-scope only today | `src/agent_toolkit_tui/skill_state.py:137` (`build_skill_rows`) |
| Per-cell builder | `src/agent_toolkit_tui/skill_state.py:89` (`_cell_for`) — already accepts arbitrary scope/home/project |
| Interactive agents | `src/agent_toolkit_tui/skill_state.py:33` — `("universal", "claude-code", "pi")` |
| Cell render | `src/agent_toolkit_tui/widgets/skill_grid.py:286` (`_cell_glyph`) — reads `row.cells.get((agent, self._scope))` |
| Header rebuild | `src/agent_toolkit_tui/widgets/skill_grid.py:255` (`_rebuild`) |
| Scope wiring | `src/agent_toolkit_tui/app.py:128-140` (`_scope_to_roots` + `_refresh_skill_view`) |
| Existing glyph table | `src/agent_toolkit_tui/widgets/skill_grid.py:39-45` |

**Key recon finding:** `_cell_for` already accepts an arbitrary `scope` and `home`/`project` pair, so building global cells while in project scope is a one-line extension inside `build_skill_rows`. No new probe paths, no new symlink semantics. The change is data-availability + render.

## 5. Design

### 5.1 Definition of "globally installed" — per agent

For each interactive agent the indicator semantics are:

| Agent | "Globally installed" means |
|---|---|
| `universal` | `~/.agents/skills/<slug>` symlink resolves to the library canonical (the existing `SkillCell.linked` for `(universal, global)`). |
| `claude-code` | The Claude-Code projection symlink at the user-scope target points to the library canonical (existing `_cell_for` logic with `scope="global"`). |
| `pi` | Same as `claude-code` but for the Pi projection target. |

Each agent's indicator is independent — a skill globally linked for `claude-code` but not `pi` shows the marker on the `claude-code` cell only. We do **not** collapse to a single per-row indicator.

`drift` and `skipped` global states are treated as "not globally linked" for indicator purposes (the indicator is strictly about a clean, resolvable global link; drift surfaces separately in global scope view).

### 5.2 Data: populate global cells when in project scope

In `build_skill_rows(scope, home, project)`:

- **Today:** for each slug, populate `cells[(agent, scope)]` for every agent.
- **Change:** when `scope == "project"` *and* `home is not None`, also populate `cells[(agent, "global")]` for every interactive agent — using `_cell_for(slug, agent, scope="global", home=home, project=None)`. (Global cells must not pass a `project` — that would conflate scopes.)
- `home` must therefore be passed even in project scope. Update `app._scope_to_roots()`:
  - Today: `("project", None, Path.cwd())`
  - New: `("project", Path.home(), Path.cwd())`
- Global-scope behaviour unchanged: caller already passes `home=Path.home(), project=None`; we don't populate project cells when in global scope (asymmetric by design — the indicator only renders in the project view).

The result: when the TUI is in project scope, every row carries both `(agent, "project")` and `(agent, "global")` cells; in global scope, only `(agent, "global")` cells (status quo).

### 5.3 Render: suffix the glyph in `_cell_glyph`

In `_cell_glyph(row, agent)` after the existing glyph-resolution logic:

- If `self._scope == "project"`:
  - Look up `global_cell = row.cells.get((agent, "global"))`.
  - If `global_cell is not None` **and** `global_cell.linked` **and** **not** `global_cell.drift` **and** **not** `global_cell.skipped`: append the global-install glyph (constant `_GLOBAL_GLYPH = "🌐"`) to the returned cell text.
  - The suffix renders for every project-cell state — linked, unlinked, drift, pending, and skipped — because the question it answers ("is this also at global?") is orthogonal to the project-cell state.
- If `self._scope == "global"`: no change.

The append must preserve the existing markup. Cell strings today are short markup snippets (e.g. `"[green]✔[/]"`, `" "`). Concatenating ` 🌐` (leading space) yields `"[green]✔[/] 🌐"` — safe for Rich because the new glyph sits outside any markup tag. Verify in tests via `Text.from_markup(...).plain`.

### 5.4 Column widths

Today: agent columns are `width=14` (`skill_grid.py:266`). Existing per-cell strings render in ≤ 1 visible char; adding ` 🌐` consumes 2 (glyph + leading space). Margin holds comfortably. No width change.

### 5.5 Column-info update

`Universal` already has an info popup (commit `ba7943e`). We add a short paragraph to its info copy explaining the 🌐 marker (since universal is the most-asked-about column). No new info registration for claude-code/pi (the indicator semantics are documented in spec and AGENTS.md; we don't want every column to grow info popups for one feature).

Concretely: append one paragraph to the `universal` entry in `column_info.py`. If `column_info.py` exposes the copy as a single string constant, edit it; if as structured fields, append a `notes` line. The plan step will inspect and pick the minimum-diff form.

### 5.6 Glyph choice & terminal safety

`🌐` (U+1F310 GLOBE WITH MERIDIANS) is the previously-shipped marker. Risk: emoji presentation variance across terminals — Rich renders it as text in most cases. Two safety nets:

1. Single constant `_GLOBAL_GLYPH = "🌐"` at the top of `skill_grid.py` alongside the other glyph constants — easy to swap if terminals misbehave.
2. A regression assertion in the new render test confirms the glyph survives `Text.from_markup(...).plain` round-trip.

If a future bug report says the glyph is mangled in a specific terminal, swapping `_GLOBAL_GLYPH = "G"` (or similar ASCII) is a one-line change. No fallback indirection or conditional logic in this PR.

## 6. Definition of done

- `build_skill_rows(scope="project", home=Path.home(), project=...)` populates both `(agent, "project")` and `(agent, "global")` cells for every interactive agent and every row. Global scope behaviour unchanged.
- `app._scope_to_roots()` returns `(scope, Path.home(), Path.cwd())` for project scope (i.e. `home` is no longer `None` in project mode).
- `SkillGrid._cell_glyph` suffixes ` 🌐` to the cell text when, in project scope, the row's `(agent, "global")` cell is a clean `linked=True` with no drift / no skipped.
- The indicator renders for each of `universal`, `claude-code`, `pi` independently.
- The `Universal` column-info popup mentions the 🌐 marker (short paragraph).
- Tests pass; new tests cover at least:
  - **state model**: `build_skill_rows(scope="project", home=..., project=...)` produces global cells alongside project cells; global scope unchanged.
  - **render**: in project scope, a row with a clean global link shows the cell ending in ` 🌐`; in global scope, the same row's cell does *not* show the marker.
  - **per-agent independence**: a row globally linked for `claude-code` but not `pi` shows the marker on claude-code, not on pi.
  - **drift/skipped global is not "linked"**: a row whose `(agent, "global")` cell is `drift=True` or `skipped=True with linked=False` does *not* show the marker.
  - **app wiring smoke test**: `_scope_to_roots()` returns `home` (not `None`) in project mode.
- Pre-commit hooks pass; no existing test regresses.
- Issue #188 closed by the merged PR.

## 7. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Emoji presentation varies by terminal. | Centralised constant; render-test round-trips via `Text.from_markup(...).plain`. Swap to ASCII is one-line if reported. |
| Doubled FS probes at project scope (now also stat global symlinks). | Acceptable: 3 extra `lstat`/`readlink` per row × N rows. The grid already does similar work when scope-switching; this just front-loads it. If profiling reveals a regression, gate behind `if home is not None`. |
| `home=None` callers regress. | Project-scope path in `app.py` is the only caller touched; `home=None` in project mode becomes a no-op path (no global cells populated) — global-installed indicator simply doesn't render. Documented and tested. |
| Universal column-info copy bloats / drifts from grid behaviour. | One short paragraph; copy stays in `column_info.py` next to the existing universal entry. Reviewed in self-review pass. |
| Per-agent SkillCell semantic for `(universal, "global")` is "bundle-symlink at `~/.agents/skills/<slug>` resolves to canonical" — different from claude-code/pi (which probe per-agent projections). | This is already how `_cell_for` distinguishes them (`skill_state.py:96-118`). Our spec inherits the existing semantics rather than redefining them; tests cover both branches. |

## 8. Test strategy summary

Following `~/.conventions/conventions/testing.md` floor:

- **Unit (state)** — extend `tests/test_tui/test_skill_state.py`: one new test seeding a project install AND a global install for one slug; assert `cells[(agent, "global")]` is populated and `linked` for the agents we set up. Companion test asserts global-scope build is unchanged (no project cells).
- **Render** — new test file `tests/test_tui/test_skill_grid_global_indicator.py` (mirrors the per-feature layout of `test_skill_grid_column_info.py`). Three async render tests:
  - project scope + global link → cell contains `🌐`
  - global scope + global link → cell does *not* contain `🌐`
  - per-agent independence — one agent linked globally, one not, assert marker presence/absence per column
  - drift/skipped global → marker absent
- **App wiring** — small unit test on `_scope_to_roots()` confirming project mode now returns `home=Path.home()`. May co-locate in an existing `tests/test_tui/test_scope_toggle.py` or as a new short file — plan step decides.

All assertions are deterministic string-or-state checks. No screenshot tests.

## 9. Open questions

None blocking. The two choices that could be revisited in review:

1. Per-agent vs per-row indicator — spec chooses per-agent (matches the old 🌐-on-asset-cell behaviour and the multi-harness scout finding from #86's spec).
2. Whether to update column-info copy in this PR or in a follow-up — spec chooses "in this PR, one short paragraph" so the affordance ships with its explanation.

If review prefers per-row or copy-deferred, both are scope reductions, not redesigns.

## 10. Sequence (preview of plan)

1. Extend `build_skill_rows` to also populate `(agent, "global")` cells when `scope="project"` and `home is not None`. Unit test.
2. Update `app._scope_to_roots()` to pass `Path.home()` in project mode. App-wiring unit test.
3. Add `_GLOBAL_GLYPH` constant + suffix logic in `_cell_glyph`. New render test file.
4. Update `column_info.py` universal entry copy to mention 🌐.
5. Run pre-commit + full pytest. Verify via the manual menu (no `.claude/testing.md` yet).

**Follow-up not filed yet:** reverse indicator (project-installed seen from global scope) — file iff requested in review.
