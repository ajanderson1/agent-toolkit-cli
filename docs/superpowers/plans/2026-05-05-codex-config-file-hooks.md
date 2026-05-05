# Codex `config_file+folder` hook adapter — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Project toolkit hook assets onto a Codex CLI install by writing `~/.codex/config.toml` `[hooks]` and vendoring scripts under `~/.codex/agent-toolkit-hooks/<slug>/`. Round-trip clean, ownership-safe, parity-test passing.

**Architecture:** Three-layer change. (1) Schema — add `spec.hook` to v1alpha2, required for `kind: hook`. (2) Adapter base — `HookEntry` dataclass + `ConfigFileFolderAdapter` Protocol; new `CodexHookAdapter` with `strategy="config_file+folder"`. (3) Dispatch + routing — kind-aware `get_adapter(harness, kind="mcp")`, new `_hook_dispatch.py`, three-branch routing in `_link_lib.py` (mcp → `_mcp_dispatch`, hook → `_hook_dispatch`, other → existing translate path). Ownership rule: managed entries identified by `command` path under `script_root`; hand-rolled entries preserved.

**Tech Stack:** Python 3.13, `tomlkit` (TOML round-trip), `pytest`, `Click`, `Textual` (TUI smoke), `uv` (dep manager), `lefthook` (pre-commit).

**Spec:** [`docs/superpowers/specs/2026-05-05-codex-config-file-hooks-design.md`](../specs/2026-05-05-codex-config-file-hooks-design.md) (committed at `da26fba`).

**Branch:** `feat/56-codex-config-file-hooks` (worktree at `.worktrees/feat-56-codex-config-file-hooks/`).

**Pre-flight one-time setup (run before Task 1):**

```bash
uv sync --all-extras
```

This installs the `tui` extra so lefthook's `uv run pytest -q` finds `textual` and `rich`. Without it, every commit will fail collection on `tests/test_tui/*`.

---

## File Structure

**Created:**
- `src/agent_toolkit/harness_adapters/codex_hook.py` — the `CodexHookAdapter` (~250 lines).
- `src/agent_toolkit/commands/_hook_dispatch.py` — hook-typed dispatcher (~120 lines), shares `_atomic_write_bytes`/`_print_pre`/`_print_post` from `_mcp_dispatch.py`.
- `tests/test_codex_hook_adapter.py` — adapter unit tests.
- `tests/test_hook_dispatch.py` — dispatcher tests (atomic + chmod + dry-run).
- `tests/test_tui_hook_integration.py` — TUI smoke (mirror of `test_tui_mcp_integration.py`).
- `tests/test_schema_hook.py` — schema validation cases.
- `tests/_fixtures/hook_assets/codex-demo/.meta.yaml` — demo asset.
- `tests/_fixtures/hook_assets/codex-demo/check.sh` — demo script.
- `tests/_fixtures/codex_config_realistic_with_hooks.toml` — round-trip fixture.

**Modified:**
- `schemas/asset-frontmatter.v1alpha2.json` — add `spec.hook` block + `kind: hook → required spec.hook` allOf clause.
- `src/agent_toolkit/_schemas/asset-frontmatter.v1alpha2.json` — identical mirror (lefthook enforces).
- `src/agent_toolkit/harness_adapters/base.py` — add `HookEntry` dataclass + `ConfigFileFolderAdapter` Protocol.
- `src/agent_toolkit/harness_adapters/__init__.py` — `get_adapter(harness, kind="mcp")` with `kind="hook"` branch.
- `src/agent_toolkit/_support.py` — add `("codex", "hook")` to `_USER_TARGETS` (sentinel value; the hook adapter manages its own paths but `is_supported` must answer True).
- `src/agent_toolkit/commands/_link_lib.py` — add `kind == "hook"` branch in projection loop (~lines 443-489).
- `tests/test_harness_matrix.py` — extend parity test to handle `config_file+folder` mechanism and call `get_adapter(harness, kind)`.
- `tests/test_tomlkit_roundtrip.py` — add new fixture-driven case.
- `docs/agent-toolkit/harness-matrix.md` — flip `codex/hook` cell, refine `codex/agent` cell.

---

## Tasks

### Task 1: Schema — add `spec.hook` block

**Files:**
- Modify: `schemas/asset-frontmatter.v1alpha2.json`
- Modify: `src/agent_toolkit/_schemas/asset-frontmatter.v1alpha2.json` (must stay byte-identical to the above; lefthook enforces).
- Create: `tests/test_schema_hook.py`

