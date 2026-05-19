# Show user-scope indicator on project-scope views — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When viewing project-scope asset state, suffix the `🌐` glyph on each `(asset, harness)` cell that is also linked at user (global) scope, across the TUI grid, CLI `at list` text mode, and a new `agent-toolkit doctor` group.

**Architecture:** Single source of truth is the per-cell `status` field that `_build_inventory()` already produces in `src/agent_toolkit_cli/commands/_list_json.py`. A new pure helper `user_scope_covered(inventory, slug, harness)` reads `status ∈ {"linked", "linked-matches", "linked-drifted"}` from the user-scope cell. The TUI grid (which already has both scopes in memory) and the new doctor group consume this helper. CLI text `at list` reuses its existing `_install_state(..., "user", ...)` path (option A in the spec) to avoid expanding scope into the latent hook/MCP text-mode refactor; a follow-up issue captures that.

**Tech Stack:** Python 3, Textual TUI, Click CLI, pytest. Tests use `tests/conftest.py` `env` fixture (CLI) and `tests/test_tui/conftest.py` `fake_home` / `fake_repo` fixtures (TUI).

**Spec:** [`docs/superpowers/specs/2026-05-18-show-user-scope-indicator-design.md`](../specs/2026-05-18-show-user-scope-indicator-design.md)

---

## File map

| File | Action | Responsibility |
|---|---|---|
| `src/agent_toolkit_cli/commands/_list_json.py` | Modify | Add pure helper `user_scope_covered()`. |
| `tests/test_list_json.py` | Modify | Unit tests for `user_scope_covered`. |
| `src/agent_toolkit_tui/widgets/asset_grid.py` | Modify | Add `🌐` suffix in `_rebuild()` when scope=="project" and user-scope cell is linked. |
| `tests/test_tui/test_asset_grid_glyphs.py` | Modify | Add `🌐` to the Rich-markup regression set. |
| `tests/test_tui/test_asset_grid_user_scope_indicator.py` | Create | New: render test for the suffix. |
| `src/agent_toolkit_cli/commands/list.py` | Modify | Suffix `🌐` on the `project:` segment when `user_state == "✓"`. |
| `tests/test_cli_list.py` | Modify | New test for the suffix. |
| `src/agent_toolkit_cli/doctor/user_scope_coverage.py` | Create | New doctor group module. |
| `src/agent_toolkit_cli/commands/doctor.py` | Modify | Register the new group in `_GROUPS` and `_run_global`. |
| `tests/test_doctor_user_scope_coverage.py` | Create | New: test the doctor group. |
| `docs/agent-toolkit/cli.md` | Modify | One paragraph + an example row showing the `🌐` indicator. |

The five-line glyph constant is intentionally inline-only (no new module). Each surface change is independent; the helper is the only shared addition.

---

## Conventions

- **Indent / style:** match neighbouring code. The codebase uses `from __future__ import annotations`, snake_case, dataclasses; do not change file headers.
- **No comments unless the WHY is non-obvious.** Per `~/.claude/CLAUDE.md`.
- **Glyph constant:** the literal string `"🌐"` is used in three call sites (TUI render, CLI list, doctor module). Each site declares it as a module-level `_USER_SCOPE_GLYPH = "🌐"` constant so a future change is a 3-file edit, not a hunt. Do not centralise into `_list_json.py` — the spec keeps the helper there pure-data; UI glyphs belong at the rendering layer.
- **"User-scope linked" predicate:** the set `{"linked", "linked-matches", "linked-drifted"}` — already used in `asset_grid.py:189` and `:250`. Reuse this set inside the new helper.

---

## Task 1: Pure helper `user_scope_covered`

**Files:**
- Modify: `src/agent_toolkit_cli/commands/_list_json.py` (append at module bottom, before the click command definitions if any)
- Test: `tests/test_list_json.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_list_json.py`:

