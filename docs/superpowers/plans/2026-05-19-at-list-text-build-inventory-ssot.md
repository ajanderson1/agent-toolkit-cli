# `at list` text-mode unification + `USER_LINKED_STATUSES` SSOT — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `at list` text mode adapter-aware by routing it through `_build_inventory()` (so hook/MCP user-scope installs are reported correctly), and collapse the triplicated `_USER_LINKED_STATUSES` constant into a single SSOT in `agent_toolkit_cli._support`.

**Architecture:**
- Move `USER_LINKED_STATUSES` (public name, no leading underscore) into `agent_toolkit_cli._support` next to `ALL_HARNESSES`/`ALL_KINDS`. The three current declaration sites import from there.
- Rewrite the text-mode loop in `commands/list.py` to call `_build_inventory(...)` once, then aggregate per-scope status into the existing `user:✓/—` `project:✓/—` glyphs via a small helper. Delete `_install_state()`.
- The 🌐 cross-scope marker reuses `USER_LINKED_STATUSES` membership tests.

**Tech Stack:** Python 3.11+, Click, pytest, `CliRunner`, frozen-set membership checks, existing inventory dict shape from `_build_inventory()`.

---

## File Structure

| File | Change |
|---|---|
| `src/agent_toolkit_cli/_support.py` | **Add** `USER_LINKED_STATUSES` constant + brief docstring |
| `src/agent_toolkit_cli/commands/_list_json.py` | **Replace** local `_USER_LINKED_STATUSES` with import re-export; `user_scope_covered()` uses imported name |
| `src/agent_toolkit_cli/doctor/user_scope_coverage.py` | **Replace** local `_USER_LINKED_STATUSES` with import |
| `src/agent_toolkit_tui/widgets/asset_grid.py` | **Replace** local `_USER_LINKED_STATUSES` (L31) with import; rename five usages (L127, 143, 192, 254, 265) to `USER_LINKED_STATUSES` |
| `src/agent_toolkit_cli/commands/list.py` | **Rewrite** text-mode render loop to consume `_build_inventory()`; **delete** `_install_state()` (L38-73); drop the `_asset_harnesses` and `harness_target_dirs` imports if no longer used |
| `tests/test_cli_list.py` | **Add** two tests: hook user-scope shows `user:✓` in text; codex MCP user-scope shows `user:✓` in text |

---

## Task 1: SSOT — define `USER_LINKED_STATUSES` in `_support.py`

**Files:**
- Modify: `src/agent_toolkit_cli/_support.py` (after `SUPPORTED_PAIRS` definition, around L78)
- Test: `tests/test_support.py` (add membership check)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_support.py`:

```python
def test_user_linked_statuses_constant():
    """USER_LINKED_STATUSES enumerates the cell statuses that count as 'this
    asset is linked at this scope for this harness'."""
    from agent_toolkit_cli._support import USER_LINKED_STATUSES

    assert USER_LINKED_STATUSES == frozenset(
        {"linked", "linked-matches", "linked-drifted"}
    )
    assert isinstance(USER_LINKED_STATUSES, frozenset)
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/test_support.py::test_user_linked_statuses_constant -v
```

Expected: FAIL with `ImportError: cannot import name 'USER_LINKED_STATUSES'`.

- [ ] **Step 3: Add the constant**

In `src/agent_toolkit_cli/_support.py`, after the `SUPPORTED_PAIRS` block (around line 78), add:

```python
# Cell statuses that count as "linked at this (scope, harness)" — the union
# of the three states the inventory builder emits when an asset has a real
# slot occupation (symlink, hook entry, or MCP entry). Imported by:
#   - commands/_list_json.py        (user_scope_covered)
#   - commands/list.py              (text-mode render)
#   - doctor/user_scope_coverage.py
#   - agent_toolkit_tui/widgets/asset_grid.py
USER_LINKED_STATUSES: frozenset[str] = frozenset(
    {"linked", "linked-matches", "linked-drifted"}
)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_support.py::test_user_linked_statuses_constant -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/_support.py tests/test_support.py
git commit -m "feat(#90): add USER_LINKED_STATUSES SSOT in _support"
```

---

## Task 2: Migrate `_list_json.py` to imported constant

**Files:**
- Modify: `src/agent_toolkit_cli/commands/_list_json.py:432, 448`

- [ ] **Step 1: Run existing tests to capture baseline**

```bash
uv run pytest tests/test_list_json.py -q
```

Expected: PASS (no changes yet, baseline).

- [ ] **Step 2: Replace local definition with import**

In `src/agent_toolkit_cli/commands/_list_json.py`:

Find the import block at L18-25 (the `from agent_toolkit_cli._support import ...` re-export block). Add `USER_LINKED_STATUSES` to it. Example:

```python
from agent_toolkit_cli._support import (  # noqa: F401 (re-exported)
    ALL_HARNESSES,
    ALL_KINDS,
    USER_LINKED_STATUSES,
    # ... whatever else is already there
)
```

(If the exact import block differs, add a separate `from agent_toolkit_cli._support import USER_LINKED_STATUSES` line — the goal is to make the name available in this module's namespace.)

Then **delete** the local definition at L432:

```python
_USER_LINKED_STATUSES = frozenset({"linked", "linked-matches", "linked-drifted"})
```

And update the reference at L448 inside `user_scope_covered()`:

```python
return cell.get("status") in USER_LINKED_STATUSES
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/test_list_json.py tests/test_doctor.py -q
```

Expected: PASS.

- [ ] **Step 4: Grep for any remaining `_USER_LINKED_STATUSES` references in this file**

```bash
grep -n "_USER_LINKED_STATUSES" src/agent_toolkit_cli/commands/_list_json.py
```

Expected: no output (constant is gone from this file).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/_list_json.py
git commit -m "refactor(#90): _list_json uses USER_LINKED_STATUSES from _support"
```