The schema changes go first because everything downstream depends on `spec.hook` shape.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_schema_hook.py`:

```python
"""Schema validation cases for kind: hook with spec.hook block."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

SCHEMA_PATH = Path(__file__).parent.parent / "src/agent_toolkit/_schemas/asset-frontmatter.v1alpha2.json"


@pytest.fixture
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _base_hook_doc() -> dict:
    return {
        "apiVersion": "agent-toolkit/v1alpha2",
        "metadata": {
            "name": "demo-hook",
            "description": "A demo hook.",
            "kind": "hook",
            "lifecycle": "experimental",
        },
        "spec": {
            "origin": "first-party",
            "vendored_via": "none",
            "harnesses": ["codex"],
            "hook": {
                "events": ["PreToolUse"],
                "command": "check.sh",
            },
        },
    }


def test_kind_hook_with_spec_hook_passes(schema):
    jsonschema.validate(_base_hook_doc(), schema)


def test_kind_hook_without_spec_hook_fails(schema):
    doc = _base_hook_doc()
    del doc["spec"]["hook"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(doc, schema)


def test_kind_hook_unknown_event_fails(schema):
    doc = _base_hook_doc()
    doc["spec"]["hook"]["events"] = ["NotAnEvent"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(doc, schema)


def test_kind_hook_empty_events_fails(schema):
    doc = _base_hook_doc()
    doc["spec"]["hook"]["events"] = []
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(doc, schema)


def test_kind_hook_with_all_optional_fields_passes(schema):
    doc = _base_hook_doc()
    doc["spec"]["hook"].update({
        "matcher": "^Bash$",
        "timeout": 10,
        "async": False,
        "status_message": "checking",
    })
    jsonschema.validate(doc, schema)


def test_non_hook_kind_without_spec_hook_passes(schema):
    """spec.hook is only required when kind == hook."""
    doc = _base_hook_doc()
    doc["metadata"]["kind"] = "skill"
    del doc["spec"]["hook"]
    jsonschema.validate(doc, schema)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_schema_hook.py -v
```

Expected: all 6 tests FAIL — either with `jsonschema.ValidationError` (the "passes" cases, because `additionalProperties: false` rejects the new `hook` key) or with no error raised when one is expected.

- [ ] **Step 3: Add `spec.hook` to the schema (both copies)**

Edit `src/agent_toolkit/_schemas/asset-frontmatter.v1alpha2.json`. Locate the `"spec"` object's `"properties"` block (after the existing `"mcp"` property). Add this new property entry:

```json
        "hook": {
          "type": "object",
          "required": ["events", "command"],
          "additionalProperties": false,
          "properties": {
            "events": {
              "type": "array",
              "minItems": 1,
              "uniqueItems": true,
              "items": {
                "enum": ["PreToolUse", "PostToolUse", "PermissionRequest",
                         "SessionStart", "UserPromptSubmit", "Stop"]
              }
            },
            "command":        { "type": "string" },
            "matcher":        { "type": "string" },
            "timeout":        { "type": "integer", "minimum": 1 },
            "async":          { "type": "boolean" },
            "status_message": { "type": "string" }
          }
        },
```

Locate the top-level `"allOf"` array (the one with the `kind: mcp` clause). Append a new clause:

```json
    {
      "if": {
        "properties": { "metadata": { "properties": { "kind": { "const": "hook" } }, "required": ["kind"] } },
        "required": ["metadata"]
      },
      "then": { "properties": { "spec": { "required": ["hook"] } } }
    }
```

Copy the resulting file byte-for-byte to `schemas/asset-frontmatter.v1alpha2.json`:

```bash
cp src/agent_toolkit/_schemas/asset-frontmatter.v1alpha2.json schemas/asset-frontmatter.v1alpha2.json
```

- [ ] **Step 4: Verify lefthook's vendor-check is satisfied**

```bash
diff schemas/asset-frontmatter.v1alpha2.json src/agent_toolkit/_schemas/asset-frontmatter.v1alpha2.json
```

Expected: no output (files identical, exit 0).

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_schema_hook.py -v
```

Expected: 6 PASS.

- [ ] **Step 6: Run full test suite to confirm no regression**

```bash
uv run pytest -q
```

Expected: all green (existing 556 tests + 6 new = 562 pass).

- [ ] **Step 7: Commit**

```bash
git add schemas/asset-frontmatter.v1alpha2.json \
        src/agent_toolkit/_schemas/asset-frontmatter.v1alpha2.json \
        tests/test_schema_hook.py
git commit -m "feat(#56): add spec.hook block to v1alpha2 schema

Required when kind: hook. Six known events (PreToolUse, PostToolUse,
PermissionRequest, SessionStart, UserPromptSubmit, Stop), optional
matcher/timeout/async/status_message. Both vendored copies bumped."
```

---

### Task 2: `HookEntry` dataclass + `ConfigFileFolderAdapter` Protocol

**Files:**
- Modify: `src/agent_toolkit/harness_adapters/base.py`
- Test: covered by Task 3 (the adapter will exercise these types).

Pure-types task. No test of its own (types alone do nothing); Task 3 imports them and tests behaviour.

- [ ] **Step 1: Add `HookEntry` dataclass**

In `src/agent_toolkit/harness_adapters/base.py`, after the existing `McpEntry` dataclass (around line 30), add:

```python
@dataclass(frozen=True)
class HookEntry:
    """One hook asset, ready for adapter consumption.

    `name` is the asset slug (the canonical id).
    `events` is the tuple of Codex hook events this asset binds to.
    `command` is the absolute path the [hooks] handler will reference
    (under script_root/<slug>/, materialised by the dispatcher).
    `script_files` maps absolute destination paths to their byte contents.
    """
    name: str
    events: tuple[str, ...]
    command: str
    matcher: str | None = None
    timeout: int | None = None
    async_: bool = False
    status_message: str | None = None
    script_files: dict[Path, bytes] = field(default_factory=dict)
```

You'll need `from dataclasses import dataclass, field` — add `field` to the existing import.

- [ ] **Step 2: Add `ConfigFileFolderAdapter` Protocol**

In the same file, after the existing `ConfigFileAdapter` Protocol, add:

```python
@runtime_checkable
class ConfigFileFolderAdapter(Protocol):
    """Hybrid strategy: own a folder of artefacts AND mutate a single config file.

    Adapter materialises files under `script_root` and surgically edits
    `config_target`. Both are mutated in one `diff()` call so they commit
    or rollback together.
    """

    name: str
    strategy: Literal["config_file+folder"]

    def can_install(self, entry) -> None: ...
    def list_installed(self, scope: Scope, project_root: Path) -> set[str]: ...
    def entry_drift(self, scope: Scope, project_root: Path, entry) -> bool: ...
    def config_target(self, scope: Scope, project_root: Path) -> Path | None: ...
    def script_root(self, scope: Scope, project_root: Path) -> Path | None: ...
    def render(self, entries) -> dict[Path, bytes]: ...
    def diff(
        self,
        scope: Scope,
        project_root: Path,
        entries,
        *,
        previously_allowed: set[str] = frozenset(),
    ) -> list[WriteAction]: ...
```

- [ ] **Step 3: Re-export from the package `__init__`**

In `src/agent_toolkit/harness_adapters/__init__.py`, extend the `from agent_toolkit.harness_adapters.base import` block and the `__all__` list:

```python
from agent_toolkit.harness_adapters.base import (
    CannotInstall,
    ConfigFileAdapter,
    ConfigFileFolderAdapter,   # added
    HookEntry,                  # added
    McpEntry,
    PluginFolderAdapter,
    Scope,
    UnimplementedAdapter,
    WriteAction,
)
```

```python
__all__ = [
    "get_adapter",
    "McpEntry",
    "HookEntry",                  # added
    "WriteAction",
    "CannotInstall",
    "Scope",
    "PluginFolderAdapter",
    "ConfigFileAdapter",
    "ConfigFileFolderAdapter",   # added
    "UnimplementedAdapter",
]
```

- [ ] **Step 4: Run full test suite to confirm no regression**

```bash
uv run pytest -q
```

Expected: same 562 PASS as before (new types are unused for now, no behaviour change).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit/harness_adapters/base.py \
        src/agent_toolkit/harness_adapters/__init__.py
git commit -m "feat(#56): add HookEntry + ConfigFileFolderAdapter Protocol

Pure additive types. HookEntry mirrors McpEntry shape, carries event
list and script_files dict. ConfigFileFolderAdapter is the hybrid
strategy used by the upcoming codex hook adapter."
```

---

### Task 3: `CodexHookAdapter` — pre-flight, target paths, and `can_install`

**Files:**
- Create: `src/agent_toolkit/harness_adapters/codex_hook.py`
- Create: `tests/test_codex_hook_adapter.py`

Build the adapter incrementally, TDD-style. This task lays down the scaffolding and the simple methods. Task 4 adds `diff()`.

- [ ] **Step 1: Write the failing tests for scaffolding**

Create `tests/test_codex_hook_adapter.py`:

```python
"""CodexHookAdapter — ConfigFileFolderAdapter for ~/.codex/config.toml [hooks]."""
from __future__ import annotations

from pathlib import Path

import pytest


def _make_entry(name: str = "demo", *, events: tuple[str, ...] = ("PreToolUse",),
                command: str | None = None, matcher: str | None = None,
                timeout: int | None = None, async_: bool = False,
                status_message: str | None = None,
                script_files: dict[Path, bytes] | None = None,
                home: Path | None = None):
    from agent_toolkit.harness_adapters.base import HookEntry

    if home is None:
        home = Path("/tmp")  # tests pass home explicitly when relevant
    if command is None:
        command = str(home / ".codex" / "agent-toolkit-hooks" / name / "check.sh")
    if script_files is None:
        script_files = {Path(command): b"#!/usr/bin/env bash\necho hi\n"}
    return HookEntry(
        name=name, events=events, command=command, matcher=matcher,
        timeout=timeout, async_=async_, status_message=status_message,
        script_files=script_files,
    )


def test_codex_hook_adapter_basic_attrs():
    from agent_toolkit.harness_adapters.codex_hook import CodexHookAdapter

    a = CodexHookAdapter()
    assert a.name == "codex"
    assert a.strategy == "config_file+folder"


def test_codex_hook_user_config_target(monkeypatch, tmp_path):
    from agent_toolkit.harness_adapters.codex_hook import CodexHookAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = CodexHookAdapter()
    assert a.config_target("user", tmp_path) == tmp_path / ".codex" / "config.toml"


def test_codex_hook_user_script_root(monkeypatch, tmp_path):
    from agent_toolkit.harness_adapters.codex_hook import CodexHookAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = CodexHookAdapter()
    assert a.script_root("user", tmp_path) == tmp_path / ".codex" / "agent-toolkit-hooks"


def test_codex_hook_project_scope_returns_none(tmp_path):
    """PR1 is user-scope only — project scope returns None to silently skip."""
    from agent_toolkit.harness_adapters.codex_hook import CodexHookAdapter

    a = CodexHookAdapter()
    assert a.config_target("project", tmp_path) is None
    assert a.script_root("project", tmp_path) is None


def test_codex_hook_can_install_accepts_known_events(tmp_path):
    from agent_toolkit.harness_adapters.codex_hook import CodexHookAdapter

    a = CodexHookAdapter()
    a.can_install(_make_entry(events=("PreToolUse", "Stop"), home=tmp_path))  # no exception


def test_codex_hook_can_install_refuses_unknown_event(tmp_path):
    from agent_toolkit.harness_adapters.codex_hook import CodexHookAdapter
    from agent_toolkit.harness_adapters.base import CannotInstall

    a = CodexHookAdapter()
    with pytest.raises(CannotInstall, match="unknown.*Boom"):
        a.can_install(_make_entry(events=("Boom",), home=tmp_path))


def test_codex_hook_can_install_refuses_empty_events(tmp_path):
    from agent_toolkit.harness_adapters.codex_hook import CodexHookAdapter
    from agent_toolkit.harness_adapters.base import CannotInstall

    a = CodexHookAdapter()
    with pytest.raises(CannotInstall, match="at least one event"):
        a.can_install(_make_entry(events=(), home=tmp_path))


def test_codex_hook_can_install_refuses_command_outside_script_root(monkeypatch, tmp_path):
    """The handler command must point inside script_root/<slug>/ — that's how
    the ownership rule (path-prefix) stays reliable."""
    from agent_toolkit.harness_adapters.codex_hook import CodexHookAdapter
    from agent_toolkit.harness_adapters.base import CannotInstall

    monkeypatch.setenv("HOME", str(tmp_path))
    a = CodexHookAdapter()
    bad = _make_entry(command="/usr/local/bin/some-script", home=tmp_path)
    with pytest.raises(CannotInstall, match="must live under"):
        a.can_install(bad)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_codex_hook_adapter.py -v
```

Expected: all 8 FAIL with `ModuleNotFoundError: No module named 'agent_toolkit.harness_adapters.codex_hook'`.

- [ ] **Step 3: Create the adapter scaffolding**

Create `src/agent_toolkit/harness_adapters/codex_hook.py`:

```python
"""Codex hook adapter — ConfigFileFolderAdapter against ~/.codex/config.toml [hooks].

