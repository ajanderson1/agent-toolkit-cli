# MCP `standard` Projection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a project-scope `standard` projection to the MCP kind that owns the shared `<project>/.mcp.json` `mcpServers` entry, normalizing `claude-code`+`pi` to a single `standard` token/lock-row at project scope.

**Architecture:** `standard` is a thin specialization of the existing JSON adapter — same `_JsonAdapter` mechanism, project target `<project>/.mcp.json`, no global target (raises). A new scope-aware `normalize_harness_tokens` collapses `claude-code`/`pi` → `standard` at project scope only. A `STANDARD_MCP_READERS` map (covered set `{claude-code, pi}`) drives `list`/`status` display. `doctor` gains a read-only `legacy-standard-dedup` finding. No lock schema migration — `standard` is a new harness *value*.

**Tech Stack:** Python 3.13, Click, pytest, the existing `mcp_adapters` / `mcp_install` / `mcp_lock` modules.

**Spec:** `docs/superpowers/specs/2026-06-13-399-mcp-standard-projection-design.md`

---

## File structure

| File | Responsibility | Action |
|---|---|---|
| `src/agent_toolkit_cli/mcp_standard.py` | `STANDARD_MCP_READERS` SSOT + `mcp_standard_covered(scope)` | Create |
| `src/agent_toolkit_cli/mcp_adapters/json_config.py` | Add `standard` `_Cell` (project target; global raises) | Modify |
| `src/agent_toolkit_cli/mcp_adapters/__init__.py` | Add `"standard": "json"` to `_MECHANISM` | Modify |
| `src/agent_toolkit_cli/commands/mcp/_common.py` | `normalize_harness_tokens` + `default_harnesses(scope)` + `_CHOICE_HARNESSES`; rewrite the "not ported" comment | Modify |
| `src/agent_toolkit_cli/commands/mcp/install_cmd.py` | Scope-aware default + `standard` in Choice + normalize | Modify |
| `src/agent_toolkit_cli/commands/mcp/uninstall_cmd.py` | `standard` in Choice + normalize | Modify |
| `src/agent_toolkit_cli/commands/mcp/list_cmd.py` | Additive `standard → claude-code, pi` line | Modify |
| `src/agent_toolkit_cli/commands/mcp/status_cmd.py` | `standard` covered-set annotation | Modify |
| `src/agent_toolkit_cli/commands/mcp/doctor_cmd.py` | `legacy-standard-dedup` read-only finding | Modify |
| `tests/test_mcp_standard.py` | Adapter + covered-set + normalize unit tests | Create |
| `tests/test_cli_mcp.py` | CLI default-set / list / status / doctor tests | Modify |

---

## Task 1: `STANDARD_MCP_READERS` covered-set SSOT

**Files:**
- Create: `src/agent_toolkit_cli/mcp_standard.py`
- Test: `tests/test_mcp_standard.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mcp_standard.py
"""Tests for the MCP standard projection: covered set, adapter, normalization."""
from __future__ import annotations

import pytest


def test_standard_covered_project_is_claude_and_pi():
    from agent_toolkit_cli.mcp_standard import mcp_standard_covered
    assert mcp_standard_covered("project") == frozenset({"claude-code", "pi"})


def test_standard_covered_unknown_scope_raises():
    from agent_toolkit_cli.mcp_standard import mcp_standard_covered
    with pytest.raises(KeyError):
        mcp_standard_covered("global")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_mcp_standard.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_toolkit_cli.mcp_standard'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/agent_toolkit_cli/mcp_standard.py
"""The MCP `standard` projection: the shared project `.mcp.json` slot.

`standard` owns the canonical `mcpServers.<slug>` entry in `<project>/.mcp.json`
— the file the claude-code AND pi MCP adapters already write at project scope
(json_config.py). Promoting it to a named projection collapses that double-write
into one token / one lock row, mirroring the agent kind's standard slot
(agent_adapters/standard.py, #361).

Covered set is HONEST and small. Despite an active proposal
(modelcontextprotocol#2218) to make root `.mcp.json` a universal standard, today
only claude-code reads a bare root `.mcp.json` and pi shares it via our own
adapter — so the covered set is {claude-code, pi}. It grows only as real clients
adopt the convention. There is NO global scope: no client reads `~/.mcp.json`.
"""
from __future__ import annotations

# Harnesses whose project config IS the shared .mcp.json `standard` owns.
# Project-scope only — there is no global standard (no `~/.mcp.json` reader).
STANDARD_MCP_READERS: dict[str, frozenset[str]] = {
    "project": frozenset({"claude-code", "pi"}),
}


def mcp_standard_covered(scope: str) -> frozenset[str]:
    """Covered harness set for a scope. KeyError on a scope with no standard
    (e.g. 'global') — fail loud, mirrors agent_adapters.standard.agents_standard_covered."""
    return STANDARD_MCP_READERS[scope]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_mcp_standard.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/mcp_standard.py tests/test_mcp_standard.py
git commit -m "feat(mcp): standard covered-set SSOT (#399)"
```