---

## Task 3: Migrate `doctor/user_scope_coverage.py`

**Files:**
- Modify: `src/agent_toolkit_cli/doctor/user_scope_coverage.py:13, 26`

- [ ] **Step 1: Run existing doctor tests for baseline**

```bash
uv run pytest tests/ -k user_scope_coverage -q
```

Expected: PASS.

- [ ] **Step 2: Replace local definition with import**

In `src/agent_toolkit_cli/doctor/user_scope_coverage.py`:

Replace lines 10-13:

```python
from agent_toolkit_cli.commands._list_json import _build_inventory, user_scope_covered
from agent_toolkit_cli.doctor.result import GroupResult, Status

_USER_LINKED_STATUSES = frozenset({"linked", "linked-matches", "linked-drifted"})
```

With:

```python
from agent_toolkit_cli._support import USER_LINKED_STATUSES
from agent_toolkit_cli.commands._list_json import _build_inventory, user_scope_covered
from agent_toolkit_cli.doctor.result import GroupResult, Status
```

Update the reference at L26:

```python
if cell.get("status") not in USER_LINKED_STATUSES:
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/ -k user_scope_coverage -q
```

Expected: PASS.

- [ ] **Step 4: Verify no remaining local references**

```bash
grep -n "_USER_LINKED_STATUSES" src/agent_toolkit_cli/doctor/user_scope_coverage.py
```

Expected: no output.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/doctor/user_scope_coverage.py
git commit -m "refactor(#90): doctor.user_scope_coverage uses USER_LINKED_STATUSES from _support"
```

---

## Task 4: Migrate `agent_toolkit_tui/widgets/asset_grid.py`

**Files:**
- Modify: `src/agent_toolkit_tui/widgets/asset_grid.py:31, 127, 143, 192, 254, 265`

- [ ] **Step 1: Run existing TUI tests for baseline**

```bash
uv run pytest tests/ -k asset_grid -q
```

Expected: PASS (if no tests, that's fine — output `no tests ran`).

- [ ] **Step 2: Replace local definition with import**

In `src/agent_toolkit_tui/widgets/asset_grid.py`:

Add import near the top (after the existing `from agent_toolkit_tui.state import ...` line at L11):

```python
from agent_toolkit_cli._support import USER_LINKED_STATUSES
```

Delete the local definition at L31:

```python
_USER_LINKED_STATUSES = frozenset({"linked", "linked-matches", "linked-drifted"})
```

(Keep `_USER_SCOPE_GLYPH = "🌐"` at L30 — that's a separate constant.)

- [ ] **Step 3: Rename the five usages**

Replace `_USER_LINKED_STATUSES` with `USER_LINKED_STATUSES` at lines 127, 143, 192, 254, 265. Use search-and-replace at file scope:

```bash
# Sanity check before edit:
grep -n "_USER_LINKED_STATUSES" src/agent_toolkit_tui/widgets/asset_grid.py
```

Then do the rename via the Edit tool with `replace_all: true` on the string `_USER_LINKED_STATUSES` → `USER_LINKED_STATUSES`. After:

```bash
grep -n "_USER_LINKED_STATUSES" src/agent_toolkit_tui/widgets/asset_grid.py
```

Expected: no output.

```bash
grep -n "USER_LINKED_STATUSES" src/agent_toolkit_tui/widgets/asset_grid.py
```

Expected: 6 lines — the import + 5 usages.

- [ ] **Step 4: Run TUI smoke test**

```bash
uv run pytest tests/ -k "asset_grid or tui" -q
```

Expected: PASS or "no tests ran".

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/widgets/asset_grid.py
git commit -m "refactor(#90): TUI asset_grid uses USER_LINKED_STATUSES from _support"
```