Round-trip via tomlkit. Managed identity: the handler `command` lives under
`script_root/<slug>/`. Hand-rolled hook entries (command not under script_root)
are preserved verbatim.

User scope only in this PR; project scope returns None (silently skip).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import tomlkit
from tomlkit import TOMLDocument, table

from agent_toolkit.harness_adapters.base import (
    CannotInstall,
    HookEntry,
    Scope,
    WriteAction,
)


_CODEX_HOOK_EVENTS: tuple[str, ...] = (
    "PreToolUse",
    "PostToolUse",
    "PermissionRequest",
    "SessionStart",
    "UserPromptSubmit",
    "Stop",
)


class CodexHookAdapter:
    name: str = "codex"
    strategy: Literal["config_file+folder"] = "config_file+folder"

    # ---- target paths ----
    def config_target(self, scope: Scope, project_root: Path) -> Path | None:
        if scope == "user":
            home = Path(os.environ.get("HOME", ""))
            return home / ".codex" / "config.toml"
        return None  # PR1: project scope unsupported

    def script_root(self, scope: Scope, project_root: Path) -> Path | None:
        if scope == "user":
            home = Path(os.environ.get("HOME", ""))
            return home / ".codex" / "agent-toolkit-hooks"
        return None  # PR1: project scope unsupported

    # ---- pre-flight ----
    def can_install(self, entry: HookEntry) -> None:
        if not entry.events:
            raise CannotInstall(
                f"{entry.name}: spec.hook.events must declare at least one event"
            )
        unknown = [e for e in entry.events if e not in _CODEX_HOOK_EVENTS]
        if unknown:
            raise CannotInstall(
                f"{entry.name}: unknown codex hook event(s): {unknown!r} "
                f"(expected subset of {_CODEX_HOOK_EVENTS})"
            )
        # Resolve script_root for the user scope (the only supported scope).
        # We don't have project_root here — we assume `command` is already
        # absolute under script_root/<slug>/ as the dispatcher set it.
        # Path prefix check uses the entry-level command path.
        home = Path(os.environ.get("HOME", ""))
        expected_prefix = home / ".codex" / "agent-toolkit-hooks" / entry.name
        if not str(entry.command).startswith(str(expected_prefix)):
            raise CannotInstall(
                f"{entry.name}: handler command {entry.command!r} must live under "
                f"{expected_prefix!r} (the path-prefix ownership rule depends on this)"
            )

    # ---- introspection (stubs to be filled by Task 4 + Task 5) ----
    def list_installed(self, scope: Scope, project_root: Path) -> set[str]:
        root = self.script_root(scope, project_root)
        if root is None or not root.is_dir():
            return set()
        return {p.name for p in root.iterdir() if p.is_dir()}

    def entry_drift(self, scope: Scope, project_root: Path, entry: HookEntry) -> bool:
        # Implemented in Task 4 alongside diff().
        raise NotImplementedError

    # ---- diff (Task 4) ----
    def render(self, entries) -> dict[Path, bytes]:
        # Implemented in Task 4.
        raise NotImplementedError

    def diff(
        self,
        scope: Scope,
        project_root: Path,
        entries: list[HookEntry],
        *,
        previously_allowed: set[str] = frozenset(),
    ) -> list[WriteAction]:
        # Implemented in Task 4.
        raise NotImplementedError
```

- [ ] **Step 4: Run tests to verify scaffolding tests pass**

```bash
uv run pytest tests/test_codex_hook_adapter.py -v
```

Expected: all 8 PASS (the scaffolding tests don't exercise diff/render/entry_drift yet).

- [ ] **Step 5: Run full test suite to confirm no regression**

```bash
uv run pytest -q
```

Expected: 562 + 8 new = 570 pass.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit/harness_adapters/codex_hook.py \
        tests/test_codex_hook_adapter.py
git commit -m "feat(#56): scaffold CodexHookAdapter (paths + can_install)

config_target/script_root/can_install/list_installed implemented.
diff/render/entry_drift stubbed for next task. User scope only;
project scope returns None per PR1 scope decision.

Path-prefix ownership rule enforced at can_install time:
handler command must live under \$HOME/.codex/agent-toolkit-hooks/<slug>/."
```

---

### Task 4: `CodexHookAdapter.diff()` — the engine

**Files:**
- Modify: `src/agent_toolkit/harness_adapters/codex_hook.py`
- Modify: `tests/test_codex_hook_adapter.py`
- Create: `tests/_fixtures/codex_config_realistic_with_hooks.toml`

This is the heart of the adapter. The `diff()` method walks two surfaces (script files + TOML), preserves hand-rolled entries, removes managed-but-no-longer-desired entries, and upserts each desired entry. Tests drive the behaviour case-by-case.

- [ ] **Step 1: Write the round-trip fixture**

Create `tests/_fixtures/codex_config_realistic_with_hooks.toml`:

```toml
# A hand-rolled config with comments + mcp_servers + hooks (mix of managed + user-owned).
model = "o4-mini"

[mcp_servers.context7]
command = "npx"
args = ["-y", "@upstash/context7-mcp"]

# User-owned hook — adapter must not touch this entry.
[[hooks.PreToolUse]]
matcher = "^Bash$"

[[hooks.PreToolUse.hooks]]
type = "command"
command = "/usr/local/bin/my-bash-guard.sh"
timeout = 5
```

This represents "what the user has on disk before linking any toolkit hook." After linking demo hook, the file should still contain this user-owned entry verbatim.

- [ ] **Step 2: Write failing diff tests**

Append to `tests/test_codex_hook_adapter.py`:

```python
import shutil


FIXTURE = Path(__file__).parent / "_fixtures" / "codex_config_realistic_with_hooks.toml"


def _seed_home(tmp_path: Path, monkeypatch) -> Path:
    """Create $HOME/.codex/ and return tmp_path."""
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".codex").mkdir()
    return tmp_path


def test_codex_hook_diff_creates_file_when_missing(monkeypatch, tmp_path):
    """No config.toml on disk → create-action with rendered TOML + create-action per script file."""
    from agent_toolkit.harness_adapters.codex_hook import CodexHookAdapter

    home = _seed_home(tmp_path, monkeypatch)
    a = CodexHookAdapter()
    entry = _make_entry(home=home)

    actions = a.diff("user", tmp_path, [entry])

    # One config.toml create + one script file create.
    paths = {act.path for act in actions}
    assert (home / ".codex" / "config.toml") in paths
    assert (home / ".codex" / "agent-toolkit-hooks" / "demo" / "check.sh") in paths
    for act in actions:
        assert act.op == "create"
        assert act.contents is not None


def test_codex_hook_diff_round_trip_byte_equal(monkeypatch, tmp_path):
    """link → write → re-diff should be empty."""
    from agent_toolkit.harness_adapters.codex_hook import CodexHookAdapter
    from agent_toolkit.commands._mcp_dispatch import _atomic_write_bytes

    home = _seed_home(tmp_path, monkeypatch)
    a = CodexHookAdapter()
    entry = _make_entry(home=home)

    actions = a.diff("user", tmp_path, [entry])
    for act in actions:
        if act.op in {"create", "update"}:
            _atomic_write_bytes(act.path, act.contents)

    # Re-diff should be empty.
    actions2 = a.diff("user", tmp_path, [entry])
    assert actions2 == []


def test_codex_hook_diff_unlink_byte_equal_to_original(monkeypatch, tmp_path):
    """link → write → unlink → write should restore byte-equality with the original."""
    from agent_toolkit.harness_adapters.codex_hook import CodexHookAdapter
    from agent_toolkit.commands._mcp_dispatch import _atomic_write_bytes

    home = _seed_home(tmp_path, monkeypatch)
    target = home / ".codex" / "config.toml"
    shutil.copy(FIXTURE, target)
    original = target.read_bytes()

    a = CodexHookAdapter()
    entry = _make_entry(home=home)

    # Link.
    for act in a.diff("user", tmp_path, [entry]):
        if act.op in {"create", "update"}:
            _atomic_write_bytes(act.path, act.contents)

    # Verify the user-owned hook is still intact in the file.
    after_link = target.read_text(encoding="utf-8")
    assert "/usr/local/bin/my-bash-guard.sh" in after_link
    assert "demo/check.sh" in after_link

    # Unlink.
    for act in a.diff("user", tmp_path, [], previously_allowed={"demo"}):
        if act.op in {"create", "update"}:
            _atomic_write_bytes(act.path, act.contents)
        elif act.op == "delete":
            try:
                act.path.unlink()
            except (FileNotFoundError, IsADirectoryError):
                pass

    assert target.read_bytes() == original


def test_codex_hook_diff_preserves_hand_rolled_groups(monkeypatch, tmp_path):
    """A user-authored matcher-group whose command is not under script_root must survive a link."""
    from agent_toolkit.harness_adapters.codex_hook import CodexHookAdapter
    from agent_toolkit.commands._mcp_dispatch import _atomic_write_bytes

    home = _seed_home(tmp_path, monkeypatch)
    target = home / ".codex" / "config.toml"
    shutil.copy(FIXTURE, target)

    a = CodexHookAdapter()
    entry = _make_entry(home=home)

    for act in a.diff("user", tmp_path, [entry]):
        if act.op in {"create", "update"}:
            _atomic_write_bytes(act.path, act.contents)

    rendered = target.read_text(encoding="utf-8")
    # User-owned hook still present.
    assert "/usr/local/bin/my-bash-guard.sh" in rendered
    # Toolkit hook also present.
    assert "agent-toolkit-hooks/demo/check.sh" in rendered


def test_codex_hook_diff_multi_event_produces_one_group_per_event(monkeypatch, tmp_path):
    """An entry with events=(PreToolUse, Stop) appears under both event arrays."""
    from agent_toolkit.harness_adapters.codex_hook import CodexHookAdapter
    from agent_toolkit.commands._mcp_dispatch import _atomic_write_bytes

    home = _seed_home(tmp_path, monkeypatch)
    a = CodexHookAdapter()
    entry = _make_entry(events=("PreToolUse", "Stop"), home=home)

    for act in a.diff("user", tmp_path, [entry]):
        if act.op in {"create", "update"}:
            _atomic_write_bytes(act.path, act.contents)

    rendered = (home / ".codex" / "config.toml").read_text(encoding="utf-8")
    assert "[[hooks.PreToolUse]]" in rendered
    assert "[[hooks.Stop]]" in rendered


def test_codex_hook_entry_drift_detects_changed_script(monkeypatch, tmp_path):
    """Drift = on-disk script bytes differ from entry's rendered bytes."""
    from agent_toolkit.harness_adapters.codex_hook import CodexHookAdapter
    from agent_toolkit.commands._mcp_dispatch import _atomic_write_bytes

    home = _seed_home(tmp_path, monkeypatch)
    a = CodexHookAdapter()
    entry = _make_entry(home=home)

    for act in a.diff("user", tmp_path, [entry]):
        if act.op in {"create", "update"}:
            _atomic_write_bytes(act.path, act.contents)

    assert a.entry_drift("user", tmp_path, entry) is False

    # Mutate the on-disk script.
    script_path = home / ".codex" / "agent-toolkit-hooks" / "demo" / "check.sh"
    script_path.write_bytes(b"#!/usr/bin/env bash\necho TAMPERED\n")

    assert a.entry_drift("user", tmp_path, entry) is True
```

- [ ] **Step 3: Run new tests to verify they fail**

```bash
uv run pytest tests/test_codex_hook_adapter.py -v -k "diff or drift or multi or hand_rolled"
```

Expected: FAIL with `NotImplementedError`.

- [ ] **Step 4: Implement `render`, `entry_drift`, and `diff`**

Edit `src/agent_toolkit/harness_adapters/codex_hook.py`. Replace the three stubbed methods with:

```python
    # ---- render: produce script file contents ----
    def render(self, entries: list[HookEntry]) -> dict[Path, bytes]:
        out: dict[Path, bytes] = {}
        for entry in entries:
            for path, data in entry.script_files.items():
                out[path] = data
        return out

    # ---- entry_drift ----
    def entry_drift(self, scope: Scope, project_root: Path, entry: HookEntry) -> bool:
        """True iff on-disk script bytes OR the [hooks] entries differ.

        Returns False when the entry is not installed; the dispatcher checks
        list_installed separately for presence.
        """
        # Script-side drift.
        for path, expected in entry.script_files.items():
            if not path.is_file():
                return True
            if path.read_bytes() != expected:
                return True

        # Config-side drift.
        target = self.config_target(scope, project_root)
        if target is None or not target.is_file():
            return True
        doc = self._read(target)
        managed_groups_for_entry = self._collect_managed_groups_for(doc, entry, scope, project_root)
        expected_groups = self._build_groups_for(entry)
        return managed_groups_for_entry != expected_groups

    # ---- diff (the engine) ----
    def diff(
        self,
        scope: Scope,
        project_root: Path,
        entries: list[HookEntry],
        *,
        previously_allowed: set[str] = frozenset(),
    ) -> list[WriteAction]:
        target = self.config_target(scope, project_root)
        root = self.script_root(scope, project_root)
        if target is None or root is None:
            return []

        actions: list[WriteAction] = []
        desired_names = {e.name for e in entries}
        managed_names = set(previously_allowed) | desired_names

        # ---- script side ----
        for entry in entries:
            for path, expected in entry.script_files.items():
                if path.is_file():
                    on_disk = path.read_bytes()
                    if on_disk == expected:
                        continue
                    actions.append(WriteAction(
                        path=path, op="update",
                        bytes_before=len(on_disk), bytes_after=len(expected),
                        contents=expected,
                    ))
                else:
                    actions.append(WriteAction(
                        path=path, op="create",
                        bytes_before=None, bytes_after=len(expected),
                        contents=expected,
                    ))

        # Removed entries: every file under root/<slug>/ is a delete.
        for slug in managed_names - desired_names:
            slug_dir = root / slug
            if slug_dir.is_dir():
                for f in slug_dir.iterdir():
                    if f.is_file():
                        actions.append(WriteAction(
                            path=f, op="delete",
                            bytes_before=f.stat().st_size, bytes_after=None,
                            contents=None,
                        ))
                # Drop the empty dir as a separate delete-action — dispatcher
                # handles dir-deletion via the same delete branch.
                actions.append(WriteAction(
                    path=slug_dir, op="delete",
                    bytes_before=0, bytes_after=None,
                    contents=None,
                ))

        # ---- config side ----
        if target.is_file():
            before_bytes = target.read_bytes()
            doc = self._read(target)
        else:
            before_bytes = b""
            doc = TOMLDocument()

        self._merge_hooks(doc, entries, root=root)

        after_bytes = tomlkit.dumps(doc).encode("utf-8")
        # Same trailing-newline strip as the MCP adapter (codex.py:146).
        if after_bytes.endswith(b"\n\n") and not before_bytes.endswith(b"\n\n"):
            after_bytes = after_bytes[:-1]

        if not target.is_file():
            if after_bytes:
                actions.append(WriteAction(
                    path=target, op="create",
                    bytes_before=None, bytes_after=len(after_bytes),
                    contents=after_bytes,
                ))
        elif after_bytes != before_bytes:
            actions.append(WriteAction(
                path=target, op="update",
                bytes_before=len(before_bytes), bytes_after=len(after_bytes),
                contents=after_bytes,
            ))

        return actions

    # ---- internals ----
    @staticmethod
    def _read(path: Path) -> TOMLDocument:
        return tomlkit.parse(path.read_text(encoding="utf-8"))

    def _is_managed_group(self, group, root: Path) -> bool:
        """A group is managed if any of its handlers' command starts with root/."""
        hooks = group.get("hooks") or []
        for h in hooks:
            cmd = h.get("command", "")
            if cmd.startswith(str(root) + "/"):
                return True
        return False

    def _build_groups_for(self, entry: HookEntry) -> dict:
        """Render a {event: matcher_group_dict} for an entry, used by drift checks."""
        out: dict[str, dict] = {}
        for event in entry.events:
            handler: dict = {"type": "command", "command": entry.command}
            if entry.timeout is not None:
                handler["timeout"] = entry.timeout
            if entry.async_:
                handler["async"] = True
            if entry.status_message is not None:
                handler["statusMessage"] = entry.status_message
            group: dict = {"hooks": [handler]}
            if entry.matcher is not None:
                group["matcher"] = entry.matcher
            out[event] = group
        return out

    def _collect_managed_groups_for(self, doc, entry: HookEntry, scope: Scope, project_root: Path) -> dict:
        """Read the existing managed groups belonging to one entry from `doc`."""
        root = self.script_root(scope, project_root)
        out: dict[str, dict] = {}
        hooks_table = doc.get("hooks")
        if hooks_table is None:
            return out
        for event in entry.events:
            arr = hooks_table.get(event) or []
            for g in arr:
                if self._is_managed_group(g, root) and any(
                    h.get("command", "").startswith(
                        str(root / entry.name) + "/"
                    )
                    for h in (g.get("hooks") or [])
                ):
                    # Convert tomlkit objects to plain dicts for comparison.
                    out[event] = {
                        "matcher": g.get("matcher"),
                        "hooks": [dict(h) for h in g.get("hooks") or []],
                    }
                    if out[event]["matcher"] is None:
                        del out[event]["matcher"]
                    break
        return out

    def _merge_hooks(
        self,
        doc: TOMLDocument,
        entries: list[HookEntry],
        *,
        root: Path,
    ) -> None:
        """Mutate `doc[hooks]` so its arrays match the desired entry set.

        - Drops every managed group (handler command starts with root/).
        - Re-emits desired entries' groups, sorted by entry name for determinism.
        - Hand-rolled groups (command not under root/) are preserved.
        - Removes the [hooks] table entirely if no managed and no hand-rolled groups remain.
        """
        # Ensure [hooks] exists if we have entries to write.
        if "hooks" not in doc and not entries:
            return
        if "hooks" not in doc:
            doc["hooks"] = table()
        hooks_table = doc["hooks"]

        # 1. Drop managed groups across all six events.
        for event in _CODEX_HOOK_EVENTS:
            arr = hooks_table.get(event)
            if arr is None:
                continue
            survivors = [g for g in arr if not self._is_managed_group(g, root)]
            if survivors:
                hooks_table[event] = survivors
            else:
                del hooks_table[event]

        # 2. Append managed groups for desired entries, sorted by entry name.
        for entry in sorted(entries, key=lambda e: e.name):
            for event in entry.events:
                handler = table()
                handler["type"] = "command"
                handler["command"] = entry.command
                if entry.timeout is not None:
                    handler["timeout"] = entry.timeout
                if entry.async_:
                    handler["async"] = True
                if entry.status_message is not None:
                    handler["statusMessage"] = entry.status_message

                group = table()
                if entry.matcher is not None:
                    group["matcher"] = entry.matcher
                group["hooks"] = [handler]

                if hooks_table.get(event) is None:
                    hooks_table[event] = [group]
                else:
                    arr = hooks_table[event]
                    arr.append(group)
                    hooks_table[event] = arr

        # 3. If [hooks] became empty, remove it.
        empty = all(
            (hooks_table.get(e) is None or len(hooks_table.get(e)) == 0)
            for e in _CODEX_HOOK_EVENTS
        )
        if empty:
            del doc["hooks"]
```