---

## Task 2: `standard` JSON adapter cell

**Files:**
- Modify: `src/agent_toolkit_cli/mcp_adapters/json_config.py:79-104` (CELLS dict)
- Modify: `src/agent_toolkit_cli/mcp_adapters/__init__.py:29-34` (_MECHANISM)
- Test: `tests/test_mcp_standard.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mcp_standard.py — append
import json


def _inner():
    return {"type": "stdio", "command": "npx", "args": ["-y", "ctx7"]}


def test_standard_adapter_writes_shared_mcp_json(tmp_path):
    from agent_toolkit_cli.mcp_adapters import get_adapter
    project = tmp_path / "proj"
    project.mkdir()
    written = get_adapter("standard").install(
        "context7", _inner(), scope="project", home=tmp_path, project=project,
    )
    assert written == project / ".mcp.json"
    doc = json.loads(written.read_text())
    assert doc["mcpServers"]["context7"] == _inner()


def test_standard_adapter_preserves_siblings_and_is_idempotent(tmp_path):
    from agent_toolkit_cli.mcp_adapters import get_adapter
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"keep": {"command": "x"}}}, indent=2) + "\n"
    )
    adapter = get_adapter("standard")
    adapter.install("context7", _inner(), scope="project", home=tmp_path, project=project)
    first = (project / ".mcp.json").read_text()
    adapter.install("context7", _inner(), scope="project", home=tmp_path, project=project)
    assert (project / ".mcp.json").read_text() == first  # idempotent
    doc = json.loads(first)
    assert doc["mcpServers"]["keep"] == {"command": "x"}   # sibling preserved
    assert doc["mcpServers"]["context7"] == _inner()


def test_standard_adapter_global_target_raises(tmp_path):
    """No global standard exists — a global config_target must fail loud."""
    from agent_toolkit_cli.mcp_adapters import get_adapter
    with pytest.raises(ValueError, match="no global target"):
        get_adapter("standard").config_target(scope="global", home=tmp_path, project=None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_mcp_standard.py -k standard_adapter -v`
Expected: FAIL — `UnsupportedMcpHarnessError: standard: no MCP adapter` (standard not yet in `_MECHANISM`).

- [ ] **Step 3: Write minimal implementation**

In `src/agent_toolkit_cli/mcp_adapters/json_config.py`, add a module-level helper above `CELLS` and a `standard` cell. First add the global-raise helper after `_opencode_translate` (before the `CELLS` dict, ~line 77):

```python
def _no_global_standard(home: Path) -> Path:
    """`standard` is a PROJECT-scope projection — there is no `~/.mcp.json`
    reader, so a global standard target is a loud, structured failure."""
    raise ValueError(
        "standard: no global target — standard is a project-scope projection "
        "(no client reads ~/.mcp.json)"
    )
```

Then add the cell inside `CELLS` (after the `pi` cell, ~line 96):

```python
    "standard": _Cell(
        name="standard",
        user_target=_no_global_standard,
        project_target=lambda proj: proj / ".mcp.json",
        servers_key="mcpServers",
        translate=_passthrough,
    ),
```

In `src/agent_toolkit_cli/mcp_adapters/__init__.py`, add `standard` to `_MECHANISM` (after `"pi": "json",`, ~line 31):

