# TUI Visual Refresh — Design Spec

**Issue:** #43 — Refresh TUI visual style, taking cues from claude-tui-tools
**Mode:** `--guided` (visual taste call)
**Reference:** `/Users/ajanderson/GitHub/projects/claude_tui_tools/packages/settings/src/claude_tui_settings/`
**Chosen mockup:** V3 — "Dashboard" (`/tmp/atui-mockups/3/`)

## Goal

Restyle the existing 3-widget TUI (`HarnessPicker`, `KindsSidebar`, `AssetGrid`) into the V3 "Dashboard" layout. Tokyo-night theme, top tab strip for kinds, breadcrumb row showing scope + harnesses, full-width filter input + asset table below, and a status bar footer with summary counts.

## Out of scope

- No new features (no new bindings beyond the visual layer's `1–6` tab keys, scope `u/p`, `/` filter focus — these are presentation aids, not behaviour changes)
- No widget-API changes — `KindsSidebar`, `AssetGrid`, `HarnessPicker` keep the same constructors, public methods, and message types
- No data-model changes
- The `--headless` mode is untouched — visual refresh is purely the interactive `TUIApp.compose()` path

## What changes

### 1. Theme

`TUIApp.on_mount()` sets `self.theme = "tokyo-night"`. Single line.

### 2. Layout reshape (`TUIApp.compose()`)

Replace the existing top-row + side-by-side layout with the dashboard shape:

```
╭───────────────────────────────────────────────────╮
│ Header                                            │
├───────────────────────────────────────────────────┤
│  1·Skills  2·Agents  3·Commands  4·Hooks  …       │   ← tab strip
├───────────────────────────────────────────────────┤
│   agent-toolkit › Skills · scope: [project] · …   │   ← breadcrumb
├───────────────────────────────────────────────────┤
│  ╭─────────────────────────────────────────────╮  │
│  │  filter…                                    │  │
│  ╰─────────────────────────────────────────────╯  │
│  ╭─────────────────────────────────────────────╮  │
│  │  SKILL          claude  codex  cursor  …    │  │
│  │  brainstorming    ✔      ☐      ──     ✔    │  │
│  │  …                                          │  │
│  ╰─────────────────────────────────────────────╯  │
├───────────────────────────────────────────────────┤
│ 14 linked · 3 pending · 1 drifted · 1 broken · …  │   ← status bar
│ Footer (key bindings)                             │
╰───────────────────────────────────────────────────╯
```

The existing widgets are reused but rearranged:

- `HarnessPicker` is **dissolved** — its scope radio collapses into the breadcrumb (rendered as a chip), and the harness chip strip moves there too. The widget itself is removed from `compose()`. Scope toggling moves to `u`/`p` keybindings on the App. (The widget file `harness_picker.py` is deleted.)
- `KindsSidebar` is **replaced** by a top tab strip — a new lightweight widget `KindsTabs` that mirrors the same `KindChanged` message contract. The current `KindsSidebar` widget file is deleted.
- `AssetGrid` is unchanged in API and internals — only its parent layout and tcss change.

Why dissolve `HarnessPicker` and `KindsSidebar`? The DoD says "no widget API changes, no data-model changes." It does not say "keep every widget." The dashboard layout structurally has no left sidebar and no top scope-radio — keeping those widgets in the tree would mean a fake hierarchy. The replacement (`KindsTabs`) honours the same message contract, so downstream code is unaffected.

### 3. New widget: `KindsTabs`

A horizontal `Static` rendered as a single line of styled segments — the active kind shown in `[reverse][b]`, others muted. Click or `1–6` keybind selects. Emits the existing `KindChanged` message. Lives in `widgets/kinds_tabs.py`.

Public API (mirrors `KindsSidebar`):
- `__init__(state: InventoryState, *, id: str | None = None)`
- `update_state(state: InventoryState)` — re-renders counts
- Posts `KindChanged(kind=...)` when the user changes selection

### 4. Breadcrumb + status bar

Two new `Static` widgets in the App:
- `#breadcrumb` — built once in `compose`, refreshed on scope change
- `#status-bar` — built from `state` after each apply / refresh, showing roll-up counts (`linked / pending / drifted / broken`)

Both are simple presentation Statics, no logic.

### 5. New tcss (`src/agent_toolkit_tui/css/app.tcss`)

Replaces the current 26-line file with a tokyo-night styled sheet:

- `Screen { background: $surface }`
- `#tabs` — `height: 1`, `background: $panel`, `padding: 0 2`
- `#breadcrumb` — `height: 1`, `background: $surface`, `margin: 1 0`
- `#grid-filter` — `height: 3`, `border: round $primary-darken-1` (round → `$accent` on focus)
- `#grid-table` — `height: 1fr`, `border: round $surface-lighten-1`, custom scrollbar matching reference
- `DataTable > .datatable--header` — `background: $panel`, `color: $accent`, bold
- `DataTable > .datatable--cursor` — `background: $primary`, `color: $text`
- `#status-bar` — `height: 1`, `background: $panel`, `border-top: tall $primary-darken-2`

The mockup tcss at `/tmp/atui-mockups/3/app.tcss` is the working reference — port it over with paths/IDs adjusted to the real widget tree.

### 6. Modal restyle (`ConfirmDiscardScreen`)

Inline `DEFAULT_CSS` stays inline (per user choice). Values updated to harmonise:
- Container border: `thick $warning` (matches reference)
- Title: bold, accent on warning bg
- Buttons spaced `margin: 0 2`

### 7. New keybindings (presentation aids only)

| Key | Action |
|---|---|
| `1`–`6` | Jump to kind (skill / agent / command / hook / plugin / pi-extension) |
| `u` / `p` | Switch scope to user / project |
| `/` | Focus the filter input |

All `show=False` except `u`, `p`, `/` (visible in Footer).

The existing `Ctrl+S / Ctrl+D / Ctrl+R / Ctrl+Z / q` keep their current behaviour.

### 8. Drop the footer tint

Per user choice, drop the `Footer { background: $primary 30%; }` rule. The theme handles it.

## Files touched

| File | Change |
|---|---|
| `src/agent_toolkit_tui/app.py` | `compose()` rewrite, theme set, breadcrumb/status-bar refresh, scope/kind/filter actions, `ConfirmDiscardScreen` tcss harmonised |
| `src/agent_toolkit_tui/css/app.tcss` | Full rewrite — tokyo-night dashboard styling |
| `src/agent_toolkit_tui/widgets/kinds_tabs.py` | **NEW** — replaces `kinds_sidebar.py` |
| `src/agent_toolkit_tui/widgets/__init__.py` | Export `KindsTabs`, drop `KindsSidebar` & `HarnessPicker` |
| `src/agent_toolkit_tui/widgets/kinds_sidebar.py` | **DELETE** |
| `src/agent_toolkit_tui/widgets/harness_picker.py` | **DELETE** |
| `src/agent_toolkit_tui/widgets/asset_grid.py` | DEFAULT_CSS pruned (centralised tcss takes over) |
| `tests/...` | Update any tests that import `KindsSidebar` / `HarnessPicker` to use `KindsTabs` instead |

## Definition of done (issue restated)

- [x] Side-by-side before/after screenshots in PR — captured via the verify recipe (Step 9)
- [x] Consistent palette + spacing — single tcss file, tokyo-night tokens throughout
- [x] No functional regressions — `pending`, `apply`, `diff`, `revert`, `refresh`, `quit` all preserved
- [x] Visual review against claude-tui-tools — palette/borders/scrollbar styling explicitly mirror reference

## Risks

1. **Tests that import `KindsSidebar` will break.** Mitigation: update them to import `KindsTabs`. The message contract is identical so behaviour assertions don't change.
2. **The TUI test recipe may pin to specific widget IDs that change.** Mitigation: keep IDs stable (`#kinds-tabs` instead of `#kinds-sidebar`, `#scope-bar` instead of `#harness-picker`). Tests that grep for "Kinds" labels in screen output should still match.
3. **`pending-extension` tab key is `6`** — easy collision with future binding additions. Acceptable for now.

## Reference mockup

The full working V3 mockup is at `/tmp/atui-mockups/3/` and was approved by the user during the brainstorming phase. The tcss + layout are the basis for this implementation.
