# TUI Label Consistency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Standardize user-facing TUI labels for asset types, harness names, Standard columns, and Pi extension library terminology.

**Architecture:** Add a small TUI-only display-name helper module, then route app/sidebar labels and grid headers through it. Keep persisted keys and CLI-facing catalog names unchanged.

**Tech Stack:** Python 3.12+, Textual `DataTable`, pytest/pytest-asyncio, existing `agent_toolkit_tui` widgets.

---

## Implementation Units

- Create `src/agent_toolkit_tui/display_names.py`: central TUI-visible label helpers.
- Create `tests/test_tui/test_display_names.py`: unit coverage for helper behavior.
- Modify `src/agent_toolkit_tui/app.py`: plural sidebar/content labels.
- Modify grid widgets:
  - `src/agent_toolkit_tui/widgets/skill_grid.py`
  - `src/agent_toolkit_tui/widgets/instruction_grid.py`
  - `src/agent_toolkit_tui/widgets/agent_grid.py`
  - `src/agent_toolkit_tui/widgets/mcp_grid.py`
  - `src/agent_toolkit_tui/widgets/pi_grid.py`
- Modify `src/agent_toolkit_tui/column_info.py`: Standard/modal wording uses display helpers where it names harnesses.
- Extend existing TUI tests for rendered headers and info copy.

## Task 1: Add TUI display-name helpers

**Files:**
- Create: `src/agent_toolkit_tui/display_names.py`
- Create: `tests/test_tui/test_display_names.py`

- [ ] **Step 1: Write failing helper tests**

Create `tests/test_tui/test_display_names.py`:

```python
from agent_toolkit_tui.display_names import (
    asset_type_label,
    harness_label,
    pi_extension_origin_label,
    standard_label,
)


def test_asset_type_labels_are_plural_for_navigation():
    assert asset_type_label("instruction", plural=True) == "Instructions"
    assert asset_type_label("skill", plural=True) == "Skills"
    assert asset_type_label("pi-extension", plural=True) == "Pi Extensions"
    assert asset_type_label("agent", plural=True) == "Agents"
    assert asset_type_label("mcp", plural=True) == "MCPs"


def test_asset_type_labels_are_title_case_for_row_headers():
    assert asset_type_label("instruction") == "Instruction"
    assert asset_type_label("skill") == "Skill"
    assert asset_type_label("pi-extension") == "Pi Extension"
    assert asset_type_label("agent") == "Agent"
    assert asset_type_label("mcp") == "MCP"


def test_harness_labels_hide_internal_cli_suffixes():
    assert harness_label("claude-code") == "Claude"
    assert harness_label("gemini-cli") == "Gemini"
    assert harness_label("codex") == "Codex"
    assert harness_label("opencode") == "OpenCode"
    assert harness_label("pi") == "Pi"
    assert harness_label("cursor") == "Cursor"


def test_harness_label_falls_back_to_titleized_key():
    assert harness_label("custom-harness") == "Custom Harness"


def test_standard_label_always_includes_count():
    assert standard_label(2) == "Standard (2)"
    assert standard_label(17) == "Standard (17)"


def test_pi_extension_origin_label_uses_library():
    assert pi_extension_origin_label("store-owned") == "library"
    assert pi_extension_origin_label("npm") == "npm"
    assert pi_extension_origin_label("untracked") == "untracked"
```

- [ ] **Step 2: Run helper tests to verify failure**

Run:

```bash
uv run pytest tests/test_tui/test_display_names.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agent_toolkit_tui.display_names'`.

- [ ] **Step 3: Implement helpers**

Create `src/agent_toolkit_tui/display_names.py`:

```python
"""User-facing display names for the Textual TUI.

This module is intentionally TUI-only: persisted lock keys, adapter names, CLI
arguments, and catalog identifiers stay unchanged.
"""
from __future__ import annotations

_ASSET_TYPE_SINGULAR: dict[str, str] = {
    "instruction": "Instruction",
    "skill": "Skill",
    "pi-extension": "Pi Extension",
    "agent": "Agent",
    "mcp": "MCP",
}

_ASSET_TYPE_PLURAL: dict[str, str] = {
    "instruction": "Instructions",
    "skill": "Skills",
    "pi-extension": "Pi Extensions",
    "agent": "Agents",
    "mcp": "MCPs",
}

_HARNESS_LABELS: dict[str, str] = {
    "claude-code": "Claude",
    "gemini-cli": "Gemini",
    "codex": "Codex",
    "opencode": "OpenCode",
    "pi": "Pi",
    "cursor": "Cursor",
}

_PI_EXTENSION_ORIGINS: dict[str, str] = {
    "store-owned": "library",
    "npm": "npm",
    "untracked": "untracked",
}


def _titleize_key(value: str) -> str:
    return " ".join(part.capitalize() for part in value.replace("_", "-").split("-") if part)


def asset_type_label(asset_type: str, *, plural: bool = False) -> str:
    labels = _ASSET_TYPE_PLURAL if plural else _ASSET_TYPE_SINGULAR
    return labels.get(asset_type, _titleize_key(asset_type))


def harness_label(harness: str) -> str:
    return _HARNESS_LABELS.get(harness, _titleize_key(harness))


def standard_label(count: int) -> str:
    return f"Standard ({count})"


def pi_extension_origin_label(origin: str) -> str:
    return _PI_EXTENSION_ORIGINS.get(origin, origin)
```

- [ ] **Step 4: Run helper tests to verify pass**

Run:

```bash
uv run pytest tests/test_tui/test_display_names.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit helpers**

```bash
git add src/agent_toolkit_tui/display_names.py tests/test_tui/test_display_names.py
git commit -m "test: cover TUI display label helpers"
```

## Task 2: Update app-level asset labels

**Files:**
- Modify: `src/agent_toolkit_tui/app.py`
- Create: `tests/test_tui/test_app_labels.py`

- [ ] **Step 1: Write failing sidebar/content-header tests**

Create `tests/test_tui/test_app_labels.py` with rendered sidebar labels and content header coverage:

```python
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_sidebar_uses_plural_title_case_asset_labels():
    from textual.widgets import OptionList
    from agent_toolkit_tui.app import TUIApp

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        sidebar = app.query_one("#asset-types-list", OptionList)
        labels = [str(option.prompt) for option in sidebar.options if not option.disabled]
        assert labels == ["Instructions", "Skills", "Pi Extensions", "Agents", "MCPs"]


@pytest.mark.asyncio
async def test_content_header_uses_plural_asset_label():
    from textual.widgets import Static
    from agent_toolkit_tui.app import TUIApp

    app = TUIApp()
    async with app.run_test() as pilot:
        app.action_asset_type("pi-extension")
        await pilot.pause()
        header = str(app.query_one("#content-header", Static).render())
        assert "Pi Extensions" in header
```

- [ ] **Step 2: Run app label tests to verify failure**

Run:

```bash
uv run pytest tests/test_tui/test_app_labels.py -q
```

Expected: FAIL because sidebar still renders lowercase singular labels and header uses singular labels.

- [ ] **Step 3: Update `app.py` labels**

In `src/agent_toolkit_tui/app.py`:

```python
from agent_toolkit_tui.display_names import asset_type_label
```

Replace `_ASSET_TYPE_LABELS` values with plural labels or remove the dict and call helper directly. The preferred implementation keeps no duplicate map:

```python
def _asset_type_label(asset_type: AssetType, *, plural: bool = False) -> str:
    return asset_type_label(asset_type, plural=plural)
```

Update sidebar compose block:

```python
yield Static("Asset Types", classes="rail-header")
yield OptionList(
    Option(_asset_type_label("instruction", plural=True), id="asset-type-instruction"),
    Option("─────────────", id="asset-type-separator", disabled=True),
    Option(_asset_type_label("skill", plural=True), id="asset-type-skill"),
    Option(_asset_type_label("pi-extension", plural=True), id="asset-type-pi-extension"),
    Option(_asset_type_label("agent", plural=True), id="asset-type-agent"),
    Option(_asset_type_label("mcp", plural=True), id="asset-type-mcp"),
    id="asset-types-list",
)
```

Update `_build_content_header()` so it uses plural labels:

```python
label = _asset_type_label(self._active_asset_type, plural=True)
return f"{label}  ·  {n} items"
```

Keep existing spacing/dot style if current code differs; only label source changes.

- [ ] **Step 4: Run app label tests to verify pass**

```bash
uv run pytest tests/test_tui/test_app_labels.py tests/test_tui/test_sidebar_highlight_sync.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit app label changes**