- [ ] **Step 5: Run the diff tests to verify they pass**

```bash
uv run pytest tests/test_codex_hook_adapter.py -v
```

Expected: 14 tests PASS (8 from Task 3 + 6 new).

- [ ] **Step 6: Run full test suite**

```bash
uv run pytest -q
```

Expected: 562 + 8 + 6 = 576 pass.

- [ ] **Step 7: Commit**

```bash
git add src/agent_toolkit/harness_adapters/codex_hook.py \
        tests/test_codex_hook_adapter.py \
        tests/_fixtures/codex_config_realistic_with_hooks.toml
git commit -m "feat(#56): implement CodexHookAdapter.diff/render/entry_drift

- Round-trip byte-equal: link → write → re-diff is empty.
- Unlink restores file byte-equal to original.
- Hand-rolled hook entries (command not under script_root) preserved.
- Multi-event entries produce one matcher-group per event.
- Drift detection reads script bytes + [hooks] entries.
- Slug-sorted emission for determinism."
```

---

### Task 5: Extend tomlkit round-trip fixture coverage

**Files:**
- Modify: `tests/test_tomlkit_roundtrip.py`

The existing test asserts `tomlkit.dumps(tomlkit.parse(...))` is byte-equal for the MCP-only fixture. We need to extend it to the new fixture to confirm tomlkit handles `[hooks]` round-trip cleanly.

- [ ] **Step 1: Read the existing test to learn the pattern**

```bash
cat tests/test_tomlkit_roundtrip.py
```

You'll see a parameterised test (or a single test with one fixture). Extend it with the new fixture.

- [ ] **Step 2: Add the new fixture case**

If the existing file uses parametrize, add the new fixture path. If it's a single test, duplicate the function with the new fixture. Specifically, ensure there's a test that does:

```python
def test_tomlkit_round_trip_codex_with_hooks():
    """The new fixture (mcp_servers + [hooks] + comments + hand-rolled groups)
    must round-trip byte-equal."""
    fx = Path(__file__).parent / "_fixtures" / "codex_config_realistic_with_hooks.toml"
    src = fx.read_bytes()
    doc = tomlkit.parse(src.decode("utf-8"))
    out = tomlkit.dumps(doc).encode("utf-8")
    assert out == src, "tomlkit round-trip drifted on [hooks] fixture"
```

(Adapt the helper imports to match what the existing test uses.)

- [ ] **Step 3: Run the test**

```bash
uv run pytest tests/test_tomlkit_roundtrip.py -v
```

Expected: PASS for both the existing fixture and the new one.

- [ ] **Step 4: Commit**

```bash
git add tests/test_tomlkit_roundtrip.py
git commit -m "test(#56): extend tomlkit round-trip coverage to [hooks] fixture"
```

---

### Task 6: Hook dispatcher (`_hook_dispatch.py`)

**Files:**
- Create: `src/agent_toolkit/commands/_hook_dispatch.py`
- Create: `tests/test_hook_dispatch.py`

The dispatcher orchestrates adapter actions, atomic writes, chmod for scripts, and the loud-print contract. Mirrors `_mcp_dispatch.apply_link` but typed for `HookEntry` and aware of file-mode.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_hook_dispatch.py`:

```python
"""_hook_dispatch.apply_link — atomic writes, 0o755 chmod, dry-run prints."""
from __future__ import annotations

import io
import os
import stat
from pathlib import Path

import pytest


def _make_adapter():
    from agent_toolkit.harness_adapters.codex_hook import CodexHookAdapter
    return CodexHookAdapter()


def _make_entry(home: Path, name: str = "demo"):
    from agent_toolkit.harness_adapters.base import HookEntry

    script_path = home / ".codex" / "agent-toolkit-hooks" / name / "check.sh"
    return HookEntry(
        name=name,
        events=("PreToolUse",),
        command=str(script_path),
        script_files={script_path: b"#!/usr/bin/env bash\necho hi\n"},
    )


def test_apply_link_creates_script_with_executable_mode(monkeypatch, tmp_path):
    from agent_toolkit.commands._hook_dispatch import apply_link

    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".codex").mkdir()

    adapter = _make_adapter()
    entry = _make_entry(tmp_path)
    out = io.StringIO()

    apply_link(
        adapter,
        scope="user",
        project_root=tmp_path,
        entries=[entry],
        dry_run=False,
        stdout=out,
    )

    script = tmp_path / ".codex" / "agent-toolkit-hooks" / "demo" / "check.sh"
    assert script.is_file()
    mode = script.stat().st_mode
    # Owner +x at minimum.
    assert mode & stat.S_IXUSR, f"expected +x on owner, got {oct(mode)}"


def test_apply_link_dry_run_prints_would_create(monkeypatch, tmp_path):
    from agent_toolkit.commands._hook_dispatch import apply_link

    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".codex").mkdir()

    adapter = _make_adapter()
    entry = _make_entry(tmp_path)
    out = io.StringIO()

    apply_link(
        adapter,
        scope="user",
        project_root=tmp_path,
        entries=[entry],
        dry_run=True,
        stdout=out,
    )

    output = out.getvalue()
    assert "would-create" in output
    # Nothing written.
    script = tmp_path / ".codex" / "agent-toolkit-hooks" / "demo" / "check.sh"
    assert not script.exists()


