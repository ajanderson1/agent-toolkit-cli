# TUI Settings Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A palette-launched Settings screen that persists a theme and a main-harness selection to `~/.agent-toolkit/tui-settings.json`, applies both live, and fails loudly on bad state.

**Architecture:** Three layers, built and tested bottom-up.

1. **Persistence** — a new `agent_toolkit_tui/settings.py`: a `TuiSettings` dataclass, `load()` / `save()`, schema validation, and a diagnostics list for the status bar. Pure, no Textual.
2. **Composition** — `composition.py` gains `effective_main_harnesses()` and per-asset helpers that take the selection as a parameter. The three source constants stay immutable; the TUI filters a copy.
3. **UI** — `screens/settings.py` (a `ModalScreen`), a palette `Provider`, and the `app.py` wiring that applies a change and rebuilds columns.

**Spec:** `docs/superpowers/specs/2026-07-28-480-tui-settings-screen.md`

**Depends on #478 and #479.** #478 makes column-header construction shared and #479 makes column info per-`(column, asset_type)`. Changing which columns exist *before* those land means both will be re-plumbed against a moving target. Build order is #478 → #479 → #480.

**Tech Stack:** Python 3.13-compatible, stdlib `json` (no new dependency), Textual `ModalScreen` / `Provider` / `Checkbox` / `Select`, pytest + pytest-asyncio.

---

## Implementation Units

- Create `src/agent_toolkit_tui/settings.py` — schema, load/save, diagnostics.
- Modify `src/agent_toolkit_tui/composition.py` — selection-aware helpers.
- Modify `src/agent_toolkit_tui/skill_state.py`, `agent_state.py` — replace import-time constants with call-time derivation.
- Create `src/agent_toolkit_tui/screens/settings.py` — the screen.
- Modify `src/agent_toolkit_tui/app.py` — palette provider, theme application, live rebuild, diagnostics surfacing.
- Tests: `tests/test_tui/test_settings_persistence.py`, `test_settings_screen.py`, and extensions to `test_composition.py`.

## Task 1: Persistence layer, test-first

**Files:**
- Create: `tests/test_tui/test_settings_persistence.py`
- Create: `src/agent_toolkit_tui/settings.py`

- [x] **Step 1: Write the failing persistence tests**

Create `tests/test_tui/test_settings_persistence.py` covering, with
`monkeypatch.setenv("AGENT_TOOLKIT_TUI_SETTINGS", str(tmp_path / "s.json"))`:

```python
def test_missing_file_returns_defaults_without_diagnostics(...)
    # gruvbox + full MAIN_HARNESSES, diagnostics == []

def test_round_trip(...)
    # save(theme="nord", harnesses=("pi",)) then load() returns exactly that

def test_malformed_json_returns_defaults_with_loud_diagnostic(...)
    # write "{not json", assert defaults AND a diagnostic naming the path

def test_unknown_schema_returns_defaults_with_loud_diagnostic(...)
    # {"schema": "agent-toolkit-tui-settings/v99"} -> defaults + diagnostic

def test_unknown_harness_key_is_retained_but_not_rendered(...)
    # persisted ["pi", "ghost-harness"] -> effective == ("pi",), diagnostic
    # names ghost-harness, and a save() round-trip STILL contains it (R6)

def test_unavailable_theme_falls_back_with_diagnostic(...)

def test_empty_selection_is_legal(...)
    # [] is a valid selection, no diagnostic

def test_env_override_is_honoured(...)
def test_default_path_is_under_agent_toolkit_home(...)
    # str(default_path()).endswith(".agent-toolkit/tui-settings.json")
```

```bash
uv run pytest tests/test_tui/test_settings_persistence.py -q
```

Expected: `ImportError` — `settings.py` does not exist. Correct red.

- [x] **Step 2: Implement `settings.py`**

Key shapes:

```python
SCHEMA = "agent-toolkit-tui-settings/v1"
DEFAULT_THEME = "gruvbox"


@dataclass(frozen=True)
class TuiSettings:
    theme: str
    harnesses: tuple[str, ...]        # effective, filtered to MAIN_HARNESSES
    unknown_harnesses: tuple[str, ...]  # retained verbatim for lossless save
    diagnostics: tuple[str, ...]        # non-empty => show in the status bar


def default_path(env: Mapping[str, str] | None = None) -> Path:
    """~/.agent-toolkit/tui-settings.json, or $AGENT_TOOLKIT_TUI_SETTINGS.

    Sibling to the existing *-lock.json files; see _paths_core for the
    precedent this mirrors.
    """
```

`load()` never raises for a *user-data* problem — it returns defaults plus a
diagnostic. It **does** propagate genuine `OSError` other than "not found"
(a permissions problem is a real fault, not bad user data).

`save()` writes `{"schema": SCHEMA, "theme": ..., "harnesses": [...]}` with
`unknown_harnesses` merged back into `harnesses`, so an unrecognised key
survives the round-trip (R6). Write atomically (temp file + `os.replace`).

- [x] **Step 3: Green + commit**

```bash
uv run pytest tests/test_tui/test_settings_persistence.py -q
git add src/agent_toolkit_tui/settings.py tests/test_tui/test_settings_persistence.py
git commit -m "feat(tui): persisted settings schema v1"
```

Include the `Device:` trailer.

## Task 2: Make composition selection-aware

**Files:**
- Modify: `src/agent_toolkit_tui/composition.py`
- Modify: `src/agent_toolkit_tui/skill_state.py`, `src/agent_toolkit_tui/agent_state.py`
- Modify: `tests/test_tui/test_composition.py`

- [x] **Step 1: Extend the invariant test to a non-default selection**

In `tests/test_tui/test_composition.py`, add:

```python
@pytest.mark.parametrize("selection", [
    MAIN_HARNESSES,                    # default
    ("claude-code", "pi"),             # narrow
    (),                                # empty is legal (spec R6)
])
def test_coverage_invariant_holds_for_any_selection(selection):
    """Every SELECTED harness is either standard-covered or has its own
    column, for every asset type it supports (#480 R8)."""


def test_selection_filters_but_never_adds():
    """A harness with no adapter for an asset type gains no column just by
    being ticked (#480 R4)."""


def test_selection_reaches_mcp_and_command_columns():
    """The three sources are reconciled: unticking codex removes it from the
    MCP grid too, and unticking gemini-cli from the Commands grid (#480 R5)."""


def test_standard_coverage_is_not_affected_by_selection():
    """What the standard slot covers is a filesystem fact, not a preference."""
```

```bash
uv run pytest tests/test_tui/test_composition.py -q
```

Expected: FAIL — the helpers take no selection yet.

- [x] **Step 2: Add selection parameters**

Give each helper an optional `selection: tuple[str, ...] | None = None`
parameter defaulting to `MAIN_HARNESSES` (so every existing caller is
unchanged), and intersect **after** the existing support/coverage rules so the
filter can never add:

```python
def skills_nonstandard_main(selection: tuple[str, ...] | None = None) -> tuple[str, ...]:
    chosen = MAIN_HARNESSES if selection is None else selection
    return tuple(n for n in MAIN_HARNESSES if not AGENTS[n].is_standard and n in chosen)
```

Same shape for `instructions_nonstandard_main`, `agents_nonstandard_main`,
`mcp_nonstandard_main` (filtering within `_MCP_HARNESSES`), and a new
`commands_main(selection)` filtering within `DEFAULT_HARNESSES`.

**Do not mutate the three constants.** Iterate over the constant and filter —
`DEFAULT_HARNESSES` in particular belongs to `agent_toolkit_cli` and must stay
untouched (spec R7).

- [x] **Step 3: Kill the import-time snapshots**

`skill_state.INTERACTIVE_AGENTS` (`skill_state.py:48`) and
`agent_state.INTERACTIVE_HARNESSES` (`agent_state.py:37`) are module-level
tuples evaluated at import. A settings change cannot move them, so convert each
to a function (`interactive_agents(selection=None)` /
`interactive_harnesses(scope, selection=None)`) and update callers.

```bash
rg -n "INTERACTIVE_AGENTS|INTERACTIVE_HARNESSES" src/ tests/
```

