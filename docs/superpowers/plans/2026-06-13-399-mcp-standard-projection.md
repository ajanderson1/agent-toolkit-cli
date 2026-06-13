# MCP `standard` Projection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a project-scope `standard` projection to the MCP kind that owns the shared `<project>/.mcp.json` `mcpServers` entry, normalizing `claude-code`+`pi` to a single `standard` token/lock-row at project scope — with a migration that genuinely converges legacy two-row locks.

**Architecture:** `standard` is a thin specialization of the existing JSON adapter — same `_JsonAdapter` mechanism, project target `<project>/.mcp.json`, no global target (raises). A new scope-aware `normalize_harness_tokens` collapses `claude-code`/`pi` → `standard` at project scope only. **Collapse-on-install**: `apply()` drops covered legacy rows into the same atomic `write_lock` when writing `standard`, so the doctor remediation converges (the one facade change). A `STANDARD_MCP_READERS` map drives `list`/`status` display; `list`'s `tracked_by_path` learns `standard` so managed entries aren't falsely flagged unmanaged. `doctor` gains a `legacy-standard-dedup` finding and `standard`-row coverage. No lock schema migration — `standard` is a new harness *value*.

**Tech Stack:** Python 3.13, Click, pytest, the existing `mcp_adapters` / `mcp_install` / `mcp_lock` modules.

**Spec:** `docs/superpowers/specs/2026-06-13-399-mcp-standard-projection-design.md`

**Deep-review findings folded in (2026-06-13):** collapse-on-install (was a no-op remediation), `list` false-unmanaged, doctor `standard`-row coverage + global guard, update/remove coverage, naming drift.

---

## File structure

| File | Responsibility | Action |
|---|---|---|
| `src/agent_toolkit_cli/mcp_standard.py` | `STANDARD_MCP_READERS` SSOT + `mcp_standard_covered(scope)` | Create |
| `src/agent_toolkit_cli/mcp_adapters/json_config.py` | Add `standard` `_Cell` (project target; global raises) | Modify |
| `src/agent_toolkit_cli/mcp_adapters/__init__.py` | Add `"standard": "json"` to `_MECHANISM` | Modify |
| `src/agent_toolkit_cli/mcp_lock.py` | `collapse_covered()` helper + open-set docstring note | Modify |
| `src/agent_toolkit_cli/mcp_install.py` | Collapse-on-install in `apply()` (the one facade change) | Modify |
| `src/agent_toolkit_cli/commands/mcp/_common.py` | `normalize_harness_tokens` + `default_harnesses(scope)` + `_CHOICE_HARNESSES`; rewrite the "not ported" comment | Modify |
| `src/agent_toolkit_cli/commands/mcp/install_cmd.py` | Scope-aware default + `standard` in Choice + normalize | Modify |
| `src/agent_toolkit_cli/commands/mcp/uninstall_cmd.py` | `standard` in Choice + normalize | Modify |
| `src/agent_toolkit_cli/commands/mcp/list_cmd.py` | `standard → claude-code, pi` line + `tracked_by_path` fix | Modify |
| `src/agent_toolkit_cli/commands/mcp/status_cmd.py` | `standard` covered-set annotation (scope-keyed) | Modify |
| `src/agent_toolkit_cli/commands/mcp/doctor_cmd.py` | `legacy-standard-dedup` finding + `standard`-row coverage | Modify |
| `tests/test_mcp_standard.py` | Adapter + covered-set + normalize + collapse unit tests | Create |
| `tests/test_cli_mcp.py` | CLI default/list/status/doctor/update/remove tests | Modify |

---

## Task 1: `STANDARD_MCP_READERS` covered-set SSOT

**Files:**
- Create: `src/agent_toolkit_cli/mcp_standard.py`
- Test: `tests/test_mcp_standard.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mcp_standard.py
"""Tests for the MCP standard projection: covered set, adapter, normalization, collapse."""
from __future__ import annotations

import json

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

In `src/agent_toolkit_cli/mcp_adapters/json_config.py`, add the global-raise helper after `_opencode_translate` (before the `CELLS` dict, ~line 77):

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
Expected: PASS (3 passed). `config_target(scope="global")` raises `ValueError` because `_JsonAdapter.config_target` calls `self._cell.user_target(home)` for global scope, which is `_no_global_standard`.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/mcp_adapters/json_config.py src/agent_toolkit_cli/mcp_adapters/__init__.py tests/test_mcp_standard.py
git commit -m "feat(mcp): standard JSON adapter cell (project target, global raises) (#399)"
```

