# Full-Catalog Main-Harness Chooser in Command Palette Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Settings modal with direct, persisted command-palette choices for themes and full-catalog main harnesses.

**Architecture:**
1. **Composition & Settings** — Split `MAIN_HARNESSES` into `DEFAULT_MAIN_HARNESSES` (today's eight fresh defaults) and `MAIN_HARNESS_CANDIDATES` (all real catalog harnesses where `show_in_standard_list=True`). Update per-asset composition helpers to intersect selected candidates with each asset's real support set (including Codex on Commands).
2. **Palette Providers & Wiring** — Add `PersistentThemeProvider` and `HarnessCommandProvider`. Inherit/yield `Theme` and `Main harnesses` system commands. Choosing a theme or toggling a harness updates `TuiSettings` and persists atomically.
3. **Pending Edit Protection & All-Grid Safety** — Create an app-level `_get_all_pending_edits()` enumeration across all six grids (`InstructionGrid`, `SkillGrid`, `CommandGrid`, `PiGrid`, `AgentGrid`, `McpGrid`). Prompt with a confirmation modal before applying main-harness toggles if any grid has queued edits; use the same helper in `action_quit()` and `_refresh_pending_label()`.
4. **Modal Cleanup** — Delete `src/agent_toolkit_tui/screens/settings.py`, `SettingsCommandProvider`, and screen-specific modal tests.

**Spec:** `docs/superpowers/specs/2026-07-28-491-main-harness-palette.md`

**Tech Stack:** Python 3.13, Textual `Provider` / `CommandPalette` / `SystemCommand`, pytest + pytest-asyncio.

---

## Implementation Units

- Modify `src/agent_toolkit_tui/composition.py` — `DEFAULT_MAIN_HARNESSES`, `MAIN_HARNESS_CANDIDATES`, support-aware per-asset functions.
- Modify `src/agent_toolkit_tui/settings.py` — default to `DEFAULT_MAIN_HARNESSES`, validate against `MAIN_HARNESS_CANDIDATES`.
- Modify `src/agent_toolkit_tui/app.py` — system commands, `PersistentThemeProvider`, `HarnessCommandProvider`, all-grid pending helper, modal confirmation.
- Delete `src/agent_toolkit_tui/screens/settings.py` and delete `tests/test_tui/test_settings_screen.py`.
- Tests: `tests/test_tui/test_composition.py`, `tests/test_tui/test_settings_persistence.py`, `tests/test_tui/test_main_harness_palette.py`.
- Documentation: `docs/agent-toolkit/tui-settings.md`, `docs/agent-toolkit/tui.md`.

---

## Task 1: Composition & Settings Constants

**Files:**
- Modify: `src/agent_toolkit_tui/composition.py`
- Modify: `src/agent_toolkit_tui/settings.py`
- Modify/Extend: `tests/test_tui/test_composition.py`, `tests/test_tui/test_settings_persistence.py`

- [ ] **Step 1: Write failing tests for composition and settings split**

Update `tests/test_tui/test_composition.py` and `tests/test_tui/test_settings_persistence.py` to test:
- `DEFAULT_MAIN_HARNESSES` holds the 8 fresh defaults in canonical order.
- `MAIN_HARNESS_CANDIDATES` contains all real `AGENTS` (and excludes `standard`, `standard-skill`, `standard-agent`).
- `commands_main` intersects with `COMMAND_SUPPORTED_HARNESSES` (including `codex`).
- `settings.load()` filters known harnesses against `MAIN_HARNESS_CANDIDATES`.

```bash
uv run pytest tests/test_tui/test_composition.py tests/test_tui/test_settings_persistence.py -q
```

- [ ] **Step 2: Implement composition & settings updates**

In `composition.py`:
- Define `DEFAULT_MAIN_HARNESSES` and `MAIN_HARNESS_CANDIDATES`.
- Update `effective_main_harnesses()` to preserve catalog order across `MAIN_HARNESS_CANDIDATES`.
- Update `skills_nonstandard_main`, `instructions_nonstandard_main`, `agents_nonstandard_main`, `mcp_nonstandard_main`, and `commands_main`.

In `settings.py`:
- Import `DEFAULT_MAIN_HARNESSES` and `MAIN_HARNESS_CANDIDATES`.
- Set `TuiSettings.harnesses` default to `DEFAULT_MAIN_HARNESSES`.
- Validate/filter effective and unknown harnesses against `MAIN_HARNESS_CANDIDATES`.

- [ ] **Step 3: Pass tests**

```bash
uv run pytest tests/test_tui/test_composition.py tests/test_tui/test_settings_persistence.py -q
```

---

## Task 2: All-Grid Pending Enumeration and Protection

**Files:**
- Modify: `src/agent_toolkit_tui/app.py`
- Tests: `tests/test_tui/test_app_pending.py` or `tests/test_tui/test_main_harness_palette.py`

- [ ] **Step 1: Add app helper `_get_all_pending_edits()`**

In `TUIApp`:
- Implement `_get_all_pending_edits()` returning all pending keys across all 6 grids (`#instruction-grid`, `#skill-grid`, `#command-grid`, `#pi-grid`, `#agent-grid`, `#mcp-grid`).
- Update `_refresh_pending_label()` and `action_quit()` to use this all-grid helper.

- [ ] **Step 2: Add pending check before main harness toggle**

When toggling a main harness:
- Check `n_pending = len(self._get_all_pending_edits())`.
- If `n_pending > 0`, push `ConfirmDiscardScreen(n_pending, message=...)`.
- If confirmed, call `apply_harness_settings(...)`.
- If cancelled/escaped or save fails, preserve pending edits and existing selection.

---

## Task 3: Command Palette Theme & Main Harness Providers

**Files:**
- Modify: `src/agent_toolkit_tui/app.py`
- Create: `tests/test_tui/test_main_harness_palette.py`

- [ ] **Step 1: Implement `PersistentThemeProvider` and `search_themes()`**

- `PersistentThemeProvider` yields available themes; selecting one calls `TUIApp.apply_theme_setting(theme_name)`.
- Override `TUIApp.search_themes()` to push `CommandPalette(providers=[PersistentThemeProvider])`.

- [ ] **Step 2: Implement `HarnessCommandProvider` and `get_system_commands()`**

- Yield `SystemCommand("Main harnesses", ..., self.action_main_harnesses)`.
- `HarnessCommandProvider` lists candidates from `MAIN_HARNESS_CANDIDATES`.
- Shows `[x]` / `[ ]` selection marker and display label. Matches key or label.
- Selection executes direct toggle per result.

- [ ] **Step 3: Remove Settings modal & screen**

- Delete `src/agent_toolkit_tui/screens/settings.py`.
- Delete `SettingsCommandProvider` and `action_settings` from `app.py`.
- Delete `tests/test_tui/test_settings_screen.py`.

---

## Task 4: Documentation & Regression Verification

**Files:**
- Modify: `docs/agent-toolkit/tui-settings.md`, `docs/agent-toolkit/tui.md`.

- [ ] **Step 1: Update documentation**

Update user docs to reflect palette-based theme and main-harness toggles.

- [ ] **Step 2: Run full regression suite**

```bash
uv run pytest -q
```

- [ ] **Step 3: Capture manual QA visual proof**

Capture screenshots/verdicts under `assets/verification/issue-491/`.