```python
    "standard": "json",
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_mcp_standard.py -k standard_adapter -v`
Expected: PASS (3 passed). The `config_target(scope="global")` path raises `ValueError` because `_JsonAdapter.config_target` calls `self._cell.user_target(home)` for global scope, which is `_no_global_standard`.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/mcp_adapters/json_config.py src/agent_toolkit_cli/mcp_adapters/__init__.py tests/test_mcp_standard.py
git commit -m "feat(mcp): standard JSON adapter cell (project target, global raises) (#399)"
```

---

## Task 3: `normalize_harness_tokens` (scope-aware) + helpers in `_common.py`

**Files:**
- Modify: `src/agent_toolkit_cli/commands/mcp/_common.py` (whole file — add functions, rewrite the "not ported" comment)
- Test: `tests/test_mcp_standard.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mcp_standard.py — append
import click


def test_normalize_project_collapses_claude_and_pi():
    from agent_toolkit_cli.commands.mcp._common import normalize_harness_tokens
    out = normalize_harness_tokens(("claude-code", "pi"), scope="project")
    assert out == ("standard",)  # both → standard, deduped


def test_normalize_project_keeps_outliers_and_order():
    from agent_toolkit_cli.commands.mcp._common import normalize_harness_tokens
    out = normalize_harness_tokens(("claude-code", "codex", "opencode"), scope="project")
    assert out == ("standard", "codex", "opencode")


def test_normalize_project_standard_token_passes_through():
    from agent_toolkit_cli.commands.mcp._common import normalize_harness_tokens
    assert normalize_harness_tokens(("standard",), scope="project") == ("standard",)


def test_normalize_global_does_not_normalize_claude_or_pi():
    from agent_toolkit_cli.commands.mcp._common import normalize_harness_tokens
    out = normalize_harness_tokens(("claude-code", "pi"), scope="global")
    assert out == ("claude-code", "pi")  # NO normalization at global scope


def test_normalize_global_rejects_standard_token():
    from agent_toolkit_cli.commands.mcp._common import normalize_harness_tokens
    with pytest.raises(click.UsageError, match="standard.*project"):
        normalize_harness_tokens(("standard",), scope="global")


def test_default_harnesses_project_is_standard_codex_opencode():
    from agent_toolkit_cli.commands.mcp._common import default_harnesses
    assert default_harnesses("project") == ("standard", "codex", "opencode")