---

## Task 3: `collapse_covered` lock helper + open-set docstring note

**Files:**
- Modify: `src/agent_toolkit_cli/mcp_lock.py` (add `collapse_covered`, docstring note)
- Test: `tests/test_mcp_standard.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mcp_standard.py — append
def test_collapse_covered_drops_covered_rows_for_slug():
    from agent_toolkit_cli.mcp_lock import McpLockEntry, collapse_covered
    lock = {
        "context7": [
            McpLockEntry("context7", "standard", "npx", "9.9.9"),
            McpLockEntry("context7", "claude-code", "npx", "9.9.9"),
            McpLockEntry("context7", "pi", "npx", "9.9.9"),
            McpLockEntry("context7", "codex", "npx", "9.9.9"),
        ],
        "other": [McpLockEntry("other", "claude-code", "npx", None)],
    }
    out = collapse_covered(lock, "context7", frozenset({"claude-code", "pi"}))
    harnesses = sorted(e.harness for e in out["context7"])
    assert harnesses == ["codex", "standard"]          # claude-code + pi dropped
    assert {e.harness for e in out["other"]} == {"claude-code"}  # other slug untouched


def test_collapse_covered_is_noop_when_no_covered_rows():
    from agent_toolkit_cli.mcp_lock import McpLockEntry, collapse_covered
    lock = {"context7": [McpLockEntry("context7", "standard", "npx", None)]}
    out = collapse_covered(lock, "context7", frozenset({"claude-code", "pi"}))
    assert [e.harness for e in out["context7"]] == ["standard"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_mcp_standard.py -k collapse_covered -v`
Expected: FAIL — `ImportError: cannot import name 'collapse_covered'`.

- [ ] **Step 3: Write minimal implementation**

In `src/agent_toolkit_cli/mcp_lock.py`, add to the module docstring (after the lock-model paragraph, before `from __future__`):

```
The `harness` field is an OPEN value set (no enum). Adding a new value (e.g.
`standard`, #399) needs no structural migration — read_lock/write_lock round-trip
any string. The bound: a binary predating a value rejects that row at
get_adapter() dispatch (UnsupportedMcpHarnessError), so the "no migration" freedom
is forward-compatible ADDITIONS only, never a silent drop.
```

Then add `collapse_covered` after `remove_entry`:

```python
def collapse_covered(
    lock: dict[str, list[McpLockEntry]], slug: str, covered: frozenset[str],
) -> dict[str, list[McpLockEntry]]:
    """Drop every row for `slug` whose harness is in `covered` (#399).

    Used when writing a `standard` row: the covered harnesses (claude-code, pi)
    project the SAME .mcp.json that standard now owns, so their legacy rows must
    not coexist with the standard row (3 rows / 1 file → partial-uninstall
    corruption). Other slugs and non-covered harness rows are untouched."""
    out = {k: list(v) for k, v in lock.items()}
    if slug in out:
        out[slug] = [e for e in out[slug] if e.harness not in covered]
        if not out[slug]:
            del out[slug]
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_mcp_standard.py -k collapse_covered -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/mcp_lock.py tests/test_mcp_standard.py
git commit -m "feat(mcp): collapse_covered lock helper + open-set contract note (#399)"
```

---

## Task 4: Collapse-on-install in `apply()`