---

## Task 5: Repo-wide grep to confirm SSOT

**Files:** (none modified — verification gate)

- [ ] **Step 1: Find every remaining local definition**

```bash
grep -rn "_USER_LINKED_STATUSES" src/ tests/
```

Expected: zero hits. If anything remains, fix it in this task before moving on.

- [ ] **Step 2: Confirm the SSOT is the only declaration**

```bash
grep -rn 'USER_LINKED_STATUSES\s*=\s*frozenset' src/ tests/
```

Expected: **exactly one** hit — in `src/agent_toolkit_cli/_support.py`.

- [ ] **Step 3: No commit if nothing changed**

If the prior tasks were clean, this task ends without a commit. If a stray reference required a fix, commit it:

```bash
git add -A
git commit -m "refactor(#90): remove last stray _USER_LINKED_STATUSES references"
```

---

## Task 6: Add the two failing tests for text-mode hook/MCP user-scope display

**Files:**
- Test: `tests/test_cli_list.py` (append two new tests at the end)

These tests must FAIL before Task 7's implementation — that proves they cover the bug.

- [ ] **Step 1: Write the failing test for a Codex MCP at user scope**

Append to `tests/test_cli_list.py`:

```python
def test_list_text_shows_user_check_for_mcp(tmp_path, monkeypatch):
    """Regression for #90: a Codex MCP installed at user scope must render
    `user:✓` in plain `at list` text output (previously `_install_state` only
    checked symlinks and missed adapter-backed installs)."""
    from pathlib import Path

    from click.testing import CliRunner

    from agent_toolkit_cli.cli import main

    home = tmp_path / "home"
    home.mkdir()
    (home / ".codex").mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)

    toolkit = tmp_path / "toolkit"
    toolkit.mkdir()
    (toolkit / ".agent-toolkit-source").write_text("")
    (toolkit / "schemas").mkdir()
    schema_src = (
        Path(__file__).resolve().parents[1]
        / "schemas"
        / "asset-frontmatter.v1alpha2.json"
    )
    (toolkit / "schemas" / "asset-frontmatter.v1alpha2.json").write_text(
        schema_src.read_text()
    )
    mcp_dir = toolkit / "mcps" / "context7"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text(
        '{"type":"stdio","command":"npx","args":["-y","@upstash/context7-mcp"]}\n'
    )
    (mcp_dir / "README.md").write_text(
        "---\napiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: context7\n  description: c.\n  lifecycle: stable\n"
        "spec:\n  origin: third-party\n  vendored_via: none\n"
        "  upstream: https://example.com\n  harnesses:\n    - codex\n"
        "  mcp:\n    transport: stdio\n    install_method: npx\n---\n"
    )

    project = tmp_path / "project"
    project.mkdir()

    runner = CliRunner()
    # Link context7 to user scope on codex (mirrors the existing JSON test
    # pattern in tests/test_list_json.py::test_list_json_mcp_codex_linked_matches_after_link).
    rl = runner.invoke(
        main,
        [
            "link",
            "user",
            "codex",
            "mcp:context7",
            "--toolkit-repo",
            str(toolkit),
            "--project",
            str(project),
        ],
    )
    assert rl.exit_code == 0, rl.output

    # Now read state in plain text mode.
    r = runner.invoke(
        main,
        ["list", "--toolkit-repo", str(toolkit), "--project", str(project)],
    )
    assert r.exit_code == 0, r.output
    mcp_row = next(
        (l for l in r.output.splitlines() if "context7" in l), None
    )
    assert mcp_row is not None, r.output
    assert "user:✓" in mcp_row, (
        f"expected 'user:✓' in MCP row (adapter-backed user-scope install), got:\n{mcp_row}"
    )
```