```bash
git add src/agent_toolkit_tui/app.py tests/test_tui/test_app_labels.py tests/test_tui/test_sidebar_highlight_sync.py
git commit -m "fix(tui): pluralize asset navigation labels"
```

## Task 3: Update grid headers and Standard counts

**Files:**
- Modify: `src/agent_toolkit_tui/widgets/skill_grid.py`
- Modify: `src/agent_toolkit_tui/widgets/instruction_grid.py`
- Modify: `src/agent_toolkit_tui/widgets/agent_grid.py`
- Modify: `src/agent_toolkit_tui/widgets/mcp_grid.py`
- Modify: `src/agent_toolkit_tui/widgets/pi_grid.py`
- Modify tests under `tests/test_tui/` for each grid.

- [ ] **Step 1: Write failing grid-header assertions**

Add exact rendered-label assertions near existing grid column tests:

```python
labels = [str(c.label) for c in table.columns.values()]
assert "Skill ⓘ" in labels
assert not any("SKILL" in label for label in labels)
assert any(label.startswith("Standard (") for label in labels)
assert not any("Claude Code" in label for label in labels)
assert not any("Gemini CLI" in label for label in labels)
```

For MCP global scope, assert raw keys are not visible:

```python
assert any("Claude" in s for s in labels)
assert any("Codex" in s for s in labels)
assert any("OpenCode" in s for s in labels)
assert not any("claude-code" in s for s in labels)
assert not any("opencode" in s for s in labels)
```

For Pi extensions:

```python
assert "Pi Extension ⓘ" in labels
assert "Origin" in labels
assert "Source" in labels
assert not any("EXTENSION" in label for label in labels)
```

- [ ] **Step 2: Run grid tests to verify failure**

```bash
uv run pytest \
  tests/test_tui/test_skill_grid_new_columns.py \
  tests/test_tui/test_instruction_grid.py \
  tests/test_tui/test_agent_grid.py \
  tests/test_tui/test_mcp_grid.py \
  tests/test_tui/test_pi_grid.py \
  -q
```

Expected: FAIL on current all-caps/raw-key labels.

- [ ] **Step 3: Update grid header code**

Import helpers where needed:

```python
from agent_toolkit_tui.display_names import asset_type_label, harness_label, standard_label
```

In `skill_grid.py`:

```python
from agent_toolkit_cli.skill_agents import AGENTS, get_standard_agents
```

Change headers:

```python
table.add_column(f"{asset_type_label('skill')} {_INFO_GLYPH}", width=20)
...
if agent == "standard":
    base = standard_label(len(get_standard_agents()))
else:
    base = harness_label(agent)
```

In `instruction_grid.py`, change standard and harness labels:

```python
from agent_toolkit_cli.instructions_matrix import instructions_matrix_rows


def _standard_count() -> int:
    return sum(1 for row in instructions_matrix_rows() if row["verdict"] == "native")
```

Use:

```python
table.add_column(f"{asset_type_label('instruction')} {_INFO_GLYPH}", width=22)
table.add_column(f"{standard_label(_standard_count())} {_INFO_GLYPH}", width=16)
...
display = harness_label(harness)
table.add_column(f"{display} {_INFO_GLYPH}", width=14)
```

In `agent_grid.py`:

```python
from agent_toolkit_cli.agent_adapters.standard import agents_standard_covered
```

Use:

```python
table.add_column(f"{asset_type_label('agent')} {_INFO_GLYPH}", width=22)
...
if harness == "standard":
    base = standard_label(len(agents_standard_covered(self._scope)))
else:
    base = harness_label(harness)
```

In `mcp_grid.py`, keep Standard present only where currently present, but centralize labels:

```python
if harness == "standard":
    from agent_toolkit_cli.mcp_standard import mcp_standard_covered
    base = standard_label(len(mcp_standard_covered("project")))
else:
    base = harness_label(harness)
```

Also change slug header:

```python
table.add_column(f"{asset_type_label('mcp')} {_INFO_GLYPH}", width=22)
```

