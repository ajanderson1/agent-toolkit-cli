# MCP Kind (v3) Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-port the `mcp` (Model Context Protocol server) asset kind into the current v3 per-kind architecture as a first-class, lock-driven, four-harness capability — `add`/`install`/`uninstall`/`remove`/`list`/`status`/`doctor` — with a config-injection adapter layer that manages MCP entries *by name* inside each harness's native config file, never by file ownership.

**Architecture:** Follow the established v3 per-kind pattern exactly (the same shape `agent` and `pi_extension` kinds use): parallel modules `mcp_install.py` / `mcp_lock.py` / `mcp_paths.py`, a `commands/mcp/` Click group, and an `mcp_adapters/` package whose `get_adapter(harness)` dispatcher is the single SSOT for the per-harness projection mechanism. The shared kind-agnostic core (`_install_core.py`) is bound via injected callables; the lockfile gains an `mcpPath` field on the shared `LockEntry` and a per-kind lock filename. Unlike folder-shaped kinds (skills/agents) that symlink or copy a markdown file, MCP is **config-injection-shaped**: each adapter surgically upserts/removes one named entry (`[mcp_servers.<name>]` in Codex TOML, `mcpServers.<name>` in Claude/Pi/OpenCode JSON) using a round-tripping parser, preserving every other byte. Every write is loud and atomic (temp file in same dir → `os.replace`).

**Tech Stack:** Python 3.11+, Click, `tomlkit` (Codex TOML round-trip — NEW dependency), stdlib `json` (Claude/Pi/OpenCode), pytest. Catalog source: `<toolkit-repo>/mcps/<name>/{config.json, README.md}` plus a sibling `<name>.toolkit.yaml` metadata sidecar.

**Prior art (re-mapped, predates v3):**
- Spec/brainstorm: `docs/superpowers/specs/2026-05-04-mcp-management-design.md` — the design these tasks implement (manage-by-name, round-trip, loud atomic writes, four harness strategy table, the empty-`{}` / absent-`.mcp.json` failure-mode notes added 2026-06-07).
- Superseded plan: `docs/superpowers/plans/2026-05-04-mcp-foundations.md` — written against the deleted v1 walker/sidecar/`_allowlist.py` machinery; **do not follow it**; this plan replaces it.
- Closed v1 issues for reference only: #55 (config_file adapters), #74 (codex HTTP transport), #125 (project-scope link absent-file bug), #141/#142 (list JSON MCP cells), #39 (TUI MCP sidebar — out of scope here).

---

## Orientation: read these before Task 1 (no edits)

Before writing any code, the engineer MUST read the agent kind as the working template — it is the closest sibling and the canonical example of every contract this plan relies on:

- `src/agent_toolkit_cli/agent_adapters/__init__.py` — the dispatcher + `Protocol` + `_guard_foreign` / `.attk` sentinel pattern. **Copy this file's structure for `mcp_adapters/__init__.py`.**
- `src/agent_toolkit_cli/agent_install.py` — the facade that binds `_install_core.py` via injected callables, and (critically) the **rollback contract**: on a projection conflict, write the lock first, apply, and roll back the prior projection on failure. The MCP facade MUST mirror this.
- `src/agent_toolkit_cli/agent_lock.py` — per-kind lock filename + `agentPath` field on the shared `LockEntry`. MCP adds `mcpPath`.
- `src/agent_toolkit_cli/agent_paths.py` — scope/root resolution.
- `src/agent_toolkit_cli/commands/agent/__init__.py` + `add_cmd.py` + `install_cmd.py` + `uninstall_cmd.py` + `remove_cmd.py` + `list_cmd.py` + `status_cmd.py` + `doctor_cmd.py` — the CLI verbs to mirror. Note the read/write scope-default split documented in the `__init__.py` docstring (read verbs `read_only=True` → global default; write verbs default to project when a project lock is present).
- `src/agent_toolkit_cli/_install_core.py` — the shared core and `InstallError` hierarchy.
- `src/agent_toolkit_cli/skill_agents.py` — `AGENTS` registry (the harness catalog). MCP adapter dispatch keys off harness name here.

**Project-memory mandates (non-negotiable, enforced by tasks below):**
1. **Install machinery has repeatedly shipped silently-broken global-scope / orphan paths with green CI.** Every install path MUST have an explicit `install → uninstall → assert-clean` round-trip test **at BOTH user and project scope** (Tasks 9, 10).
2. **`uninstall` is non-destructive; `remove` is destructive.** `uninstall` removes the harness projection only and leaves the canonical/lock intact; `remove` drops the canonical entry + lock entry. Mirror the agent kind's contract exactly (project memory: a misnamed `uninstall -g` once `rmtree`'d the canonical store).
3. **Apply-over-existing MUST roll back the prior projection on a Canonical/PointerConflict** (mirror `install_cmd` rollback contract).
4. **Packaged-resource paths must survive a wheel install** — no `parents[N]` walks to find repo files at runtime; the catalog is resolved via the toolkit-repo flag, not relative-to-`__file__` (Task 11 guard).

## Out of scope (explicit — deferred to follow-up issues)