**Files:**
- Modify: `src/agent_toolkit_cli/mcp_install.py:154-162` (inside the per-harness loop / before write_lock)
- Test: `tests/test_mcp_install.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mcp_install.py — append (match the file's existing import style)
def test_apply_standard_collapses_legacy_claude_pi_rows(tmp_path):
    """Writing a `standard` row drops pre-existing claude-code/pi rows for the
    same slug (collapse-on-install), so the lock converges to one row."""
    import json
    from agent_toolkit_cli import mcp_install
    from agent_toolkit_cli.mcp_lock import lock_path_for_scope

    # Seed a library asset.
    library = tmp_path / ".agent-toolkit" / "mcps"
    d = library / "context7"
    d.mkdir(parents=True)
    (d / "config.json").write_text('{"type":"stdio","command":"npx","args":["-y","ctx7"]}\n')
    (d / "README.md").write_text("# context7\n")
    (library / "context7.toolkit.yaml").write_text(
        "name: context7\ndescription: x.\ntransport: stdio\ninstall_method: npx\nresolved_version: 1.0.0\n"
    )
    project = tmp_path / "proj"
    project.mkdir()
    # Seed a legacy two-row project lock.
    (project / "mcps-lock.json").write_text(json.dumps({
        "version": 1, "mcps": {"context7": [
            {"harness": "claude-code", "source": "npx", "pin": "1.0.0"},
            {"harness": "pi", "source": "npx", "pin": "1.0.0"},
        ]}}, indent=2) + "\n")

    mcp_install.apply(
        slug="context7", harnesses=["standard"], scope="project",
        library_root=library, home=tmp_path, project=project,
    )

    lock = json.loads((project / "mcps-lock.json").read_text())
    harnesses = [e["harness"] for e in lock["mcps"]["context7"]]
    assert harnesses == ["standard"]  # claude-code + pi collapsed away
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_mcp_install.py -k apply_standard_collapses -v`
Expected: FAIL — the lock keeps `claude-code` + `pi` + `standard` (3 rows): `upsert_entry` dedupes by harness name, so the legacy rows survive.

- [ ] **Step 3: Write minimal implementation**

In `src/agent_toolkit_cli/mcp_install.py`, inside `apply()`'s per-harness loop, after the existing `lock = upsert_entry(...)` call (~line 156-160), add the collapse for the `standard` harness at project scope. Add the import at the top of the file:

```python
from agent_toolkit_cli.mcp_lock import (
    McpLockEntry,
    collapse_covered,
    lock_path_for_scope,
    read_lock,
    remove_entry,
    upsert_entry,
    write_lock,
)
from agent_toolkit_cli.mcp_standard import mcp_standard_covered
```

Then, immediately after the `lock = upsert_entry(lock, McpLockEntry(...))` line:

```python
            # #399 collapse-on-install: writing `standard` drops the covered
            # legacy rows (claude-code/pi) for this slug, folded into the SAME
            # lock object written once below — so the 3-row state never persists.
            if harness == "standard" and scope == "project":
                lock = collapse_covered(lock, slug, mcp_standard_covered("project"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_mcp_install.py -k apply_standard_collapses -v`