def test_default_harnesses_global_is_the_concrete_four():
    from agent_toolkit_cli.commands.mcp._common import default_harnesses
    assert default_harnesses("global") == ("claude-code", "codex", "opencode", "pi")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_mcp_standard.py -k "normalize or default_harnesses" -v`
Expected: FAIL — `ImportError: cannot import name 'normalize_harness_tokens'`.

- [ ] **Step 3: Write minimal implementation**

In `src/agent_toolkit_cli/commands/mcp/_common.py`, rewrite the module docstring's "not ported" paragraph (lines 8-12) to explain the reversal, then add the new functions after `_HARNESSES`. Replace the docstring lines 8-12:

```python
parse_harness_tokens IS now ported (#399) but as a SCOPE-AWARE normalizer:
at PROJECT scope `claude-code` and `pi` both normalize to `standard` (the
shared <project>/.mcp.json IS the standard slot — see mcp_standard.py); at
GLOBAL scope there is NO standard (no `~/.mcp.json` reader), so they pass
through unchanged and a `standard` token is rejected. This reverses the prior
"deliberately not ported" decision: the project `.mcp.json` genuinely is a
standard slot, it is just project-scoped.
```

Then add after `_HARNESSES` (line 30):

```python
# The --harness Choice universe: the four concrete harnesses + the synthetic
# `standard` token. Validation is permissive here; normalize_harness_tokens and
# the adapter enforce the scope rules (standard is project-only).
_CHOICE_HARNESSES: tuple[str, ...] = (*_HARNESSES, "standard")


def default_harnesses(scope: str) -> tuple[str, ...]:
    """The no-flag install target set, scope-aware.

    Project: `standard` (covers claude-code+pi via the shared .mcp.json) plus the
    genuine outliers codex (TOML) and opencode (`mcp` key) — one .mcp.json write,
    no double-write. Global: the concrete four (no standard exists globally)."""
    if scope == "project":
        return ("standard", "codex", "opencode")
    return _HARNESSES


def normalize_harness_tokens(tokens: tuple[str, ...], *, scope: str) -> tuple[str, ...]:
    """Normalize explicit --harness tokens, scope-aware, order-preserving + deduped.

    Project: claude-code → standard, pi → standard (the shared .mcp.json is the
    standard slot). Global: no normalization; a `standard` token is rejected
    (there is no global standard). Mirrors commands/agent/_common.py but on the
    already-split tuple (MCP uses a repeatable --harness flag, not a comma string)
    and with the project/global asymmetry the agent kind lacks."""
    if scope == "project":
        mapped = ["standard" if t in ("claude-code", "pi") else t for t in tokens]
    else:
        if "standard" in tokens:
            raise click.UsageError(
                "standard is a project-scope projection; it has no global target "
                "(no client reads ~/.mcp.json). Use -p, or name a concrete harness."
            )
        mapped = list(tokens)
    seen: set[str] = set()
    out: list[str] = []
    for t in mapped:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return tuple(out)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_mcp_standard.py -k "normalize or default_harnesses" -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/mcp/_common.py tests/test_mcp_standard.py
git commit -m "feat(mcp): scope-aware harness normalization + default set (#399)"
```

---

## Task 4: Wire `install_cmd` to scope-aware default + normalize + `standard` Choice

**Files:**
- Modify: `src/agent_toolkit_cli/commands/mcp/install_cmd.py:14,33,50-57`
- Test: `tests/test_cli_mcp.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_mcp.py — append
def test_mcp_install_project_default_is_standard_not_double_write(tmp_path, monkeypatch):
    """No --harness at project scope → one `standard` lock row for .mcp.json,
    NOT separate claude-code + pi rows (the de-dup #399 delivers)."""
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    result = CliRunner().invoke(main, ["mcp", "install", "context7", "-p"])
    assert result.exit_code == 0, result.output
    # .mcp.json has the entry
    doc = json.loads((project / ".mcp.json").read_text())
    assert "context7" in doc["mcpServers"]
    # lock has ONE standard row for the shared file, no claude-code/pi rows
    lock = json.loads((project / "mcps-lock.json").read_text())
    harnesses = {e["harness"] for e in lock["mcps"]["context7"]}
    assert "standard" in harnesses
    assert "claude-code" not in harnesses
    assert "pi" not in harnesses


def test_mcp_install_claude_and_pi_collapse_to_standard(tmp_path, monkeypatch):
    """Explicit --harness claude-code --harness pi at project scope → one write,
    one standard row."""
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    result = CliRunner().invoke(
        main,
        ["mcp", "install", "context7", "--harness", "claude-code", "--harness", "pi", "-p"],
    )
    assert result.exit_code == 0, result.output
    lock = json.loads((project / "mcps-lock.json").read_text())
    harnesses = [e["harness"] for e in lock["mcps"]["context7"]]
    assert harnesses == ["standard"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_mcp.py -k "default_is_standard or collapse_to_standard" -v`
Expected: FAIL — the lock will contain `claude-code`/`pi` rows (current behavior), so the `not in harnesses` assertions fail.

- [ ] **Step 3: Write minimal implementation**

In `src/agent_toolkit_cli/commands/mcp/install_cmd.py`:

Change the import (line 14):

```python
from agent_toolkit_cli.commands.mcp._common import (
    _CHOICE_HARNESSES,
    default_harnesses,
    normalize_harness_tokens,
    scope_and_roots,
)
```

Change the Choice (line 32-35):

```python
@click.option(
    "--harness", "harnesses", multiple=True,
    type=click.Choice(_CHOICE_HARNESSES),
    help="Harness to install into (repeatable). Default: standard + codex + opencode (project).",
)
```

Replace the target resolution (line 57) — after `scope, home, project = scope_and_roots(...)` and `effective_home`/`library` are computed:

```python
    if harnesses:
        targets = list(normalize_harness_tokens(tuple(harnesses), scope=scope))
    else:
        targets = list(default_harnesses(scope))
```

(Remove the old `targets = list(harnesses) or list(_HARNESSES)` line and the now-unused `_HARNESSES` import.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_mcp.py -k "default_is_standard or collapse_to_standard" -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Run the existing install tests (regression guard)**

Run: `uv run pytest tests/test_cli_mcp.py -k install -v`
Expected: PASS — including `test_mcp_install_project_claude` (explicit `--harness claude-code -p` still writes `.mcp.json`; note its lock row is now `standard`, but that test only asserts the `.mcp.json` content, which is unchanged).

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/commands/mcp/install_cmd.py tests/test_cli_mcp.py
git commit -m "feat(mcp): install uses scope-aware default + standard normalization (#399)"
```

---

## Task 5: Wire `uninstall_cmd` to `standard` Choice + normalize

**Files:**
- Modify: `src/agent_toolkit_cli/commands/mcp/uninstall_cmd.py:16,33-37,59-66`
- Test: `tests/test_cli_mcp.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_mcp.py — append
def test_mcp_uninstall_standard_removes_only_named_entry(tmp_path, monkeypatch):
    """Install via standard, hand-add a sibling, uninstall standard → only ours gone."""
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    CliRunner().invoke(main, ["mcp", "install", "context7", "-p"])
    # hand-add a sibling entry
    doc = json.loads((project / ".mcp.json").read_text())
    doc["mcpServers"]["sibling"] = {"command": "z"}
    (project / ".mcp.json").write_text(json.dumps(doc, indent=2) + "\n")
    result = CliRunner().invoke(
        main, ["mcp", "uninstall", "context7", "--harness", "standard", "-p"],
    )
    assert result.exit_code == 0, result.output
    doc2 = json.loads((project / ".mcp.json").read_text())
    assert "context7" not in doc2["mcpServers"]
    assert doc2["mcpServers"]["sibling"] == {"command": "z"}


def test_mcp_uninstall_claude_normalizes_to_standard(tmp_path, monkeypatch):
    """`--harness claude-code -p` on a standard-installed slug resolves to the
    standard row (normalization is symmetric with install)."""
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    CliRunner().invoke(main, ["mcp", "install", "context7", "-p"])  # standard row
    result = CliRunner().invoke(
        main, ["mcp", "uninstall", "context7", "--harness", "claude-code", "-p"],
    )
    assert result.exit_code == 0, result.output
    doc = json.loads((project / ".mcp.json").read_text())
    assert "context7" not in doc["mcpServers"]
    lock = json.loads((project / "mcps-lock.json").read_text())
    assert "context7" not in lock["mcps"]  # standard row removed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_mcp.py -k "uninstall_standard or uninstall_claude_normalizes" -v`
Expected: FAIL — `test_mcp_uninstall_standard...` fails at the Choice (`standard` not a valid `--harness`); `test_mcp_uninstall_claude_normalizes...` fails because `--harness claude-code` targets a non-existent `claude-code` lock row, leaving the standard row + `.mcp.json` entry in place.

- [ ] **Step 3: Write minimal implementation**

In `src/agent_toolkit_cli/commands/mcp/uninstall_cmd.py`:

Change the import (line 16):

```python
from agent_toolkit_cli.commands.mcp._common import (
    _CHOICE_HARNESSES,
    normalize_harness_tokens,
    scope_and_roots,
)
```

Change the Choice (line 33-37):

```python
@click.option(
    "--harness", "harnesses", multiple=True,
    type=click.Choice(_CHOICE_HARNESSES),
    help="Harness to remove from (repeatable). Default: every harness in the lock.",
)
```

Change the targets block (line 59-66):

```python
    if harnesses:
        targets = list(normalize_harness_tokens(tuple(harnesses), scope=scope))
    else:
        lock_path = lock_path_for_scope(scope, home=effective_home, project=project)
        lock = read_lock(lock_path)
        targets = [e.harness for e in lock.get(slug, [])]
        if not targets:
            raise click.ClickException(f"{slug} is not installed at {scope} scope")
```

(`_HARNESSES` is still imported for nothing now — remove it from the import if unused, or keep only what's referenced. After this change `uninstall_cmd` no longer references `_HARNESSES`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_mcp.py -k "uninstall_standard or uninstall_claude_normalizes" -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/mcp/uninstall_cmd.py tests/test_cli_mcp.py
git commit -m "feat(mcp): uninstall accepts + normalizes standard (#399)"
```

---

## Task 6: `list` — additive `standard → claude-code, pi` covered-set line

**Files:**
- Modify: `src/agent_toolkit_cli/commands/mcp/list_cmd.py:17-20,100-119`
- Test: `tests/test_cli_mcp.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_mcp.py — append
def test_mcp_list_standard_row_shows_covered_set(tmp_path, monkeypatch):
    """A standard lock row prints its covered set: claude-code, pi."""
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    CliRunner().invoke(main, ["mcp", "install", "context7", "-p"])  # standard row
    result = CliRunner().invoke(main, ["mcp", "list", "-p"])
    assert result.exit_code == 0, result.output
    assert "standard" in result.output
    assert "claude-code" in result.output and "pi" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_mcp.py -k list_standard_row -v`
Expected: FAIL — the current `list` iterates only `_HARNESSES` (concrete four); it prints per-harness marks but no `standard` covered-set line.

- [ ] **Step 3: Write minimal implementation**

In `src/agent_toolkit_cli/commands/mcp/list_cmd.py`, add the import (after line 19):

```python
from agent_toolkit_cli.mcp_standard import STANDARD_MCP_READERS, mcp_standard_covered
```

Then, inside the `for slug in slugs:` loop, after the existing `for harness in _HARNESSES:` per-harness mark block (after line 119), add the standard expansion:

```python
        # #399: if this slug has a `standard` lock row, print its covered set so
        # the user sees the shared .mcp.json reaches claude-code + pi via one row.
        if "standard" in locked and scope in STANDARD_MCP_READERS:
            covered = ", ".join(sorted(mcp_standard_covered(scope)))
            click.echo(f"  ✔ standard → {covered}")
```

(`locked` is the dict built at line 100: `locked = {e.harness: e for e in lock.get(slug, [])}`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_mcp.py -k list_standard_row -v`
Expected: PASS.

- [ ] **Step 5: Run existing list tests (regression guard)**

Run: `uv run pytest tests/test_cli_mcp.py -k list -v`
Expected: PASS — existing `test_mcp_list_shows_seeded_slug` and the unmanaged-entry tests unaffected (the per-harness loop and path-dedup are untouched).

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/commands/mcp/list_cmd.py tests/test_cli_mcp.py
git commit -m "feat(mcp): list expands standard row to its covered set (#399)"
```

---

## Task 7: `status` — `standard` covered-set annotation

**Files:**
- Modify: `src/agent_toolkit_cli/commands/mcp/status_cmd.py:53-57`
- Test: `tests/test_cli_mcp.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_mcp.py — append
def test_mcp_status_standard_row_annotated(tmp_path, monkeypatch):
    """status annotates a standard row with its covered set."""
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    CliRunner().invoke(main, ["mcp", "install", "context7", "-p"])  # standard row
    result = CliRunner().invoke(main, ["mcp", "status", "-p"])
    assert result.exit_code == 0, result.output
    assert "standard" in result.output
    assert "claude-code" in result.output and "pi" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_mcp.py -k status_standard_row -v`
Expected: FAIL — `status` prints `context7\tstandard\tfloating` with no covered-set annotation, so `claude-code`/`pi` are absent from the output.

- [ ] **Step 3: Write minimal implementation**

In `src/agent_toolkit_cli/commands/mcp/status_cmd.py`, change `_echo_slug` (lines 53-57):

```python
def _echo_slug(slug: str, entries: list) -> None:
    """One line per (slug, harness): `<slug>\t<harness>\t<pin|floating>`. A
    `standard` harness row is annotated with its covered set (#399)."""
    from agent_toolkit_cli.mcp_standard import mcp_standard_covered

    for entry in sorted(entries, key=lambda e: e.harness):
        pin = entry.pin if entry.pin else "floating"
        line = f"{slug}\t{entry.harness}\t{pin}"
        if entry.harness == "standard":
            try:
                covered = ", ".join(sorted(mcp_standard_covered("project")))
                line += f"\t→ {covered}"
            except KeyError:
                pass
        click.echo(line)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_mcp.py -k status_standard_row -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/mcp/status_cmd.py tests/test_cli_mcp.py
git commit -m "feat(mcp): status annotates standard row with covered set (#399)"
```

---

## Task 8: `doctor` — `legacy-standard-dedup` read-only finding

**Files:**
- Modify: `src/agent_toolkit_cli/commands/mcp/doctor_cmd.py:103-167` (`_diagnose`)
- Test: `tests/test_cli_mcp.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_mcp.py — append
def test_mcp_doctor_flags_legacy_standard_dedup(tmp_path, monkeypatch):
    """A project lock with BOTH claude-code + pi rows for one slug (the pre-#399
    shape) is flagged for collapse to `standard`. Read-only: lock unchanged."""
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    # Write a legacy two-row lock by hand, and the matching .mcp.json entry.
    (project / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"context7": {"type": "stdio", "command": "npx",
         "args": ["-y", "ctx7@9.9.9"]}}}, indent=2) + "\n"
    )
    (project / "mcps-lock.json").write_text(json.dumps({
        "version": 1,
        "mcps": {"context7": [
            {"harness": "claude-code", "source": "npx", "pin": "9.9.9"},
            {"harness": "pi", "source": "npx", "pin": "9.9.9"},
        ]},
    }, indent=2) + "\n")
    before = (project / "mcps-lock.json").read_text()
    result = CliRunner().invoke(main, ["mcp", "doctor", "-p"])
    assert "legacy-standard-dedup" in result.output
    assert "context7" in result.output
    # read-only: doctor must not have rewritten the lock
    assert (project / "mcps-lock.json").read_text() == before
    assert result.exit_code == 1  # findings present → exit 1 (existing contract)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_mcp.py -k legacy_standard_dedup -v`