```python
import pytest

from agent_toolkit_cli.commands._list_json import user_scope_covered


_LINKED_STATUSES = ("linked", "linked-matches", "linked-drifted")
_NOT_LINKED_STATUSES = (
    "unlinked", "unsupported", "broken",
    "unlinked-allowlisted", "installed-not-allowlisted",
)


def _inv(*cells):
    """Build a minimal inventory dict containing one asset with given cells."""
    return {
        "assets": [
            {
                "slug": "foo",
                "kind": "skill",
                "cells": list(cells),
            }
        ]
    }


@pytest.mark.parametrize("status", _LINKED_STATUSES)
def test_user_scope_covered_true_for_linked_user_cell(status):
    inv = _inv({"harness": "claude", "scope": "user", "status": status})
    assert user_scope_covered(inv, slug="foo", harness="claude") is True


@pytest.mark.parametrize("status", _NOT_LINKED_STATUSES)
def test_user_scope_covered_false_for_non_linked_user_cell(status):
    inv = _inv({"harness": "claude", "scope": "user", "status": status})
    assert user_scope_covered(inv, slug="foo", harness="claude") is False


def test_user_scope_covered_ignores_project_scope_cells():
    inv = _inv(
        {"harness": "claude", "scope": "project", "status": "linked"},
        {"harness": "claude", "scope": "user", "status": "unlinked"},
    )
    assert user_scope_covered(inv, slug="foo", harness="claude") is False


def test_user_scope_covered_per_harness():
    inv = _inv(
        {"harness": "claude", "scope": "user", "status": "linked"},
        {"harness": "codex",  "scope": "user", "status": "unlinked"},
    )
    assert user_scope_covered(inv, slug="foo", harness="claude") is True
    assert user_scope_covered(inv, slug="foo", harness="codex") is False


def test_user_scope_covered_unknown_slug_returns_false():
    inv = _inv({"harness": "claude", "scope": "user", "status": "linked"})
    assert user_scope_covered(inv, slug="missing", harness="claude") is False


def test_user_scope_covered_unknown_harness_returns_false():
    inv = _inv({"harness": "claude", "scope": "user", "status": "linked"})
    assert user_scope_covered(inv, slug="foo", harness="opencode") is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_list_json.py -k user_scope_covered -v
```

Expected: all fail with `ImportError: cannot import name 'user_scope_covered' from 'agent_toolkit_cli.commands._list_json'`.

- [ ] **Step 3: Implement the helper**

Append to `src/agent_toolkit_cli/commands/_list_json.py` (after `_build_inventory` and before the click command, if present; otherwise at module bottom):

```python
_USER_LINKED_STATUSES = frozenset({"linked", "linked-matches", "linked-drifted"})


def user_scope_covered(inventory: dict, *, slug: str, harness: str) -> bool:
    """Return True iff the (slug, harness) user-scope cell is in a linked state.

    Pure function over the inventory dict produced by `_build_inventory()`.
    """
    for asset in inventory.get("assets", []):
        if asset.get("slug") != slug:
            continue
        for cell in asset.get("cells", []):
            if cell.get("harness") != harness:
                continue
            if cell.get("scope") != "user":
                continue
            return cell.get("status") in _USER_LINKED_STATUSES
    return False
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_list_json.py -k user_scope_covered -v
```

Expected: 6 passed (the 5 named tests, with the two parametrized ones counted as multiple).

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
uv run pytest -q
```

Expected: all tests pass (no breakage to existing inventory consumers).

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/commands/_list_json.py tests/test_list_json.py
git commit -m "feat(#86): user_scope_covered helper for cross-scope indicator"
```

---

## Task 2: TUI — render `🌐` suffix on project-scope cells

**Files:**
- Modify: `src/agent_toolkit_tui/widgets/asset_grid.py` (l.13 add constant; l.218–225 add suffix logic)
- Modify: `tests/test_tui/test_asset_grid_glyphs.py` (add `🌐` to the regression set)
- Test: `tests/test_tui/test_asset_grid_user_scope_indicator.py` (new)

- [ ] **Step 1: Write the failing render test**

Create `tests/test_tui/test_asset_grid_user_scope_indicator.py`:

```python
"""Render-level test: 🌐 suffix appears on project-scope cells whose user-scope cell is linked."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_toolkit_tui.state import AssetRow, CellState, InventoryState
from agent_toolkit_tui.widgets.asset_grid import AssetGrid


def _row(slug: str, *, claude_user: str, claude_project: str) -> AssetRow:
    return AssetRow(
        slug=slug,
        kind="skill",
        origin="first-party",
        description="",
        path=Path(f"/fake/{slug}"),
        declared_harnesses=("claude",),
        cells={
            ("claude", "user"):    CellState(status=claude_user,    target_path=None, allowlisted=True),
            ("claude", "project"): CellState(status=claude_project, target_path=None, allowlisted=True),
        },
    )


def _state(*rows: AssetRow) -> InventoryState:
    return InventoryState(toolkit_root=Path("/fake"), rows=rows, all_harnesses=("claude",))


@pytest.mark.parametrize("user_status", ["linked", "linked-matches", "linked-drifted"])
def test_project_scope_cell_gets_globe_suffix_when_user_scope_linked(user_status):
    state = _state(_row("alpha", claude_user=user_status, claude_project="linked"))
    grid = AssetGrid(state)
    grid._scope = "project"
    cell_text = grid._cell_glyph(row=state.rows[0], harness="claude")
    assert "🌐" in cell_text


def test_project_scope_cell_no_globe_when_user_scope_not_linked():
    state = _state(_row("alpha", claude_user="unlinked", claude_project="linked"))
    grid = AssetGrid(state)
    grid._scope = "project"
    cell_text = grid._cell_glyph(row=state.rows[0], harness="claude")
    assert "🌐" not in cell_text


def test_user_scope_view_never_renders_globe():
    state = _state(_row("alpha", claude_user="linked", claude_project="linked"))
    grid = AssetGrid(state)
    grid._scope = "user"
    cell_text = grid._cell_glyph(row=state.rows[0], harness="claude")
    assert "🌐" not in cell_text


def test_pending_op_takes_precedence_over_globe_suffix():
    state = _state(_row("alpha", claude_user="linked", claude_project="unlinked"))
    grid = AssetGrid(state)
    grid._scope = "project"
    grid._pending[("project", "claude", "skill", "alpha")] = "link"
    cell_text = grid._cell_glyph(row=state.rows[0], harness="claude")
    # Pending overlay should be visible; globe is dropped to keep cell readable.
    assert "[yellow]" in cell_text
    assert "🌐" not in cell_text
```

- [ ] **Step 2: Run the new test to verify it fails**

```bash
uv run pytest tests/test_tui/test_asset_grid_user_scope_indicator.py -v
```

Expected: all fail with `AttributeError: 'AssetGrid' object has no attribute '_cell_glyph'`.

- [ ] **Step 3: Implement the suffix in `asset_grid.py`**

In `src/agent_toolkit_tui/widgets/asset_grid.py`:

(a) Add the constant just after `_GLYPH` (around l.22):

```python
_USER_SCOPE_GLYPH = "🌐"
_USER_LINKED_STATUSES = frozenset({"linked", "linked-matches", "linked-drifted"})
```

(b) Extract the per-cell glyph computation in `_rebuild` into a method so the test can call it directly without driving the full DataTable. Replace the loop body inside `_rebuild` (l.215–225) so it delegates:

```python
        for row in rows:
            cells = [row.slug]
            for h in self._visible_harnesses:
                cells.append(self._cell_glyph(row=row, harness=h))
            # Schema allows duplicate (kind, slug) pairs at distinct paths
            ...
```

(c) Add the new `_cell_glyph` method (place it right after `_rebuild` so internals stay grouped):

```python
    def _cell_glyph(self, *, row: AssetRow, harness: str) -> str:
        """Compute the glyph string for a single cell, honouring pending ops
        and the user-scope coverage indicator."""
        cell = row.cells.get((harness, self._scope))
        glyph = _GLYPH.get(cell.status, "  ") if cell else "  "
        pending = self._pending.get((self._scope, harness, row.kind, row.slug))
        if pending == "link":
            return _PENDING_LINK
        if pending == "unlink":
            return _PENDING_UNLINK
        if self._scope == "project":
            user_cell = row.cells.get((harness, "user"))
            if user_cell is not None and user_cell.status in _USER_LINKED_STATUSES:
                return f"{glyph} {_USER_SCOPE_GLYPH}"
        return glyph
```