Expected: PASS. The single `write_lock(lock_path, lock)` at the end of the loop persists the collapsed lock atomically.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/mcp_install.py tests/test_mcp_install.py
git commit -m "feat(mcp): collapse-on-install drops covered legacy rows when writing standard (#399)"
```

---

## Task 5: `normalize_harness_tokens` (scope-aware) + helpers in `_common.py`

**Files:**
- Modify: `src/agent_toolkit_cli/commands/mcp/_common.py` (add functions, rewrite the "not ported" comment)
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

In `src/agent_toolkit_cli/commands/mcp/_common.py`, rewrite the docstring "not ported" paragraph (lines 8-12):

```python
normalize_harness_tokens IS now ported (#399) but as a SCOPE-AWARE normalizer
(NOT named parse_harness_tokens — MCP uses a repeatable --harness flag, so it
takes an already-split tuple, not a comma string). At PROJECT scope `claude-code`
and `pi` both normalize to `standard` (the shared <project>/.mcp.json IS the
standard slot — see mcp_standard.py); at GLOBAL scope there is NO standard (no
`~/.mcp.json` reader), so they pass through unchanged and a `standard` token is
rejected. This reverses the prior "deliberately not ported" decision: the project
`.mcp.json` genuinely is a standard slot, it is just project-scoped.
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

## Task 6: Wire `install_cmd` to scope-aware default + normalize + `standard` Choice

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
    doc = json.loads((project / ".mcp.json").read_text())
    assert "context7" in doc["mcpServers"]
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


def test_mcp_install_collapses_preexisting_legacy_lock(tmp_path, monkeypatch):
    """A pre-existing legacy claude-code+pi lock is COLLAPSED by `install -p`
    (the doctor remediation genuinely converges, not a no-op)."""
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    (project / "mcps-lock.json").write_text(json.dumps({
        "version": 1, "mcps": {"context7": [
            {"harness": "claude-code", "source": "npx", "pin": "9.9.9"},
            {"harness": "pi", "source": "npx", "pin": "9.9.9"},
        ]}}, indent=2) + "\n")
    result = CliRunner().invoke(main, ["mcp", "install", "context7", "-p"])
    assert result.exit_code == 0, result.output
    lock = json.loads((project / "mcps-lock.json").read_text())
    harnesses = sorted(e["harness"] for e in lock["mcps"]["context7"])
    assert harnesses == ["codex", "opencode", "standard"]  # legacy rows gone
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_mcp.py -k "default_is_standard or collapse_to_standard or collapses_preexisting" -v`
Expected: FAIL — the lock will contain `claude-code`/`pi` rows (current behavior).

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

Replace the target resolution (line 57) — after `scope, home, project = scope_and_roots(...)`, `effective_home`, `library`:

```python
    if harnesses:
        targets = list(normalize_harness_tokens(tuple(harnesses), scope=scope))
    else:
        targets = list(default_harnesses(scope))
```

(Remove the old `targets = list(harnesses) or list(_HARNESSES)` line and the now-unused `_HARNESSES` import.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_mcp.py -k "default_is_standard or collapse_to_standard or collapses_preexisting" -v`
Expected: PASS (3 passed). The collapse test passes because Task 4's collapse-on-install drops the legacy rows.

- [ ] **Step 5: Regression guard**

Run: `uv run pytest tests/test_cli_mcp.py -k install -v`
Expected: PASS — `test_mcp_install_project_claude` still asserts `.mcp.json` content (unchanged).

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/commands/mcp/install_cmd.py tests/test_cli_mcp.py
git commit -m "feat(mcp): install uses scope-aware default + standard normalization (#399)"
```

---

## Task 7: Wire `uninstall_cmd` to `standard` Choice + normalize

**Files:**
- Modify: `src/agent_toolkit_cli/commands/mcp/uninstall_cmd.py:16,33-37,59-66`
- Test: `tests/test_cli_mcp.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_mcp.py — append
def test_mcp_uninstall_standard_removes_only_named_entry(tmp_path, monkeypatch):
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    CliRunner().invoke(main, ["mcp", "install", "context7", "-p"])
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
Expected: FAIL — `standard` not a valid `--harness` (Choice); and `--harness claude-code` targets a non-existent `claude-code` lock row.

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

(`uninstall_cmd` no longer references `_HARNESSES` — remove it from the import.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_mcp.py -k "uninstall_standard or uninstall_claude_normalizes" -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/mcp/uninstall_cmd.py tests/test_cli_mcp.py
git commit -m "feat(mcp): uninstall accepts + normalizes standard (#399)"
```

---

## Task 8: `list` — covered-set line + `tracked_by_path` fix (no false unmanaged)

**Files:**
- Modify: `src/agent_toolkit_cli/commands/mcp/list_cmd.py:17-20,100-119,132-159`
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


def test_mcp_list_standard_install_not_flagged_unmanaged(tmp_path, monkeypatch):
    """A managed standard entry must NOT be falsely re-surfaced as [!] unmanaged."""
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    CliRunner().invoke(main, ["mcp", "install", "context7", "-p"])  # standard row
    result = CliRunner().invoke(main, ["mcp", "list", "-p"])
    assert result.exit_code == 0, result.output
    assert "unmanaged: context7" not in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_mcp.py -k "list_standard_row or standard_install_not_flagged" -v`
Expected: FAIL — `standard_row`: no covered-set line. `not_flagged`: the `tracked_by_path` loop iterates `_HARNESSES`, never credits the `standard` row, so `context7` prints `[!] unmanaged: context7 (claude-code)`. (Confirm `test_mcp_list_managed_shared_file_not_flagged_unmanaged` at line ~283 ALSO fails now — it's the same bug; fixing this task fixes it.)

- [ ] **Step 3: Write minimal implementation**

In `src/agent_toolkit_cli/commands/mcp/list_cmd.py`, add the import (after line 19):

```python
from agent_toolkit_cli.mcp_standard import STANDARD_MCP_READERS, mcp_standard_covered
```

**(a) Covered-set line** — inside the `for slug in slugs:` loop, after the existing `for harness in _HARNESSES:` per-harness mark block (after line 119):

```python
        if "standard" in locked and scope in STANDARD_MCP_READERS:
            covered = ", ".join(sorted(mcp_standard_covered(scope)))
            click.echo(f"  ✔ standard → {covered}")
```

**(b) `tracked_by_path` fix** — in the unmanaged-scan grouping loop (~line 132-146), after the `for harness in _HARNESSES:` block that populates `tracked_by_path`, add the `standard` path:

```python
    # #399: credit `standard` lock rows toward the shared .mcp.json path, so a
    # standard-managed entry is not falsely re-surfaced as [!] unmanaged. The
    # standard adapter's project target IS <project>/.mcp.json.
    if scope in STANDARD_MCP_READERS:
        std_adapter = get_adapter("standard")
        try:
            std_path = std_adapter.config_target(
                scope=scope, home=effective_home, project=project_root
            ).resolve()
        except ValueError:
            std_path = None
        if std_path is not None:
            std_slugs = {
                slug for slug, entries in lock.items()
                if any(e.harness == "standard" for e in entries)
            }
            tracked_by_path.setdefault(std_path, set()).update(std_slugs)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_mcp.py -k "list_standard_row or standard_install_not_flagged or managed_shared_file_not_flagged" -v`
Expected: PASS — including the pre-existing `test_mcp_list_managed_shared_file_not_flagged_unmanaged`.

- [ ] **Step 5: Regression guard**

Run: `uv run pytest tests/test_cli_mcp.py -k list -v`
Expected: PASS — `test_mcp_list_shows_seeded_slug` and the unmanaged-sibling tests unaffected.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/commands/mcp/list_cmd.py tests/test_cli_mcp.py
git commit -m "feat(mcp): list expands standard covered set + fixes false-unmanaged scan (#399)"
```

---

## Task 9: `status` — `standard` covered-set annotation (scope-keyed)

**Files:**
- Modify: `src/agent_toolkit_cli/commands/mcp/status_cmd.py:33-57`
- Test: `tests/test_cli_mcp.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_mcp.py — append
def test_mcp_status_standard_row_annotated(tmp_path, monkeypatch):
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
Expected: FAIL — `status` prints `context7\tstandard\tfloating`, no covered-set annotation.

- [ ] **Step 3: Write minimal implementation**

In `src/agent_toolkit_cli/commands/mcp/status_cmd.py`, thread the resolved `scope` into `_echo_slug` so the annotation is scope-keyed (not hardcoded `"project"`). At the call sites (lines 46, 50) pass `scope`; change `_echo_slug`:

```python
def _echo_slug(slug: str, entries: list, scope: str) -> None:
    """One line per (slug, harness): `<slug>\t<harness>\t<pin|floating>`. A
    `standard` harness row is annotated with its covered set (#399), keyed off
    the resolved scope (no global standard exists, so a global `standard` row —
    which should never occur — degrades to no annotation rather than a wrong one)."""
    from agent_toolkit_cli.mcp_standard import STANDARD_MCP_READERS, mcp_standard_covered

    for entry in sorted(entries, key=lambda e: e.harness):
        pin = entry.pin if entry.pin else "floating"
        line = f"{slug}\t{entry.harness}\t{pin}"
        if entry.harness == "standard" and scope in STANDARD_MCP_READERS:
            covered = ", ".join(sorted(mcp_standard_covered(scope)))
            line += f"\t→ {covered}"
        click.echo(line)
```

Update the two `_echo_slug(slug, ...)` calls to `_echo_slug(slug, entries, scope)` and `_echo_slug(slug, lock[slug], scope)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_mcp.py -k status_standard_row -v`
Expected: PASS.

- [ ] **Step 5: Regression guard**

Run: `uv run pytest tests/test_cli_mcp.py -k status -v`
Expected: PASS — `test_mcp_status_after_install` still passes (the `standard` row's `→ claude-code, pi` annotation keeps the `claude-code` substring present).

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/commands/mcp/status_cmd.py tests/test_cli_mcp.py
git commit -m "feat(mcp): status annotates standard row with covered set (#399)"
```

---

## Task 10: `doctor` — `legacy-standard-dedup` finding + `standard`-row coverage

**Files:**
- Modify: `src/agent_toolkit_cli/commands/mcp/doctor_cmd.py:103-167` (`_diagnose`)
- Test: `tests/test_cli_mcp.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_mcp.py — append
def test_mcp_doctor_flags_legacy_standard_dedup(tmp_path, monkeypatch):
    """A project lock with claude-code + pi rows is flagged for collapse. Read-only."""
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    (project / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"context7": {"type": "stdio", "command": "npx",
         "args": ["-y", "ctx7@9.9.9"]}}}, indent=2) + "\n"
    )
    (project / "mcps-lock.json").write_text(json.dumps({
        "version": 1, "mcps": {"context7": [
            {"harness": "claude-code", "source": "npx", "pin": "9.9.9"},
            {"harness": "pi", "source": "npx", "pin": "9.9.9"},
        ]}}, indent=2) + "\n")
    before = (project / "mcps-lock.json").read_text()
    result = CliRunner().invoke(main, ["mcp", "doctor", "-p"])
    assert "legacy-standard-dedup" in result.output
    assert "context7" in result.output
    assert (project / "mcps-lock.json").read_text() == before  # read-only
    assert result.exit_code == 1


def test_mcp_doctor_flags_partially_collapsed_standard_plus_pi(tmp_path, monkeypatch):
    """The orphan-row shape {standard, pi} also fires the finding (so an orphan
    pi row left by a non-normalized uninstall is surfaced, not hidden)."""
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    (project / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"context7": {"type": "stdio", "command": "npx",
         "args": ["-y", "ctx7@9.9.9"]}}}, indent=2) + "\n"
    )
    (project / "mcps-lock.json").write_text(json.dumps({
        "version": 1, "mcps": {"context7": [
            {"harness": "standard", "source": "npx", "pin": "9.9.9"},
            {"harness": "pi", "source": "npx", "pin": "9.9.9"},
        ]}}, indent=2) + "\n")
    result = CliRunner().invoke(main, ["mcp", "doctor", "-p"])
    assert "legacy-standard-dedup" in result.output