- [ ] **Step 2: Write the failing test for a Claude hook at user scope**

Append to `tests/test_cli_list.py`:

```python
def test_list_text_shows_user_check_for_hook(tmp_path, monkeypatch):
    """Regression for #90: a Claude hook installed at user scope must render
    `user:✓` in plain `at list` text output."""
    import shutil
    from pathlib import Path

    from click.testing import CliRunner

    from agent_toolkit_cli.cli import main

    home = tmp_path / "home"
    home.mkdir()
    (home / ".claude").mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)

    toolkit = tmp_path / "toolkit"
    toolkit.mkdir()
    (toolkit / ".agent-toolkit-source").write_text("")
    (toolkit / "schemas").mkdir()
    schema_src = (
        Path(__file__).resolve().parents[1]
        / "schemas"
        / "asset-frontmatter.v1alpha2.json"
    )
    (toolkit / "schemas" / "asset-frontmatter.v1alpha2.json").write_text(
        schema_src.read_text()
    )

    # Reuse the demo-hook fixture used by tests/test_list_json.py.
    fixture_src = (
        Path(__file__).resolve().parent / "_fixtures" / "hook_assets" / "codex-demo"
    )
    hook_dir = toolkit / "hooks" / "demo-hook"
    hook_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(fixture_src, hook_dir, dirs_exist_ok=True)
    (hook_dir / "README.md").write_text(
        "---\napiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: demo-hook\n  description: Demo.\n  kind: hook\n  lifecycle: experimental\n"
        "spec:\n  origin: first-party\n  vendored_via: none\n  harnesses:\n    - claude\n"
        "  hook:\n    events: [PreToolUse]\n    command: check.sh\n"
        "    matcher: \"^Bash$\"\n    timeout: 10\n---\n"
    )

    project = tmp_path / "project"
    project.mkdir()

    runner = CliRunner()
    rl = runner.invoke(
        main,
        [
            "link",
            "user",
            "claude",
            "hook:demo-hook",
            "--toolkit-repo",
            str(toolkit),
            "--project",
            str(project),
        ],
    )
    assert rl.exit_code == 0, rl.output

    r = runner.invoke(
        main,
        ["list", "--toolkit-repo", str(toolkit), "--project", str(project)],
    )
    assert r.exit_code == 0, r.output
    hook_row = next(
        (l for l in r.output.splitlines() if "demo-hook" in l), None
    )
    assert hook_row is not None, r.output
    assert "user:✓" in hook_row, (
        f"expected 'user:✓' in hook row (adapter-backed user-scope install), got:\n{hook_row}"
    )
```

> **Note on hook fixture:** The fixture path `tests/_fixtures/hook_assets/codex-demo` is the same one used by `test_list_json.py:_seed_hook_toolkit`. If linking via `claude` harness fails because the fixture is codex-specific, switch the harness in this test to `codex` and the YAML/hook scaffolding to match. The implementing agent should mirror whichever harness the existing fixture supports for a successful link.

- [ ] **Step 3: Run the new tests to verify they FAIL**

```bash
uv run pytest tests/test_cli_list.py::test_list_text_shows_user_check_for_mcp tests/test_cli_list.py::test_list_text_shows_user_check_for_hook -v
```

Expected: BOTH FAIL — likely with `assert 'user:✓' in mcp_row` failing because text mode renders `user:—`. **This failure proves the test covers the bug.** Do not commit yet.

- [ ] **Step 4: No commit** (the implementation comes in Task 7 — these tests will be committed together with the fix to keep the bisect-clean history).

---

## Task 7: Rewrite `commands/list.py` text mode through `_build_inventory()`