def test_apply_link_propagates_cannot_install(monkeypatch, tmp_path):
    from agent_toolkit.commands._hook_dispatch import apply_link
    from agent_toolkit.harness_adapters.base import CannotInstall, HookEntry

    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".codex").mkdir()

    adapter = _make_adapter()
    bad = HookEntry(
        name="bad",
        events=("Boom",),  # unknown event
        command=str(tmp_path / ".codex" / "agent-toolkit-hooks" / "bad" / "x.sh"),
        script_files={},
    )
    out = io.StringIO()

    with pytest.raises(CannotInstall, match="unknown"):
        apply_link(
            adapter,
            scope="user",
            project_root=tmp_path,
            entries=[bad],
            dry_run=False,
            stdout=out,
        )


def test_build_hook_entries_reads_meta_and_script(tmp_path, monkeypatch):
    """_build_hook_entries reads hooks/<slug>/.meta.yaml + the script file."""
    from agent_toolkit.commands._hook_dispatch import _build_hook_entries

    monkeypatch.setenv("HOME", str(tmp_path))

    toolkit = tmp_path / "toolkit"
    hook_dir = toolkit / "hooks" / "demo"
    hook_dir.mkdir(parents=True)
    (hook_dir / ".meta.yaml").write_text(
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n"
        "  name: demo\n"
        "  description: A demo hook.\n"
        "  kind: hook\n"
        "  lifecycle: experimental\n"
        "spec:\n"
        "  origin: first-party\n"
        "  vendored_via: none\n"
        "  harnesses: [codex]\n"
        "  hook:\n"
        "    events: [PreToolUse]\n"
        "    command: check.sh\n"
        "    matcher: '^Bash$'\n"
        "    timeout: 10\n",
        encoding="utf-8",
    )
    (hook_dir / "check.sh").write_bytes(b"#!/usr/bin/env bash\necho hi\n")

    entries = _build_hook_entries(toolkit, ["demo"])
    assert len(entries) == 1
    e = entries[0]
    assert e.name == "demo"
    assert e.events == ("PreToolUse",)
    assert e.matcher == "^Bash$"
    assert e.timeout == 10
    expected_script = tmp_path / ".codex" / "agent-toolkit-hooks" / "demo" / "check.sh"
    assert e.command == str(expected_script)
    assert e.script_files[expected_script] == b"#!/usr/bin/env bash\necho hi\n"


def test_build_hook_entries_skips_missing_assets(tmp_path):
    from agent_toolkit.commands._hook_dispatch import _build_hook_entries

    toolkit = tmp_path / "toolkit"
    (toolkit / "hooks").mkdir(parents=True)
    # Slug "ghost" has no directory.
    entries = _build_hook_entries(toolkit, ["ghost"])
    assert entries == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_hook_dispatch.py -v
```

Expected: all FAIL with `ModuleNotFoundError: No module named 'agent_toolkit.commands._hook_dispatch'`.

- [ ] **Step 3: Create the dispatcher**

Create `src/agent_toolkit/commands/_hook_dispatch.py`:

```python
"""Dispatcher: orchestrates CodexHookAdapter.diff() output into atomic writes + chmod.

Mirrors _mcp_dispatch.apply_link but typed for HookEntry. Reuses the atomic
write engine and loud-print contract from _mcp_dispatch.

The dispatcher is the boundary between the toolkit source-of-truth (where
hooks/<slug>/ lives) and the harness-projected output (script_root/<slug>/).
The adapter never reads the toolkit directory.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import IO, Iterable

import yaml

from agent_toolkit.harness_adapters.base import (
    HookEntry,
    Scope,
    UnimplementedAdapter,
    WriteAction,
)
from agent_toolkit.commands._mcp_dispatch import (
    _atomic_write_bytes,
    _print_post,
    _print_pre,
)


def _build_hook_entries(toolkit_root: Path, slugs: Iterable[str]) -> list[HookEntry]:
    """Resolve slugs → HookEntry by reading hooks/<slug>/.meta.yaml + the script.

    Skips slugs whose hooks/<slug>/.meta.yaml is not present. Each entry's
    `command` is resolved to an absolute destination path under
    $HOME/.codex/agent-toolkit-hooks/<slug>/<command>.
    """
    home = Path(os.environ.get("HOME", ""))
    script_root = home / ".codex" / "agent-toolkit-hooks"

    entries: list[HookEntry] = []
    for slug in slugs:
        hook_dir = toolkit_root / "hooks" / slug
        meta_path = hook_dir / ".meta.yaml"
        if not meta_path.is_file():
            continue
        meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
        spec_hook = ((meta.get("spec") or {}).get("hook")) or {}
        command_rel = spec_hook.get("command")
        if not command_rel:
            continue

        # Source script (in toolkit) and destination script (under script_root).
        src_script = hook_dir / command_rel
        if not src_script.is_file():
            continue
        dest_script = script_root / slug / command_rel
        script_bytes = src_script.read_bytes()

        entries.append(HookEntry(
            name=slug,
            events=tuple(spec_hook.get("events") or ()),
            command=str(dest_script),
            matcher=spec_hook.get("matcher"),
            timeout=spec_hook.get("timeout"),
            async_=bool(spec_hook.get("async", False)),
            status_message=spec_hook.get("status_message"),
            script_files={dest_script: script_bytes},
        ))
    return entries


def apply_link(
    adapter,
    *,
    scope: Scope,
    project_root: Path,
    entries: list[HookEntry],
    dry_run: bool,
    stdout: IO[str],
    previously_allowed: set[str] = frozenset(),
) -> list[WriteAction]:
    """Reconcile adapter state to the desired hook entry set.

    Pre-flight every entry (CannotInstall propagates). In dry-run, prints
    `would-<op>: <path>` per non-unchanged action. In real-run, writes
    bytes atomically, chmods scripts under script_root to 0o755, and
    prints the loud-print contract pair.
    """
    if isinstance(adapter, UnimplementedAdapter):
        return []

    for entry in entries:
        adapter.can_install(entry)

    actions = adapter.diff(
        scope, project_root, entries,
        previously_allowed=previously_allowed,
    )

    if dry_run:
        for act in actions:
            if act.op == "unchanged":
                continue
            print(f"would-{act.op}: {act.path}", file=stdout)
        return actions

    script_root = adapter.script_root(scope, project_root)

    for act in actions:
        if act.op == "unchanged":
            continue
        _print_pre(act, stdout)
        _execute_action(act, script_root)
        _print_post(act, stdout)
    return actions


def _execute_action(act: WriteAction, script_root: Path | None) -> None:
    if act.op in {"create", "update"}:
        if act.contents is None:
            raise RuntimeError(f"{act.op} action missing contents: {act.path}")
        _atomic_write_bytes(act.path, act.contents)
        # Chmod 0o755 if the path lives under script_root.
        if script_root is not None and _path_under(act.path, script_root):
            os.chmod(act.path, 0o755)
    elif act.op == "delete":
        if act.path.is_dir():
            try:
                act.path.rmdir()  # only works if empty; files were deleted earlier
            except (FileNotFoundError, OSError):
                pass
        else:
            try:
                act.path.unlink()
            except FileNotFoundError:
                pass


def _path_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_hook_dispatch.py -v
```

Expected: 5 PASS.

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest -q
```

Expected: 576 + 5 = 581 pass.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit/commands/_hook_dispatch.py \
        tests/test_hook_dispatch.py
git commit -m "feat(#56): hook dispatcher with atomic writes + 0o755 chmod

_hook_dispatch.apply_link mirrors _mcp_dispatch.apply_link but typed
for HookEntry. Reuses atomic-write engine + loud-print pair. Chmods
0o755 on any WriteAction whose path lives under script_root. Handles
delete-action for both files and (now-empty) slug directories.

_build_hook_entries reads hooks/<slug>/.meta.yaml + the script file
and packs them into HookEntry.script_files keyed by destination path."
```

---

### Task 7: Kind-aware `get_adapter()` + `_link_lib` routing + `_support` row

**Files:**
- Modify: `src/agent_toolkit/harness_adapters/__init__.py`
- Modify: `src/agent_toolkit/_support.py`
- Modify: `src/agent_toolkit/commands/_link_lib.py`
- Modify: `tests/test_harness_matrix.py`
- Test: ad-hoc unit test `test_get_adapter_kind_aware` added inline.

This is the wiring task. End-to-end, `agent-toolkit link --harness=codex hook:demo` must reach the new dispatcher.

- [ ] **Step 1: Write the failing kind-aware test**

Create `tests/test_get_adapter_kind_aware.py`:

```python
"""get_adapter is kind-aware: codex+mcp → CodexAdapter, codex+hook → CodexHookAdapter."""
from __future__ import annotations


def test_get_adapter_codex_mcp_returns_mcp_adapter():
    from agent_toolkit.harness_adapters import get_adapter
    from agent_toolkit.harness_adapters.codex import CodexAdapter

    a = get_adapter("codex", "mcp")
    assert isinstance(a, CodexAdapter)
    assert a.strategy == "config_file"


def test_get_adapter_codex_hook_returns_hook_adapter():
    from agent_toolkit.harness_adapters import get_adapter
    from agent_toolkit.harness_adapters.codex_hook import CodexHookAdapter

    a = get_adapter("codex", "hook")
    assert isinstance(a, CodexHookAdapter)
    assert a.strategy == "config_file+folder"


def test_get_adapter_default_kind_is_mcp_for_backcompat():
    """Existing callers that don't pass kind must keep working."""
    from agent_toolkit.harness_adapters import get_adapter
    from agent_toolkit.harness_adapters.codex import CodexAdapter

    a = get_adapter("codex")
    assert isinstance(a, CodexAdapter)