def test_mcp_doctor_clean_on_standard_install(tmp_path, monkeypatch):
    """A clean standard install passes doctor — no missing/drifted on the standard row."""
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    CliRunner().invoke(main, ["mcp", "install", "context7", "-p"])  # one standard row
    result = CliRunner().invoke(main, ["mcp", "doctor", "-p"])
    assert result.exit_code == 0, result.output
    assert "all clean" in result.output
    assert "legacy-standard-dedup" not in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_mcp.py -k "legacy_standard_dedup or partially_collapsed or doctor_clean_on_standard" -v`
Expected: FAIL — `legacy-standard-dedup` not emitted (no such finding). `doctor_clean_on_standard` may already pass (clean standard install drift-checks via passthrough) — confirm; if it passes pre-change it's a coverage-locking test, fine.

- [ ] **Step 3: Write minimal implementation**

In `src/agent_toolkit_cli/commands/mcp/doctor_cmd.py`, add the import (top):

```python
from agent_toolkit_cli.mcp_standard import mcp_standard_covered
```

Inside `_diagnose`, after `entries = lock[slug]` (line 117), add the legacy-dedup check:

```python
        # #399: legacy/partially-collapsed standard de-dup. At project scope, if a
        # slug's rows intersect the covered set {claude-code, pi}, those rows
        # project the same .mcp.json the `standard` row owns (or should own) and
        # must collapse to one `standard` row. Fires on the pure 2-row legacy
        # shape AND the partially-collapsed {standard, pi}/{standard, claude-code}
        # shape (so an orphan covered row is surfaced, not hidden). Read-only:
        # remediation is `mcp install <slug> -p` (collapse-on-install converges it).
        if scope == "project":
            row_harnesses = {e.harness for e in entries}
            if row_harnesses & mcp_standard_covered("project"):
                findings.append(Finding(
                    slug=slug, harness="standard",
                    finding_type="legacy-standard-dedup",
                    detail=(
                        "project lock has claude-code/pi rows for the shared "
                        f".mcp.json; collapse to one `standard` row with "
                        f"`mcp install {slug} -p`"
                    ),
                ))