Every hit must become a call. Note `agent_state.py:37` also freezes
`agents_nonstandard_main("global")` — pass the real scope while you are here,
which fixes the latent per-scope inconsistency #478 deliberately left alone.
Say so in the PR body; it is a behaviour change, small but real.

Tests import these names — update them rather than keeping a compatibility
alias, so no caller silently keeps the frozen value.

- [x] **Step 4: Green + commit**

```bash
uv run pytest tests/test_tui -q
git add src/agent_toolkit_tui tests/test_tui
git commit -m "feat(tui): selection-aware column composition"
```

## Task 3: The settings screen and palette entry

**Files:**
- Create: `src/agent_toolkit_tui/screens/settings.py`
- Modify: `src/agent_toolkit_tui/app.py`
- Create: `tests/test_tui/test_settings_screen.py`

- [x] **Step 1: Write the failing screen tests**

```python
async def test_palette_exposes_settings_command(...)
    # the app's command provider yields a hit matching "settings"

async def test_settings_screen_opens_and_closes(...)

async def test_theme_change_applies_and_persists(...)
    # select a theme -> app.theme changes AND the file round-trips

async def test_unticking_a_harness_removes_its_column(...)
    # untick pi -> the skills grid no longer has a "Pi" header, and the
    # agents grid loses it too (spec R5: one setting, all tabs)

async def test_standard_covered_harness_is_shown_as_no_op(...)
    # a standard-covered harness is labelled as having no own column to hide

async def test_unticking_everything_leaves_a_usable_grid(...)
    # slug + Standard + State + Source still render; no exception

async def test_bad_settings_file_surfaces_a_status_bar_notice(...)
```

- [x] **Step 2: Build the screen**

`SettingsScreen(ModalScreen[None])` with the `ConfirmDiscardScreen` /
`ColumnInfoModal` chrome idiom already in the codebase (`escape` closes):

- a `Select` (or `OptionList`) of `self.app.available_themes` — never a
  hardcoded list (spec R3);
- a `Checkbox` per `MAIN_HARNESSES` member, labelled with `harness_label()`,
  and for standard-covered harnesses an inline note that unticking has no
  visible effect on that asset type (spec R4);
- Save / Cancel.

Apply on save: write via `settings.save()`, set `self.app.theme`, then rebuild
the grids.

- [x] **Step 3: Register the palette command**

Add a `Provider` subclass yielding a `Settings` hit and register it on
`TUIApp.COMMANDS`. Per spec R2 there is **no** keybinding — do not add one.

Verify the palette is reachable in this Textual version:

```bash
uv run python -c "from textual.app import App; print(App.COMMANDS)"
```

- [x] **Step 4: Apply settings at startup**

In `on_mount`, load settings before `_show_asset_type`, apply the theme, and
push any `diagnostics` into the status bar. Replace the bare
`try/except Exception` around the theme assignment (`app.py:213-215`) — an
invalid persisted theme is already handled by `settings.load()`, so a raw
exception here is a genuine fault and must not be swallowed.

- [x] **Step 5: Rebuild columns on change**

A selection change must rebuild every grid's columns, not just the visible one
— otherwise a hidden tab keeps stale columns until its next refresh. Route
through the existing per-asset refresh helpers and confirm each grid's
`set_rows`/`_rebuild` re-derives its column list from the now-parameterised
composition helpers.

Preserve pending queues where the existing contract allows (`set_rows` clears
by contract — say so in the PR body rather than silently losing a user's queued
toggles after a settings change).

- [x] **Step 6: Green + commit**

```bash
uv run pytest tests/test_tui/test_settings_screen.py tests/test_tui -q
git add src/agent_toolkit_tui tests/test_tui
git commit -m "feat(tui): settings screen from the command palette"
```

## Task 4: Documentation

- [x] **Step 1: Document the new schema**

`docs/agent-toolkit/` already documents `skill-lock.md`. Add
`tui-settings.md`: the file location, the env override, every field, the v1
schema, the failure behaviours from R6, and the explicit statement that **the
CLI does not read it** (spec R7).