def test_get_adapter_unknown_harness_raises():
    import pytest
    from agent_toolkit.harness_adapters import get_adapter

    with pytest.raises(ValueError, match="unknown harness"):
        get_adapter("nope", "mcp")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_get_adapter_kind_aware.py -v
```

Expected: `test_get_adapter_codex_hook_returns_hook_adapter` FAILs (the others may pass thanks to the existing default-MCP behaviour — but the kind="hook" branch doesn't exist yet).

- [ ] **Step 3: Update `get_adapter` to be kind-aware**

Edit `src/agent_toolkit/harness_adapters/__init__.py`. Replace the `get_adapter` function with:

```python
def get_adapter(harness: str, kind: str = "mcp"):
    """Return the adapter for `(harness, kind)`.

    Raises ValueError on unknown harness. Returns UnimplementedAdapter for
    known-but-pending pairs.

    The `kind` parameter exists because some harnesses have different
    adapters for different asset kinds (e.g. codex has a config_file
    adapter for mcp and a config_file+folder adapter for hook). Defaults
    to "mcp" for backward compatibility with existing call sites.
    """
    if harness not in _KNOWN_HARNESSES:
        raise ValueError(f"unknown harness {harness!r}")
    if harness == "codex" and kind == "mcp":
        from agent_toolkit.harness_adapters.codex import CodexAdapter
        return CodexAdapter()
    if harness == "codex" and kind == "hook":
        from agent_toolkit.harness_adapters.codex_hook import CodexHookAdapter
        return CodexHookAdapter()
    return UnimplementedAdapter(harness)
```

- [ ] **Step 4: Run kind-aware tests to verify they pass**

```bash
uv run pytest tests/test_get_adapter_kind_aware.py -v
```

Expected: 4 PASS.

- [ ] **Step 5: Add `("codex", "hook")` to `_USER_TARGETS`**

Edit `src/agent_toolkit/_support.py`. In `_USER_TARGETS`, add a row after the existing `("codex", "skill")` line:

```python
    ("codex", "skill"):        "{home}/.codex/skills",
    ("codex", "hook"):         "{home}/.codex/agent-toolkit-hooks",  # config_file+folder
```

The path is the script_root, used by `harness_target_dir` for inventory/list paths. The hook adapter manages its own writes — `_USER_TARGETS` membership is what makes `is_supported("codex", "hook", scope="user")` answer True so the linker routes to the hook dispatcher.

Note: do **not** add a `_PROJECT_TARGETS` row. PR1 is user-scope only; `is_supported("codex", "hook", scope="project")` returning False is desired.

- [ ] **Step 6: Add the `kind == "hook"` branch in `_link_lib.py`**

Edit `src/agent_toolkit/commands/_link_lib.py`. Find the projection loop (around line 443 in `for kind in KINDS_FOR_PROJECTION:`). After the existing `if kind == "mcp":` block (which ends around line 489 with `continue`), add a parallel block for hooks:

```python
        if kind == "hook":
            section = kind_to_section(kind)
            hook_allowed_slugs = list(allowed.get(section, []))

            from agent_toolkit.commands._hook_dispatch import (  # noqa: PLC0415
                _build_hook_entries, apply_link,
            )
            from agent_toolkit.harness_adapters import get_adapter  # noqa: PLC0415
            from agent_toolkit.harness_adapters.base import (  # noqa: PLC0415
                CannotInstall, UnimplementedAdapter,
            )

            adapter = get_adapter(harness, kind="hook")
            if isinstance(adapter, UnimplementedAdapter):
                if hook_allowed_slugs:
                    print(adapter.skip_message(), file=stdout)
                continue

            if previous_allowed is not None:
                prev_hooks = set(previous_allowed.get(section) or [])
            else:
                prev_hooks = set(hook_allowed_slugs)

            entries = _build_hook_entries(toolkit_root, hook_allowed_slugs)
            try:
                apply_link(
                    adapter,
                    scope=scope,
                    project_root=project_root,
                    entries=entries,
                    dry_run=dry_run,
                    stdout=stdout,
                    previously_allowed=prev_hooks,
                )
            except CannotInstall as exc:
                print(f"warning: {exc}", file=stdout)
                continue
            continue
```

The `kind == "hook"` block goes **before** the `is_supported` check below it (so we don't fall through into the symlink/translate path).

- [ ] **Step 7: Update the parity test to handle kind-aware adapters and the new mechanism**

Edit `tests/test_harness_matrix.py`. Three edits:

a) Add `"config_file+folder"` to the module-level `VALID_MECHANISMS` frozenset (around line 33):

```python
VALID_MECHANISMS = frozenset(
    [
        "symlink",
        "config_file",
        "config_file+folder",
        "plugin_folder",
        "translate",
        "unsupported (gap)",
        "unsupported (by design)",
    ]
)
```

`_cell_mechanism()` (line 79) already does longest-match-first (line 86: `sorted(..., key=len, reverse=True)`), so `config_file+folder` will be matched before `config_file`. No change to `_cell_mechanism` needed.

b) In `class TestAdapterParity`, update both methods so the set of allowed mechanisms includes `"config_file+folder"`:

```python
adapter_mechanisms = {"config_file", "plugin_folder", "config_file+folder"}
```

c) In the same two methods, change `get_adapter(harness)` to `get_adapter(harness, kind)`:

```python
adapter = get_adapter(harness, kind)
```

(replace both call sites — one in `test_config_file_and_plugin_folder_cells_have_real_adapters`, one in `test_adapter_strategy_matches_doc_cell`).

- [ ] **Step 8: Run full test suite**

```bash
uv run pytest -q
```

Expected: existing tests pass. Some `test_harness_matrix` tests may fail because the matrix doc still says `unsupported (by design)` for `codex/hook` — that's fixed in Task 8. For now, only the parity tests should be skipped/satisfied because no cell yet says `config_file+folder`.

If a non-parity test fails, fix it before continuing. Common failure: a test that calls `get_adapter("codex")` without a kind and now hits the wrong branch — but the default-`kind="mcp"` keeps backward compat, so this should not happen.

- [ ] **Step 9: Commit**

```bash
git add src/agent_toolkit/harness_adapters/__init__.py \
        src/agent_toolkit/_support.py \
        src/agent_toolkit/commands/_link_lib.py \
        tests/test_harness_matrix.py \
        tests/test_get_adapter_kind_aware.py
git commit -m "feat(#56): kind-aware get_adapter + hook routing in _link_lib

- get_adapter(harness, kind='mcp') — default keeps existing callers working.
- ('codex','hook') added to _USER_TARGETS so is_supported answers True.
- _link_lib projection loop gains a hook branch parallel to mcp branch.
- TestAdapterParity accepts 'config_file+folder' mechanism and calls
  get_adapter(harness, kind)."