Expected: FAIL — `legacy-standard-dedup` not in output (no such finding exists yet). Note the existing drift checks may emit `drifted`/`missing` for these rows, but never `legacy-standard-dedup`.

- [ ] **Step 3: Write minimal implementation**

In `src/agent_toolkit_cli/commands/mcp/doctor_cmd.py`, inside `_diagnose`, add the legacy-dedup check at the top of the `for slug in sorted(lock):` loop body — after `entries = lock[slug]` (line 117), before the env/per-entry loop:

```python
        # #399: legacy two-row standard de-dup. A project lock with BOTH
        # claude-code AND pi rows for one slug predates the `standard`
        # projection — both write the shared <project>/.mcp.json, so they
        # should collapse to a single `standard` row. Read-only finding:
        # remediation is `mcp install <slug> -p` (which now resolves to
        # standard and upserts one row).
        if scope == "project":
            row_harnesses = {e.harness for e in entries}
            if "claude-code" in row_harnesses and "pi" in row_harnesses:
                findings.append(Finding(
                    slug=slug, harness="standard",
                    finding_type="legacy-standard-dedup",
                    detail=(
                        "project lock has separate claude-code + pi rows for the "
                        "shared .mcp.json; collapse to one `standard` row with "
                        f"`mcp install {slug} -p`"
                    ),
                ))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_mcp.py -k legacy_standard_dedup -v`
