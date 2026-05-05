# Close harness/asset adapter gaps — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing `(harness, kind)` support matrix the SSOT in a new `agent_toolkit._support` module, and turn every silent-skip on an unsupported pair into a structured `UnsupportedPair` raise — so users cannot queue an allow-list change that exits 0 with nothing written.

**Architecture:** Extract the matrix tables (`_USER_TARGETS`, `_PROJECT_TARGETS`) plus `ALL_HARNESSES` / `ALL_KINDS` from `commands/_list_json.py` into a new top-level helper module `src/agent_toolkit/_support.py`. Add `is_supported(harness, kind)`, `validate_pair(ctx, harness, kind)` (Click-exit pattern, parallels `validate_harness`), and an `UnsupportedPair` exception. `_link_lib.maybe_link()` raises the exception when given an unsupported pair from a direct caller; `project_from_file` filters its loop by `is_supported` so the dead `if target_dir is None: continue` branch becomes an `assert` invariant. `commands/unlink.py` and `doctor/symlinks.py` (which has its own copy of the table) are migrated to import the SSOT.

**Tech Stack:** Python 3.12, Click, pytest, Textual (TUI tests use `App.run_test()` + Pilot).

---

## File Structure

| File | Responsibility | Disposition |
|---|---|---|
| `src/agent_toolkit/_support.py` | NEW. SSOT for the support matrix; exports `SUPPORTED_PAIRS`, `ALL_HARNESSES`, `ALL_KINDS`, `_USER_TARGETS`, `_PROJECT_TARGETS`, `is_supported`, `validate_pair`, `UnsupportedPair`. | create |
| `src/agent_toolkit/commands/_list_json.py` | Re-export `ALL_HARNESSES` / `ALL_KINDS` from `_support` (back-compat shim, since `commands/list.py` and tests import from here); drop the local `_USER_TARGETS` / `_PROJECT_TARGETS` definitions and the historical "Mirror of bin/lib/common.sh" comment. | edit |
| `src/agent_toolkit/commands/_link_lib.py` | Drop local `ALL_HARNESSES`; import from `_support`. `maybe_link` calls `is_supported` and raises `UnsupportedPair` on mismatch. `project_from_file` projection loop filters by `is_supported`; the `if target_dir is None: continue` becomes `assert target_dir is not None`. `harness_target_dir` is unchanged (still returns `None` for unsupported pairs — used by callers like `list.py`'s `--report` that need a "may-fail" lookup). | edit |
| `src/agent_toolkit/commands/unlink.py` | `_do_all`'s `if target_dir is None or not target_dir.is_dir(): continue` keeps the `not target_dir.is_dir()` branch but uses `is_supported` to short-circuit unsupported pairs (no behavior change — the existing `is_dir()` guard was effectively the same — but now reads from the SSOT). | edit |
| `src/agent_toolkit/doctor/symlinks.py` | Drop local `_USER_PATHS` table; derive from the SSOT (`_PROJECT_TARGETS` keys + relative paths). Drop the "Mirror bin/lib/common.sh" comment. | edit |
| `src/agent_toolkit/doctor/allowlist_audit.py` | Update import: `_USER_TARGETS` from `_support` instead of `commands._list_json`. | edit |
| `src/agent_toolkit/commands/list.py` | Update import: `ALL_HARNESSES` from `_support` (or keep importing from `_list_json` shim — pick one). Loop in `_link_status` already handles `target_dir is None`; no logic change needed. | edit |
| `tests/test_support.py` | NEW. Cover `SUPPORTED_PAIRS` membership, `is_supported`, `validate_pair`, `UnsupportedPair`. | create |
| `tests/test_link_lib.py` | Add cases for `maybe_link` raising `UnsupportedPair` and `project_from_file` filtering by `is_supported`. Update import path for `ALL_HARNESSES` if shim is dropped. | edit |
| `tests/test_cli_link.py` | Add CliRunner case: `link --harness codex --plan -` with `agent: foo` exits 2 with structured message. | edit |
| `tests/test_tui/test_app.py` | Add regression: pressing Space on an `unsupported` cell yields no `AssetToggled`, no pending entry; rendered glyph stays `──`. | edit |

The historical `bin/lib/common.sh` comment in `commands/_list_json.py` and `doctor/symlinks.py` is removed — bash CLI was retired (`2026-05-04-retire-bash-cli-design.md`).

---

## Task 1: Add the `_support` SSOT module

**Files:**
- Create: `src/agent_toolkit/_support.py`
- Test: `tests/test_support.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_support.py
"""Tests for the (harness, kind) support matrix SSOT."""
from __future__ import annotations

import pytest

from agent_toolkit._support import (
    ALL_HARNESSES,
    ALL_KINDS,
    SUPPORTED_PAIRS,
    UnsupportedPair,
    _PROJECT_TARGETS,
    _USER_TARGETS,
    is_supported,
    validate_pair,
)


def test_all_harnesses_is_canonical():
    assert ALL_HARNESSES == ("claude", "codex", "opencode", "pi")


def test_all_kinds_is_canonical():
    assert ALL_KINDS == (
        "skill", "agent", "command", "hook", "plugin", "mcp", "pi-extension",
    )


def test_supported_pairs_match_target_keys():
    """SUPPORTED_PAIRS is derived from the target tables — no second SSOT."""
    assert SUPPORTED_PAIRS == frozenset(_USER_TARGETS.keys())
    assert frozenset(_USER_TARGETS.keys()) == frozenset(_PROJECT_TARGETS.keys())


def test_supported_pairs_known_members():
    # Spot-check: claude has the full kind set; codex/opencode have only skill.
    assert ("claude", "skill") in SUPPORTED_PAIRS
    assert ("claude", "agent") in SUPPORTED_PAIRS
    assert ("claude", "command") in SUPPORTED_PAIRS
    assert ("claude", "hook") in SUPPORTED_PAIRS
    assert ("claude", "plugin") in SUPPORTED_PAIRS
    assert ("codex", "skill") in SUPPORTED_PAIRS
    assert ("opencode", "skill") in SUPPORTED_PAIRS
    assert ("pi", "pi-extension") in SUPPORTED_PAIRS


def test_supported_pairs_known_holes():
    """The matrix gaps that issue #32 will close."""
    assert ("codex", "agent") not in SUPPORTED_PAIRS
    assert ("opencode", "agent") not in SUPPORTED_PAIRS
    assert ("opencode", "command") not in SUPPORTED_PAIRS
    assert ("pi", "command") not in SUPPORTED_PAIRS


def test_is_supported_matches_set_membership():
    assert is_supported("claude", "skill") is True
    assert is_supported("opencode", "agent") is False
    assert is_supported("nonsense", "skill") is False


def test_unsupported_pair_message_names_pair():
    exc = UnsupportedPair("opencode", "agent")
    assert "opencode" in str(exc)
    assert "agent" in str(exc)


def test_validate_pair_accepts_supported():
    import click

    ctx = click.Context(click.Command("noop"))
    validate_pair(ctx, "claude", "skill")  # must not raise


def test_validate_pair_rejects_unsupported_with_exit_2(capsys):
    import click

    ctx = click.Context(click.Command("noop"))
    with pytest.raises(click.exceptions.Exit) as exc:
        validate_pair(ctx, "opencode", "agent")
    assert exc.value.exit_code == 2
    captured = capsys.readouterr()
    assert "opencode" in captured.err
    assert "agent" in captured.err
    # The error names supported kinds for the given harness as a hint.
    assert "skill" in captured.err
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/fix-30-close-harness-asset-adapter-gaps && uv run pytest tests/test_support.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'agent_toolkit._support'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/agent_toolkit/_support.py
"""Single source of truth for the (harness, asset-kind) support matrix.

The matrix encodes which (harness, kind) pairs the toolkit can currently
project to a real on-disk slot. Adding a row here is the only place a new
adapter slot needs declaring; consumers (`_link_lib`, `_list_json`,
`commands/unlink`, `doctor/*`) read from here.

Issue #30: silent-skip on unsupported pairs is now a structured raise.
Issue #32 tracks closing remaining matrix gaps (e.g. opencode agents).
"""
from __future__ import annotations

import os
from pathlib import Path

import click

ALL_HARNESSES: tuple[str, ...] = ("claude", "codex", "opencode", "pi")
ALL_KINDS: tuple[str, ...] = (
    "skill", "agent", "command", "hook", "plugin", "mcp", "pi-extension",
)

_USER_TARGETS: dict[tuple[str, str], str] = {
    ("claude", "skill"):       "{home}/.claude/skills",
    ("claude", "agent"):       "{home}/.claude/agents",
    ("claude", "command"):     "{home}/.claude/commands",
    ("claude", "hook"):        "{home}/.claude/hooks",
    ("claude", "plugin"):      "{home}/.claude/plugins",
    ("codex", "skill"):        "{home}/.codex/skills",
    ("opencode", "skill"):     "{home}/.config/opencode/skills",
    ("pi", "skill"):           "{home}/.pi/agent/skills",
    ("pi", "agent"):           "{home}/.pi/agent/agents",
    ("pi", "pi-extension"):    "{home}/.pi/agent/extensions",
}
_PROJECT_TARGETS: dict[tuple[str, str], str] = {
    ("claude", "skill"):       ".claude/skills",
    ("claude", "agent"):       ".claude/agents",
    ("claude", "command"):     ".claude/commands",
    ("claude", "hook"):        ".claude/hooks",
    ("claude", "plugin"):      ".claude/plugins",
    ("codex", "skill"):        ".codex/skills",
    ("opencode", "skill"):     ".opencode/skills",
    ("pi", "skill"):           ".pi/agent/skills",
    ("pi", "agent"):           ".pi/agent/agents",
    ("pi", "pi-extension"):    ".pi/agent/extensions",
}

# Derived: SUPPORTED_PAIRS = the set of (harness, kind) pairs with adapter slots.
# Both tables MUST share the same key set; tested in tests/test_support.py.
SUPPORTED_PAIRS: frozenset[tuple[str, str]] = frozenset(_USER_TARGETS.keys())


class UnsupportedPair(Exception):
    """Raised when an apply path is asked to act on a (harness, kind) pair
    that has no adapter slot in the support matrix.

    Carry the pair on the exception so callers can format messages or
    surface them in structured CLI errors.
    """

    def __init__(self, harness: str, kind: str) -> None:
        self.harness = harness
        self.kind = kind
        super().__init__(
            f"unsupported (harness, kind) pair: ({harness!r}, {kind!r})"
        )


def is_supported(harness: str, kind: str) -> bool:
    """True iff `(harness, kind)` has a real adapter slot in the matrix."""
    return (harness, kind) in SUPPORTED_PAIRS


def supported_kinds_for(harness: str) -> tuple[str, ...]:
    """Return the kinds the given harness supports, in `ALL_KINDS` order."""
    return tuple(k for k in ALL_KINDS if (harness, k) in SUPPORTED_PAIRS)


def validate_pair(ctx: click.Context, harness: str, kind: str) -> None:
    """Exit 2 with a structured stderr message if the pair is unsupported.

    Mirrors the shape of `_link_lib.validate_harness` so Click subcommands
    can reuse it consistently.
    """
    if is_supported(harness, kind):
        return
    supported = supported_kinds_for(harness)
    if supported:
        hint = f"supported kinds for {harness!r}: " + " ".join(supported)
    else:
        hint = f"{harness!r} has no supported kinds"
    click.echo(
        f"unsupported (harness, kind) pair: ({harness!r}, {kind!r}) — {hint}",
        err=True,
    )
    ctx.exit(2)


def slot_dir(
    harness: str,
    kind: str,
    scope: str,
    project_root: Path,
) -> Path | None:
    """Return the absolute slot directory for a `(harness, kind, scope)` triple,
    or `None` if the pair is unsupported. Mirrors the prior
    `_list_json._slot_dir` helper.
    """
    home = Path(os.environ.get("HOME", ""))
    if scope == "user":
        tmpl = _USER_TARGETS.get((harness, kind))
        return Path(tmpl.format(home=str(home))) if tmpl else None
    rel = _PROJECT_TARGETS.get((harness, kind))
    return (project_root / rel) if rel else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_support.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit/_support.py tests/test_support.py
git commit -m "feat(_support): SSOT for (harness, kind) matrix + UnsupportedPair"
```

---

## Task 2: Migrate `_list_json.py` to import from `_support`

**Files:**
- Modify: `src/agent_toolkit/commands/_list_json.py:18-58`
- Test: existing `tests/test_list_json.py` (must keep passing)

- [ ] **Step 1: Read the current state**

Lines 18-58 of `_list_json.py` define `ALL_HARNESSES`, `ALL_KINDS`, `_USER_TARGETS`, `_PROJECT_TARGETS`, and `_slot_dir`. The historical comment at line 18-20 references `_link_lib.ALL_HARNESSES` and the bash table.

- [ ] **Step 2: Edit `_list_json.py` — replace local definitions with re-exports**

Replace lines 18-58 (everything from the `# Kept in lockstep` comment through the end of the `_slot_dir` function) with:

```python
# Re-export from the SSOT module so existing callers (commands/list.py,
# tests/test_link_lib.py, etc.) keep their import paths working.
from agent_toolkit._support import (  # noqa: F401  (re-exported)
    ALL_HARNESSES,
    ALL_KINDS,
    _PROJECT_TARGETS,
    _USER_TARGETS,
    slot_dir as _slot_dir,
)
```

Keep the rest of the file (the `_expected_source`, `_cell_status`, `_build_inventory`, `list_json` Click command) unchanged.

- [ ] **Step 3: Run pytest to verify nothing broke**

Run: `uv run pytest tests/test_list_json.py tests/test_cli_list.py -v`
Expected: all pass (no contract change for the list path).

- [ ] **Step 4: Run the full TUI suite to confirm**

Run: `uv run pytest tests/test_tui/ -q`
Expected: all pass (the TUI consumes `_list_json` JSON, not Python imports).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit/commands/_list_json.py
git commit -m "refactor(_list_json): import support matrix from _support SSOT"
```

---

## Task 3: Migrate `_link_lib.py` to import from `_support`; raise `UnsupportedPair` in `maybe_link`

**Files:**
- Modify: `src/agent_toolkit/commands/_link_lib.py:17-20, 145-188, 264-266`
- Test: `tests/test_link_lib.py`

- [ ] **Step 1: Write the failing tests for `maybe_link` raising and `project_from_file` filtering**

Append to `tests/test_link_lib.py`:

```python
# ===========================================================================
# Issue #30 — UnsupportedPair on direct apply
# ===========================================================================


def test_maybe_link_raises_unsupported_pair_for_codex_agent(tmp_path):
    """maybe_link must refuse an unsupported (harness, kind) loudly."""
    from agent_toolkit._support import UnsupportedPair
    from agent_toolkit.commands._link_lib import LinkCounters, maybe_link

    asset_path = tmp_path / "agent.md"
    asset_path.write_text("---\nspec:\n  harnesses: [codex]\n---\nbody\n")
    target = tmp_path / "target"
    target.mkdir()
    counters = LinkCounters()
    import io

    with pytest.raises(UnsupportedPair) as exc:
        maybe_link(
            harness="codex",
            kind="agent",
            slug="foo",
            asset_path=asset_path,
            target_dir=target,
            toolkit_root=tmp_path,
            dry_run=True,
            counters=counters,
            stdout=io.StringIO(),
        )
    assert exc.value.harness == "codex"
    assert exc.value.kind == "agent"


def test_project_from_file_skips_unsupported_kinds_silently(tmp_path, monkeypatch):
    """project_from_file iterates only supported kinds for the given harness.

    For `harness=codex` the loop must only touch `kind=skill` (the only
    supported pair besides MCP). No raise — the loop's pre-filter is the
    boundary; raises happen at direct entry-points like `maybe_link`.
    """
    from agent_toolkit.commands._link_lib import LinkCounters, project_from_file

    monkeypatch.setenv("HOME", str(tmp_path))
    project_root = tmp_path / "project"
    project_root.mkdir()
    allowlist_path = project_root / ".agent-toolkit.yaml"
    allowlist_path.write_text("skills: []\nagents: [foo]\n")
    counters = LinkCounters()
    import io
    out = io.StringIO()

    # Empty toolkit (no assets) — exercises the loop without I/O.
    toolkit_root = tmp_path / "toolkit"
    toolkit_root.mkdir()

    project_from_file(
        scope="project",
        harness="codex",
        toolkit_root=toolkit_root,
        project_root=project_root,
        allowlist_path=allowlist_path,
        dry_run=True,
        counters=counters,
        stdout=out,
    )
    # No exception. Counters are zero (no assets discovered).
    assert counters.created == counters.removed == counters.would_link == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_link_lib.py::test_maybe_link_raises_unsupported_pair_for_codex_agent tests/test_link_lib.py::test_project_from_file_skips_unsupported_kinds_silently -v`

Expected: FAIL — first test fails with no raise (current `maybe_link` falls through silently); second fails with `ImportError` if not yet wired, or passes trivially if the existing loop already iterates all kinds (we'll see).

- [ ] **Step 3: Edit `_link_lib.py` imports (lines 17-20)**

Replace:

```python
from agent_toolkit.commands._list_json import _PROJECT_TARGETS, _USER_TARGETS
from agent_toolkit.walker import Asset, discover_assets, extract_frontmatter, frontmatter_path

ALL_HARNESSES: tuple[str, ...] = ("claude", "codex", "opencode", "pi")
```

With:

```python
from agent_toolkit._support import (
    ALL_HARNESSES,
    UnsupportedPair,
    _PROJECT_TARGETS,
    _USER_TARGETS,
    is_supported,
)
from agent_toolkit.walker import Asset, discover_assets, extract_frontmatter, frontmatter_path
```

- [ ] **Step 4: Edit `maybe_link` to raise `UnsupportedPair` (around line 145-188)**

Add a guard at the top of `maybe_link`:

```python
def maybe_link(
    *,
    harness: str,
    kind: str,
    slug: str,
    asset_path: Path,
    target_dir: Path,
    toolkit_root: Path,
    dry_run: bool,
    counters: LinkCounters,
    stdout: IO[str],
) -> None:
    """Create/replace/skip a symlink for one asset; update counters."""
    if not is_supported(harness, kind):
        raise UnsupportedPair(harness, kind)
    source_path = _expected_source(asset_path, kind)
    # …rest unchanged…
```

- [ ] **Step 5: Edit `project_from_file` to filter by `is_supported` (around line 219-266)**

Find the loop `for kind in KINDS_FOR_PROJECTION:`. Inside, after the `if kind == "mcp":` block (which dispatches via adapter — leave untouched), add:

```python
        if kind == "mcp":
            # …existing MCP dispatch unchanged…
            continue
        if not is_supported(harness, kind):
            # Boundary: caller asked for a harness/kind pair we have no slot
            # for. Silent-skip is wrong (#30) but non-MCP kinds reach here
            # from a discovery loop, not user input — we honour the filter
            # rather than raise. Direct entrypoints (maybe_link) raise.
            continue
        target_dir = harness_target_dir(harness, kind, scope, project_root)
        assert target_dir is not None, (
            f"is_supported({harness!r}, {kind!r}) is True but "
            f"harness_target_dir returned None — invariant broken"
        )
```

Remove the existing lines 264-266:

```python
        target_dir = harness_target_dir(harness, kind, scope, project_root)
        if target_dir is None:
            continue
```

- [ ] **Step 6: Run the new tests to verify they pass**

Run: `uv run pytest tests/test_link_lib.py -v`

Expected: all `test_link_lib.py` cases pass, including the two new ones.

- [ ] **Step 7: Run the full pytest suite to catch regressions**

Run: `uv run pytest -q`

Expected: 422+ tests, all green.

- [ ] **Step 8: Commit**

```bash
git add src/agent_toolkit/commands/_link_lib.py tests/test_link_lib.py
git commit -m "fix(_link_lib): raise UnsupportedPair, filter project_from_file by SSOT"
```

---

## Task 4: CliRunner integration — `link --harness codex` with unsupported plan line

**Files:**
- Modify: `tests/test_cli_link.py`

The CLI's `link` subcommand reads its plan via stdin when `--plan -`. We assert the user-facing failure mode.

- [ ] **Step 1: Find the existing `--plan` test in `test_cli_link.py`**

Run: `grep -n "plan" /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/fix-30-close-harness-asset-adapter-gaps/tests/test_cli_link.py | head -20`

Use the existing pattern as a template — the test uses `CliRunner` from `click.testing`, sets up a tmp toolkit, and invokes `agent-toolkit link --harness X --plan -` with `input=` for stdin.

- [ ] **Step 2: Append the failing test**

Append at the bottom of `tests/test_cli_link.py`:

```python
# ===========================================================================
# Issue #30 — link refuses unsupported (harness, kind) loudly
# ===========================================================================


def test_link_plan_with_unsupported_pair_exits_2_with_message(tmp_path, monkeypatch):
    """`link --harness codex --plan -` with `agent: foo` must exit 2 (not 0)
    and the stderr names the pair plus the supported kinds for codex."""
    from click.testing import CliRunner

    from agent_toolkit.cli import cli

    monkeypatch.setenv("HOME", str(tmp_path))
    toolkit = tmp_path / "toolkit"
    toolkit.mkdir()
    project = tmp_path / "project"
    project.mkdir()

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--toolkit-repo", str(toolkit),
            "link",
            "--project", str(project),
            "--harness", "codex",
            "--plan", "-",
        ],
        input="agent: foo\n",
        catch_exceptions=False,
    )
    assert result.exit_code == 2, (
        f"expected exit 2, got {result.exit_code}; output:\n{result.output}"
    )
    # Click writes ClickException messages via `result.output` when stderr
    # is captured by the runner.
    msg = result.output + (result.stderr if hasattr(result, "stderr") else "")
    assert "unsupported" in msg.lower()
    assert "codex" in msg
    assert "agent" in msg
    # Hint surface: at least one supported kind is named for guidance.
    assert "skill" in msg
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest tests/test_cli_link.py::test_link_plan_with_unsupported_pair_exits_2_with_message -v`

Expected: FAIL — current behaviour exits 0 (silent skip).

- [ ] **Step 4: Wire the guard into the link command path**

Open `src/agent_toolkit/commands/link.py`. Find the plan-iteration code (uses `iter_plan_lines`, then per-line dispatches). For each `(kind, slug)` from the plan, call `validate_pair(ctx, harness, kind)` before queuing the work.

If the link command does not already have a `ctx`, accept it via `@click.pass_context`. Locate the loop that consumes `iter_plan_lines` output; insert the validation just after parsing each line and before any `maybe_link` call.

If the validation lives in `_link_lib` rather than `link.py` (it's the more natural seam), add a tiny helper:

```python
# in src/agent_toolkit/commands/_link_lib.py
def validate_plan_pair(ctx: click.Context, harness: str, kind: str) -> None:
    """Click-shape wrapper: exit 2 if (harness, kind) is unsupported."""
    from agent_toolkit._support import validate_pair
    validate_pair(ctx, harness, kind)
```

…and call `validate_plan_pair(ctx, harness, kind)` in the link command after each `iter_plan_lines` iteration.

(Implementer: read `src/agent_toolkit/commands/link.py` first to find the right insertion point. The change is one line per plan-iteration site; the spec assumes there are 1 or 2 such sites. If more — apply to all.)

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/test_cli_link.py::test_link_plan_with_unsupported_pair_exits_2_with_message -v`

Expected: PASS, exit code 2, stderr contains "unsupported", "codex", "agent", "skill".

- [ ] **Step 6: Run the full link/unlink/list suite to catch regressions**

Run: `uv run pytest tests/test_cli_link.py tests/test_cli_unlink.py tests/test_cli_list.py -q`

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add src/agent_toolkit/commands/link.py src/agent_toolkit/commands/_link_lib.py tests/test_cli_link.py
git commit -m "feat(link): exit 2 on unsupported (harness, kind) plan lines"
```

---

## Task 5: Migrate `unlink.py`, `doctor/symlinks.py`, `doctor/allowlist_audit.py` to the SSOT

**Files:**
- Modify: `src/agent_toolkit/commands/unlink.py:19, 158-160`
- Modify: `src/agent_toolkit/doctor/symlinks.py:1-22`
- Modify: `src/agent_toolkit/doctor/allowlist_audit.py:19`

- [ ] **Step 1: Read existing test coverage for these files**

Run:
```bash
ls tests/test_cli_unlink.py tests/test_doctor*.py
```

These tests must continue to pass — no new tests required for the migration; the SSOT consolidation is pure refactor.

- [ ] **Step 2: Edit `unlink.py`**

The existing line 158-160:

```python
        target_dir = harness_target_dir(harness, kind, scope, project_root)
        if target_dir is None or not target_dir.is_dir():
            continue
```

Replace with:

```python
        from agent_toolkit._support import is_supported  # local import to avoid cycles
        if not is_supported(harness, kind):
            continue
        target_dir = harness_target_dir(harness, kind, scope, project_root)
        if not target_dir.is_dir():
            continue
```

Reasoning: `target_dir is None` becomes unreachable behind the `is_supported` filter, but the `is_dir()` check stays — the dir may not have been created yet in a fresh project.

- [ ] **Step 3: Edit `doctor/symlinks.py`**

Replace lines 10-22 (the local `_USER_PATHS` table and the `# Mirror …` comment) with:

```python
from agent_toolkit._support import _USER_TARGETS

# Strip the "{home}/" template prefix to get a relative path under $HOME,
# matching this module's existing convention of joining with `home / rel`.
_USER_PATHS: dict[tuple[str, str], str] = {
    pair: tmpl.removeprefix("{home}/")
    for pair, tmpl in _USER_TARGETS.items()
}
```

This preserves the existing `_USER_PATHS` shape while sourcing data from the SSOT.

- [ ] **Step 4: Edit `doctor/allowlist_audit.py`**

Change line 19:

```python
from agent_toolkit.commands._list_json import _USER_TARGETS
```

to:

```python
from agent_toolkit._support import _USER_TARGETS
```

- [ ] **Step 5: Run pytest**

Run: `uv run pytest -q`

Expected: 422+ tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit/commands/unlink.py src/agent_toolkit/doctor/symlinks.py src/agent_toolkit/doctor/allowlist_audit.py
git commit -m "refactor(doctor, unlink): consume the _support SSOT"
```

---

## Task 6: TUI regression — Space on unsupported cell is a no-op

**Files:**
- Modify: `tests/test_tui/test_app.py`

The TUI already guards `unsupported` cells in `AssetGrid._toggle_at` (asset_grid.py:120, 136, 180, 253). This task pins that behavior with a regression test.

- [ ] **Step 1: Find the existing toggle tests in `test_app.py`**

Run: `grep -n "press.*space\|toggle\|pending_entries" /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/fix-30-close-harness-asset-adapter-gaps/tests/test_tui/test_app.py | head -30`

Use them as a template for the new test. The pattern uses `app.run_test()` + Pilot, sets the cursor to a specific cell, presses Space, and asserts on `grid.pending_entries()`.

- [ ] **Step 2: Identify or build a fixture asset that has an unsupported cell**

The fixture `_doc()` already produces inventory state. We need an asset whose declared harnesses include `codex` (so the column is rendered for the row) but whose kind is `agent` (an unsupported pair for codex). If the existing fixture lacks this, extend it minimally — see `tests/test_tui/conftest.py` for fixture builders.

If the existing `_doc()` doesn't include an `(agent, codex declared)` row, extend the fixture inline in the test (don't modify the shared fixture):

```python
def _doc_with_unsupported_cell():
    """Variant fixture: includes an agent asset that declares codex."""
    base = _doc()
    base["assets"].append({
        "kind": "agent",
        "slug": "codex-only-agent",
        "origin": "test",
        "description": "agent declaring codex (unsupported pair)",
        "path": "/fake/agents/codex-only-agent.md",
        "declared_harnesses": ["codex"],
        "cells": [
            {"harness": "codex", "scope": "user",    "status": "unsupported", "target": None, "allowlisted": False},
            {"harness": "codex", "scope": "project", "status": "unsupported", "target": None, "allowlisted": False},
            # other harnesses also unsupported for this slug:
            {"harness": "claude",   "scope": "user",    "status": "unsupported", "target": None, "allowlisted": False},
            {"harness": "claude",   "scope": "project", "status": "unsupported", "target": None, "allowlisted": False},
            {"harness": "opencode", "scope": "user",    "status": "unsupported", "target": None, "allowlisted": False},
            {"harness": "opencode", "scope": "project", "status": "unsupported", "target": None, "allowlisted": False},
            {"harness": "pi",       "scope": "user",    "status": "unsupported", "target": None, "allowlisted": False},
            {"harness": "pi",       "scope": "project", "status": "unsupported", "target": None, "allowlisted": False},
        ],
    })
    return base
```

(Implementer: inspect what `_doc()` and `FakeRunner` actually return in the existing tests — adjust the dict shape to match. This stub is illustrative.)

- [ ] **Step 3: Append the failing test**

Append to `tests/test_tui/test_app.py`:

```python
async def test_space_on_unsupported_cell_is_noop():
    """Pressing Space on an `unsupported` cell yields no AssetToggled and
    no pending entry. Regression for issue #30."""
    from agent_toolkit_tui.widgets import AssetGrid
    from textual.coordinate import Coordinate
    from textual.widgets import DataTable

    runner = FakeRunner(_doc_with_unsupported_cell())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#asset-grid", AssetGrid)
        table = grid.query_one("#grid-table", DataTable)

        # Find the row index of the unsupported asset.
        target_row = None
        for i, row in enumerate(grid._rows):  # internal but stable
            if row.slug == "codex-only-agent":
                target_row = i
                break
        assert target_row is not None, "fixture missing the unsupported asset row"

        # Cursor on column 1 (first harness column; cell status is unsupported).
        table.cursor_coordinate = Coordinate(row=target_row, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()

        assert not grid.pending_entries(), (
            "Space on an unsupported cell must not queue a pending edit"
        )
```

- [ ] **Step 4: Run the test to verify it passes (this is a regression test, not a new feature)**

Run: `uv run pytest tests/test_tui/test_app.py::test_space_on_unsupported_cell_is_noop -v`

Expected: PASS — `_toggle_at` already guards `unsupported`, so the test pins the existing behavior.

If the test FAILS: `_toggle_at` is letting an unsupported cell through. Inspect `src/agent_toolkit_tui/widgets/asset_grid.py:120,136,180,253` and confirm the guard is reached for the cursor position; the fixture may need adjusting.

- [ ] **Step 5: Commit**

```bash
git add tests/test_tui/test_app.py
git commit -m "test(tui): pin Space-on-unsupported-cell as no-op (regression #30)"
```

---

## Task 7: Footer-hint scrub — verify "Opencode gap" / "Codex gap" strings are absent

**Files:**
- Test: ad-hoc shell check (no test file).

- [ ] **Step 1: Run the grep**

Run:
```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/fix-30-close-harness-asset-adapter-gaps && \
grep -rni "Opencode gap\|Codex gap\|opencode gap\|codex gap" src/ tests/ docs/ || echo "(no hits)"
```

Expected: `(no hits)`. If hits appear, remove them in this task.

- [ ] **Step 2: If no hits, skip to commit; if hits, edit those files to remove the hint and re-run pytest**

If the grep returned `(no hits)`: nothing to do. Note in the commit message that the workaround was already removed upstream (likely in commit `08134e1`).

If hits: remove the hint from the source(s) in question, re-run `uv run pytest -q`, and proceed.

- [ ] **Step 3: Commit (if changes were needed) or skip**

```bash
# only if changes were made
git add <files>
git commit -m "chore(tui): remove leftover Opencode/Codex gap footer hints (#30)"
```

If no changes: this task adds no commit. Move on.

---

## Task 8: Spec note + smoke

**Files:**
- Modify: `docs/agent-toolkit/cli.md` (if it documents the support matrix).
- Smoke: `agent-toolkit doctor`.

- [ ] **Step 1: Check whether `docs/agent-toolkit/cli.md` documents the matrix**

Run: `grep -n "harness_target_dir\|_USER_TARGETS\|support matrix\|claude.*codex.*opencode\|skill.*agent.*command.*hook" /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/fix-30-close-harness-asset-adapter-gaps/docs/agent-toolkit/cli.md`

If a matrix appears in the doc, ensure it matches the SSOT. If not, leave the doc alone.

- [ ] **Step 2: Doctor smoke**

Run: `uv run agent-toolkit --toolkit-repo ~/GitHub/agent-toolkit doctor`

Expected: no new failures introduced; same checks pass as before this work.

- [ ] **Step 3: Commit (if doc changes were made)**

```bash
# only if cli.md was edited
git add docs/agent-toolkit/cli.md
git commit -m "docs(cli): refresh support matrix table to match SSOT"
```

---

## Self-Review

**Spec coverage check:**

| AC | Task |
|---|---|
| AC#1 (`_support.py` exports) | Task 1 |
| AC#2 (matrix moved to `_support`, two import sites) | Tasks 2 + 5 (moves to `_support`; `_list_json`, `_link_lib`, `unlink`, `doctor/symlinks`, `doctor/allowlist_audit` import from there) |
| AC#3 (`project_from_file` filters by `is_supported`; `target_dir is None` branch unreachable) | Task 3 Step 5 (assert + filter) |
| AC#4 (`maybe_link` raises `UnsupportedPair`) | Task 3 Step 4 |
| AC#5 (`link --harness codex --plan -` with `agent: foo` exits 2) | Task 4 |
| AC#6 (`_list_json` cells contract unchanged) | Task 2 Steps 3-4 (existing tests must still pass) |
| AC#7 (TUI regression: Space on unsupported cell is no-op) | Task 6 |
| AC#8 (no "Opencode gap" / "Codex gap" strings in tree) | Task 7 |
| AC#9 (`uv run pytest -q` green) | Task 3 Step 7 + Task 5 Step 5 (each task pre-flights pytest) |
| AC#10 (`doctor` passes) | Task 8 Step 2 |

All 10 ACs map to a concrete task.

**Placeholder scan:** the only deliberate "look at the existing pattern" instructions are in Tasks 4 and 6 — both about reading the existing test fixture (`_doc()`, FakeRunner) and CliRunner setup before adapting. These are concrete pointers, not TBDs.

**Type consistency:** `is_supported(harness: str, kind: str) -> bool` and `validate_pair(ctx, harness, kind)` are used identically across Tasks 1-5. `UnsupportedPair(harness, kind)` carries both fields per Task 1 and is asserted on in Task 3.

---

## Plan complete. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks, fast iteration via `superpowers:subagent-driven-development`.
2. **Inline Execution** — execute tasks in this session via `superpowers:executing-plans`, batch with checkpoints.

Flow.md Step 6 specifies `superpowers:subagent-driven-development`, so the parent agent will dispatch that.