- [ ] **Step 4: Run the new test to verify it passes**

```bash
uv run pytest tests/test_tui/test_asset_grid_user_scope_indicator.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Add `🌐` to the glyph-markup regression test**

In `tests/test_tui/test_asset_grid_glyphs.py`, locate the iterable of glyphs that get round-tripped through `Text.from_markup(...).plain` (look for `_GLYPH` import or a literal list of glyph strings). Add `"🌐"` to that list. If the test file currently iterates `_GLYPH.values()` only, add a parameterised case for `_USER_SCOPE_GLYPH`:

```python
from agent_toolkit_tui.widgets.asset_grid import _USER_SCOPE_GLYPH


def test_user_scope_glyph_survives_rich_markup():
    from rich.text import Text
    assert Text.from_markup(_USER_SCOPE_GLYPH).plain == _USER_SCOPE_GLYPH
```

- [ ] **Step 6: Run the glyph-regression test**

```bash
uv run pytest tests/test_tui/test_asset_grid_glyphs.py -v
```

Expected: all pass, including the new assertion.

- [ ] **Step 7: Run the full TUI test suite**

```bash
uv run pytest tests/test_tui/ -q
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add src/agent_toolkit_tui/widgets/asset_grid.py tests/test_tui/test_asset_grid_user_scope_indicator.py tests/test_tui/test_asset_grid_glyphs.py
git commit -m "feat(#86): TUI project-scope view shows 🌐 suffix when asset linked at user scope"
```

---

## Task 3: CLI `at list` text-mode — suffix `🌐` on project segment

**Files:**
- Modify: `src/agent_toolkit_cli/commands/list.py` (around l.235 row format)
- Test: `tests/test_cli_list.py`

- [ ] **Step 1: Write the failing CLI test**

Append to `tests/test_cli_list.py`:

```python
def test_at_list_marks_project_segment_when_user_scope_linked(env, tmp_path):
    """When an asset is linked at both user and project scope, the row's
    `project:✓` segment is suffixed with 🌐 to flag user-scope coverage."""
    from click.testing import CliRunner
    from agent_toolkit_cli.cli import cli

    toolkit_root = env["toolkit_root"]
    # Seed a skill in the toolkit repo, mark it allowlisted in BOTH yamls,
    # and create the symlink at user and project scope.
    env["seed_skill"]("alpha", harnesses=["claude"])
    user_yaml = env["home"] / ".agent-toolkit.yaml"
    user_yaml.write_text("skills:\n  - alpha\n")
    project_yaml = tmp_path / ".agent-toolkit.yaml"
    project_yaml.write_text("skills:\n  - alpha\n")

    # Create user-scope symlink: ~/.claude/skills/alpha → toolkit_root/skills/alpha
    user_slot = env["home"] / ".claude" / "skills"
    user_slot.mkdir(parents=True, exist_ok=True)
    (user_slot / "alpha").symlink_to(toolkit_root / "skills" / "alpha")
    # Create project-scope symlink
    proj_slot = tmp_path / ".claude" / "skills"
    proj_slot.mkdir(parents=True, exist_ok=True)
    (proj_slot / "alpha").symlink_to(toolkit_root / "skills" / "alpha")

    result = CliRunner().invoke(
        cli, ["--toolkit-repo", str(toolkit_root), "list",
              "--project", str(tmp_path), "skill"],
    )
    assert result.exit_code == 0, result.output
    # Find the alpha row.
    alpha_row = next((l for l in result.output.splitlines() if "alpha" in l), None)
    assert alpha_row is not None, result.output
    # Both states are linked, so we expect the globe suffix on the project segment.
    assert "project:✓ 🌐" in alpha_row