Expected: PASS. (The finding appends alongside any drift findings; the `exit 1` contract at `doctor_cmd.py:212` already fires when findings is non-empty.)

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/mcp/doctor_cmd.py tests/test_cli_mcp.py
git commit -m "feat(mcp): doctor flags legacy claude-code+pi lock for standard dedup (#399)"
```

---

## Task 9: Reconcile existing tests broken by the project-default change

The project-scope no-flag default changes from the four concrete harnesses to
`(standard, codex, opencode)`, and `--harness claude-code/pi -p` now produces a
`standard` lock row. Two existing tests in `tests/test_cli_mcp.py` bake in the
old behavior and MUST be updated (intended behavior change, not a regression).
Audit them explicitly before the full-suite run.

**Files:**
- Modify: `tests/test_cli_mcp.py` (`test_install_all_four_harnesses_round_trip`, ~line 540)

- [ ] **Step 1: Run the two at-risk tests to see the breakage**

Run: `uv run pytest tests/test_cli_mcp.py -k "all_four_harnesses_round_trip or status_after_install" -v`
Expected:
- `test_mcp_status_after_install` (line 122) — likely still PASSES: it installs `--harness claude-code -p`, then asserts `"claude-code" in status output`. The lock row is now `standard`, but the new `→ claude-code, pi` covered-set annotation (Task 7) keeps the substring present. Leave it as-is; it is still a valid assertion.
- `test_install_all_four_harnesses_round_trip[-p, project]` — inspect: the `r1 = install context7 -p` no longer fans to four; at project scope it writes `(standard, codex, opencode)`. The post-uninstall `is_installed` loop over all four still passes (claude-code/pi read the `.mcp.json` that standard removed; opencode/codex were installed+removed). But the `# default = all four` comment is now FALSE and the lock-row assertion's intent shifted. Confirm whether it passes or fails as written.