```

Then guard the existing per-entry loop against a global-scope `standard` row (deep-review B). In the `for entry in sorted(entries, ...)` block, after `harness = entry.harness` (before `adapter = get_adapter(harness)`, ~line 131-132), add:

```python
            if harness == "standard" and scope != "project":
                # A `standard` row at global scope is structurally invalid (no
                # global standard target); skip the per-entry checks rather than
                # emit a misleading `missing` when config_target raises.
                continue
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_mcp.py -k "legacy_standard_dedup or partially_collapsed or doctor_clean_on_standard" -v`
Expected: PASS (3 passed). The `exit 1` contract at `doctor_cmd.py:212` fires for the legacy/partial tests; `doctor_clean_on_standard` returns `all clean` (exit 0) because a single `standard` row does not intersect... wait: a `{standard}`-only lock does NOT intersect `{claude-code, pi}`, so no finding — correct.

- [ ] **Step 5: Regression guard**

Run: `uv run pytest tests/test_cli_mcp.py -k doctor -v`
Expected: PASS — `test_mcp_doctor_clean` installs `--harness claude-code -p` (now a `standard` row); a single `standard` row does not fire the new finding, so it stays clean.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/commands/mcp/doctor_cmd.py tests/test_cli_mcp.py
git commit -m "feat(mcp): doctor flags legacy/partial standard dedup + covers standard rows (#399)"
```