def test_at_list_no_marker_when_user_scope_not_linked(env, tmp_path):
    """Same asset, only project-scope linked → no 🌐 suffix."""
    from click.testing import CliRunner
    from agent_toolkit_cli.cli import cli

    toolkit_root = env["toolkit_root"]
    env["seed_skill"]("alpha", harnesses=["claude"])
    project_yaml = tmp_path / ".agent-toolkit.yaml"
    project_yaml.write_text("skills:\n  - alpha\n")
    proj_slot = tmp_path / ".claude" / "skills"
    proj_slot.mkdir(parents=True, exist_ok=True)
    (proj_slot / "alpha").symlink_to(toolkit_root / "skills" / "alpha")

    result = CliRunner().invoke(
        cli, ["--toolkit-repo", str(toolkit_root), "list",
              "--project", str(tmp_path), "skill"],
    )
    assert result.exit_code == 0, result.output
    alpha_row = next((l for l in result.output.splitlines() if "alpha" in l), None)
    assert alpha_row is not None, result.output
    assert "🌐" not in alpha_row
```

**Fixture note for the implementing engineer:** read `tests/conftest.py` (around l.124) for the exact shape of the `env` fixture. The fixture monkeypatches `HOME` to a tmp dir and provides seed helpers. If the fixture API differs from the names used above (`env["home"]`, `env["toolkit_root"]`, `env["seed_skill"]`), adapt the test to the actual fixture API but **do not** invent new fixtures — reuse what's there. If a needed seeder doesn't exist, build the file tree inline with `tmp_path` / `home` paths.

- [ ] **Step 2: Run the new tests to verify they fail**

```bash
uv run pytest tests/test_cli_list.py -k user_scope -v
```

Expected: assertions fail because the row does not yet contain ` 🌐`.

- [ ] **Step 3: Implement the suffix in `list.py`**

Open `src/agent_toolkit_cli/commands/list.py`. Add a module-level constant near the top (after `_KIND_TITLE`):

```python
_USER_SCOPE_GLYPH = "🌐"
```

In the row-construction loop (l.235), change:

```python
row = f"  {asset.slug:<20} {h_display:<30} user:{user_state} project:{project_state}"
```

to:

```python
project_suffix = f" {_USER_SCOPE_GLYPH}" if user_state == "✓" and project_state == "✓" else ""
row = (
    f"  {asset.slug:<20} {h_display:<30} "
    f"user:{user_state} project:{project_state}{project_suffix}"
)
```

**Rationale for the `user_state == "✓" and project_state == "✓"` predicate:** the indicator's job is "you have a project-scope link AND the asset is also at user scope". If there is no project-scope link, the project view is already a `—`; adding `🌐` there would be noise. The spec frames the indicator as "the project-scope view shows that this asset is also covered globally" — i.e. you have it at both. (If review prefers "show whenever user-scope is linked regardless of project-scope state", the predicate becomes `user_state == "✓"` alone. Stick with the AND form here; it's the narrower, less noisy default.)

- [ ] **Step 4: Run the new tests to verify they pass**

```bash
uv run pytest tests/test_cli_list.py -k user_scope -v
```

Expected: 2 passed.

- [ ] **Step 5: Run all CLI list tests**

```bash
uv run pytest tests/test_cli_list.py -q
```

Expected: all pass — no regression of existing rows since the suffix is gated on the AND predicate and previous tests don't have both scopes linked.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/commands/list.py tests/test_cli_list.py
git commit -m "feat(#86): at list text mode suffixes 🌐 when project- and user-scope both linked"
```

---

## Task 4: New `doctor` group `user-scope-coverage`

**Files:**
- Create: `src/agent_toolkit_cli/doctor/user_scope_coverage.py`
- Modify: `src/agent_toolkit_cli/commands/doctor.py` (l.10–19 imports, l.23 `_GROUPS`, l.96 `_run_global` runners)
- Test: `tests/test_doctor_user_scope_coverage.py` (new)

- [ ] **Step 1: Write the failing doctor test**

Create `tests/test_doctor_user_scope_coverage.py`:

```python
"""doctor user-scope-coverage group: lists (asset, harness) pairs linked at both scopes."""
from __future__ import annotations

from pathlib import Path


def test_user_scope_coverage_lists_both_scope_pairs(env, tmp_path):
    """A skill linked at both user and project scope for one harness shows up
    once in the doctor group's findings, with a single OK-or-INFO status."""
    from agent_toolkit_cli.doctor import user_scope_coverage as g

    toolkit_root = env["toolkit_root"]
    env["seed_skill"]("alpha", harnesses=["claude"])

    user_yaml = env["home"] / ".agent-toolkit.yaml"
    user_yaml.write_text("skills:\n  - alpha\n")
    project_yaml = tmp_path / ".agent-toolkit.yaml"
    project_yaml.write_text("skills:\n  - alpha\n")

    user_slot = env["home"] / ".claude" / "skills"
    user_slot.mkdir(parents=True, exist_ok=True)
    (user_slot / "alpha").symlink_to(toolkit_root / "skills" / "alpha")
    proj_slot = tmp_path / ".claude" / "skills"
    proj_slot.mkdir(parents=True, exist_ok=True)
    (proj_slot / "alpha").symlink_to(toolkit_root / "skills" / "alpha")

    result = g.run(toolkit_root, project_root=tmp_path)
    # Informational only — never FAIL (this is not drift).
    from agent_toolkit_cli.doctor.result import Status
    assert result.status in (Status.OK, Status.WARN)
    # Exactly one finding for (alpha, claude).
    assert any("alpha" in f and "claude" in f for f in result.findings)


def test_user_scope_coverage_no_findings_when_no_overlap(env, tmp_path):
    """When nothing is linked at both scopes, the group reports OK with no findings."""
    from agent_toolkit_cli.doctor import user_scope_coverage as g
    from agent_toolkit_cli.doctor.result import Status

    toolkit_root = env["toolkit_root"]
    env["seed_skill"]("alpha", harnesses=["claude"])

    # Only project-scope linked; not user-scope.
    project_yaml = tmp_path / ".agent-toolkit.yaml"
    project_yaml.write_text("skills:\n  - alpha\n")
    proj_slot = tmp_path / ".claude" / "skills"
    proj_slot.mkdir(parents=True, exist_ok=True)
    (proj_slot / "alpha").symlink_to(toolkit_root / "skills" / "alpha")

    result = g.run(toolkit_root, project_root=tmp_path)
    assert result.status == Status.OK
    assert result.findings == []


def test_user_scope_coverage_registered_in_doctor_groups():
    """The new group is wired into the doctor command."""
    from agent_toolkit_cli.commands.doctor import _GROUPS
    assert "user-scope-coverage" in _GROUPS
```

- [ ] **Step 2: Run the new tests to verify they fail**

```bash
uv run pytest tests/test_doctor_user_scope_coverage.py -v
```

Expected: all fail (`ImportError: cannot import name 'user_scope_coverage' …`).

- [ ] **Step 3: Implement the doctor group module**

Create `src/agent_toolkit_cli/doctor/user_scope_coverage.py`:

```python
"""doctor group: list assets linked at both user and project scope.

Informational only — by spec this is NOT drift; cross-scope deconfliction is
tracked separately in #69.
"""
from __future__ import annotations

from pathlib import Path

from agent_toolkit_cli.commands._list_json import _build_inventory, user_scope_covered
from agent_toolkit_cli.doctor.result import GroupResult, Status


def run(toolkit_root: Path, *, project_root: Path | None = None) -> GroupResult:
    project_root = Path(project_root) if project_root is not None else Path.cwd()
    inventory = _build_inventory(toolkit_root, project_root)

    overlaps: list[str] = []
    _LINKED = frozenset({"linked", "linked-matches", "linked-drifted"})
    for asset in inventory.get("assets", []):
        slug = asset.get("slug", "?")
        for cell in asset.get("cells", []):
            if cell.get("scope") != "project":
                continue
            if cell.get("status") not in _LINKED:
                continue
            harness = cell.get("harness")
            if user_scope_covered(inventory, slug=slug, harness=harness):
                overlaps.append(f"{slug} ({asset.get('kind', '?')}, {harness})")

    if not overlaps:
        return GroupResult(
            name="user-scope-coverage",
            status=Status.OK,
            summary="No assets are linked at both user and project scope.",
            findings=[],
        )
    return GroupResult(
        name="user-scope-coverage",
        status=Status.OK,
        summary=f"{len(overlaps)} asset(s) linked at both scopes (informational).",
        findings=overlaps,
    )
```