- `fix` (drift reconciliation) and `diff` (dry-run) verbs. `doctor` reports drift but does not write.
- `push` / `update` / `reset` / `import` verbs for MCP (skills/agents have them; MCP foundations does not need them — the catalog is hand-authored or scaffolded via `add`).
- The TUI MCPs section (#39 lineage).
- Schema bump to `v1alpha2` / `metadata.kind` discriminator.
- `verify:` command execution (arbitrary shell; opt-in `--verify` is a follow-up).
- `ingest` of one-off MCPs from URLs.
- `--force` running-`claude`-process guard for `~/.claude.json` (record as a known limitation in `doctor`; full guard is a follow-up).

---

## File Structure

**New files:**

- `src/agent_toolkit_cli/mcp_paths.py` — scope + catalog-root resolution for the MCP kind. Mirrors `agent_paths.py`.
- `src/agent_toolkit_cli/mcp_lock.py` — `mcp-lock.json` reader/writer; adds `mcpPath` to the shared `LockEntry` consumers. Mirrors `agent_lock.py`.
- `src/agent_toolkit_cli/mcp_catalog.py` — reads `<toolkit-repo>/mcps/<name>/{config.json}` + sibling `<name>.toolkit.yaml` metadata; returns an `McpAsset` (slug, inner_config dict, metadata dict, transport, install_method).
- `src/agent_toolkit_cli/mcp_install.py` — the facade: `apply()` / `uninstall()` / `remove()` binding `_install_core.py` and dispatching to `mcp_adapters.get_adapter()`. Mirrors `agent_install.py` including the rollback contract.
- `src/agent_toolkit_cli/mcp_adapters/__init__.py` — `McpAdapter` Protocol, `get_adapter(harness)` SSOT dispatcher, shared atomic-write + round-trip-read helpers, `McpProjectionConflictError`.
- `src/agent_toolkit_cli/mcp_adapters/json_config.py` — config-file adapter for Claude / Pi / OpenCode (JSON family). Per-harness target paths + per-harness key translation in per-cell dicts inside the module.
- `src/agent_toolkit_cli/mcp_adapters/toml_config.py` — config-file adapter for Codex (`~/.codex/config.toml` via `tomlkit`).
- `src/agent_toolkit_cli/commands/mcp/__init__.py` — the `mcp` Click group + subcommand registration. Mirrors `commands/agent/__init__.py`.
- `src/agent_toolkit_cli/commands/mcp/_common.py` — shared scope/root resolution for the verbs.
- `src/agent_toolkit_cli/commands/mcp/{add,install,uninstall,remove,list,status,doctor}_cmd.py` — the seven verbs.

**New test files:**

- `tests/test_mcp_catalog.py`
- `tests/test_mcp_lock.py`
- `tests/test_mcp_adapters_json.py`
- `tests/test_mcp_adapters_toml.py`
- `tests/test_mcp_install.py`
- `tests/test_cli_mcp.py` — CLI-level round-trip + both-scope tests (the project-memory guard).
- `tests/test_mcp_wheel.py` — runs the built wheel from outside the repo (packaged-resource guard).

**Modified files:**

- `src/agent_toolkit_cli/cli.py` — register the `mcp` command group.
- `src/agent_toolkit_cli/_install_core.py` — only if a new injected callable is genuinely required (prefer not; verify the agent facade already exposes the seam).
- `pyproject.toml` — add `tomlkit` dependency.
- `docs/agent-toolkit/roadmap.md` — strike `mcp` from the Phase 2 pending list.
- `README.md` — note MCP is now a supported kind (four harnesses, foundations slice).

---

## Task 1: Add the `tomlkit` dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add the dependency**

In `pyproject.toml`, add `tomlkit>=0.13` to the `[project] dependencies` array (alongside the existing runtime deps such as `click`).

- [ ] **Step 2: Lock + verify import**

Run: `uv lock && uv sync`
Run: `uv run python -c "import tomlkit; print(tomlkit.__version__)"`
Expected: prints a version ≥ 0.13, exit 0.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build: add tomlkit for Codex MCP config round-trip"
```

---

## Task 2: MCP catalog reader (`mcp_catalog.py`)

**Files:**
- Create: `src/agent_toolkit_cli/mcp_catalog.py`
- Test: `tests/test_mcp_catalog.py`

The catalog convention is `<toolkit-repo>/mcps/<slug>/config.json` (the inner MCP server config — `{type, command, args, ...}`, NO `mcpServers` wrapper) plus a sibling `<slug>.toolkit.yaml` metadata sidecar at `<toolkit-repo>/mcps/<slug>.toolkit.yaml`. The README.md is human prose and is NOT parsed for metadata.

- [ ] **Step 1: Write the failing test**

Create `tests/test_mcp_catalog.py`:

```python
"""Tests for src/agent_toolkit_cli/mcp_catalog.py — catalog discovery + parse."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_toolkit_cli.mcp_catalog import McpAsset, list_catalog, load_mcp_asset


def _write_catalog_entry(
    toolkit: Path, slug: str, *, inner: str, sidecar: str
) -> None:
    mcp_dir = toolkit / "mcps" / slug
    mcp_dir.mkdir(parents=True, exist_ok=True)
    (mcp_dir / "config.json").write_text(inner)
    (mcp_dir / "README.md").write_text(f"# {slug}\n")
    (toolkit / "mcps" / f"{slug}.toolkit.yaml").write_text(sidecar)


def test_load_mcp_asset_reads_inner_and_sidecar(tmp_path):
    _write_catalog_entry(
        tmp_path,
        "context7",
        inner='{"type": "stdio", "command": "npx", "args": ["-y", "ctx7"]}\n',
        sidecar=(
            "name: context7\n"
            "description: Up-to-date docs MCP.\n"
            "transport: stdio\n"
            "install_method: npx\n"
            "env:\n"
            "  - DEFAULT_MINIMUM_TOKENS\n"
        ),
    )
    asset = load_mcp_asset(tmp_path, "context7")
    assert isinstance(asset, McpAsset)
    assert asset.slug == "context7"
    assert asset.inner_config["command"] == "npx"
    assert asset.inner_config["args"] == ["-y", "ctx7"]
    assert asset.transport == "stdio"
    assert asset.install_method == "npx"
    assert asset.env == ["DEFAULT_MINIMUM_TOKENS"]


def test_load_mcp_asset_missing_slug_raises(tmp_path):
    (tmp_path / "mcps").mkdir()
    with pytest.raises(FileNotFoundError):
        load_mcp_asset(tmp_path, "does-not-exist")


def test_list_catalog_returns_slugs_sorted(tmp_path):
    for slug in ("zeta", "alpha"):
        _write_catalog_entry(
            tmp_path, slug,
            inner='{"type":"stdio","command":"npx"}\n',
            sidecar=f"name: {slug}\ndescription: x.\ntransport: stdio\ninstall_method: npx\n",
        )
    assert list_catalog(tmp_path) == ["alpha", "zeta"]


def test_load_mcp_asset_without_sidecar_uses_defaults(tmp_path):
    """A bare config.json with no sidecar is still loadable; metadata is empty,
    transport/install_method fall back to None (doctor surfaces the gap later)."""
    mcp_dir = tmp_path / "mcps" / "orphan"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text('{"type":"stdio","command":"npx"}\n')
    asset = load_mcp_asset(tmp_path, "orphan")
    assert asset.slug == "orphan"
    assert asset.metadata == {}
    assert asset.transport is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_mcp_catalog.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_toolkit_cli.mcp_catalog'`.

- [ ] **Step 3: Implement `mcp_catalog.py`**

Create `src/agent_toolkit_cli/mcp_catalog.py`:

```python
"""Read MCP entries from the toolkit catalog.

Catalog convention: `<toolkit-repo>/mcps/<slug>/config.json` (inner MCP server
config, no mcpServers wrapper) plus a sibling metadata sidecar at
`<toolkit-repo>/mcps/<slug>.toolkit.yaml`. README.md is human prose, not parsed.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class McpAsset:
    slug: str
    inner_config: dict
    metadata: dict = field(default_factory=dict)

    @property
    def transport(self) -> str | None:
        return self.metadata.get("transport")

    @property
    def install_method(self) -> str | None:
        return self.metadata.get("install_method")

    @property
    def env(self) -> list[str]:
        return list(self.metadata.get("env", []))


def _mcps_dir(toolkit_root: Path) -> Path:
    return toolkit_root / "mcps"


def load_mcp_asset(toolkit_root: Path, slug: str) -> McpAsset:
    """Load one MCP asset by slug. Raises FileNotFoundError if config.json absent."""
    config_path = _mcps_dir(toolkit_root) / slug / "config.json"
    if not config_path.is_file():
        raise FileNotFoundError(
            f"MCP '{slug}' not found in catalog: {config_path} does not exist"
        )
    inner = json.loads(config_path.read_text(encoding="utf-8"))
    sidecar_path = _mcps_dir(toolkit_root) / f"{slug}.toolkit.yaml"
    metadata: dict = {}
    if sidecar_path.is_file():
        metadata = yaml.safe_load(sidecar_path.read_text(encoding="utf-8")) or {}
    return McpAsset(slug=slug, inner_config=inner, metadata=metadata)


def list_catalog(toolkit_root: Path) -> list[str]:
    """Return sorted slugs of every MCP directory containing a config.json."""
    mcps = _mcps_dir(toolkit_root)
    if not mcps.is_dir():
        return []
    slugs = [
        d.name
        for d in mcps.iterdir()
        if d.is_dir() and (d / "config.json").is_file()
    ]
    return sorted(slugs)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_mcp_catalog.py -v`
Expected: PASS — all four tests.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/mcp_catalog.py tests/test_mcp_catalog.py
git commit -m "feat(mcp): catalog reader for mcps/<slug>/config.json + sidecar"
```

---

## Task 3: MCP adapter base — Protocol, dispatcher, atomic write, foreign-file guard

**Files:**
- Create: `src/agent_toolkit_cli/mcp_adapters/__init__.py`
- Test: `tests/test_mcp_adapters_json.py` (base-behaviour tests live here; per-family tests added in Tasks 4–5)

This mirrors `agent_adapters/__init__.py`: a `Protocol`, a `get_adapter()` SSOT dispatcher keyed off the harness name, and the shared atomic-write helper. The config-file family differs from the agent kind in that the destination is a *shared* config file we surgically edit, not a file we own outright — so the conflict model is "manage by name" (Rule 2 of the spec): we never refuse to write the file, we only ever touch our named entry.

- [ ] **Step 1: Write the failing test**

Create `tests/test_mcp_adapters_json.py`:

```python
"""Tests for the MCP adapter base + JSON-family adapter."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_toolkit_cli.mcp_adapters import (
    UnsupportedMcpHarnessError,
    atomic_write_text,
    get_adapter,
)


def test_get_adapter_dispatches_known_harnesses():
    for harness in ("claude", "codex", "opencode", "pi"):
        adapter = get_adapter(harness)
        assert adapter.name == harness


def test_get_adapter_unknown_harness_raises():
    with pytest.raises(UnsupportedMcpHarnessError):
        get_adapter("emacs")


def test_atomic_write_text_replaces_in_place(tmp_path):
    target = tmp_path / "config.json"
    target.write_text('{"old": true}')
    atomic_write_text(target, '{"new": true}')
    assert json.loads(target.read_text()) == {"new": True}
    # No temp files left behind
    leftovers = [p for p in tmp_path.iterdir() if p.name != "config.json"]
    assert leftovers == []


def test_atomic_write_text_creates_parent_dirs(tmp_path):
    target = tmp_path / "nested" / "deep" / "config.json"
    atomic_write_text(target, "{}")
    assert target.read_text() == "{}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_mcp_adapters_json.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_toolkit_cli.mcp_adapters'`.

- [ ] **Step 3: Implement the base `__init__.py`**

Create `src/agent_toolkit_cli/mcp_adapters/__init__.py`:

```python
"""Per-harness MCP projection adapters, dispatched by harness name.

MCP is config-injection-shaped: each adapter surgically upserts/removes ONE
named entry inside the harness's native config file, preserving every other
byte (Rule 2 of the design spec: manage by name, never by file ownership).

Two mechanism modules:
  - json_config: claude / pi / opencode — mcpServers.<name> in a JSON document.
  - toml_config: codex — [mcp_servers.<name>] in a TOML document (tomlkit).

get_adapter() is the single SSOT for the harness → mechanism map. No parallel
registry exists. Mirrors agent_adapters/__init__.py.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Literal, Protocol

from agent_toolkit_cli._install_core import InstallError


class UnsupportedMcpHarnessError(InstallError):
    """Harness has no MCP adapter (not one of claude/codex/opencode/pi)."""


# Harness → mechanism module. The single SSOT.
_MECHANISM: dict[str, Literal["json", "toml"]] = {
    "claude": "json",
    "pi": "json",
    "opencode": "json",
    "codex": "toml",
}


def atomic_write_text(target: Path, content: str) -> None:
    """Write `content` to `target` atomically (temp file in same dir → os.replace).

    Same-directory staging guarantees atomicity across filesystems. Creates
    parent directories if absent.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp_name, target)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


class McpAdapter(Protocol):
    """Per-harness install/uninstall contract for the MCP kind."""

    name: str

    def config_target(self, *, scope: str, home: Path, project: Path | None) -> Path:
        """The config file this adapter mutates (round-trip), e.g. ~/.codex/config.toml."""
        ...

    def install(
        self,
        slug: str,
        inner_config: dict,
        *,
        scope: str,
        home: Path,
        project: Path | None = None,
    ) -> Path:
        """Upsert the named MCP entry into the harness config. Returns the path written.

        Idempotent: re-running with the same inner_config produces a byte-identical
        managed entry. Creates the config file with a valid empty shape if absent.
        """
        ...

    def uninstall(
        self,
        slug: str,
        *,
        scope: str,
        home: Path,
        project: Path | None = None,
    ) -> None:
        """Remove the named MCP entry. Idempotent (no-op if absent). Leaves all
        other entries and the surrounding document byte-equal."""
        ...

    def is_installed(
        self,
        slug: str,
        *,
        scope: str,
        home: Path,
        project: Path | None = None,
    ) -> bool:
        """True if the named entry currently exists in the harness config."""
        ...


def get_adapter(harness_name: str) -> McpAdapter:
    """Return the MCP adapter for a harness. SSOT dispatch by mechanism family."""
    mech = _MECHANISM.get(harness_name)
    if mech is None:
        raise UnsupportedMcpHarnessError(
            f"{harness_name}: no MCP adapter — supported harnesses are "
            f"{', '.join(sorted(_MECHANISM))}."
        )
    if mech == "json":
        from agent_toolkit_cli.mcp_adapters import json_config
        return json_config.adapter_for(harness_name)
    if mech == "toml":
        from agent_toolkit_cli.mcp_adapters import toml_config
        return toml_config.adapter_for(harness_name)
    raise RuntimeError(f"unreachable: unknown mechanism {mech!r}")


__all__ = [
    "McpAdapter",
    "UnsupportedMcpHarnessError",
    "atomic_write_text",
    "get_adapter",
]
```

- [ ] **Step 4: Run test to verify it fails differently**

Run: `uv run pytest tests/test_mcp_adapters_json.py -v`
Expected: FAIL — now `ModuleNotFoundError: No module named 'agent_toolkit_cli.mcp_adapters.json_config'` (the dispatcher imports it). Tasks 4 fixes this. The `atomic_write_text` tests should PASS already; the `get_adapter` tests fail on the missing submodule import.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/mcp_adapters/__init__.py tests/test_mcp_adapters_json.py
git commit -m "feat(mcp): adapter base — Protocol, get_adapter SSOT, atomic write"
```

---

## Task 4: JSON-family adapter (Claude / Pi / OpenCode)

**Files:**
- Create: `src/agent_toolkit_cli/mcp_adapters/json_config.py`
- Test: `tests/test_mcp_adapters_json.py` (extend)

Per the spec's strategy table: Claude writes `mcpServers.<name>` to `.mcp.json` (project) / `~/.claude.json` (user); Pi writes to `<project>/.pi/mcp.json` / `~/.config/mcp/mcp.json`; OpenCode writes `mcp.<name>` to `<project>/opencode.json` / `~/.config/opencode/opencode.json` and translates the inner config to OpenCode's native shape. This task implements Claude + Pi (identical `mcpServers` shape); OpenCode's translation is its own per-cell branch.

**Critical (project memory + spec failure-mode notes):** the round-trip read MUST normalise both an **absent file** and a **bare `{}`** (no `mcpServers` key) to `{"mcpServers": {}}` before upsert — never short-circuit on absence (the v2.3.0 audit silent-no-op bug) and never write through an invalid bare `{}`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_mcp_adapters_json.py`:

```python
def _claude_inner():
    return {"type": "stdio", "command": "npx", "args": ["-y", "ctx7"]}


def test_claude_install_creates_file_with_valid_shape_when_absent(tmp_path):
    """Absent .mcp.json must be created as {"mcpServers": {...}}, NOT skipped."""
    adapter = get_adapter("claude")
    project = tmp_path / "proj"
    project.mkdir()
    written = adapter.install(
        "context7", _claude_inner(), scope="project", home=tmp_path, project=project,
    )
    assert written == project / ".mcp.json"
    doc = json.loads(written.read_text())
    assert doc["mcpServers"]["context7"] == _claude_inner()


def test_claude_install_normalises_bare_empty_object(tmp_path):
    """A bare {} (no mcpServers key) is normalised to {"mcpServers": {}} then upserted."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".mcp.json").write_text("{}\n")
    adapter = get_adapter("claude")
    adapter.install("context7", _claude_inner(), scope="project", home=tmp_path, project=project)
    doc = json.loads((project / ".mcp.json").read_text())
    assert doc == {"mcpServers": {"context7": _claude_inner()}}


def test_claude_install_preserves_hand_rolled_entries(tmp_path):
    """Round-trip: a hand-rolled entry is byte-preserved; only our name is added."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"handrolled": {"command": "x"}}}, indent=2) + "\n"
    )
    adapter = get_adapter("claude")
    adapter.install("context7", _claude_inner(), scope="project", home=tmp_path, project=project)
    doc = json.loads((project / ".mcp.json").read_text())
    assert doc["mcpServers"]["handrolled"] == {"command": "x"}
    assert doc["mcpServers"]["context7"] == _claude_inner()


def test_claude_uninstall_removes_only_named_entry(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    adapter = get_adapter("claude")
    adapter.install("context7", _claude_inner(), scope="project", home=tmp_path, project=project)
    # Add a hand-rolled neighbour by hand
    doc = json.loads((project / ".mcp.json").read_text())
    doc["mcpServers"]["keepme"] = {"command": "y"}
    (project / ".mcp.json").write_text(json.dumps(doc, indent=2) + "\n")
    adapter.uninstall("context7", scope="project", home=tmp_path, project=project)
    doc2 = json.loads((project / ".mcp.json").read_text())
    assert "context7" not in doc2["mcpServers"]
    assert doc2["mcpServers"]["keepme"] == {"command": "y"}


def test_claude_uninstall_absent_is_noop(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    get_adapter("claude").uninstall("context7", scope="project", home=tmp_path, project=project)
    # No crash; no file created
    assert not (project / ".mcp.json").exists()


def test_claude_install_is_idempotent(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    adapter = get_adapter("claude")
    adapter.install("context7", _claude_inner(), scope="project", home=tmp_path, project=project)
    first = (project / ".mcp.json").read_text()
    adapter.install("context7", _claude_inner(), scope="project", home=tmp_path, project=project)
    assert (project / ".mcp.json").read_text() == first


def test_claude_user_scope_target_is_home_claude_json(tmp_path):
    adapter = get_adapter("claude")
    target = adapter.config_target(scope="user", home=tmp_path, project=None)
    assert target == tmp_path / ".claude.json"


def test_opencode_install_translates_to_native_shape(tmp_path):
    """OpenCode: command:str+args[] → command:[exe,...args]; env → environment."""
    project = tmp_path / "proj"
    project.mkdir()
    adapter = get_adapter("opencode")
    adapter.install(
        "context7",
        {"type": "stdio", "command": "npx", "args": ["-y", "ctx7"], "env": {"K": "${V}"}},
        scope="project", home=tmp_path, project=project,
    )
    doc = json.loads((project / "opencode.json").read_text())
    entry = doc["mcp"]["context7"]
    assert entry["command"] == ["npx", "-y", "ctx7"]
    assert entry["environment"] == {"K": "{env:V}"}
    assert entry["type"] == "local"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_mcp_adapters_json.py -v`
Expected: FAIL — `json_config` module missing.

- [ ] **Step 3: Implement `json_config.py`**

Create `src/agent_toolkit_cli/mcp_adapters/json_config.py`:

```python
"""JSON-family MCP adapters: claude, pi, opencode.

Each surgically upserts/removes one named entry inside a JSON config document,
preserving every other entry. Per-harness target paths and key translation live
in the per-cell CELLS dict (mechanism = code path; cell = data row).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from agent_toolkit_cli.mcp_adapters import atomic_write_text


@dataclass(frozen=True)
class _Cell:
    name: str
    # (scope) -> path, given home + optional project
    user_target: Callable[[Path], Path]
    project_target: Callable[[Path], Path]
    servers_key: str                       # "mcpServers" (claude/pi) | "mcp" (opencode)
    translate: Callable[[dict], dict]      # inner_config -> harness-native entry


def _passthrough(inner: dict) -> dict:
    """Claude/Pi accept the catalog inner config verbatim."""
    return dict(inner)


def _opencode_translate(inner: dict) -> dict:
    """OpenCode native shape: command joined to a list, env→environment, ${V}→{env:V}."""
    cmd = [inner["command"], *inner.get("args", [])] if "command" in inner else []
    out: dict = {"type": "local", "command": cmd}
    env = inner.get("env")
    if isinstance(env, dict):
        out["environment"] = {
            k: v.replace("${", "{env:").replace("}", "}") if isinstance(v, str) else v
            for k, v in env.items()
        }
    return out


CELLS: dict[str, _Cell] = {
    "claude": _Cell(
        name="claude",
        user_target=lambda home: home / ".claude.json",
        project_target=lambda proj: proj / ".mcp.json",
        servers_key="mcpServers",
        translate=_passthrough,
    ),
    "pi": _Cell(
        name="pi",
        user_target=lambda home: home / ".config" / "mcp" / "mcp.json",
        project_target=lambda proj: proj / ".pi" / "mcp.json",
        servers_key="mcpServers",
        translate=_passthrough,
    ),
    "opencode": _Cell(
        name="opencode",
        user_target=lambda home: home / ".config" / "opencode" / "opencode.json",
        project_target=lambda proj: proj / "opencode.json",
        servers_key="mcp",
        translate=_opencode_translate,
    ),
}


class _JsonAdapter:
    def __init__(self, cell: _Cell) -> None:
        self._cell = cell
        self.name = cell.name

    def config_target(self, *, scope: str, home: Path, project: Path | None) -> Path:
        if scope == "user":
            return self._cell.user_target(home)
        if project is None:
            raise ValueError("project scope requires a project root")
        return self._cell.project_target(project)

    def _read(self, path: Path) -> dict:
        """Round-trip read. Absent file or bare {} → {<servers_key>: {}}."""
        key = self._cell.servers_key
        if not path.is_file():
            return {key: {}}
        doc = json.loads(path.read_text(encoding="utf-8") or "{}")
        if not isinstance(doc, dict):
            raise ValueError(f"{path}: expected a JSON object, got {type(doc).__name__}")
        if key not in doc or not isinstance(doc.get(key), dict):
            doc[key] = {}
        return doc

    def install(self, slug, inner_config, *, scope, home, project=None) -> Path:
        target = self.config_target(scope=scope, home=home, project=project)
        doc = self._read(target)
        doc[self._cell.servers_key][slug] = self._cell.translate(inner_config)
        # Deterministic render: sorted keys at the servers level for stable output.
        doc[self._cell.servers_key] = dict(sorted(doc[self._cell.servers_key].items()))
        atomic_write_text(target, json.dumps(doc, indent=2) + "\n")
        return target

    def uninstall(self, slug, *, scope, home, project=None) -> None:
        target = self.config_target(scope=scope, home=home, project=project)
        if not target.is_file():
            return
        doc = self._read(target)
        servers = doc[self._cell.servers_key]
        if slug in servers:
            del servers[slug]
            atomic_write_text(target, json.dumps(doc, indent=2) + "\n")

    def is_installed(self, slug, *, scope, home, project=None) -> bool:
        target = self.config_target(scope=scope, home=home, project=project)
        if not target.is_file():
            return False
        doc = self._read(target)
        return slug in doc[self._cell.servers_key]


def adapter_for(harness_name: str) -> _JsonAdapter:
    return _JsonAdapter(CELLS[harness_name])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_mcp_adapters_json.py -v`
Expected: PASS — all base + JSON-family tests.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/mcp_adapters/json_config.py tests/test_mcp_adapters_json.py
git commit -m "feat(mcp): JSON-family adapter (claude/pi/opencode) with absent/bare-{} normalisation"
```

---

## Task 5: TOML-family adapter (Codex)

**Files:**
- Create: `src/agent_toolkit_cli/mcp_adapters/toml_config.py`
- Test: `tests/test_mcp_adapters_toml.py`

Codex stores MCP servers as `[mcp_servers.<name>]` tables in `~/.codex/config.toml`. `tomlkit` round-trips the document so unrelated tables and comments survive byte-for-byte. The byte-equality round-trip test (spec acceptance #8) is the gate here.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_mcp_adapters_toml.py`:

```python
"""Tests for the Codex TOML-family MCP adapter."""
from __future__ import annotations

from pathlib import Path

import tomlkit

from agent_toolkit_cli.mcp_adapters import get_adapter

INNER = {"type": "stdio", "command": "npx", "args": ["-y", "ctx7"]}


def test_codex_user_target(tmp_path):
    adapter = get_adapter("codex")
    assert adapter.config_target(scope="user", home=tmp_path, project=None) == (
        tmp_path / ".codex" / "config.toml"
    )


def test_codex_install_adds_mcp_servers_table(tmp_path):
    adapter = get_adapter("codex")
    adapter.install("context7", INNER, scope="user", home=tmp_path)
    doc = tomlkit.parse((tmp_path / ".codex" / "config.toml").read_text())
    assert doc["mcp_servers"]["context7"]["command"] == "npx"
    assert doc["mcp_servers"]["context7"]["args"] == ["-y", "ctx7"]


def test_codex_round_trip_preserves_unrelated_tables_and_comments(tmp_path):
    """Acceptance #8: link an unrelated MCP, unlink it → byte-equal to source."""
    cfg = tmp_path / ".codex" / "config.toml"
    cfg.parent.mkdir(parents=True)
    source = (
        "# my codex config\n"
        "model = \"gpt-5\"\n\n"
        "[tui]\n"
        "theme = \"dark\"  # keep me\n\n"
        "[mcp_servers.handrolled]\n"
        "command = \"x\"\n"
    )
    cfg.write_text(source)
    adapter = get_adapter("codex")
    adapter.install("context7", INNER, scope="user", home=tmp_path)
    adapter.uninstall("context7", scope="user", home=tmp_path)
    assert cfg.read_text() == source


def test_codex_uninstall_removes_only_named_table(tmp_path):
    adapter = get_adapter("codex")
    adapter.install("context7", INNER, scope="user", home=tmp_path)
    adapter.install("other", {"command": "y"}, scope="user", home=tmp_path)
    adapter.uninstall("context7", scope="user", home=tmp_path)
    doc = tomlkit.parse((tmp_path / ".codex" / "config.toml").read_text())
    assert "context7" not in doc["mcp_servers"]
    assert doc["mcp_servers"]["other"]["command"] == "y"


def test_codex_install_idempotent(tmp_path):
    adapter = get_adapter("codex")
    adapter.install("context7", INNER, scope="user", home=tmp_path)
    first = (tmp_path / ".codex" / "config.toml").read_text()
    adapter.install("context7", INNER, scope="user", home=tmp_path)
    assert (tmp_path / ".codex" / "config.toml").read_text() == first
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_mcp_adapters_toml.py -v`
Expected: FAIL — `toml_config` module missing.

- [ ] **Step 3: Implement `toml_config.py`**

Create `src/agent_toolkit_cli/mcp_adapters/toml_config.py`:

```python
"""Codex TOML-family MCP adapter.

Manages [mcp_servers.<name>] tables in ~/.codex/config.toml (user) /
<project>/.codex/config.toml (project) via tomlkit, preserving all other
tables and comments byte-for-byte.
"""
from __future__ import annotations

from pathlib import Path

import tomlkit
from tomlkit import TOMLDocument

from agent_toolkit_cli.mcp_adapters import atomic_write_text


class _CodexAdapter:
    name = "codex"

    def config_target(self, *, scope: str, home: Path, project: Path | None = None) -> Path:
        if scope == "user":
            return home / ".codex" / "config.toml"
        if project is None:
            raise ValueError("project scope requires a project root")
        return project / ".codex" / "config.toml"

    def _read(self, path: Path) -> TOMLDocument:
        if not path.is_file():
            return tomlkit.document()
        return tomlkit.parse(path.read_text(encoding="utf-8"))

    def _translate(self, inner: dict) -> dict:
        """Codex mcp_servers entry: command + args + env (+ optional url/transport).
        The catalog inner shape already matches Codex closely; pass through the
        recognised keys, dropping the catalog-only 'type' marker."""
        out: dict = {}
        if "command" in inner:
            out["command"] = inner["command"]
        if "args" in inner:
            out["args"] = list(inner["args"])
        if "env" in inner and isinstance(inner["env"], dict):
            out["env"] = dict(inner["env"])
        if "url" in inner:
            out["url"] = inner["url"]
        return out

    def install(self, slug, inner_config, *, scope, home, project=None) -> Path:
        target = self.config_target(scope=scope, home=home, project=project)
        doc = self._read(target)
        if "mcp_servers" not in doc:
            doc["mcp_servers"] = tomlkit.table(is_super_table=True)
        entry = tomlkit.table()
        for k, v in self._translate(inner_config).items():
            entry[k] = v
        doc["mcp_servers"][slug] = entry
        atomic_write_text(target, tomlkit.dumps(doc))
        return target

    def uninstall(self, slug, *, scope, home, project=None) -> None:
        target = self.config_target(scope=scope, home=home, project=project)
        if not target.is_file():
            return
        doc = self._read(target)
        servers = doc.get("mcp_servers")
        if servers is not None and slug in servers:
            del servers[slug]
            if len(servers) == 0:
                del doc["mcp_servers"]
            atomic_write_text(target, tomlkit.dumps(doc))

    def is_installed(self, slug, *, scope, home, project=None) -> bool:
        target = self.config_target(scope=scope, home=home, project=project)
        if not target.is_file():
            return False
        servers = self._read(target).get("mcp_servers")
        return servers is not None and slug in servers


def adapter_for(harness_name: str) -> _CodexAdapter:
    assert harness_name == "codex"
    return _CodexAdapter()
```

> **Implementation note for the engineer:** if `test_codex_round_trip_preserves_unrelated_tables_and_comments` fails on byte-equality because deleting the last `[mcp_servers.context7]` table leaves a stray blank line or the `[mcp_servers]` super-table header behind, adjust `uninstall` to also prune the now-empty super-table (the code above does `del doc["mcp_servers"]` when empty). If a trailing-newline mismatch remains, normalise by comparing `tomlkit.dumps(tomlkit.parse(source))` to the source in the test setup, or trim the test's source to tomlkit's canonical form — do NOT special-case whitespace in production code.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_mcp_adapters_toml.py -v`
Expected: PASS. If the round-trip byte-equality test fails, apply the implementation note above before moving on.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/mcp_adapters/toml_config.py tests/test_mcp_adapters_toml.py
git commit -m "feat(mcp): Codex TOML adapter with byte-preserving round-trip"
```

---

## Task 6: MCP paths + lock (`mcp_paths.py`, `mcp_lock.py`)

**Files:**
- Create: `src/agent_toolkit_cli/mcp_paths.py`
- Create: `src/agent_toolkit_cli/mcp_lock.py`
- Test: `tests/test_mcp_lock.py`

The lock records which (scope, harness, slug) projections this tool created, so `uninstall`/`remove`/`status` know what is tool-owned vs hand-rolled. Mirror `agent_lock.py`: a per-kind lock filename (`mcp-lock.json`) and an `mcpPath`-style record. Because MCP writes into shared config files rather than a single owned path, the lock records the **set of (harness, scope, slug)** managed entries plus the catalog source ref.

- [ ] **Step 1: Read the sibling first**

Read `src/agent_toolkit_cli/agent_lock.py` and `src/agent_toolkit_cli/agent_paths.py` in full. The MCP versions mirror them; deviate only where the config-injection model requires (no single `path` per slug — instead a list of harness projections).

- [ ] **Step 2: Write the failing test**

Create `tests/test_mcp_lock.py`:

```python
"""Tests for mcp_lock.py — the mcp-lock.json reader/writer."""
from __future__ import annotations

from pathlib import Path

from agent_toolkit_cli.mcp_lock import (
    McpLockEntry,
    lock_path_for_scope,
    read_lock,
    upsert_entry,
    remove_entry,
    write_lock,
)


def test_lock_path_user_scope(tmp_path):
    assert lock_path_for_scope("user", home=tmp_path, project=None) == (
        tmp_path / ".agent-toolkit" / "mcp-lock.json"
    )


def test_lock_path_project_scope(tmp_path):
    assert lock_path_for_scope("project", home=tmp_path, project=tmp_path / "p") == (
        tmp_path / "p" / "mcp-lock.json"
    )


def test_round_trip_empty(tmp_path):
    p = tmp_path / "mcp-lock.json"
    write_lock(p, {})
    assert read_lock(p) == {}


def test_upsert_and_remove(tmp_path):
    p = tmp_path / "mcp-lock.json"
    lock = read_lock(p)
    lock = upsert_entry(lock, McpLockEntry(slug="context7", harness="claude", source="ajanderson1/agent-toolkit"))
    write_lock(p, lock)
    reloaded = read_lock(p)
    assert "context7" in reloaded
    assert reloaded["context7"][0].harness == "claude"
    reloaded = remove_entry(reloaded, slug="context7", harness="claude")
    assert "context7" not in reloaded


def test_upsert_two_harnesses_same_slug(tmp_path):
    lock = upsert_entry({}, McpLockEntry(slug="context7", harness="claude", source="s"))
    lock = upsert_entry(lock, McpLockEntry(slug="context7", harness="codex", source="s"))
    harnesses = sorted(e.harness for e in lock["context7"])
    assert harnesses == ["claude", "codex"]
    # Removing one leaves the other
    lock = remove_entry(lock, slug="context7", harness="claude")
    assert [e.harness for e in lock["context7"]] == ["codex"]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_mcp_lock.py -v`
Expected: FAIL — module missing.

- [ ] **Step 4: Implement `mcp_lock.py`**

Create `src/agent_toolkit_cli/mcp_lock.py`:

```python
"""mcp-lock.json — records tool-owned MCP projections per (slug, harness).

User scope: ~/.agent-toolkit/mcp-lock.json. Project scope: <project>/mcp-lock.json.
Each slug maps to a list of McpLockEntry (one per harness it is installed into).
Mirrors agent_lock.py's filename-per-kind convention.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

LOCK_FILENAME = "mcp-lock.json"


@dataclass(frozen=True)
class McpLockEntry:
    slug: str
    harness: str
    source: str          # catalog source ref, e.g. "ajanderson1/agent-toolkit"


def lock_path_for_scope(scope: str, *, home: Path, project: Path | None) -> Path:
    if scope == "user":
        return home / ".agent-toolkit" / LOCK_FILENAME
    if project is None:
        raise ValueError("project scope requires a project root")
    return project / LOCK_FILENAME


def read_lock(path: Path) -> dict[str, list[McpLockEntry]]:
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8") or "{}")
    out: dict[str, list[McpLockEntry]] = {}
    for slug, entries in raw.get("mcps", {}).items():
        out[slug] = [McpLockEntry(slug=slug, **e) for e in entries]
    return out


def write_lock(path: Path, lock: dict[str, list[McpLockEntry]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialisable = {
        "mcps": {
            slug: [
                {"harness": e.harness, "source": e.source}
                for e in sorted(entries, key=lambda x: x.harness)
            ]
            for slug, entries in sorted(lock.items())
        }
    }
    path.write_text(json.dumps(serialisable, indent=2) + "\n", encoding="utf-8")


def upsert_entry(lock: dict[str, list[McpLockEntry]], entry: McpLockEntry) -> dict[str, list[McpLockEntry]]:
    out = {k: list(v) for k, v in lock.items()}
    existing = [e for e in out.get(entry.slug, []) if e.harness != entry.harness]
    existing.append(entry)
    out[entry.slug] = existing
    return out


def remove_entry(lock: dict[str, list[McpLockEntry]], *, slug: str, harness: str) -> dict[str, list[McpLockEntry]]:
    out = {k: list(v) for k, v in lock.items()}
    if slug in out:
        out[slug] = [e for e in out[slug] if e.harness != harness]
        if not out[slug]:
            del out[slug]
    return out
```

- [ ] **Step 5: Implement `mcp_paths.py`**

Create `src/agent_toolkit_cli/mcp_paths.py` by mirroring `agent_paths.py`'s scope/root resolution. Read `agent_paths.py` and reproduce its `scope_and_roots(...)` signature and `read_only` semantics for the MCP kind (the catalog root comes from the toolkit-repo resolution shared helper `_repo_resolution.py` — reuse it, do not re-implement). Keep this file thin: it resolves `(scope, home, project, toolkit_root)` for the verbs.

```python
"""Scope + root resolution for the MCP kind. Mirrors agent_paths.py."""
from __future__ import annotations

from pathlib import Path

from agent_toolkit_cli.agent_paths import scope_and_roots as _agent_scope_and_roots

# MCP scope resolution is identical to the agent kind's: read verbs default to
# global outside a project; write verbs default to project when a project lock
# is present. Delegate to the shared resolver rather than fork the logic.
scope_and_roots = _agent_scope_and_roots
```

> **Implementation note:** if `agent_paths.scope_and_roots` hard-codes the agent lock filename for its "project lock present?" probe, it cannot be reused verbatim — in that case copy the function into `mcp_paths.py` and swap the probe to `mcp_lock.LOCK_FILENAME`. Verify by reading `agent_paths.py` in Step 1. Prefer delegation; fork only if the probe is kind-specific.

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_mcp_lock.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/agent_toolkit_cli/mcp_lock.py src/agent_toolkit_cli/mcp_paths.py tests/test_mcp_lock.py
git commit -m "feat(mcp): mcp-lock.json reader/writer + paths resolution"
```

---

## Task 7: Install facade (`mcp_install.py`) — apply / uninstall / remove with rollback

**Files:**
- Create: `src/agent_toolkit_cli/mcp_install.py`
- Test: `tests/test_mcp_install.py`

The facade is the heart of the kind: it loads the catalog asset, dispatches to every requested harness adapter, writes the lock, and on a per-harness failure **rolls back the projections it already made this call** (mirror `agent_install.py`'s rollback contract — project memory: TUI/CLI apply must roll back prior on conflict). It enforces the contract split: `uninstall` removes harness projections only (lock entry dropped, catalog untouched); `remove` is `uninstall` + dropping nothing extra in foundations (no canonical store for MCPs — the catalog is the source — so `remove` == `uninstall` of ALL harnesses for that slug + ensure no lock entry remains; document this so the destructive/non-destructive contract is explicit even though they converge for a catalog-sourced kind).

- [ ] **Step 1: Read the sibling first**

Read `src/agent_toolkit_cli/agent_install.py` in full, focusing on `apply()`'s rollback path. Reproduce the structure.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_mcp_install.py`:

```python
"""Tests for the MCP install facade — apply/uninstall/remove + rollback."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_toolkit_cli import mcp_install
from agent_toolkit_cli.mcp_lock import lock_path_for_scope, read_lock


def _seed_catalog(toolkit: Path, slug="context7"):
    d = toolkit / "mcps" / slug
    d.mkdir(parents=True)
    (d / "config.json").write_text('{"type":"stdio","command":"npx","args":["-y","ctx7"]}\n')
    (d / "README.md").write_text(f"# {slug}\n")
    (toolkit / "mcps" / f"{slug}.toolkit.yaml").write_text(
        f"name: {slug}\ndescription: x.\ntransport: stdio\ninstall_method: npx\n"
    )


def test_apply_installs_and_writes_lock_project(tmp_path):
    toolkit = tmp_path / "toolkit"
    _seed_catalog(toolkit)
    project = tmp_path / "proj"
    project.mkdir()
    mcp_install.apply(
        slug="context7", harnesses=["claude"], scope="project",
        toolkit_root=toolkit, home=tmp_path, project=project,
    )
    doc = json.loads((project / ".mcp.json").read_text())
    assert "context7" in doc["mcpServers"]
    lock = read_lock(lock_path_for_scope("project", home=tmp_path, project=project))
    assert lock["context7"][0].harness == "claude"


def test_apply_installs_two_harnesses(tmp_path):
    toolkit = tmp_path / "toolkit"
    _seed_catalog(toolkit)
    project = tmp_path / "proj"
    project.mkdir()
    mcp_install.apply(
        slug="context7", harnesses=["claude", "codex"], scope="project",
        toolkit_root=toolkit, home=tmp_path, project=project,
    )
    assert "context7" in json.loads((project / ".mcp.json").read_text())["mcpServers"]
    assert (project / ".codex" / "config.toml").is_file()
    lock = read_lock(lock_path_for_scope("project", home=tmp_path, project=project))
    assert sorted(e.harness for e in lock["context7"]) == ["claude", "codex"]


def test_uninstall_removes_projection_keeps_catalog(tmp_path):
    toolkit = tmp_path / "toolkit"
    _seed_catalog(toolkit)
    project = tmp_path / "proj"
    project.mkdir()
    mcp_install.apply(
        slug="context7", harnesses=["claude"], scope="project",
        toolkit_root=toolkit, home=tmp_path, project=project,
    )
    mcp_install.uninstall(
        slug="context7", harnesses=["claude"], scope="project",
        toolkit_root=toolkit, home=tmp_path, project=project,
    )
    doc = json.loads((project / ".mcp.json").read_text())
    assert "context7" not in doc["mcpServers"]
    # Catalog still intact (non-destructive contract)
    assert (toolkit / "mcps" / "context7" / "config.json").is_file()
    # Lock entry gone
    lock = read_lock(lock_path_for_scope("project", home=tmp_path, project=project))
    assert "context7" not in lock


def test_apply_rolls_back_prior_projection_on_later_failure(tmp_path, monkeypatch):
    """If the 2nd harness adapter raises, the 1st harness's projection is rolled back."""
    toolkit = tmp_path / "toolkit"
    _seed_catalog(toolkit)
    project = tmp_path / "proj"
    project.mkdir()

    from agent_toolkit_cli import mcp_adapters
    real_get = mcp_adapters.get_adapter

    def boom_get(name):
        adapter = real_get(name)
        if name == "codex":
            def explode(*a, **k):
                raise RuntimeError("simulated codex failure")
            adapter.install = explode  # type: ignore[attr-defined]
        return adapter

    monkeypatch.setattr(mcp_install, "get_adapter", boom_get, raising=False)
    # If facade imports get_adapter by name, patch there; else patch the module attr it uses.

    with pytest.raises(RuntimeError):
        mcp_install.apply(
            slug="context7", harnesses=["claude", "codex"], scope="project",
            toolkit_root=toolkit, home=tmp_path, project=project,
        )
    # Claude projection rolled back
    mcp_path = project / ".mcp.json"
    if mcp_path.is_file():
        assert "context7" not in json.loads(mcp_path.read_text()).get("mcpServers", {})
    # Lock not left with a partial entry
    lock = read_lock(lock_path_for_scope("project", home=tmp_path, project=project))
    assert "context7" not in lock
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_mcp_install.py -v`
Expected: FAIL — module missing.

- [ ] **Step 4: Implement `mcp_install.py`**

Create `src/agent_toolkit_cli/mcp_install.py`:

```python
"""MCP install facade: apply / uninstall / remove across harness adapters.

apply() installs one catalog MCP into N harnesses, writes the lock, and rolls
back projections made THIS CALL if a later adapter fails (mirrors
agent_install.apply()'s rollback contract). uninstall() removes harness
projections (non-destructive: catalog + other-scope locks untouched). remove()
is the destructive verb; for a catalog-sourced kind it equals uninstalling the
slug from every harness recorded in the lock.
"""
from __future__ import annotations

import sys
from pathlib import Path

from agent_toolkit_cli.mcp_adapters import get_adapter
from agent_toolkit_cli.mcp_catalog import load_mcp_asset
from agent_toolkit_cli.mcp_lock import (
    McpLockEntry,
    lock_path_for_scope,
    read_lock,
    remove_entry,
    upsert_entry,
    write_lock,
)

_SOURCE_REF = "ajanderson1/agent-toolkit"  # catalog provenance; refine if multi-source


def _loud(msg: str) -> None:
    print(msg, file=sys.stdout)


def apply(
    *,
    slug: str,
    harnesses: list[str],
    scope: str,
    toolkit_root: Path,
    home: Path,
    project: Path | None = None,
) -> None:
    """Install `slug` into each harness. Atomic across harnesses: roll back on failure."""
    asset = load_mcp_asset(toolkit_root, slug)
    lock_path = lock_path_for_scope(scope, home=home, project=project)
    lock = read_lock(lock_path)

    done: list[str] = []
    try:
        for harness in harnesses:
            adapter = get_adapter(harness)
            target = adapter.config_target(scope=scope, home=home, project=project)
            _loud(f"→ writing {target}")
            adapter.install(slug, asset.inner_config, scope=scope, home=home, project=project)
            _loud(f"✓ wrote {target}")
            lock = upsert_entry(lock, McpLockEntry(slug=slug, harness=harness, source=_SOURCE_REF))
            done.append(harness)
        write_lock(lock_path, lock)
    except BaseException:
        # Roll back every projection made this call; do not write a partial lock.
        for harness in done:
            try:
                get_adapter(harness).uninstall(slug, scope=scope, home=home, project=project)
                _loud(f"↩ rolled back {harness}:{slug}")
            except Exception:  # rollback must not mask the original error
                pass
        raise


def uninstall(
    *,
    slug: str,
    harnesses: list[str],
    scope: str,
    toolkit_root: Path,
    home: Path,
    project: Path | None = None,
) -> None:
    """Remove `slug`'s projection from each named harness. Non-destructive:
    the catalog and any other-scope lock are untouched."""
    lock_path = lock_path_for_scope(scope, home=home, project=project)
    lock = read_lock(lock_path)
    for harness in harnesses:
        adapter = get_adapter(harness)
        target = adapter.config_target(scope=scope, home=home, project=project)
        _loud(f"→ removing {slug} from {target}")
        adapter.uninstall(slug, scope=scope, home=home, project=project)
        lock = remove_entry(lock, slug=slug, harness=harness)
    write_lock(lock_path, lock)


def remove(
    *,
    slug: str,
    scope: str,
    toolkit_root: Path,
    home: Path,
    project: Path | None = None,
) -> None:
    """Destructive verb: uninstall `slug` from EVERY harness recorded in the lock.

    For a catalog-sourced kind there is no owned canonical store to delete (the
    catalog is the source of truth), so remove == full-fan-out uninstall. Kept as
    a distinct verb to preserve the kind-wide non-destructive(uninstall) /
    destructive(remove) contract.
    """
    lock_path = lock_path_for_scope(scope, home=home, project=project)
    lock = read_lock(lock_path)
    harnesses = [e.harness for e in lock.get(slug, [])]
    if not harnesses:
        _loud(f"{slug}: nothing to remove (no lock entry at {scope} scope)")
        return
    uninstall(
        slug=slug, harnesses=harnesses, scope=scope,
        toolkit_root=toolkit_root, home=home, project=project,
    )
```

> **Implementation note on the rollback test:** the test patches `mcp_install.get_adapter`. The facade above imports `get_adapter` into its own namespace (`from ... import get_adapter`), so `monkeypatch.setattr(mcp_install, "get_adapter", ...)` patches the right reference. Keep the import style as written so the test's patch target is correct.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_mcp_install.py -v`
Expected: PASS — including the rollback test.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/mcp_install.py tests/test_mcp_install.py
git commit -m "feat(mcp): install facade with cross-harness rollback + uninstall/remove split"
```

---

## Task 8: CLI command group (`commands/mcp/`)

**Files:**
- Create: `src/agent_toolkit_cli/commands/mcp/__init__.py`
- Create: `src/agent_toolkit_cli/commands/mcp/_common.py`
- Create: `src/agent_toolkit_cli/commands/mcp/{add,install,uninstall,remove,list,status,doctor}_cmd.py`
- Modify: `src/agent_toolkit_cli/cli.py`
- Test: `tests/test_cli_mcp.py` (smoke-level here; the round-trip + both-scope guard is Task 9)

Mirror `commands/agent/` exactly: a Click group, read verbs (`list`, `status`, `doctor`) pass `read_only=True`; write verbs (`install`, `uninstall`, `remove`) default to project when a project lock is present; `add` scaffolds a catalog entry (global-only, no `-p`).

- [ ] **Step 1: Read the sibling first**

Read `src/agent_toolkit_cli/commands/agent/__init__.py`, `install_cmd.py`, `uninstall_cmd.py`, `list_cmd.py`, `status_cmd.py`, `doctor_cmd.py`, and `_common.py`. Reproduce their flag surface and scope-resolution calls.

- [ ] **Step 2: Implement the group + verbs**

Create `src/agent_toolkit_cli/commands/mcp/__init__.py`:

```python
"""`agent-toolkit-cli mcp <verb>` — manage MCP servers across four harnesses
via config-injection adapters + mcp-lock.json. Mirrors commands/agent/.

Read verbs (list/status/doctor) pass read_only=True → default to global outside
a project. Write verbs (install/uninstall/remove) default to project when a
project lock is present. `add` scaffolds a catalog entry (global-only).
Supported harnesses: claude, codex, opencode, pi.
"""
from __future__ import annotations

import click

from agent_toolkit_cli.commands.mcp.add_cmd import add_cmd
from agent_toolkit_cli.commands.mcp.doctor_cmd import doctor_cmd
from agent_toolkit_cli.commands.mcp.install_cmd import install_cmd
from agent_toolkit_cli.commands.mcp.list_cmd import list_cmd
from agent_toolkit_cli.commands.mcp.remove_cmd import remove_cmd
from agent_toolkit_cli.commands.mcp.status_cmd import status_cmd
from agent_toolkit_cli.commands.mcp.uninstall_cmd import uninstall_cmd


@click.group(name="mcp")
def mcp() -> None:
    """Manage MCP servers via config-injection adapters + mcp-lock.json."""


mcp.add_command(list_cmd)
mcp.add_command(list_cmd, name="ls")
mcp.add_command(status_cmd)
mcp.add_command(add_cmd)
mcp.add_command(install_cmd)
mcp.add_command(uninstall_cmd)
mcp.add_command(remove_cmd)
mcp.add_command(doctor_cmd)
```

Create `src/agent_toolkit_cli/commands/mcp/install_cmd.py` (the canonical write verb; the others follow the same shape — read the agent siblings for `_common` helpers and reproduce):

```python
"""`agent-toolkit-cli mcp install <slug> [--harness ...] [-g|-p]`."""
from __future__ import annotations

import click

from agent_toolkit_cli import mcp_install
from agent_toolkit_cli.mcp_paths import scope_and_roots

_HARNESSES = ("claude", "codex", "opencode", "pi")


@click.command(name="install")
@click.argument("slug")
@click.option("--harness", "harnesses", multiple=True, type=click.Choice(_HARNESSES),
              help="Harness(es) to install into. Repeatable. Default: all four.")
@click.option("-g", "--global", "global_", is_flag=True, help="User scope.")
@click.option("-p", "--project", "project_", is_flag=True, help="Project scope.")
def install_cmd(slug: str, harnesses: tuple[str, ...], global_: bool, project_: bool) -> None:
    """Install a catalog MCP into one or more harnesses."""
    scope, home, project, toolkit_root = scope_and_roots(
        global_=global_, project_=project_, read_only=False,
    )
    targets = list(harnesses) or list(_HARNESSES)
    mcp_install.apply(
        slug=slug, harnesses=targets, scope=scope,
        toolkit_root=toolkit_root, home=home, project=project,
    )
    click.echo(f"✓ installed {slug} → {', '.join(targets)} ({scope} scope)")
```

Create the remaining verb files mirroring the agent siblings:
- `uninstall_cmd.py` — same flags as install; calls `mcp_install.uninstall`. Default harnesses = those in the lock for `slug` (read the lock; if none specified and none in lock, error "not installed").
- `remove_cmd.py` — `slug` arg + scope flags; calls `mcp_install.remove`.
- `list_cmd.py` — `read_only=True`; prints catalog slugs and, per slug, which harnesses are installed at the resolved scope (via `get_adapter(h).is_installed`).
- `status_cmd.py` — `read_only=True`; prints the lock contents for the resolved scope.
- `add_cmd.py` — global-only scaffold: writes `mcps/<slug>/config.json` + `mcps/<slug>.toolkit.yaml` skeleton into the toolkit repo (mirror `commands/agent/add_cmd.py`'s shape; keep minimal).
- `doctor_cmd.py` — `read_only=True`; for each lock entry, check `is_installed` matches the lock (report orphan lock entries / missing projections), and warn on declared `env:` vars absent from the environment. NEVER writes (foundations `doctor` is read-only; `fix` is deferred).

Create `src/agent_toolkit_cli/commands/mcp/_common.py` mirroring `commands/agent/_common.py` (shared `--harness` choice tuple, scope-flag decorators) to keep the verb files DRY.

- [ ] **Step 3: Register the group in `cli.py`**

In `src/agent_toolkit_cli/cli.py`, add the import alongside the others:

```python
from agent_toolkit_cli.commands.mcp import mcp
```

and register it next to the other kinds:

```python
main.add_command(mcp)
main.add_command(mcp, name="mcps")
```

- [ ] **Step 4: Write a CLI smoke test**

Create `tests/test_cli_mcp.py`:

```python
"""CLI smoke tests for the mcp command group."""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def _seed(toolkit: Path, slug="context7"):
    d = toolkit / "mcps" / slug
    d.mkdir(parents=True)
    (d / "config.json").write_text('{"type":"stdio","command":"npx","args":["-y","ctx7"]}\n')
    (d / "README.md").write_text(f"# {slug}\n")
    (toolkit / "mcps" / f"{slug}.toolkit.yaml").write_text(
        f"name: {slug}\ndescription: x.\ntransport: stdio\ninstall_method: npx\n"
    )


def test_mcp_group_registered():
    result = CliRunner().invoke(main, ["mcp", "--help"])
    assert result.exit_code == 0
    assert "install" in result.output
    assert "uninstall" in result.output


def test_mcp_install_project_claude(tmp_path, monkeypatch):
    toolkit = tmp_path / "toolkit"
    _seed(toolkit)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("AGENT_TOOLKIT_REPO", str(toolkit))
    monkeypatch.chdir(project)
    result = CliRunner().invoke(
        main, ["mcp", "install", "context7", "--harness", "claude", "-p"],
    )
    assert result.exit_code == 0, result.output
    doc = json.loads((project / ".mcp.json").read_text())
    assert "context7" in doc["mcpServers"]
```

> **Note:** the exact env-var / flag names for toolkit-repo resolution (`AGENT_TOOLKIT_REPO` vs `--toolkit-repo`) must match what `_repo_resolution.py` / `agent_paths.scope_and_roots` actually read — confirm against the agent CLI tests in Step 1 and adjust the test + `scope_and_roots` call accordingly.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli_mcp.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/commands/mcp src/agent_toolkit_cli/cli.py tests/test_cli_mcp.py
git commit -m "feat(mcp): CLI command group (install/uninstall/remove/list/status/add/doctor)"
```

---

## Task 9: Round-trip + both-scope CLI guard tests (the project-memory mandate)

**Files:**
- Test: `tests/test_cli_mcp.py` (extend)

Project memory: v3 install machinery has **repeatedly shipped silently-broken global-scope / orphan paths with green CI** because tests only covered one scope or only the happy install (never the uninstall round-trip). This task makes that impossible to repeat for MCP. These tests are the gate; they must be RED before the facade is trusted and GREEN after.

- [ ] **Step 1: Write the round-trip + both-scope tests**

Append to `tests/test_cli_mcp.py`:

```python
import pytest


@pytest.mark.parametrize("scope_flag, scope_name", [("-g", "user"), ("-p", "project")])
def test_install_uninstall_round_trip_both_scopes(tmp_path, monkeypatch, scope_flag, scope_name):
    """install → uninstall leaves the harness config with NO managed entry, at BOTH scopes."""
    toolkit = tmp_path / "toolkit"
    _seed(toolkit)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("AGENT_TOOLKIT_REPO", str(toolkit))
    monkeypatch.chdir(project)
    runner = CliRunner()

    r1 = runner.invoke(main, ["mcp", "install", "context7", "--harness", "claude", scope_flag])
    assert r1.exit_code == 0, r1.output

    # Determine the target file for this scope
    target = (tmp_path / ".claude.json") if scope_name == "user" else (project / ".mcp.json")
    assert "context7" in json.loads(target.read_text())["mcpServers"]

    r2 = runner.invoke(main, ["mcp", "uninstall", "context7", "--harness", "claude", scope_flag])
    assert r2.exit_code == 0, r2.output
    assert "context7" not in json.loads(target.read_text())["mcpServers"]


@pytest.mark.parametrize("scope_flag, scope_name", [("-g", "user"), ("-p", "project")])
def test_install_all_four_harnesses_round_trip(tmp_path, monkeypatch, scope_flag, scope_name):
    """All four adapters install AND fully uninstall at both scopes (no orphan projections)."""
    toolkit = tmp_path / "toolkit"
    _seed(toolkit)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("AGENT_TOOLKIT_REPO", str(toolkit))
    monkeypatch.chdir(project)
    runner = CliRunner()

    r1 = runner.invoke(main, ["mcp", "install", "context7", scope_flag])  # default = all four
    assert r1.exit_code == 0, r1.output

    r2 = runner.invoke(main, ["mcp", "uninstall", "context7", scope_flag])
    assert r2.exit_code == 0, r2.output

    # No harness config should still hold the managed entry.
    from agent_toolkit_cli.mcp_adapters import get_adapter
    home = tmp_path
    proj = None if scope_name == "user" else project
    for h in ("claude", "codex", "opencode", "pi"):
        assert not get_adapter(h).is_installed(
            "context7", scope=scope_name, home=home, project=proj,
        ), f"{h} left an orphan projection at {scope_name} scope"

    # Lock has no residual entry
    from agent_toolkit_cli.mcp_lock import lock_path_for_scope, read_lock
    lock = read_lock(lock_path_for_scope(scope_name, home=home, project=proj))
    assert "context7" not in lock


@pytest.mark.parametrize("scope_flag, scope_name", [("-g", "user"), ("-p", "project")])
def test_uninstall_preserves_hand_rolled_neighbour(tmp_path, monkeypatch, scope_flag, scope_name):
    """A hand-rolled MCP in the same file survives our install+uninstall byte-for-byte."""
    toolkit = tmp_path / "toolkit"
    _seed(toolkit)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("AGENT_TOOLKIT_REPO", str(toolkit))
    monkeypatch.chdir(project)

    target = (tmp_path / ".claude.json") if scope_name == "user" else (project / ".mcp.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"mcpServers": {"handrolled": {"command": "x"}}}, indent=2) + "\n")

    runner = CliRunner()
    runner.invoke(main, ["mcp", "install", "context7", "--harness", "claude", scope_flag])
    runner.invoke(main, ["mcp", "uninstall", "context7", "--harness", "claude", scope_flag])

    doc = json.loads(target.read_text())
    assert doc["mcpServers"]["handrolled"] == {"command": "x"}
    assert "context7" not in doc["mcpServers"]
```

- [ ] **Step 2: Run the guard suite**

Run: `uv run pytest tests/test_cli_mcp.py -v`
Expected: PASS — all parametrised both-scope round-trips. If any FAIL at `-g`/user scope, that is exactly the class of bug this task exists to catch — fix the facade/adapter, do not weaken the test.

- [ ] **Step 3: Commit**

```bash
git add tests/test_cli_mcp.py
git commit -m "test(mcp): both-scope install→uninstall round-trip guard (orphan/global regression)"
```

---

## Task 10: Full suite + real-catalog smoke

**Files:** none (verification task)

- [ ] **Step 1: Run the full unit suite**

Run: `uv run pytest -q`
Expected: PASS, no regressions in existing kinds.

- [ ] **Step 2: Run any bats CLI tests if present**

Run: `[ -d tests/bats ] && bats tests/bats || echo "no bats suite"`
Expected: PASS or "no bats suite".

- [ ] **Step 3: Smoke against the real catalog**

```bash
uv run agent-toolkit mcp list -g
uv run agent-toolkit mcp install context7 --harness claude -p
cat ./.mcp.json
uv run agent-toolkit mcp uninstall context7 --harness claude -p
cat ./.mcp.json
```

Expected: `list` shows real catalog slugs (context7, playwright, …); install adds `mcpServers.context7` to `./.mcp.json` with loud `→ writing` / `✓ wrote` lines; uninstall removes it leaving `{"mcpServers": {}}`. **Important:** this writes into the agent-toolkit-cli repo's own `.mcp.json` (gitignored) — verify it does not get committed.

- [ ] **Step 4: Commit (if any fixes were needed)**

```bash
git add -A && git commit -m "fix(mcp): address full-suite + real-catalog smoke findings"
```

(Skip if nothing changed.)

---

## Task 11: Packaged-resource (wheel) guard

**Files:**
- Test: `tests/test_mcp_wheel.py`

Project memory (#305): a kind once read repo files via `parents[N]` and crashed on every wheel install while CI stayed green (it only ran from the source tree). MCP resolves its catalog via the toolkit-repo flag, not relative-to-`__file__`, so it should be immune — this test PROVES it by running the built wheel from outside the repo.

- [ ] **Step 1: Write the wheel test**

Create `tests/test_mcp_wheel.py`:

```python
"""Guard: the mcp command group works from a built wheel, run outside the repo.

Mirrors the #305 packaged-resource regression guard. Skipped if uv is absent.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv not available")
def test_mcp_install_from_wheel(tmp_path):
    # Build the wheel
    dist = tmp_path / "dist"
    subprocess.run(["uv", "build", "--wheel", "-o", str(dist)], cwd=REPO, check=True)
    wheel = next(dist.glob("*.whl"))

    # Install into an isolated venv OUTSIDE the repo tree
    venv = tmp_path / "venv"
    subprocess.run(["uv", "venv", str(venv)], check=True)
    bin_dir = venv / ("Scripts" if (venv / "Scripts").exists() else "bin")
    subprocess.run(["uv", "pip", "install", "--python", str(bin_dir / "python"), str(wheel)], check=True)

    # Seed a synthetic catalog + project entirely outside the repo
    toolkit = tmp_path / "toolkit"
    d = toolkit / "mcps" / "demo"
    d.mkdir(parents=True)
    (d / "config.json").write_text('{"type":"stdio","command":"npx","args":["-y","demo"]}\n')
    (d / "README.md").write_text("# demo\n")
    (toolkit / "mcps" / "demo.toolkit.yaml").write_text(
        "name: demo\ndescription: x.\ntransport: stdio\ninstall_method: npx\n"
    )
    project = tmp_path / "proj"
    project.mkdir()

    env = {"HOME": str(tmp_path), "AGENT_TOOLKIT_REPO": str(toolkit), "PATH": str(bin_dir)}
    import os
    env = {**os.environ, **env}
    r = subprocess.run(
        [str(bin_dir / "agent-toolkit"), "mcp", "install", "demo", "--harness", "claude", "-p"],
        cwd=project, env=env, capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    doc = json.loads((project / ".mcp.json").read_text())
    assert "demo" in doc["mcpServers"]
```

- [ ] **Step 2: Run the wheel test**

Run: `uv run pytest tests/test_mcp_wheel.py -v`
Expected: PASS (or SKIP if `uv` absent in the runner — acceptable).

- [ ] **Step 3: Commit**

```bash
git add tests/test_mcp_wheel.py
git commit -m "test(mcp): wheel-install guard — mcp install works outside the source tree"
```

---

## Task 12: Documentation + roadmap

**Files:**
- Modify: `docs/agent-toolkit/roadmap.md`
- Modify: `README.md`

- [ ] **Step 1: Strike `mcp` from the Phase 2 pending list**

In `docs/agent-toolkit/roadmap.md`, update the Phase 2 heading and table: remove `mcp` from "revisit agent, command, hook, mcp, plugin, pi-extension" (it is now shipped), or add a "delivered" note in the table row for `mcp` pointing at this plan, consistent with how the walker/sidecar retirement is annotated ("delivered in vX.Y.Z").

- [ ] **Step 2: Note MCP support in the README**

In `README.md`, add MCP to the supported-kinds list with the foundations caveat:

```markdown
- **MCPs** — `agent-toolkit mcp install <slug>` projects a catalog MCP into
  Claude / Codex / OpenCode / Pi by surgically editing each harness's native
  config (manage-by-name, never file ownership; loud atomic writes). `list`,
  `status`, `uninstall`, `remove`, and a read-only `doctor` are supported.
  Drift `fix`, dry-run `diff`, and the TUI MCPs section land in a follow-up.
```

- [ ] **Step 3: Commit**

```bash
git add docs/agent-toolkit/roadmap.md README.md
git commit -m "docs(mcp): mark mcp kind shipped in roadmap + README"
```

---

## Task 13: Final verification + branch finish

**Files:** none

- [ ] **Step 1: Full green gate**

Run:
```bash
uv run pytest -q
uv run ruff check src tests
git status
```
Expected: tests green, lint clean, working tree clean (the repo's own `.mcp.json` is gitignored and must not appear as a tracked change — verify).

- [ ] **Step 2: Finish the branch**

Use `superpowers:finishing-a-development-branch` to open the PR (target: PR awaiting eyeball, per the aj-flow Auto→PR terminus). The PR description should link this plan, the design spec, and the closed v1 issues (#55, #74, #125) as prior art, and call out that this is the **foundations slice** (fix/diff/TUI/opencode-pi-translation-edge-cases deferred).

---

## Plan Self-Review

**1. Spec coverage** (against `2026-05-04-mcp-management-design.md`, scoped to foundations):
- Manage-by-name, never file ownership → Tasks 4/5 (surgical upsert/remove). ✅
- Round-trip parsers preserve other bytes → Tasks 4 (JSON), 5 (TOML byte-equality test). ✅
- Loud atomic writes (`→ writing` / `✓ wrote`, temp+`os.replace`) → Task 3 `atomic_write_text` + Task 7 facade messages. ✅
- Four harness strategy table (claude/codex/opencode/pi) → Tasks 4 (3 JSON) + 5 (codex TOML), all-four round-trip in Task 9. ✅
- Acceptance #1 install via mechanism without secrets → Task 8/9 (env passed through verbatim, never read). ✅
- Acceptance #2 byte-identical re-run → idempotency tests Tasks 4/5. ✅
- Acceptance #3 unlink removes only named entry, neighbours byte-equal → Tasks 4/5/9. ✅
- Acceptance #4 list shows install state → Task 8 `list_cmd`. ✅
- Acceptance #6 doctor reports drift / missing env → Task 8 `doctor_cmd` (read-only subset). ✅
- Acceptance #8 round-trip byte-equal with comments+unknown sections → Task 5 TOML test. ✅
- The empty-`{}` / absent-`.mcp.json` failure-mode notes (added 2026-06-07) → Task 4 normalisation tests. ✅
- **Deferred (explicitly out of scope, not gaps):** schema v1alpha2 bump (Acc #9), `diff` (Acc #5), `fix` (Acc #7), TUI (Acc #10), `--force` running-process guard. Recorded in "Out of scope".

**2. Placeholder scan:** No "TBD"/"handle edge cases"/"similar to Task N" — every code step has concrete code. The verb files in Task 8 beyond `install_cmd` are described by behaviour + "mirror the agent sibling" rather than full code; this is deliberate (they are thin and the agent sibling IS the concrete template the engineer reads in Step 1), but it is the one spot a builder must read siblings rather than copy-paste. Flagged here honestly.

**3. Type consistency:** `McpAsset` (catalog) / `McpAdapter` (Protocol) / `McpLockEntry` (lock) used consistently. `get_adapter(harness)` signature identical across base, install facade, and tests. `config_target(scope=, home=, project=)`, `install(slug, inner_config, scope=, home=, project=)`, `uninstall(slug, scope=, home=, project=)`, `is_installed(...)` — identical across `json_config`, `toml_config`, Protocol, facade, and tests. `scope_and_roots(global_=, project_=, read_only=)` matches the agent sibling (verified in Task 6 Step 1 / Task 8 Step 1 — the one place the builder must confirm the real signature and adjust if it differs).

**One known soft spot the builder must resolve by reading siblings:** the exact toolkit-repo resolution mechanism (`AGENT_TOOLKIT_REPO` env vs `--toolkit-repo` flag vs `_repo_resolution.py` default) and the precise `scope_and_roots` return tuple. Tasks 6 and 8 both instruct reading the agent sibling first and adjusting; the tests note the same. This is correct dependency-direction (reuse the shared resolver) but cannot be pinned to exact code without the sibling open.