- [ ] **Step 2: Update `test_install_all_four_harnesses_round_trip` for the project default**

Split the project-scope expectation from global. The global branch keeps `# default = all four`. For the project branch, the no-flag default is `(standard, codex, opencode)` and the round-trip-clean assertion still holds (all four `is_installed` are False after uninstall, because claude-code/pi read the standard-owned `.mcp.json`). Update only the misleading comment and add a project-scope lock-shape assertion after `r1`:

```python
    r1 = runner.invoke(main, ["mcp", "install", "context7", scope_flag])  # global: four; project: standard+codex+opencode
    assert r1.exit_code == 0, r1.output

    # #399: at project scope the no-flag default writes ONE standard row for the
    # shared .mcp.json (not separate claude-code+pi rows) plus codex+opencode.
    if scope_name == "project":
        from agent_toolkit_cli.mcp_lock import lock_path_for_scope as _lp, read_lock as _rl
        _lk = _rl(_lp("project", home=tmp_path, project=project))
        _hs = {e.harness for e in _lk["context7"]}
        assert "standard" in _hs and "claude-code" not in _hs and "pi" not in _hs
```

(The rest of the test — the uninstall and the all-four `is_installed`-False loop — is unchanged and still correct: standard's uninstall clears `.mcp.json`, so claude-code/pi read clean.)

- [ ] **Step 3: Run the updated test**

Run: `uv run pytest tests/test_cli_mcp.py -k all_four_harnesses_round_trip -v`
Expected: PASS at both `-g` and `-p`.

- [ ] **Step 4: Run the full MCP test surface**

Run: `uv run pytest tests/test_mcp_standard.py tests/test_cli_mcp.py tests/test_mcp_adapters_json.py tests/test_mcp_install.py tests/test_mcp_lock.py -v`
Expected: PASS (all green).

- [ ] **Step 5: Run the whole suite**

Run: `uv run pytest -q 2>&1 | tail -20`
Expected: PASS except the 2 known-whitelisted HOME-isolation env failures (`test_empty_machine_is_empty` / inventory global-pi). Reproduce those on `main` if uncertain; they are pre-existing and unrelated.

- [ ] **Step 6: Lint + type gate**

Run: `uv run ruff check src/agent_toolkit_cli/mcp_standard.py src/agent_toolkit_cli/commands/mcp/ src/agent_toolkit_cli/mcp_adapters/ && uv run mypy src/agent_toolkit_cli/mcp_standard.py src/agent_toolkit_cli/commands/mcp/`
Expected: net-zero NEW ruff/mypy errors vs `main` (the repo carries pre-existing mypy debt; the bar is "no NEW errors in touched files").

- [ ] **Step 7: Final commit (if any lint/type fixes were needed)**

```bash
git add -A
git commit -m "chore(mcp): lint/type clean for standard projection (#399)"
```

---

## Acceptance-criteria → task map

| AC (issue #399) | Task |
|---|---|
| `standard` project target writes `mcpServers.<slug>`, preserves siblings | 2 |
| claude-code/pi normalize to standard at project scope | 3, 4 |
| global: NO normalization, no standard target | 2 (raise), 3 (reject) |
| install/list/status/doctor understand standard; list/status expand covered set | 4, 6, 7, 8 |
| lock records standard as a new value, no schema migration | 2, 4 (verified in lock JSON) |
| doctor reconciles legacy two-row lock, non-destructively | 8 |
| manage-by-name preserved (collision warning covers standard) | 2 (adapter reuse) |
| codex/opencode unaffected | 4, 9 (regression) |