- [ ] **Step 4: Register the group in `doctor.py`**

In `src/agent_toolkit_cli/commands/doctor.py`:

(a) Import alongside the others (l.10–19):

```python
from agent_toolkit_cli.doctor import (
    allowlist_audit as g_allowlist_audit,
    conventions as g_conventions,
    duplicates as g_duplicates,
    environment as g_environment,
    frontmatter as g_frontmatter,
    harness_homes as g_harness_homes,
    submodules as g_submodules,
    symlinks as g_symlinks,
    user_scope_coverage as g_user_scope_coverage,
)
```

(b) Add to `_GROUPS` (l.23) — append:

```python
_GROUPS = (
    "environment", "symlink-integrity", "conventions", "submodule-health",
    "frontmatter", "duplicates", "harness-homes", "allowlist-audit", "mcps",
    "user-scope-coverage",
)
```

(c) Add to `_run_global` runners (l.96) — append before the `group_name` filter:

```python
    runners: list[tuple[str, callable]] = [
        ("environment", lambda: g_environment.run(root)),
        ("symlink-integrity", lambda: g_symlinks.run(root, harness=harness)),
        ("conventions", lambda: g_conventions.run(root, harness=harness)),
        ("submodule-health", lambda: g_submodules.run(root)),
        ("frontmatter", lambda: g_frontmatter.run(root)),
        ("duplicates", lambda: g_duplicates.run(root)),
        ("harness-homes", lambda: g_harness_homes.run()),
        ("allowlist-audit", lambda: g_allowlist_audit.run(root, project_root=Path.cwd())),
        ("mcps", lambda: g_mcps.run(root, harness=harness, scope=scope, project_root=Path.cwd())),
        ("user-scope-coverage", lambda: g_user_scope_coverage.run(root, project_root=Path.cwd())),
    ]
```

- [ ] **Step 5: Run the new tests to verify they pass**

```bash
uv run pytest tests/test_doctor_user_scope_coverage.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Run the full doctor test set**

```bash
uv run pytest tests/test_doctor* -q
```

Expected: all pass. If `tests/test_doctor_groups.py` enumerates `_GROUPS`, it will see the new entry; verify it still passes (it should, since the new group is informational-only and follows the same `GroupResult` shape).

- [ ] **Step 7: Commit**

```bash
git add src/agent_toolkit_cli/doctor/user_scope_coverage.py src/agent_toolkit_cli/commands/doctor.py tests/test_doctor_user_scope_coverage.py
git commit -m "feat(#86): doctor user-scope-coverage group lists assets linked at both scopes"
```

---

## Task 5: Doc update

**Files:**
- Modify: `docs/agent-toolkit/cli.md`

- [ ] **Step 1: Locate the `at list` section**

```bash
grep -n "^## " docs/agent-toolkit/cli.md | head
```

- [ ] **Step 2: Add one paragraph + example row**

Under the `at list` section (or the most appropriate sub-section discovered in step 1), add:

```markdown
### Cross-scope coverage indicator

When the same asset is linked at both user and project scope, the project
segment of the row carries a 🌐 suffix to flag the redundancy. Example:

    alpha                [claude]                       user:✓ project:✓ 🌐