**Files:**
- Modify: `src/agent_toolkit_cli/commands/list.py` (rewrite render loop, delete `_install_state()`)

- [ ] **Step 1: Confirm the failing tests from Task 6 are still failing**

```bash
uv run pytest tests/test_cli_list.py::test_list_text_shows_user_check_for_mcp tests/test_cli_list.py::test_list_text_shows_user_check_for_hook -v
```

Expected: FAIL (sanity).

- [ ] **Step 2: Rewrite the text render block**

In `src/agent_toolkit_cli/commands/list.py`:

(a) Update the imports near the top. **Remove**:

```python
from agent_toolkit_cli.commands._link_lib import (
    KINDS_FOR_PROJECTION,
    _asset_harnesses,
    harness_target_dir,
    harness_target_dirs,
)
```

**Replace with** (keeping only what's still used — `KINDS_FOR_PROJECTION` is still needed; `harness_target_dir`/`harness_target_dirs`/`_asset_harnesses` are not after the rewrite):

```python
from agent_toolkit_cli._support import USER_LINKED_STATUSES
from agent_toolkit_cli.commands._link_lib import KINDS_FOR_PROJECTION
from agent_toolkit_cli.commands._list_json import ALL_HARNESSES, _build_inventory
```

Remove the unused `discover_assets` import if it no longer has callers in this file:

```bash
grep -n "discover_assets" src/agent_toolkit_cli/commands/list.py
```

If only the import remains, drop it.

(b) Delete the entire `_install_state()` function (L38-73).

(c) Replace the text render block (current L204-252, starting at the `_ui.header(...)` call) with:

```python
    _ui.header(
        f"Asset inventory (filter: kind={kind_filter or 'any'},"
        f" harness={harness_filter or 'any'}):"
    )

    inv = _build_inventory(
        toolkit_root, project_root, kind=kind_filter, harness=harness_filter
    )

    def _scope_glyph(cells: list[dict], scope: str) -> str:
        """Return '✓' iff any cell at this scope is in a linked state, else '—'.

        For text mode we collapse all harnesses/aliases for the scope into
        one glyph — the bracket already discloses which harnesses declared it.
        """
        for c in cells:
            if c.get("scope") != scope:
                continue
            if c.get("status") in USER_LINKED_STATUSES:
                return "✓"
        return "—"

    # Group inventory assets by kind to preserve the previous "KIND (N)" headers.
    by_kind: dict[str, list[dict]] = {}
    for asset in inv.get("assets", []):
        by_kind.setdefault(asset["kind"], []).append(asset)

    for kind in KINDS_FOR_PROJECTION:
        if kind_filter and kind_filter != kind:
            continue
        assets_for_kind = by_kind.get(kind, [])
        rows: list[str] = []
        for asset in assets_for_kind:
            declared = asset.get("declared_harnesses") or []
            # When a harness filter is active, _build_inventory has already
            # narrowed cells to that harness; declared_harnesses is unfiltered
            # (it's the on-disk frontmatter) so respect the filter here for
            # the bracket display as well.
            if harness_filter and harness_filter not in declared:
                continue

            cells = asset.get("cells", [])
            user_state = _scope_glyph(cells, "user")
            project_state = _scope_glyph(cells, "project")

            if harness_filter:
                h_display = ""
            else:
                h_display = f"[{' '.join(declared)}]"

            project_suffix = (
                f" {_USER_SCOPE_GLYPH}"
                if user_state == "✓" and project_state == "✓"
                else ""
            )
            row = (
                f"  {asset['slug']:<20} {h_display:<30} "
                f"user:{user_state} project:{project_state}{project_suffix}"
            )
            rows.append(row)

        if rows:
            title = _KIND_TITLE[kind]
            click.echo(f"{title} ({len(rows)})")
            for row in rows:
                click.echo(row)

    _ui.summary("Done.")
```

(d) Also remove the now-unused `kind_to_section` / `read_allowlist` imports if those were only referenced by `_install_state` — check first:

```bash
grep -n "kind_to_section\|read_allowlist" src/agent_toolkit_cli/commands/list.py
```

If no remaining references, remove the `from agent_toolkit_cli._allowlist import kind_to_section, read_allowlist` import.

Same check for `os` — if only `os.environ` for `AGENT_TOOLKIT_QUIET` remains, keep `os`; if no references at all remain, drop the import.

- [ ] **Step 3: Run the two new tests — they should PASS now**

```bash
uv run pytest tests/test_cli_list.py::test_list_text_shows_user_check_for_mcp tests/test_cli_list.py::test_list_text_shows_user_check_for_hook -v
```

Expected: BOTH PASS.

- [ ] **Step 4: Run the full `test_cli_list.py` to confirm no regressions**

```bash
uv run pytest tests/test_cli_list.py -v
```

Expected: ALL PASS. Particular attention to:
- `test_list_shows_user_check` (symlink → `user:✓`)
- `test_list_project_check` (project symlink → `project:✓`)
- `test_list_text_includes_mcps` (MCPs section + `[claude]` bracket)
- `test_at_list_marks_project_segment_when_user_scope_linked` (🌐 suffix)
- `test_at_list_no_marker_when_user_scope_not_linked`
- `test_at_list_no_marker_when_only_user_scope_linked`

If any pre-existing test fails, **read the failure carefully**. The output format must remain `user:<glyph> project:<glyph>[ 🌐]`, the bracket must show `[h1 h2 ...]` for declared harnesses, the section headers must be `KIND (N)`, and the row left-padding (`  slug:<20`) must be preserved.

- [ ] **Step 5: Run the full test suite**

```bash
uv run pytest -q
```

Expected: ALL PASS. If anything else breaks (doctor, list-json, TUI), fix before continuing.

- [ ] **Step 6: Commit (test + implementation together)**

```bash
git add src/agent_toolkit_cli/commands/list.py tests/test_cli_list.py
git commit -m "fix(#90): at list text mode consumes _build_inventory; delete _install_state"
```

---

## Task 8: Final repo-wide sanity grep

**Files:** (none modified — verification gate)

- [ ] **Step 1: Confirm `_install_state` is gone**

```bash
grep -rn "_install_state" src/ tests/
```

Expected: no output.

- [ ] **Step 2: Confirm exactly one `USER_LINKED_STATUSES = frozenset(...)` declaration**

```bash
grep -rn 'USER_LINKED_STATUSES\s*=\s*frozenset' src/ tests/
```

Expected: exactly one hit — in `src/agent_toolkit_cli/_support.py`.

- [ ] **Step 3: Confirm no `_USER_LINKED_STATUSES` remains anywhere**

```bash
grep -rn "_USER_LINKED_STATUSES" src/ tests/
```

Expected: no output.

- [ ] **Step 4: Run lint + tests one more time**

```bash
uv run ruff check . && uv run mypy --strict src/ && uv run pytest -q
```

Expected: ALL CLEAN.

If everything passes, no further commit. The branch is ready for self-review.

---

## Self-Review (writing-plans checklist)

**Spec coverage:**
- DOD bullet "text mode consumes `_build_inventory()`" → Task 7 ✓
- DOD bullet "`_install_state` removed (or shrunk)" → Task 7 (removed) + Task 8 verify ✓
- DOD bullet "test for Claude hook at user scope shows `user:✓`" → Task 6 ✓
- DOD bullet "test for Codex MCP at user scope shows `user:✓`" → Task 6 ✓
- DOD bullet "exactly one `_USER_LINKED_STATUSES` (now `USER_LINKED_STATUSES`)" → Tasks 1-5 + 8 verify ✓
- Spec note "asset_grid.py inline literals at lines 127/143/192/254/265 are *usages* of the constant, not new sets" → Task 4 renames them ✓

**Placeholder scan:** No "TBD", "TODO", "implement later", or "similar to Task N" in any step. Each code step has the exact code to add.

**Type consistency:** The new helper `_scope_glyph` consumes the `cells` list of dicts (matches `_build_inventory()`'s schema). `USER_LINKED_STATUSES` is referenced as a `frozenset[str]` everywhere. No drift.

**One judgement call flagged for the executing agent:** In Task 6 step 2 (hook fixture), if `link user claude hook:demo-hook` does not succeed (because the demo fixture is codex-specific), the test should switch to the harness the fixture supports. Better to ship one passing test (codex hook) than two failing ones — the DOD's intent is "adapter-backed user-scope install shows `user:✓` for hooks AND MCPs," and either harness exercises the same code path.