```

---

### Task 8: Demo asset + matrix update + parity test green

**Files:**
- Create: `tests/_fixtures/hook_assets/codex-demo/.meta.yaml`
- Create: `tests/_fixtures/hook_assets/codex-demo/check.sh`
- Modify: `docs/agent-toolkit/harness-matrix.md`

The matrix update is a hard prerequisite for the parity test to assert anything. Demo asset is needed for the TUI smoke test in Task 9.

- [ ] **Step 1: Create the demo asset**

Create `tests/_fixtures/hook_assets/codex-demo/.meta.yaml`:

```yaml
apiVersion: agent-toolkit/v1alpha2
metadata:
  name: codex-demo
  description: Demo hook used by round-trip and TUI smoke tests.
  kind: hook
  lifecycle: experimental
spec:
  origin: first-party
  vendored_via: none
  harnesses: [codex]
  hook:
    events: [PreToolUse]
    command: check.sh
    matcher: "^Bash$"
    timeout: 10
```

Create `tests/_fixtures/hook_assets/codex-demo/check.sh`:

```sh
#!/usr/bin/env bash
echo "codex-demo PreToolUse hook" >&2
exit 0
```

- [ ] **Step 2: Update the matrix doc**

Edit `docs/agent-toolkit/harness-matrix.md`. Three changes:

a) In the `## Mechanisms` section (around line 9), add a new bullet after the `config_file` and `plugin_folder` bullets, before `translate`:

```
- **config_file+folder** — adapter both mutates a single named config file
  AND owns a managed sub-folder of artefacts. Both surfaces commit or
  rollback together via one `diff()` call. Used for codex hooks (script
  files under `~/.codex/agent-toolkit-hooks/<slug>/` plus `[hooks]`
  entries in `~/.codex/config.toml`).
```

`VALID_MECHANISMS` in `tests/test_harness_matrix.py` (Task 7) was already updated to match.

b) Find the Codex row's `hook` cell (currently `unsupported (by design) — Codex has no hooks API at the user level`). Replace with:

```
config_file+folder → ~/.codex/config.toml [hooks] + ~/.codex/agent-toolkit-hooks/<slug>/
```

c) Find the Codex row's `agent` cell. Replace its rationale text with:

```
unsupported (by design) — Codex's [agents] config surface (added in CLI 0.128.0) is for harness-internal agent declarations, not toolkit-shape agents (markdown body + frontmatter). Refined per #56.
```

(Match the surrounding markdown formatting — table cells, escaping, etc.)

- [ ] **Step 3: Run the parity test**

```bash
uv run pytest tests/test_harness_matrix.py -v
```

Expected: PASS — `codex/hook` cell now claims `config_file+folder`, `get_adapter("codex", "hook")` returns `CodexHookAdapter` with matching strategy.

- [ ] **Step 4: Run full test suite**

```bash
uv run pytest -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add tests/_fixtures/hook_assets/codex-demo/.meta.yaml \
        tests/_fixtures/hook_assets/codex-demo/check.sh \
        docs/agent-toolkit/harness-matrix.md
git commit -m "feat(#56): codex/hook matrix cell + demo asset

Matrix doc flips codex/hook to config_file+folder and refines the
codex/agent rationale to cite the [agents] config-surface mismatch
(deferred per spec). Demo asset under tests/_fixtures/hook_assets/
backs the TUI smoke test."
```

---

### Task 9: TUI smoke test

**Files:**
- Create: `tests/test_tui_hook_integration.py`

Mirror of `tests/test_tui_mcp_integration.py`. Seeds a hook asset in a temp toolkit, calls the link plan, asserts both the TOML and script land correctly.

- [ ] **Step 1: Read the existing MCP smoke test for the pattern**

```bash
cat tests/test_tui_mcp_integration.py
```

Note the fixtures, the `CLIRunner` (or equivalent) usage, and the skip condition (e.g. `pytest.skip` if `agent-toolkit` is not on `$PATH`).

- [ ] **Step 2: Create the hook smoke test**

Create `tests/test_tui_hook_integration.py`. Use the MCP test as a template; the substantive differences:

```python
"""TUI smoke: link a codex hook asset and verify config.toml + script."""
from __future__ import annotations

import shutil
import stat
from pathlib import Path

import pytest


_FIXTURE = Path(__file__).parent / "_fixtures" / "hook_assets" / "codex-demo"


def _seed_toolkit(tmp_path: Path) -> Path:
    """Copy the demo asset into a fresh hooks/<slug>/ tree."""
    toolkit = tmp_path / "toolkit"
    dest = toolkit / "hooks" / "codex-demo"
    dest.mkdir(parents=True)
    shutil.copytree(_FIXTURE, dest, dirs_exist_ok=True)
    return toolkit


def test_tui_hook_link_creates_config_and_script(monkeypatch, tmp_path):
    """Link a codex hook through the TUI's CLI runner; assert both artefacts land."""
    pytest.importorskip("agent_toolkit_tui")
    if shutil.which("agent-toolkit") is None:
        pytest.skip("agent-toolkit not on PATH")

    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".codex").mkdir()

    toolkit = _seed_toolkit(tmp_path)

    # Use the same CLIRunner pattern as test_tui_mcp_integration.py.
    # (The existing MCP test imports CLIRunner from a known module — copy
    # that import here. If it lives in agent_toolkit_tui.cli_runner or
    # similar, mirror that.)
    from agent_toolkit_tui.cli_runner import CLIRunner

    runner = CLIRunner(toolkit_root=toolkit)
    runner.link_plan(scope="user", harness="codex", entries=[("hook", "codex-demo")])

    state = runner.list_state(harness="codex", scope="user", kind="hook")
    assert state == "linked-matches", f"expected linked-matches, got {state!r}"

    config = tmp_path / ".codex" / "config.toml"
    assert config.is_file()
    assert "agent-toolkit-hooks/codex-demo/check.sh" in config.read_text(encoding="utf-8")

    script = tmp_path / ".codex" / "agent-toolkit-hooks" / "codex-demo" / "check.sh"
    assert script.is_file()
    mode = script.stat().st_mode
    assert mode & stat.S_IXUSR, f"expected +x on owner, got {oct(mode)}"
```

If the MCP test imports `CLIRunner` from a different path or uses a different signature, adapt this accordingly. The shape (seed → link_plan → assert state + files) is the constant.

- [ ] **Step 3: Run the smoke test**

```bash
uv run pytest tests/test_tui_hook_integration.py -v
```

Expected: PASS (or SKIP cleanly if `agent-toolkit` is not on `$PATH` in the CI runner — same behaviour as the MCP version).

- [ ] **Step 4: Run full test suite**

```bash
uv run pytest -q
```

Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add tests/test_tui_hook_integration.py
git commit -m "test(#56): TUI smoke for codex hook link

Seeds a codex-demo hook asset in a temp toolkit, runs link_plan via
CLIRunner, asserts both ~/.codex/config.toml and the script under
~/.codex/agent-toolkit-hooks/codex-demo/ land with +x set."
```

---

## Self-review

- ✓ **Spec coverage.** Schema (Task 1), HookEntry+Protocol (Task 2), CodexHookAdapter scaffolding+can_install (Task 3), CodexHookAdapter.diff (Task 4), tomlkit round-trip extension (Task 5), `_hook_dispatch` (Task 6), kind-aware `get_adapter`+`_link_lib` routing+`_support` row (Task 7), demo asset + matrix update + parity (Task 8), TUI smoke (Task 9).
- ✓ **No placeholders.** Every step has either complete code or a precise edit instruction.
- ✓ **Type consistency.** `HookEntry` shape matches across adapter, dispatcher, builder. `script_root` returns `Path | None` everywhere. `_CODEX_HOOK_EVENTS` defined once in `codex_hook.py`.
- ✓ **Schema-vendor-check.** Task 1 explicitly copies the source schema to `schemas/` and runs `diff` to confirm equality before committing.
- ✓ **TDD discipline.** Every task that adds behaviour writes tests first, runs them red, implements, runs them green.
- ✓ **lefthook compatibility.** Pre-flight `uv sync --all-extras` ensures the test suite collects cleanly so every commit's pre-commit hook runs against the full suite.

## Issue-close handoff (post-merge)

Not part of this plan, but flagged for completeness — when the PR merges, the issue close comment must:

1. Document the `[agents]` deferral with rationale (see spec § "agents deferral — issue closing comment").
2. File the follow-up issue: *"Investigate Codex `[agents]` projection from kind:agent"*.
3. File a second follow-up if helpful: *"Codex `[hooks]` project scope — verify and add"*.

These are `flow` Step 12 territory, not implementation tasks.