The indicator is informational only — it does not block or warn. (Policy
enforcement of cross-scope installs is tracked separately in issue #69.)
The same indicator appears in the TUI's project-scope grid view and in the
`agent-toolkit doctor user-scope-coverage` group output.
```

- [ ] **Step 3: Commit**

```bash
git add docs/agent-toolkit/cli.md
git commit -m "docs(#86): document cross-scope coverage indicator in at list reference"
```

---

## Task 6: File the follow-up issue noted in the spec

The spec's § 5.3.2 option-A choice leaves a latent hook/MCP-correctness gap in CLI text-mode (`at list` reads symlinks directly instead of consuming `_build_inventory`). File this as a follow-up so we don't lose track.

- [ ] **Step 1: File the issue**

```bash
gh issue create \
  --title "CLI \`at list\` text mode should consume _build_inventory, not parallel _install_state" \
  --label "type:chore" \
  --assignee "@me" \
  --body "$(cat <<'EOF'
## Goal
Unify CLI `at list` text mode with the shared `_build_inventory()` codepath so hook and MCP user-scope installs are reported correctly in text mode.

## Context
Today `commands/list.py` `_install_state()` only checks symlink presence. For hooks and MCPs the "install" is a JSON entry in a harness config file, not a symlink, so `_install_state` will report `—` even when the hook/MCP is in fact installed. The TUI and `--format=json` consumers go through `_build_inventory()` and are correct.

This was flagged during work on #86 (cross-scope visual indicator). #86 used option A (reuse the existing parallel `_install_state` path) to keep that PR focused; this issue captures option B.

## Out of scope
- Changing `--format=json` output (already correct).
- Touching the TUI render path.
- Anything in #69 (policy enforcement).

## Definition of done
- `commands/list.py` text mode consumes `_build_inventory()` directly.
- `_install_state` is removed (or shrunk to a thin per-cell formatter).
- Test added: `at list` for a Claude hook installed at user scope shows `user:✓` in text mode.
- Test added: `at list` for a Codex MCP installed at user scope shows `user:✓` in text mode.

Discovered in: #86
EOF
)"
```

- [ ] **Step 2: Note the issue number**

Capture the URL/number printed by `gh issue create`. Reference it from the comment to add in step 3.

- [ ] **Step 3: Add reference comment back to the spec (no commit yet — bundled with the next task)**

Add a single line to the bottom of `docs/superpowers/specs/2026-05-18-show-user-scope-indicator-design.md`:

```markdown
**Follow-up filed:** #<NEW_ISSUE_NUMBER> — unify `at list` text mode with `_build_inventory()`.
```

- [ ] **Step 4: Commit the spec amendment**

```bash
git add docs/superpowers/specs/2026-05-18-show-user-scope-indicator-design.md
git commit -m "docs(#86): record follow-up issue # for at list refactor"
```

---

## Task 7: Final verification pass

- [ ] **Step 1: Run the entire test suite**

```bash
uv run pytest -q
```

Expected: all green.

- [ ] **Step 2: Smoke-test the CLI by hand**

```bash
uv run agent-toolkit-cli --toolkit-repo ~/GitHub/agent-toolkit list skill | head -20
uv run agent-toolkit-cli --toolkit-repo ~/GitHub/agent-toolkit doctor --group user-scope-coverage
```

Expected: at least one row demonstrates the 🌐 suffix if you have a skill linked at both scopes locally; doctor group prints OK with zero findings if you don't. Capture both outputs to `assets/verification/86/manual-cli.log` for the PR.

- [ ] **Step 3: Smoke-test the TUI**

```bash
uv run agent-toolkit-cli --toolkit-repo ~/GitHub/agent-toolkit tui
```

In the TUI: switch to project scope. If any asset is linked at both scopes, confirm the 🌐 suffix renders in its cell. Quit. Capture a screenshot or terminal-recording snippet to `assets/verification/86/manual-tui.png` (or `.log`).

(If your local environment has nothing linked at both scopes, document that and rely on the unit + render tests for coverage; do not fabricate state.)

- [ ] **Step 4: Lefthook / pre-commit final pass**

```bash
git status
# Confirm nothing uncommitted unexpectedly.
```

If anything is dangling, decide deliberately: either commit with a tidy message or revert. No mystery work-in-progress.

---

## Self-review checklist (engineer ticks before handing back)

- [ ] Each spec § 6 DoD bullet has a corresponding task: helper (T1) · TUI (T2) · CLI text (T3) · doctor (T4) · all 7 kinds covered transitively (T1 helper is kind-agnostic; T2/T3/T4 consume the same `_build_inventory()` cells; pi-extension's user-scope view exemption is implicit since `_PROJECT_TARGETS` excludes it).
- [ ] Glyph `🌐` survives Rich markup (T2 step 5).
- [ ] No file changes outside the table at the top of this plan.
- [ ] All new tests deterministic (no sleeps, no clock, no network).
- [ ] No `# TODO` left behind in production code.
- [ ] Follow-up issue filed (T6) and referenced from the spec.