In `pi_grid.py`, change slug header:

```python
table.add_column(f"{asset_type_label('pi-extension')} {_INFO_GLYPH}", width=24)
```

Keep the active scope column as `Pi ⓘ` because it is the Pi runtime column, not a harness key leak.

Also update cell-info titles and prose in `skill_grid.py`, `instruction_grid.py`, `agent_grid.py`, and `mcp_grid.py` so user-facing sentences use `harness_label(harness)`:

```python
display = harness_label(harness)
title = f"{row.slug} · {display} @ {self._scope}"
body = f"Installed.\nAgent {row.slug} is projected into {display} @ {self._scope}."
```

Leave exact CLI snippets unchanged when they need raw flags, for example `--harness claude-code`, because copy/paste correctness beats display polish inside command examples.

- [ ] **Step 4: Run grid tests to verify pass**

```bash
uv run pytest \
  tests/test_tui/test_skill_grid_new_columns.py \
  tests/test_tui/test_instruction_grid.py \
  tests/test_tui/test_agent_grid.py \
  tests/test_tui/test_mcp_grid.py \
  tests/test_tui/test_pi_grid.py \
  -q
```

Expected: PASS.

- [ ] **Step 5: Commit grid header changes**

```bash
git add src/agent_toolkit_tui/widgets tests/test_tui
git commit -m "fix(tui): normalize grid header labels"
```

## Task 4: Replace Pi extension store wording with library wording

**Files:**
- Modify: `src/agent_toolkit_tui/widgets/pi_grid.py`
- Modify: `tests/test_tui/test_pi_grid.py`

- [ ] **Step 1: Write failing Pi origin tests**

Add tests that seed a `PiExtensionRow` with `origin="store-owned"`, render the grid, and assert visible cell text:

```python
assert any("library" in str(cell) for cell in table.get_row(row_key))
assert not any("store" in str(cell).lower() for cell in table.get_row(row_key))
```

Add direct helper assertions for origin and slug info text:

```python
body = grid._origin_info_body()
assert "library-owned" in body
assert "agent-toolkit library" in body
assert "Store path" not in body
assert "store-owned" not in body

slug_body = grid._extension_info_body(row)
assert "Origin: library" in slug_body
assert "Library path:" in slug_body
assert "Store path:" not in slug_body
assert "store-owned" not in slug_body
```

If `_origin_info_body()` and `_extension_info_body()` do not exist yet, create helpers in the implementation step and test them directly.

- [ ] **Step 2: Run Pi tests to verify failure**

```bash
uv run pytest tests/test_tui/test_pi_grid.py -q
```

Expected: FAIL because current origin markup renders `store` and help text says `store-owned` / `Store path`.

- [ ] **Step 3: Update Pi origin rendering and help copy**

In `pi_grid.py`, import:

```python
from agent_toolkit_tui.display_names import pi_extension_origin_label
```

Replace `_ORIGIN_MARKUP` with:

```python
_ORIGIN_MARKUP = {
    "store-owned": "[blue]library[/]",
    "npm": "[cyan]npm[/]",
    "untracked": "[dim]untracked[/]",
}
```

Keep `_origin_glyph()` routed through `pi_extension_origin_label()` for fallback values:

```python
def _origin_glyph(self, origin: str) -> str:
    return _ORIGIN_MARKUP.get(origin, pi_extension_origin_label(origin))
```

Add helper for info text:

```python
def _origin_info_body() -> str:
    return (
        "Origin labels:\n\n"
        "[b]library-owned[/]: cloned into the agent-toolkit library;\n"
        "  managed via pi-extension add/install/update.\n"
        "[b]npm[/]: registry package in Pi settings.json packages[];\n"
        "  managed via pi-extension install (scope toggle).\n"
        "[b]untracked[/]: found in Pi's extensions/ dir but not in\n"
        "  the asset-type lock. Use pi-extension import to adopt."
    )
```

Add helper for slug info so raw origin enum values do not leak:

```python
def _extension_info_body(row: PiExtensionRow) -> str:
    body = (
        f"Pi extension [b]{row.slug}[/]\n"
        f"Origin: {pi_extension_origin_label(row.origin)}\n"
        f"Source: {row.source}"
    )
    if row.origin == "store-owned":
        from agent_toolkit_cli.pi_extension_paths import library_pi_extension_path
        ext_dir = library_pi_extension_path(row.slug)
        body += f"\nLibrary path: {ext_dir}"
    return body
```

Use helpers in `action_info()`:

```python
if col == _COL_EXTENSION:
    title = f"{row.slug} · extension"
    body = _extension_info_body(row)
elif col == _COL_ORIGIN:
    title = f"{row.slug} · origin"
    body = _origin_info_body()
```

Keep internal `row.origin == "store-owned"` checks unchanged.

- [ ] **Step 4: Run Pi tests to verify pass**

```bash
uv run pytest tests/test_tui/test_pi_grid.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Pi terminology change**

```bash
git add src/agent_toolkit_tui/widgets/pi_grid.py tests/test_tui/test_pi_grid.py
git commit -m "fix(tui): call extension store entries library-owned"
```

## Task 5: Update Standard info modal display names

**Files:**
- Modify: `src/agent_toolkit_tui/column_info.py`
- Modify: `tests/test_tui/test_column_info.py`

- [ ] **Step 1: Write failing column-info tests**

Add assertions:

```python
def test_standard_info_uses_tui_harness_display_names():
    info = get_column_info("standard", context={
        "asset_type": "skills",
        "names": ("claude-code", "gemini-cli", "codex", "opencode"),
        "global_linked": False,
    })
    text = "\n".join(info.lines)
    assert "Claude" in text
    assert "Gemini" in text
    assert "Codex" in text
    assert "OpenCode" in text
    assert "claude-code" not in text
    assert "gemini-cli" not in text
    assert "Claude Code" not in text
    assert "Gemini CLI" not in text
```

Standard modal bullets should be display-only. Exact CLI command snippets elsewhere may still include raw harness flags for copy/paste correctness.

- [ ] **Step 2: Run column-info tests to verify failure**

```bash
uv run pytest tests/test_tui/test_column_info.py -q
```

Expected: FAIL because bullets currently use `AGENTS[name].display_name`, which renders `Claude Code` and `Gemini CLI`.

- [ ] **Step 3: Update bullet display names**

In `column_info.py`, import:

```python
from agent_toolkit_tui.display_names import harness_label
```

Change bullets:

```python
bullets = [f"  • {harness_label(name)}" for name in harness_names]
```

Do not include raw keys in Standard modal prose; this modal is explanatory UI, not a CLI command block.

- [ ] **Step 4: Run column-info tests to verify pass**

```bash
uv run pytest tests/test_tui/test_column_info.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit column info copy**

```bash
git add src/agent_toolkit_tui/column_info.py tests/test_tui/test_column_info.py
git commit -m "fix(tui): use concise harness names in column info"
```

## Task 6: Full verification and PR handoff

**Files:**
- No source edits unless tests reveal regressions.

- [ ] **Step 1: Run focused TUI test suite**

```bash
uv run pytest tests/test_tui -q
```

Expected: PASS.

- [ ] **Step 2: Run full test suite**

```bash
uv run pytest -q
```

Expected: PASS.

- [ ] **Step 3: Manual TUI smoke check**

Run:

```bash
uv run agent-toolkit-tui
```

Check visually:

- Sidebar labels are `Instructions`, `Skills`, `Pi Extensions`, `Agents`, `MCPs`.
- Header reads plural asset label plus item count.
- Grid headers are title case.
- `Standard` headers all include `(N)` where visible.
- Harness headers say `Claude` and `Gemini`, not `Claude Code` / `Gemini CLI`.
- Pi extension origin cells say `library`, not `store`.

- [ ] **Step 4: Capture verification evidence**

Save command output and a screenshot if available under:

```text
assets/verification/448/
```

Use a short text file if screenshot capture is not practical:

```text
assets/verification/448/tui-label-smoke.txt
```

- [ ] **Step 5: Final commit if verification artifacts are committed by project practice**

If verification artifacts are committed in this repo, run:

```bash
git add assets/verification/448
git commit -m "test(tui): capture label consistency verification"
```

If artifacts are not committed, leave them untracked and mention their path in PR notes.