---

## Task 11: `update` / `remove` regression coverage

**Files:**
- Test only: `tests/test_cli_mcp.py` (verifies existing `update_cmd`/`remove_cmd` behave on a `standard` lock)

- [ ] **Step 1: Write the tests**

```python
# tests/test_cli_mcp.py — append
def test_mcp_remove_standard_fully_clears(tmp_path, monkeypatch):
    """`mcp remove` on a standard install removes the .mcp.json entry and the row."""
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    CliRunner().invoke(main, ["mcp", "install", "context7", "-p"])  # standard row
    result = CliRunner().invoke(main, ["mcp", "remove", "context7", "-p"])
    assert result.exit_code == 0, result.output
    doc = json.loads((project / ".mcp.json").read_text())
    assert "context7" not in doc.get("mcpServers", {})
    lock = json.loads((project / "mcps-lock.json").read_text())
    assert "context7" not in lock.get("mcps", {})


def test_mcp_update_standard_reprojects(tmp_path, monkeypatch):
    """`mcp update` (NO scope flag — it re-projects every reachable locked
    projection) re-projects a clean post-#399 project `standard` row without
    crashing on the synthetic harness, and the row stays `standard`."""
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    CliRunner().invoke(main, ["mcp", "install", "context7", "-p"])  # standard row
    result = CliRunner().invoke(main, ["mcp", "update", "context7"])  # no -p: update has no scope flag
    assert result.exit_code == 0, result.output
    lock = json.loads((project / "mcps-lock.json").read_text())
    harnesses = [e["harness"] for e in lock["mcps"]["context7"]]
    assert "standard" in harnesses
    assert "claude-code" not in harnesses and "pi" not in harnesses
    doc = json.loads((project / ".mcp.json").read_text())
    assert "context7" in doc["mcpServers"]
```

- [ ] **Step 2: Run the tests**

Run: `uv run pytest tests/test_cli_mcp.py -k "remove_standard_fully or update_standard_reprojects" -v`
Expected: PASS without code changes — `remove` fans the lock's `standard` row → `get_adapter("standard")` removes the entry; `update` (which has NO scope flag and re-projects every reachable locked projection — `update_cmd.py:1,7-9`) replays the `standard` row → re-projects `.mcp.json`. If either FAILS, that's a real uncovered bug — fix in `update_cmd.py`/`remove_cmd.py` and re-run.

- [ ] **Step 3: Commit**

```bash
git add tests/test_cli_mcp.py
git commit -m "test(mcp): update/remove regression coverage for standard rows (#399)"
```

---

## Task 12: Reconcile existing tests broken by the project-default change

The project default changes to `(standard, codex, opencode)`, and `--harness claude-code/pi -p` now yields a `standard` lock row. Audit the tests that bake in the old shape.

**Files:**
- Modify: `tests/test_cli_mcp.py` (`test_install_all_four_harnesses_round_trip`, ~line 540)