- [x] **Step 2: Note it in AGENTS.md**

Add `tui-settings.json` to the code map so the next agent finds it.

- [x] **Step 3: Commit**

```bash
git add docs AGENTS.md
git commit -m "docs: tui-settings.json schema v1"
```

## Task 5: Regression sweep and visual judgment

- [x] **Step 1: Full suite**

```bash
uv run pytest -q
```

- [x] **Step 2: Constant-mutation scan**

```bash
rg -n "MAIN_HARNESSES|_MCP_HARNESSES|DEFAULT_HARNESSES" src/
```

Every hit must be a **read**. No assignment, no `list(...)` mutation, and
nothing in `src/agent_toolkit_cli/` may import from `agent_toolkit_tui`.

```bash
rg -n "agent_toolkit_tui" src/agent_toolkit_cli/
```

Expected: no hits. This is the spec R7 boundary.

- [x] **Step 3: CLI determinism check**

With a non-default selection persisted, confirm the CLI is unaffected:

```bash
uv run agent-toolkit-cli skill list
uv run agent-toolkit-cli skill status
```

Output must be byte-identical to a run with the settings file removed. This is
the load-bearing check for R7 — if it differs, stop.

- [x] **Step 4: Manual visual check**

```bash
uv run agent-toolkit-tui
```

1. `ctrl+p` → `Settings` opens the screen.
2. Change the theme; it applies immediately; restart; it persisted.
3. Untick a non-standard harness (e.g. Pi); its column disappears from **every**
   tab that had it; restart; still gone.
4. Untick a standard-covered harness; the screen says it has no own column;
   nothing changes visually.
5. Untick everything; grids still render slug + Standard + State + Source.
6. Corrupt the file (`echo '{' > ~/.agent-toolkit/tui-settings.json`); relaunch;
   defaults load **and** a status-bar notice names the file.
7. Hand-add `"ghost-harness"` to the file; relaunch; notice shown, and the key
   is still in the file afterwards.

Screenshots into `assets/verification/issue-480/`, one-line visual verdict in
the PR body per `~/.conventions/conventions/testing.md`.

- [x] **Step 5: Final commit**

```bash
git add -A src/agent_toolkit_tui tests docs
git commit -m "test(tui): settings persistence and column filtering"
```

## Risk controls

- Do not start before #478 and #479 land.
- Do not add a new runtime dependency. Use stdlib `json`; `tomlkit` is for the
  foreign Codex config, not toolkit state.
- Do not mutate `MAIN_HARNESSES`, `_MCP_HARNESSES`, or `DEFAULT_HARNESSES`.
- Do not let `agent_toolkit_cli` read the settings file or import from
  `agent_toolkit_tui`. If a CLI behaviour seems to need it, stop and escalate —
  that is a spec-level change, not an implementation detail.
- Do not drop unknown harness keys on save; retention is required by R6.
- Do not let a bad settings file crash launch, and do not let it fail silently
  either. Both are failures.
- Do not add a keybinding for the settings screen.
- Do not expand the tickbox list to the full `AGENTS` catalog; that reverses the
  #351 long-tail decision.
- Do not persist scope, filter text, or pending queues in v1 — schema creep on
  a brand-new file is how it becomes unversionable.

## Self-review checklist

- Spec coverage: R1 Task 1; R2 Task 3 Step 3; R3 Task 3 Steps 2 + 4; R4 Task 2
  Step 2 + Task 3 Step 2; R5 Task 2 Step 2 + `test_selection_reaches_mcp_and_command_columns`;
  R6 the whole of Task 1 Step 1; R7 Task 5 Steps 2–3; R8 Task 2 Step 1.
- Test-first: Tasks 1, 2, and 3 each land failing tests before implementation.
- Scope guard: no file under `src/agent_toolkit_cli/` is modified.
- New-schema obligations: versioned marker, documented in `docs/agent-toolkit/`,
  lossless round-trip, loud failure. All four are explicit steps.
- Placeholder scan: Task 1 and Task 3 test names are signatures to fill from the
  named existing idioms; no `TODO(...)` or `<...>` remains.