- [ ] **Step 1: Run the at-risk tests**

Run: `uv run pytest tests/test_cli_mcp.py -k "all_four_harnesses_round_trip or status_after_install or managed_shared_file_not_flagged" -v`
Expected:
- `managed_shared_file_not_flagged` — now PASSES (fixed in Task 8).
- `status_after_install` — PASSES (the `→ claude-code, pi` annotation keeps the substring).
- `test_install_all_four_harnesses_round_trip[-p]` — inspect: `r1 = install context7 -p` no longer fans four; project writes `(standard, codex, opencode)`. The post-uninstall all-four `is_installed`-False loop still passes (claude-code/pi read the standard-owned `.mcp.json`). The `# default = all four` comment is now false for project.

- [ ] **Step 2: Update `test_install_all_four_harnesses_round_trip`**

For the project branch, fix the comment and add a lock-shape assertion after `r1`:

```python
    r1 = runner.invoke(main, ["mcp", "install", "context7", scope_flag])  # global: four; project: standard+codex+opencode
    assert r1.exit_code == 0, r1.output

    if scope_name == "project":
        from agent_toolkit_cli.mcp_lock import lock_path_for_scope as _lp, read_lock as _rl
        _lk = _rl(_lp("project", home=tmp_path, project=project))
        _hs = {e.harness for e in _lk["context7"]}
        assert "standard" in _hs and "claude-code" not in _hs and "pi" not in _hs
```

(The uninstall + all-four `is_installed`-False loop is unchanged and still correct.)

- [ ] **Step 3: Run the updated test**

Run: `uv run pytest tests/test_cli_mcp.py -k all_four_harnesses_round_trip -v`
Expected: PASS at both `-g` and `-p`.

- [ ] **Step 4: Commit**

```bash
git add tests/test_cli_mcp.py
git commit -m "test(mcp): reconcile round-trip test with project standard default (#399)"
```

---

## Task 13: Full-suite regression + lint/type gate

**Files:** none (verification only)

- [ ] **Step 1: Full MCP test surface**

Run: `uv run pytest tests/test_mcp_standard.py tests/test_cli_mcp.py tests/test_mcp_adapters_json.py tests/test_mcp_install.py tests/test_mcp_lock.py -v`
Expected: PASS (all green).

- [ ] **Step 2: Whole suite**

Run: `uv run pytest -q 2>&1 | tail -20`
Expected: PASS except the 2 known-whitelisted HOME-isolation env failures (`test_empty_machine_is_empty` / inventory global-pi). Reproduce on `main` if uncertain.

- [ ] **Step 3: Lint + type gate**

Run: `uv run ruff check src/agent_toolkit_cli/mcp_standard.py src/agent_toolkit_cli/mcp_install.py src/agent_toolkit_cli/mcp_lock.py src/agent_toolkit_cli/commands/mcp/ src/agent_toolkit_cli/mcp_adapters/ && uv run mypy src/agent_toolkit_cli/mcp_standard.py src/agent_toolkit_cli/commands/mcp/ src/agent_toolkit_cli/mcp_install.py`
Expected: net-zero NEW ruff/mypy errors vs `main`.

- [ ] **Step 4: Final commit (if lint/type fixes needed)**

```bash
git add -A
git commit -m "chore(mcp): lint/type clean for standard projection (#399)"
```

---

## Acceptance-criteria → task map

| AC (issue #399) | Task |
|---|---|
| `standard` project target writes `mcpServers.<slug>`, preserves siblings | 2 |
| claude-code/pi normalize to standard at project scope | 5, 6 |
| global: NO normalization, no standard target | 2 (raise), 5 (reject) |
| install/list/status/doctor understand standard; list/status expand covered set | 6, 8, 9, 10 |
| lock records standard as a new value, no schema migration | 2, 6 (verified in lock JSON) |
| doctor reconciles legacy two-row lock, non-destructively | 10 |
| **legacy migration actually converges (collapse-on-install)** | 3, 4 |
| **list no false-unmanaged on standard entries** | 8 |
| **doctor covers standard rows + global guard** | 10 |
| **update/remove behave on standard rows** | 11 |
| manage-by-name preserved (collision warning covers standard) | 2 (adapter reuse) |
| codex/opencode unaffected | 6, 12, 13 (regression) |
