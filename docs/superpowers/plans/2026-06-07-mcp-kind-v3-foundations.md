# MCP Kind (v3) Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-port the `mcp` (Model Context Protocol server) asset kind into the current v3 per-kind architecture as a first-class, lock-driven, four-harness capability — `add`/`install`/`uninstall`/`remove`/`update`/`list`/`status`/`doctor` — with a config-injection adapter layer that manages MCP entries *by name* inside each harness's native config file, never by file ownership.

**Architecture:** Follow the established v3 per-kind pattern exactly (the same shape `agent` and `pi_extension` kinds use): parallel modules `mcp_install.py` / `mcp_lock.py` (scope resolution lives in `commands/mcp/_common.py` — see Task 6), a `commands/mcp/` Click group, and an `mcp_adapters/` package whose `get_adapter(harness)` dispatcher is the single SSOT for the per-harness projection mechanism. The shared kind-agnostic core (`_install_core.py`) is bound via injected callables; the lock is a per-kind file (`mcps-lock.json`, plural per convention) with an **independent, versioned `McpLockEntry` record** — deliberately NOT the shared `LockEntry` (a per-harness projection list per slug doesn't fit its one-canonical-path shape), but aligned for the bundle composite's future grouping field (decision record in "Deferred / Open Questions"). Unlike folder-shaped kinds (skills/agents) that symlink or copy a markdown file, MCP is **config-injection-shaped**: each adapter surgically upserts/removes one named entry (`[mcp_servers.<name>]` in Codex TOML, `mcpServers.<name>` in Claude/Pi/OpenCode JSON) using a round-tripping parser, preserving every other byte. Every write is loud and atomic (temp file in same dir → `os.replace`).

**Tech Stack:** Python 3.12+ (per `requires-python`), Click, `tomlkit` (Codex TOML round-trip — NEW dependency), stdlib `json` (Claude/Pi/OpenCode), pytest. Library entry shape: `~/.agent-toolkit/mcps/<slug>/{config.json, README.md}` plus a sibling `<slug>.toolkit.yaml` metadata sidecar.

**Library model (decision 2026-06-10, supersedes the earlier "dedicated catalog repo" decision):** MCP entries live in a **library at `~/.agent-toolkit/mcps/`** — the same substrate position as `~/.agent-toolkit/skills/` etc.: a local store you `add` to, ready to install. It is NOT a managed clone of any repo and there is NO catalog-repo prerequisite. `mcp add` AUTHORS entries from flags (a skill's upstream is a git repo so its `add` clones; an MCP's upstream is an npm/PyPI package, docker image, URL, or local path, so its `add` writes the entry directly). Consequences: `resolve_toolkit_root()` / `_repo_resolution.py` / marker files are NOT used by this kind at all — the library root derives from `home` (`home / ".agent-toolkit" / "mcps"`), entries sit at the library root (`<slug>/config.json` + `<slug>.toolkit.yaml`, no intermediate `mcps/` dir), and tests simply seed a tmp `$HOME`. Cross-machine library sync (git-ifying the dir + a `push` verb on the skill-push `divergence()` pattern) is a deferred follow-up.

**Sources + version transparency (decision 2026-06-10):** v1 supports `npx`, `uvx`, `docker`, `url` (remote HTTP), and `local` (existing directory on disk). Git-clone-and-build sources (where this tool would fetch and build a server repo) are deferred — note `uvx --from git+url@ref` already covers pinned Python git sources without any build machinery. Versioning is **transparency, not enforcement**: `add` best-effort RESOLVES the current version (`npm view <pkg> version`; PyPI JSON API; docker tag as given, digest recorded when cheap; git HEAD SHA for `--local` when the path is a repo) and writes it into the entry (`pkg@1.4.2` / `pkg==2.0.1`), so projected configs are effectively pinned underneath (sidestepping the npx/uvx sticky-stale caches) while the UX stays "floating with explicit update". If resolution fails (offline / tool absent), the entry is stored unpinned and `list`/`doctor` show it as `floating` — never block. The `update` verb advances the float explicitly: re-resolve, rewrite the entry, re-upsert every locked projection, print `old → new`.

**Prior art (re-mapped, predates v3):**
- Spec/brainstorm: `docs/superpowers/specs/2026-05-04-mcp-management-design.md` — the design these tasks implement (manage-by-name, round-trip, loud atomic writes, four harness strategy table, the empty-`{}` / absent-`.mcp.json` failure-mode notes added 2026-06-07).
- Superseded plan: `docs/superpowers/plans/2026-05-04-mcp-foundations.md` — written against the deleted v1 walker/sidecar/`_allowlist.py` machinery; **do not follow it**; this plan replaces it.
- Closed v1 issues for reference only: #55 (config_file adapters), #74 (codex HTTP transport), #125 (project-scope link absent-file bug), #141/#142 (list JSON MCP cells), #39 (TUI MCP sidebar — out of scope here).

---

## Orientation: read these before Task 1 (no edits)

Before writing any code, the engineer MUST read the agent kind as the working template — it is the closest sibling and the canonical example of every contract this plan relies on:

- `src/agent_toolkit_cli/agent_adapters/__init__.py` — the dispatcher + `Protocol` + `_guard_foreign` / `.attk` sentinel pattern. **Copy this file's structure for `mcp_adapters/__init__.py`.**
- `src/agent_toolkit_cli/agent_install.py` — the facade that binds `_install_core.py` via injected callables. **Note:** the actual **rollback contract** precedent (write the lock first, apply, roll back the prior projection on failure) lives in `src/agent_toolkit_cli/commands/instructions/install_cmd.py` — `agent_install.apply()` itself has no try/except rollback path. Read BOTH; the MCP facade MUST implement the rollback contract (Task 7's facade code is the authoritative shape).
- `src/agent_toolkit_cli/agent_lock.py` — per-kind lock filename + `agentPath` field on the shared `LockEntry`. MCP deliberately does NOT mirror this: it keeps an independent, versioned `McpLockEntry` (decision 2026-06-10 — see "Deferred / Open Questions" record).
- `src/agent_toolkit_cli/agent_paths.py` — scope/root resolution.
- `src/agent_toolkit_cli/commands/agent/__init__.py` + `add_cmd.py` + `install_cmd.py` + `uninstall_cmd.py` + `remove_cmd.py` + `list_cmd.py` + `status_cmd.py` + `doctor_cmd.py` — the CLI verbs to mirror. Note the read/write scope-default split documented in the `__init__.py` docstring (read verbs `read_only=True` → global default; write verbs default to project when a project lock is present).
- `src/agent_toolkit_cli/_install_core.py` — the shared core and `InstallError` hierarchy.
- `src/agent_toolkit_cli/skill_agents.py` — `AGENTS` registry (the harness catalog). MCP adapter dispatch keys off harness name here.

**Spec scope mapping — why this plan deviates from the design document:**

The spec (`2026-05-04-mcp-management-design.md`) was written against the **v1 architecture** (walker, allow-list authority, `link`/`unlink`/`diff`/`fix`/`new` verbs, `v1alpha2` schema bump). The v3 per-kind architecture (shipped for skill/agent/instructions/pi-extension) supersedes the walker model with per-kind facades and lock-driven tracking — the **lock replaces the allow-list as the authority on what we manage** (spec Rule 1 re-mapped); the spec's mechanism rules (manage-by-name, round-trip parsers, structural drift, loud atomic writes) carry over unchanged. Verb mapping: `link`→`install`, `unlink`→`uninstall`, `new`→`add`, `check`/`doctor`→`doctor`; spec acceptance #1–4, #6, #8 are implemented here; #5 (`diff`), #7 (`fix`), #9 (schema v1alpha2), #10 (TUI) are deferred per issue #329's out-of-scope list. The spec's `harness_adapters/` package name becomes `mcp_adapters/` per the v3 per-kind naming convention (`agent_adapters/` precedent); the empty `harness_adapters/` directory on disk is a v1 stub — do not write into it.

**Project-memory mandates (non-negotiable, enforced by tasks below):**
1. **Install machinery has repeatedly shipped silently-broken global-scope / orphan paths with green CI.** Every install path MUST have an explicit `install → uninstall → assert-clean` round-trip test **at BOTH global and project scope** (Tasks 9, 10).
2. **`uninstall` is non-destructive; `remove` is destructive.** `uninstall` removes the harness projection only and leaves the canonical/lock intact; `remove` drops the canonical entry + lock entry. Mirror the agent kind's contract exactly (project memory: a misnamed `uninstall -g` once `rmtree`'d the canonical store).
3. **Apply-over-existing MUST roll back the prior projection on a Canonical/PointerConflict** (mirror `install_cmd` rollback contract).
4. **Packaged-resource paths must survive a wheel install** — no `parents[N]` walks to find repo files at runtime; the library root derives from `home` (`~/.agent-toolkit/mcps/`), never relative-to-`__file__` (Task 11 guard).

## Out of scope (explicit — deferred to follow-up issues)

- `fix` (drift reconciliation) and `diff` (dry-run) verbs. `doctor` reports drift but does not write. (`update` IS in scope — see Task 8: re-resolve + re-upsert is the verb that makes version transparency coherent.)
- `push` / `reset` / `import` verbs for MCP. `push`'s follow-up semantics are already defined: git-ify the library dir and publish via the skill-push `divergence()` pattern (commit+push the library). Not needed until cross-machine sync matters.
- **Git-clone-and-build sources** (this tool fetching + building a server repo — the materialization layer). `uvx --from git+url@ref` and `npx github:owner/repo#ref` already cover pinned git sources via the package managers.
- Cross-machine library sync (the library is machine-local in v1; entries are cheap to re-`add`).
- The TUI MCPs section (#39 lineage).
- Schema bump to `v1alpha2` / `metadata.kind` discriminator.
- `verify:` command execution (arbitrary shell; opt-in `--verify` is a follow-up).
- `ingest` of one-off MCPs from arbitrary pasted JSON (flag-driven `add` covers the common cases in two commands; a paste-ingest is a follow-up).
- The FULL running-`claude`-process guard machinery for `~/.claude.json` is a follow-up — but a **minimal guard ships in this slice** (spec Rule 5 makes it core write-safety): before any global-scope claude-code write, the facade checks for a running `claude` process (`pgrep -x claude`, best-effort) and refuses with a clear message; `--force` bypasses. `~/.claude.json` is a live state file Claude rewrites continuously — an unguarded read→rewrite→replace can silently destroy state Claude wrote in between (Task 7).

---

## File Structure

**New files:**

- `src/agent_toolkit_cli/mcp_lock.py` — `mcps-lock.json` reader/writer with an independent, versioned `McpLockEntry` record (decision 2026-06-10: independent-but-aligned; see Task 6 and the decision record below).
- `src/agent_toolkit_cli/mcp_library.py` — the library reader/writer: `library_root(home) = home/".agent-toolkit"/"mcps"`; reads `<library>/<slug>/config.json` + sibling `<slug>.toolkit.yaml`; returns an `McpAsset` (slug, inner_config dict, metadata dict, transport, install_method); `write_entry()` used by `add`.
- `src/agent_toolkit_cli/mcp_install.py` — the facade: `apply()` / `uninstall()` / `remove()` binding `_install_core.py` and dispatching to `mcp_adapters.get_adapter()`. Mirrors `agent_install.py` including the rollback contract.
- `src/agent_toolkit_cli/mcp_adapters/__init__.py` — `McpAdapter` Protocol, `get_adapter(harness)` SSOT dispatcher, shared atomic-write + round-trip-read helpers, `McpProjectionConflictError`.
- `src/agent_toolkit_cli/mcp_adapters/json_config.py` — config-file adapter for Claude / Pi / OpenCode (JSON family). Per-harness target paths + per-harness key translation in per-cell dicts inside the module.
- `src/agent_toolkit_cli/mcp_adapters/toml_config.py` — config-file adapter for Codex (`~/.codex/config.toml` via `tomlkit`).
- `src/agent_toolkit_cli/commands/mcp/__init__.py` — the `mcp` Click group + subcommand registration. Mirrors `commands/agent/__init__.py`.
- `src/agent_toolkit_cli/commands/mcp/_common.py` — shared scope/root resolution for the verbs.
- `src/agent_toolkit_cli/commands/mcp/{add,install,uninstall,remove,update,list,status,doctor}_cmd.py` — the eight verbs.

**New test files:**

- `tests/test_mcp_library.py`
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

## Task 2: MCP library reader/writer (`mcp_library.py`)

**Files:**
- Create: `src/agent_toolkit_cli/mcp_library.py`
- Test: `tests/test_mcp_library.py`

The library lives at `~/.agent-toolkit/mcps/` (derived from `home` — NOT a repo clone, NOT resolved via `_repo_resolution.py`). Entry convention, at the library root: `<library>/<slug>/config.json` (the inner MCP server config — `{type, command, args, ...}`, NO `mcpServers` wrapper) plus a sibling `<slug>.toolkit.yaml` metadata sidecar at `<library>/<slug>.toolkit.yaml`. The README.md is human prose and is NOT parsed for metadata.

- [ ] **Step 1: Write the failing test**

Create `tests/test_mcp_library.py`:

```python
"""Tests for src/agent_toolkit_cli/mcp_library.py — library discovery + parse."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_toolkit_cli.mcp_library import (
    McpAsset,
    library_root,
    list_library,
    load_mcp_asset,
)


def test_library_root_derives_from_home(tmp_path):
    assert library_root(tmp_path) == tmp_path / ".agent-toolkit" / "mcps"


def _write_library_entry(
    library: Path, slug: str, *, inner: str, sidecar: str
) -> None:
    mcp_dir = library / slug
    mcp_dir.mkdir(parents=True, exist_ok=True)
    (mcp_dir / "config.json").write_text(inner)
    (mcp_dir / "README.md").write_text(f"# {slug}\n")
    (library / f"{slug}.toolkit.yaml").write_text(sidecar)


def test_load_mcp_asset_reads_inner_and_sidecar(tmp_path):
    _write_library_entry(
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
    with pytest.raises(FileNotFoundError):
        load_mcp_asset(tmp_path, "does-not-exist")


def test_list_library_returns_slugs_sorted(tmp_path):
    for slug in ("zeta", "alpha"):
        _write_library_entry(
            tmp_path, slug,
            inner='{"type":"stdio","command":"npx"}\n',
            sidecar=f"name: {slug}\ndescription: x.\ntransport: stdio\ninstall_method: npx\n",
        )
    assert list_library(tmp_path) == ["alpha", "zeta"]


def test_load_mcp_asset_without_sidecar_uses_defaults(tmp_path):
    """A bare config.json with no sidecar is still loadable; metadata is empty,
    transport/install_method fall back to None (doctor surfaces the gap later)."""
    mcp_dir = tmp_path / "orphan"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text('{"type":"stdio","command":"npx"}\n')
    asset = load_mcp_asset(tmp_path, "orphan")
    assert asset.slug == "orphan"
    assert asset.metadata == {}
    assert asset.transport is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_mcp_library.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_toolkit_cli.mcp_library'`.

- [ ] **Step 3: Implement `mcp_library.py`**

Create `src/agent_toolkit_cli/mcp_library.py`:

```python
"""The MCP library at ~/.agent-toolkit/mcps/ — read entries, write entries (add).

Library convention (entries at the library ROOT, no intermediate dir):
`<library>/<slug>/config.json` (inner MCP server config, no mcpServers wrapper)
plus a sibling metadata sidecar at `<library>/<slug>.toolkit.yaml`.
README.md is human prose, not parsed. The library is a plain local store —
NOT a repo clone; the root derives from home, never from _repo_resolution.
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

    @property
    def resolved_version(self) -> str | None:
        """Version transparency: what `add`/`update` last resolved, or None (floating)."""
        return self.metadata.get("resolved_version")


def library_root(home: Path) -> Path:
    """The MCP library root. Derives from home — wheel-safe, no parents[N]."""
    return home / ".agent-toolkit" / "mcps"


def load_mcp_asset(library: Path, slug: str) -> McpAsset:
    """Load one MCP asset by slug. Raises FileNotFoundError if config.json absent."""
    config_path = library / slug / "config.json"
    if not config_path.is_file():
        raise FileNotFoundError(
            f"MCP '{slug}' not found in the library: {config_path} does not exist — add it first: agent-toolkit-cli mcp add {slug} --npx|--uvx|--docker|--url|--local …"
        )
    inner = json.loads(config_path.read_text(encoding="utf-8"))
    _validate_inner_config(slug, inner, config_path)
    sidecar_path = library / f"{slug}.toolkit.yaml"
    metadata: dict = {}
    if sidecar_path.is_file():
        metadata = yaml.safe_load(sidecar_path.read_text(encoding="utf-8")) or {}
    return McpAsset(slug=slug, inner_config=inner, metadata=metadata)


def _validate_inner_config(slug: str, inner: object, path: Path) -> None:
    """Structural validation — bounds the injection surface to well-typed values.

    The inner config is written into live harness configs where the harness
    EXECUTES it; a malformed shape (command as list, args containing dicts)
    must fail loudly at load time, not propagate into ~/.claude.json.
    """
    if not isinstance(inner, dict):
        raise ValueError(f"{path}: inner config must be a JSON object")
    if "command" in inner and not isinstance(inner["command"], str):
        raise ValueError(f"{path}: 'command' must be a string")
    if "args" in inner and not (
        isinstance(inner["args"], list)
        and all(isinstance(a, str) for a in inner["args"])
    ):
        raise ValueError(f"{path}: 'args' must be a list of strings")
    if "env" in inner and not (
        isinstance(inner["env"], dict)
        and all(isinstance(k, str) and isinstance(v, str) for k, v in inner["env"].items())
    ):
        raise ValueError(f"{path}: 'env' must be a string→string object")


def list_library(library: Path) -> list[str]:
    """Return sorted slugs of every entry directory containing a config.json."""
    if not library.is_dir():
        return []
    slugs = [
        d.name
        for d in library.iterdir()
        if d.is_dir() and (d / "config.json").is_file()
    ]
    return sorted(slugs)


def write_entry(library: Path, slug: str, *, inner_config: dict, metadata: dict) -> Path:
    """Author one library entry (used by `mcp add`). Returns the entry dir.

    Refuses to overwrite an existing entry unless the caller deleted it first
    (re-`add` of an existing slug is an explicit error; `update` is the verb
    that rewrites entries).
    """
    entry = library / slug
    if (entry / "config.json").is_file():
        raise FileExistsError(f"MCP '{slug}' already exists in the library: {entry}")
    entry.mkdir(parents=True, exist_ok=True)
    (entry / "config.json").write_text(
        json.dumps(inner_config, indent=2) + "\n", encoding="utf-8"
    )
    (entry / "README.md").write_text(f"# {slug}\n", encoding="utf-8")
    (library / f"{slug}.toolkit.yaml").write_text(
        yaml.safe_dump(metadata, sort_keys=True), encoding="utf-8"
    )
    return entry
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_mcp_library.py -v`
Expected: PASS — all four tests.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/mcp_library.py tests/test_mcp_library.py
git commit -m "feat(mcp): library reader/writer for ~/.agent-toolkit/mcps/<slug>"
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
    for harness in ("claude-code", "codex", "opencode", "pi"):
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
    "claude-code": "json",
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

**Review-resolved contracts for this task (added after critical review):**

1. **JSON-family preservation contract is STRUCTURAL, not byte-level.** `json.dumps(indent=2)` re-serialises the whole document, so a user file with compact formatting or 4-space indent is reformatted on first write — spec acceptance #3/#8's byte-equality is achievable only for the TOML family (tomlkit round-trips). For the JSON family the contract is: every pre-existing entry is **structurally identical** before/after, entry order preserved (no re-sort), and re-runs are byte-idempotent. This deviation from the spec is deliberate and recorded in the Plan Self-Review. The worst case (`~/.claude.json` whole-file re-indent at global scope) is mitigated by the running-claude guard below.
2. **Pi targets MUST be empirically verified before the CELLS values are trusted (spec open item #3 — never closed).** Add a verification step before implementing: launch Pi against a scratch project containing `.pi/mcp.json` and confirm the server is offered; same for `~/.config/mcp/mcp.json` at user scope. If either path is not read, change the cell and record the verified source in the cell's comment. An unread target means installs succeed, doctor reports healthy, and the MCP never loads — exactly the silent-green-breakage class Mandate 1 exists to kill.
3. **Installed-harness sentinel (spec failure-mode table).** Each cell carries a `sentinel` (e.g. `~/.claude/` for claude-code, `~/.codex/` for codex, `~/.config/opencode/` for opencode, `~/.pi/` for pi). The facade checks the sentinel before dispatching to an adapter: when absent, print `"<harness> does not appear to be installed (<sentinel> missing); skipping"` and skip — exit 0. NEVER unconditionally `mkdir -p` a harness config tree for a harness that is not installed. `atomic_write_text` stays generic (no sentinel logic in the write primitive).
4. **OpenCode refusal path (spec: "Refuse if source uses `${VAR:-default}`").** `_opencode_translate` MUST raise (not silently mistranslate) when an env value contains shell-default syntax `${...:-...}` or any `${` that the mechanical substring replace cannot cleanly map — a silent write of `{env:VAR:-default}` is a malformed reference OpenCode will choke on. Raise `InstallError` naming the variable; the facade's rollback handles multi-harness installs. Test both the refusal and the clean `${VAR}` → `{env:VAR}` path.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_mcp_adapters_json.py`:

```python
def _claude_inner():
    return {"type": "stdio", "command": "npx", "args": ["-y", "ctx7"]}


def test_claude_install_creates_file_with_valid_shape_when_absent(tmp_path):
    """Absent .mcp.json must be created as {"mcpServers": {...}}, NOT skipped."""
    adapter = get_adapter("claude-code")
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
    adapter = get_adapter("claude-code")
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
    adapter = get_adapter("claude-code")
    adapter.install("context7", _claude_inner(), scope="project", home=tmp_path, project=project)
    doc = json.loads((project / ".mcp.json").read_text())
    assert doc["mcpServers"]["handrolled"] == {"command": "x"}
    assert doc["mcpServers"]["context7"] == _claude_inner()


def test_claude_uninstall_removes_only_named_entry(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    adapter = get_adapter("claude-code")
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
    get_adapter("claude-code").uninstall("context7", scope="project", home=tmp_path, project=project)
    # No crash; no file created
    assert not (project / ".mcp.json").exists()


def test_claude_install_is_idempotent(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    adapter = get_adapter("claude-code")
    adapter.install("context7", _claude_inner(), scope="project", home=tmp_path, project=project)
    first = (project / ".mcp.json").read_text()
    adapter.install("context7", _claude_inner(), scope="project", home=tmp_path, project=project)
    assert (project / ".mcp.json").read_text() == first


def test_claude_user_scope_target_is_home_claude_json(tmp_path):
    adapter = get_adapter("claude-code")
    target = adapter.config_target(scope="global", home=tmp_path, project=None)
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
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from agent_toolkit_cli._install_core import InstallError
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
    """Claude/Pi accept the library inner config verbatim."""
    return dict(inner)


def _opencode_translate(inner: dict) -> dict:
    """OpenCode native shape: command joined to a list, env→environment, ${V}→{env:V}.

    Refuses (raises InstallError) on shell-default syntax ${VAR:-default} — the
    mechanical replace cannot represent it and a silent mistranslation would
    write a malformed reference into opencode.json (spec strategy table).
    """
    cmd = [inner["command"], *inner.get("args", [])] if "command" in inner else []
    out: dict = {"type": "local", "command": cmd}
    env = inner.get("env")
    if isinstance(env, dict):
        translated = {}
        for k, v in env.items():
            if isinstance(v, str) and re.search(r"\$\{[^}]*:-", v):
                raise InstallError(
                    f"opencode: cannot translate env var {k!r} — shell-default "
                    f"syntax ${{VAR:-default}} has no OpenCode equivalent. "
                    f"Adjust the catalog entry or skip --harness opencode."
                )
            translated[k] = (
                v.replace("${", "{env:") if isinstance(v, str) else v
            )
        out["environment"] = translated
    return out


CELLS: dict[str, _Cell] = {
    "claude-code": _Cell(
        name="claude-code",
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
        if scope == "global":
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
        # Upsert ONLY our named entry. Do NOT re-sort pre-existing neighbours —
        # hand-rolled entry order is the user's; re-running with the same input
        # is still byte-idempotent because the upsert is positionally stable.
        doc[self._cell.servers_key][slug] = self._cell.translate(inner_config)
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
    assert adapter.config_target(scope="global", home=tmp_path, project=None) == (
        tmp_path / ".codex" / "config.toml"
    )


def test_codex_install_adds_mcp_servers_table(tmp_path):
    adapter = get_adapter("codex")
    adapter.install("context7", INNER, scope="global", home=tmp_path)
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
    adapter.install("context7", INNER, scope="global", home=tmp_path)
    adapter.uninstall("context7", scope="global", home=tmp_path)
    assert cfg.read_text() == source


def test_codex_uninstall_removes_only_named_table(tmp_path):
    adapter = get_adapter("codex")
    adapter.install("context7", INNER, scope="global", home=tmp_path)
    adapter.install("other", {"command": "y"}, scope="global", home=tmp_path)
    adapter.uninstall("context7", scope="global", home=tmp_path)
    doc = tomlkit.parse((tmp_path / ".codex" / "config.toml").read_text())
    assert "context7" not in doc["mcp_servers"]
    assert doc["mcp_servers"]["other"]["command"] == "y"


def test_codex_install_idempotent(tmp_path):
    adapter = get_adapter("codex")
    adapter.install("context7", INNER, scope="global", home=tmp_path)
    first = (tmp_path / ".codex" / "config.toml").read_text()
    adapter.install("context7", INNER, scope="global", home=tmp_path)
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
        if scope == "global":
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
        The library inner shape already matches Codex closely; pass through the
        recognised keys, dropping the library-only 'type' marker."""
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

The lock records which (scope, harness, slug) projections this tool created, so `uninstall`/`remove`/`status` know what is tool-owned vs hand-rolled. It follows `agent_lock.py`'s per-kind-filename convention (`mcps-lock.json`) but deliberately NOT its shared-`LockEntry` record: because MCP writes into shared config files rather than a single owned path, the lock records the **set of (harness, scope, slug)** managed entries plus provenance (`source` = install_method) and version transparency (`pin`), in an independent versioned envelope (decision 2026-06-10).

- [ ] **Step 1: Read the sibling first**

Read `src/agent_toolkit_cli/agent_lock.py` and `src/agent_toolkit_cli/agent_paths.py` in full. The MCP versions mirror them; deviate only where the config-injection model requires (no single `path` per slug — instead a list of harness projections).

- [ ] **Step 2: Write the failing test**

Create `tests/test_mcp_lock.py`:

```python
"""Tests for mcp_lock.py — the mcps-lock.json reader/writer."""
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
    assert lock_path_for_scope("global", home=tmp_path, project=None) == (
        tmp_path / ".agent-toolkit" / "mcps-lock.json"
    )


def test_lock_path_project_scope(tmp_path):
    assert lock_path_for_scope("project", home=tmp_path, project=tmp_path / "p") == (
        tmp_path / "p" / "mcps-lock.json"
    )


def test_round_trip_empty(tmp_path):
    p = tmp_path / "mcps-lock.json"
    write_lock(p, {})
    assert read_lock(p) == {}


def test_upsert_and_remove(tmp_path):
    p = tmp_path / "mcps-lock.json"
    lock = read_lock(p)
    lock = upsert_entry(lock, McpLockEntry(slug="context7", harness="claude-code", source="ajanderson1/mcps"))
    write_lock(p, lock)
    reloaded = read_lock(p)
    assert "context7" in reloaded
    assert reloaded["context7"][0].harness == "claude-code"
    reloaded = remove_entry(reloaded, slug="context7", harness="claude-code")
    assert "context7" not in reloaded


def test_upsert_two_harnesses_same_slug(tmp_path):
    lock = upsert_entry({}, McpLockEntry(slug="context7", harness="claude-code", source="s"))
    lock = upsert_entry(lock, McpLockEntry(slug="context7", harness="codex", source="s"))
    harnesses = sorted(e.harness for e in lock["context7"])
    assert harnesses == ["claude-code", "codex"]
    # Removing one leaves the other
    lock = remove_entry(lock, slug="context7", harness="claude-code")
    assert [e.harness for e in lock["context7"]] == ["codex"]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_mcp_lock.py -v`
Expected: FAIL — module missing.

- [ ] **Step 4: Implement `mcp_lock.py`**

Create `src/agent_toolkit_cli/mcp_lock.py`:

```python
"""mcps-lock.json — records tool-owned MCP projections per (slug, harness).

Global scope: ~/.agent-toolkit/mcps-lock.json. Project scope: <project>/mcps-lock.json.
Each slug maps to a list of McpLockEntry (one per harness it is installed into).
Mirrors agent_lock.py's filename-per-kind convention (plural, like agents-lock.json).

Lock-model decision (2026-06-10, #329 critical review): the record stays
INDEPENDENT of skill_lock.LockEntry — a per-harness projection list per slug
genuinely does not fit LockEntry's one-canonical-path-per-slug shape — but is
ALIGNED for future composability: versioned envelope ({"version": 1, "mcps": ...})
and entries are plain objects so the bundle composite's grouping field
(see docs/solutions/architecture-patterns/clone-and-project-substrate-for-
bundle-plugin-capability-2026-06-10.md) can be added without a migration.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

LOCK_FILENAME = "mcps-lock.json"
LOCK_VERSION = 1


@dataclass(frozen=True)
class McpLockEntry:
    slug: str
    harness: str
    source: str            # provenance: the entry's install_method ("npx"|"uvx"|"docker"|"url"|"local")
    pin: str | None = None  # version transparency: resolved version at install time, None = floating


def lock_path_for_scope(scope: str, *, home: Path, project: Path | None) -> Path:
    if scope == "global":
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
        # Tolerant read: ignore unknown per-entry keys (future grouping field).
        out[slug] = [
            McpLockEntry(
                slug=slug, harness=e["harness"], source=e["source"],
                pin=e.get("pin"),
            )
            for e in entries
        ]
    return out


def write_lock(path: Path, lock: dict[str, list[McpLockEntry]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialisable = {
        "version": LOCK_VERSION,
        "mcps": {
            slug: [
                {"harness": e.harness, "source": e.source,
                 **({"pin": e.pin} if e.pin else {})}
                for e in sorted(entries, key=lambda x: x.harness)
            ]
            for slug, entries in sorted(lock.items())
        },
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

- [ ] **Step 5: Implement scope resolution in `commands/mcp/_common.py` (NOT `mcp_paths.py`)**

**Corrected after review — the original step pointed at a function that does not exist.** `scope_and_roots` does NOT live in `agent_paths.py`; it lives in `src/agent_toolkit_cli/commands/agent/_common.py:20` with signature:

```python
def scope_and_roots(
    global_: bool,
    project: bool,
    ctx_project: Path | None,
    *,
    read_only: bool = False,
) -> tuple[Scope, Path | None, Path | None]:   # Scope = Literal["project", "global"]
```

It returns a **3-tuple** (never any library/toolkit root), and its "project lock present?" probe is hard-coded to `AGENT_BINDING.lock_filename` (`agents-lock.json`) — so it CANNOT be delegated to: an MCP delegate would key the read-verb scope default off the wrong lockfile. The fork is **required, not conditional**:

Create `src/agent_toolkit_cli/commands/mcp/_common.py` as a copy of `commands/agent/_common.py` with the lock-filename probe swapped to `mcp_lock.LOCK_FILENAME` (`"mcps-lock.json"`). The library root derives from `home` via `mcp_library.library_root(home)` — never bundled into `scope_and_roots`, never resolved via `_repo_resolution.py`. Drop `mcp_paths.py` entirely (the lock-path helper lives in `mcp_lock.py`; scope resolution lives in `commands/mcp/_common.py`; no third module is needed).

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_mcp_lock.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/agent_toolkit_cli/mcp_lock.py src/agent_toolkit_cli/mcp_paths.py tests/test_mcp_lock.py
git commit -m "feat(mcp): mcps-lock.json reader/writer + paths resolution"
```

---

## Task 7: Install facade (`mcp_install.py`) — apply / uninstall / remove with rollback

**Files:**
- Create: `src/agent_toolkit_cli/mcp_install.py`
- Test: `tests/test_mcp_install.py`

The facade is the heart of the kind: it loads the library asset, dispatches to every requested harness adapter, writes the lock, and on a per-harness failure **rolls back the projections it already made this call** (rollback precedent: `commands/instructions/install_cmd.py` — project memory: TUI/CLI apply must roll back prior on conflict).

**Review-resolved facade duties (added after critical review):** (a) **installed-harness sentinel** — before dispatching to an adapter, check the harness sentinel dir (Task 4 note #3); absent → loud skip, exit 0; (b) **running-claude guard** — before a global-scope claude-code write, best-effort `pgrep -x claude`; found → refuse with a clear message unless `--force` (see Out of scope note); (c) **hand-rolled collision warning** — before upserting, if `adapter.is_installed(slug)` is true but the lock has NO entry for (slug, harness), print `WARNING: overwriting existing hand-rolled entry '<slug>' in <path> — this entry was not previously managed by agent-toolkit`; do not block (manage-by-name is correct), but the user must see the collision. Add a test asserting the warning fires.

It enforces the contract split: `uninstall` removes harness projections only (lock entry dropped, library untouched); `remove` is `uninstall` of ALL harnesses for that slug + ensure no lock entry remains — the library entry itself is NOT deleted (delete it with plain `rm -r` or a future `mcp remove --purge`; document this so the destructive/non-destructive contract is explicit even though they nearly converge for a library-sourced kind).

- [ ] **Step 1: Read the sibling first**

Read `src/agent_toolkit_cli/agent_install.py` in full for the facade shape, and `src/agent_toolkit_cli/commands/instructions/install_cmd.py` for the rollback precedent (`agent_install.apply()` itself contains no rollback path — the Task 7 facade code below is the authoritative rollback contract for MCP).

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


def _seed_library(library: Path, slug="context7"):
    d = library / slug
    d.mkdir(parents=True)
    (d / "config.json").write_text('{"type":"stdio","command":"npx","args":["-y","ctx7@9.9.9"]}\n')
    (d / "README.md").write_text(f"# {slug}\n")
    (library / f"{slug}.toolkit.yaml").write_text(
        f"name: {slug}\ndescription: x.\ntransport: stdio\ninstall_method: npx\nresolved_version: 9.9.9\n"
    )


def test_apply_installs_and_writes_lock_project(tmp_path):
    library = tmp_path / "library"
    _seed_library(library)
    project = tmp_path / "proj"
    project.mkdir()
    mcp_install.apply(
        slug="context7", harnesses=["claude-code"], scope="project",
        library_root=library, home=tmp_path, project=project,
    )
    doc = json.loads((project / ".mcp.json").read_text())
    assert "context7" in doc["mcpServers"]
    lock = read_lock(lock_path_for_scope("project", home=tmp_path, project=project))
    assert lock["context7"][0].harness == "claude-code"


def test_apply_installs_two_harnesses(tmp_path):
    library = tmp_path / "library"
    _seed_library(library)
    project = tmp_path / "proj"
    project.mkdir()
    mcp_install.apply(
        slug="context7", harnesses=["claude-code", "codex"], scope="project",
        library_root=library, home=tmp_path, project=project,
    )
    assert "context7" in json.loads((project / ".mcp.json").read_text())["mcpServers"]
    assert (project / ".codex" / "config.toml").is_file()
    lock = read_lock(lock_path_for_scope("project", home=tmp_path, project=project))
    assert sorted(e.harness for e in lock["context7"]) == ["claude-code", "codex"]


def test_uninstall_removes_projection_keeps_catalog(tmp_path):
    library = tmp_path / "library"
    _seed_library(library)
    project = tmp_path / "proj"
    project.mkdir()
    mcp_install.apply(
        slug="context7", harnesses=["claude-code"], scope="project",
        library_root=library, home=tmp_path, project=project,
    )
    mcp_install.uninstall(
        slug="context7", harnesses=["claude-code"], scope="project",
        library_root=library, home=tmp_path, project=project,
    )
    doc = json.loads((project / ".mcp.json").read_text())
    assert "context7" not in doc["mcpServers"]
    # Catalog still intact (non-destructive contract)
    assert (library / "context7" / "config.json").is_file()
    # Lock entry gone
    lock = read_lock(lock_path_for_scope("project", home=tmp_path, project=project))
    assert "context7" not in lock


def test_apply_rolls_back_prior_projection_on_later_failure(tmp_path, monkeypatch):
    """If the 2nd harness adapter raises, the 1st harness's projection is rolled back."""
    library = tmp_path / "library"
    _seed_library(library)
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
            slug="context7", harnesses=["claude-code", "codex"], scope="project",
            library_root=library, home=tmp_path, project=project,
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
from agent_toolkit_cli.mcp_library import load_mcp_asset
from agent_toolkit_cli.mcp_lock import (
    McpLockEntry,
    lock_path_for_scope,
    read_lock,
    remove_entry,
    upsert_entry,
    write_lock,
)

def _loud(msg: str) -> None:
    print(msg, file=sys.stdout)


def apply(
    *,
    slug: str,
    harnesses: list[str],
    scope: str,
    library_root: Path,
    home: Path,
    project: Path | None = None,
) -> None:
    """Install `slug` into each harness. Atomic across harnesses: roll back on failure."""
    asset = load_mcp_asset(library_root, slug)
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
            lock = upsert_entry(lock, McpLockEntry(
                slug=slug, harness=harness,
                source=asset.install_method or "unknown",
                pin=asset.resolved_version,
            ))
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
    library_root: Path,
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
    library_root: Path,
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
        library_root=library_root, home=home, project=project,
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

Mirror `commands/agent/` exactly: a Click group, read verbs (`list`, `status`, `doctor`) pass `read_only=True`; write verbs (`install`, `uninstall`, `remove`) default to project when a project lock is present; `add` authors a library entry from source flags (global-only, no `-p`); `update` re-resolves + re-projects.

- [ ] **Step 1: Read the sibling first**

Read `src/agent_toolkit_cli/commands/agent/__init__.py`, `install_cmd.py`, `uninstall_cmd.py`, `list_cmd.py`, `status_cmd.py`, `doctor_cmd.py`, and `_common.py`. Reproduce their flag surface and scope-resolution calls.

- [ ] **Step 2: Implement the group + verbs**

Create `src/agent_toolkit_cli/commands/mcp/__init__.py`:

```python
"""`agent-toolkit-cli mcp <verb>` — manage MCP servers across four harnesses
via config-injection adapters + mcps-lock.json. Mirrors commands/agent/.

Read verbs (list/status/doctor) pass read_only=True → default to global outside
a project. Write verbs (install/uninstall/remove) default to project when a
project lock is present. `add` authors a library entry from flags (global-only); `update` advances the float.
Supported harnesses: claude-code, codex, opencode, pi.
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
from agent_toolkit_cli.commands.mcp.update_cmd import update_cmd


@click.group(name="mcp")
def mcp() -> None:
    """Manage MCP servers via config-injection adapters + mcps-lock.json."""


mcp.add_command(list_cmd)
mcp.add_command(list_cmd, name="ls")
mcp.add_command(status_cmd)
mcp.add_command(add_cmd)
mcp.add_command(install_cmd)
mcp.add_command(uninstall_cmd)
mcp.add_command(remove_cmd)
mcp.add_command(update_cmd)
mcp.add_command(doctor_cmd)
```

Create `src/agent_toolkit_cli/commands/mcp/install_cmd.py` (the canonical write verb; the others follow the same shape — read the agent siblings for `_common` helpers and reproduce):

```python
"""`agent-toolkit-cli mcp install <slug> [--harness ...] [-g|-p]`."""
from __future__ import annotations

import click
from pathlib import Path

from agent_toolkit_cli import mcp_install
from agent_toolkit_cli.commands.mcp._common import scope_and_roots
from agent_toolkit_cli.mcp_library import library_root

_HARNESSES = ("claude-code", "codex", "opencode", "pi")


@click.command(name="install")
@click.argument("slug")
@click.option("--harness", "harnesses", multiple=True, type=click.Choice(_HARNESSES),
              help="Harness(es) to install into. Repeatable. Default: all four "
                   "(harnesses not detected on this machine are warned and skipped).")
@click.option("-g", "--global", "global_", is_flag=True, help="Global (user) scope.")
@click.option("-p", "--project", "project_flag", is_flag=True, help="Project scope.")
@click.option("--force", is_flag=True,
              help="Bypass the running-claude guard for ~/.claude.json writes.")
@click.pass_context
def install_cmd(ctx, slug: str, harnesses: tuple[str, ...], global_: bool,
                project_flag: bool, force: bool) -> None:
    """Install a library MCP into one or more harnesses."""
    # Mirrors commands/agent/install_cmd.py: 3-tuple return; ctx threads the
    # project root. The library root derives from home — no repo resolution.
    scope, home, project = scope_and_roots(
        global_, project_flag, ctx.obj.get("project_root") if ctx.obj else None,
    )
    library = library_root(Path.home())
    targets = list(harnesses) or list(_HARNESSES)
    mcp_install.apply(
        slug=slug, harnesses=targets, scope=scope,
        library_root=library, home=home, project=project, force=force,
    )
    click.echo(f"✓ installed {slug} → {', '.join(targets)} ({scope} scope)")
```

Create the remaining verb files mirroring the agent siblings:
- `uninstall_cmd.py` — same flags as install; calls `mcp_install.uninstall`. Default harnesses = those in the lock for `slug` (read the lock; if none specified and none in lock, error "not installed").
- `remove_cmd.py` — `slug` arg + scope flags; calls `mcp_install.remove`.
- `list_cmd.py` — `read_only=True`; prints library slugs with their resolved version (or `floating`) and, per slug, which harnesses are installed at the resolved scope (via `get_adapter(h).is_installed`). When the scope lock's `pin` lags the library entry's version, show it: `<pin> (library: <version> — stale)`.
- `status_cmd.py` — `read_only=True`; prints the lock contents for the resolved scope.
- `add_cmd.py` — **flag-driven authoring into the library** (global-only — the library is per-user): exactly ONE source flag is required:
  - `--npx <pkg>` → inner `{type: stdio, command: "npx", args: ["-y", "<pkg>@<resolved>"]}`; resolve current version via `npm view <pkg> version` (best-effort, subprocess, short timeout).
  - `--uvx <pkg>` → `{type: stdio, command: "uvx", args: ["<pkg>==<resolved>"]}`; resolve via the PyPI JSON API (`https://pypi.org/pypi/<pkg>/json`, stdlib urllib, short timeout).
  - `--docker <image[:tag]>` → `{type: stdio, command: "docker", args: ["run", "--rm", "-i", "<image:tag>"]}`; tag as given (default `latest`), digest recorded in the sidecar when `docker image inspect` is cheap and available.
  - `--url <https://…>` → `{type: http, url: "<url>"}`; nothing to resolve.
  - `--local <dir> --command "<cmd …>"` → the given command verbatim (recommend the `uv --directory <abs-dir> run <entrypoint>` shape so no `cwd` field is needed — not every harness supports one); if `<dir>` is a git repo, record its HEAD SHA as the resolved version.
  - Optional: `--env VAR` (repeatable — declared env var NAMES for doctor), `--description`.
  - Writes via `mcp_library.write_entry()`: `config.json` + `<slug>.toolkit.yaml` (with `install_method`, `transport`, `resolved_version` when resolution succeeded). **Resolution failure is NOT an error** — store unpinned, print `note: could not resolve a version for <pkg>; stored floating`, and `list`/`doctor` show `floating`. Re-`add` of an existing slug errors (use `update`).
- `update_cmd.py` — **advance the float, explicitly** (`mcp update <slug> [-g|-p]`; write-verb scope default: project when a project lock is present). TWO independent reconciliations, both always run:
  1. **Registry vs library entry:** re-resolve the entry's source (same per-method resolution as `add`); if the resolution moved, rewrite the library entry (config.json args + sidecar `resolved_version`). NOTE the library is per-user — this rewrite is global state even under `-p`; other scopes become *stale*, which `doctor`/`list` surface (see below).
  2. **Library entry vs THIS scope's projections:** re-upsert every harness the resolved-scope lock lists for the slug whenever its installed render or lock `pin` differs from the CURRENT entry — **regardless of whether step 1 changed anything** (otherwise a scope that lagged behind an earlier other-scope update could never catch up: registry==entry would short-circuit and strand it). Refresh `pin` on the re-upserted lock entries.

  Output: `<slug>: <old> → <new> (<harnesses>) [<scope>]` where old/new come from the LOCK PINS (not the registry delta); `<slug>: up to date (<version>)` only when BOTH reconciliations were no-ops. `--url` entries: step 1 is a no-op; `--local`: step 1 refreshes the recorded HEAD SHA. Scope semantics: **the library answers WHICH version; the scope answers WHERE** — versions cannot intentionally diverge per scope (explicit v1 non-goal: per-scope version pinning, i.e. holding one project at an older version while the library moves, would require the lock `pin` to become the render authority — a follow-up that inverts the data flow; do NOT half-implement it). Transient staleness across scopes is expected and visible: `list` shows `<pin> (library: <version> — stale)` when a lock pin lags the entry, and `doctor`'s structural-drift check reports it per (slug, harness).
- `doctor_cmd.py` — `read_only=True`; three checks per lock entry, NEVER writes (foundations `doctor` is read-only; `fix` is deferred):
  1. **Orphans/missing**: `is_installed` matches the lock (report orphan lock entries / missing projections).
  2. **Structural drift (spec Rule 4 — this is what makes "doctor reports drift" true):** load the library asset, render it through the adapter's `translate`, and compare structurally (parsed equality, not text) against the installed entry; report `drifted` per (slug, harness) when they differ. Read-only — reconciliation is the deferred `fix` verb.
  3. **Env presence**: warn on declared `env:` vars absent from the environment. **Print variable NAMES only, never values** — e.g. `WARNING: env var DATABASE_URL (declared by context7) is not set`; a test MUST assert doctor output never contains the value of a seeded env var (the no-secrets non-goal applies to terminal output too).

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


def _seed(home: Path, slug="context7"):
    """Seed a library entry under HOME/.agent-toolkit/mcps/ (the real library root)."""
    library = home / ".agent-toolkit" / "mcps"
    d = library / slug
    d.mkdir(parents=True)
    (d / "config.json").write_text('{"type":"stdio","command":"npx","args":["-y","ctx7@9.9.9"]}\n')
    (d / "README.md").write_text(f"# {slug}\n")
    (library / f"{slug}.toolkit.yaml").write_text(
        f"name: {slug}\ndescription: x.\ntransport: stdio\ninstall_method: npx\nresolved_version: 9.9.9\n"
    )


def test_mcp_group_registered():
    result = CliRunner().invoke(main, ["mcp", "--help"])
    assert result.exit_code == 0
    assert "install" in result.output
    assert "uninstall" in result.output


def test_mcp_install_project_claude(tmp_path, monkeypatch):
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    result = CliRunner().invoke(
        main, ["mcp", "install", "context7", "--harness", "claude-code", "-p"],
    )
    assert result.exit_code == 0, result.output
    doc = json.loads((project / ".mcp.json").read_text())
    assert "context7" in doc["mcpServers"]
```

> **Note:** there is NO toolkit-repo resolution in this kind — `_repo_resolution.py` is untouched. The library root is `Path.home()/".agent-toolkit"/"mcps"`, so tests control it entirely via `monkeypatch.setenv("HOME", …)` (Path.home() honours `HOME` on POSIX). `Path.home()` is called at verb runtime (never at import time) so the monkeypatch always lands.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli_mcp.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/commands/mcp src/agent_toolkit_cli/cli.py tests/test_cli_mcp.py
git commit -m "feat(mcp): CLI command group (add/install/uninstall/remove/update/list/status/doctor)"
```

---

## Task 9: Round-trip + both-scope CLI guard tests (the project-memory mandate)

**Files:**
- Test: `tests/test_cli_mcp.py` (extend)

Project memory: v3 install machinery has **repeatedly shipped silently-broken global-scope / orphan paths with green CI** because tests only covered one scope or only the happy install (never the uninstall round-trip). This task makes that impossible to repeat for MCP. These tests are the gate; they must be RED before the facade is trusted and GREEN after.

Also covered here: an **`update` flow test** — monkeypatch the version-resolution helper to return a bumped version, run `mcp update <slug>`, assert the library entry's `config.json` args + sidecar `resolved_version` were rewritten, every locked harness's installed entry shows the new version (re-upserted), the lock `pin` refreshed, and output contains `old → new`. A second case: resolver returns the same version AND projections match the entry → no writes, output `up to date`. A third case (the cross-scope catch-up trap): seed the library entry at 1.5.0 but a scope lock/projection at 1.4.2, resolver returns 1.5.0 (registry == entry, no entry rewrite) → update MUST still re-upsert the stale projections and refresh pins (reconciliation 2 runs independently of reconciliation 1). And an **`add` resolution-failure test** — monkeypatch the resolver to raise, assert the entry is stored floating (no version in args, no `resolved_version`) with a loud note, exit 0.

- [ ] **Step 1: Write the round-trip + both-scope tests**

Append to `tests/test_cli_mcp.py`:

```python
import pytest


@pytest.mark.parametrize("scope_flag, scope_name", [("-g", "global"), ("-p", "project")])
def test_install_uninstall_round_trip_both_scopes(tmp_path, monkeypatch, scope_flag, scope_name):
    """install → uninstall leaves the harness config with NO managed entry, at BOTH scopes."""
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    runner = CliRunner()

    r1 = runner.invoke(main, ["mcp", "install", "context7", "--harness", "claude-code", scope_flag])
    assert r1.exit_code == 0, r1.output

    # Determine the target file for this scope
    target = (tmp_path / ".claude.json") if scope_name == "global" else (project / ".mcp.json")
    assert "context7" in json.loads(target.read_text())["mcpServers"]

    r2 = runner.invoke(main, ["mcp", "uninstall", "context7", "--harness", "claude-code", scope_flag])
    assert r2.exit_code == 0, r2.output
    assert "context7" not in json.loads(target.read_text())["mcpServers"]


@pytest.mark.parametrize("scope_flag, scope_name", [("-g", "global"), ("-p", "project")])
def test_install_all_four_harnesses_round_trip(tmp_path, monkeypatch, scope_flag, scope_name):
    """All four adapters install AND fully uninstall at both scopes (no orphan projections)."""
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)
    runner = CliRunner()

    r1 = runner.invoke(main, ["mcp", "install", "context7", scope_flag])  # default = all four
    assert r1.exit_code == 0, r1.output

    r2 = runner.invoke(main, ["mcp", "uninstall", "context7", scope_flag])
    assert r2.exit_code == 0, r2.output

    # No harness config should still hold the managed entry.
    from agent_toolkit_cli.mcp_adapters import get_adapter
    home = tmp_path
    proj = None if scope_name == "global" else project
    for h in ("claude-code", "codex", "opencode", "pi"):
        assert not get_adapter(h).is_installed(
            "context7", scope=scope_name, home=home, project=proj,
        ), f"{h} left an orphan projection at {scope_name} scope"

    # Lock has no residual entry
    from agent_toolkit_cli.mcp_lock import lock_path_for_scope, read_lock
    lock = read_lock(lock_path_for_scope(scope_name, home=home, project=proj))
    assert "context7" not in lock


@pytest.mark.parametrize("scope_flag, scope_name", [("-g", "global"), ("-p", "project")])
def test_uninstall_preserves_hand_rolled_neighbour(tmp_path, monkeypatch, scope_flag, scope_name):
    """A hand-rolled MCP in the same file survives our install+uninstall byte-for-byte."""
    _seed(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(project)

    target = (tmp_path / ".claude.json") if scope_name == "global" else (project / ".mcp.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"mcpServers": {"handrolled": {"command": "x"}}}, indent=2) + "\n")

    runner = CliRunner()
    runner.invoke(main, ["mcp", "install", "context7", "--harness", "claude-code", scope_flag])
    runner.invoke(main, ["mcp", "uninstall", "context7", "--harness", "claude-code", scope_flag])

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

## Task 10: Full suite + real-library smoke

**Files:** none (verification task)

- [ ] **Step 1: Run the full unit suite**

Run: `uv run pytest -q`
Expected: PASS, no regressions in existing kinds.

- [ ] **Step 2: Run any bats CLI tests if present**

Run: `[ -d tests/bats ] && bats tests/bats || echo "no bats suite"`
Expected: PASS or "no bats suite".

- [ ] **Step 3: End-to-end smoke against the real library (`~/.agent-toolkit/mcps/`)**

```bash
uv run agent-toolkit-cli mcp add context7 --npx @upstash/context7-mcp   # authors ~/.agent-toolkit/mcps/context7/ + resolves the current version
uv run agent-toolkit-cli mcp list -g
uv run agent-toolkit-cli mcp install context7 --harness claude-code -p
cat ./.mcp.json
uv run agent-toolkit-cli mcp update context7
uv run agent-toolkit-cli mcp uninstall context7 --harness claude-code -p
cat ./.mcp.json
```

Expected: `add` authors the entry with a resolved version visible in the output; `list` shows `context7` with its version; install adds `mcpServers.context7` to `./.mcp.json` with loud `→ writing` / `✓ wrote` lines; `update` reports up-to-date or a version bump; uninstall removes it leaving `{"mcpServers": {}}`. **Important:** the smoke entry lands in the REAL `~/.agent-toolkit/mcps/` — fine to keep (it is a real, useful entry) or `rm -r` after. Also: this writes into the agent-toolkit-cli repo's own `.mcp.json` (gitignored) — verify it does not get committed.

- [ ] **Step 4: Commit (if any fixes were needed)**

```bash
git add -A && git commit -m "fix(mcp): address full-suite + real-library smoke findings"
```

(Skip if nothing changed.)

---

## Task 11: Packaged-resource (wheel) guard

**Files:**
- Test: `tests/test_mcp_wheel.py`

Project memory (#305): a kind once read repo files via `parents[N]` and crashed on every wheel install while CI stayed green (it only ran from the source tree). MCP derives its library root from `home`, never relative-to-`__file__`, so it should be immune — this test PROVES it by running the built wheel from outside the repo.

- [ ] **Step 1: Write the wheel test**

Create `tests/test_mcp_wheel.py`:

```python
"""Guard: the mcp command group works from a built wheel, run outside the repo.

Mirrors the #305 packaged-resource regression guard. Follows the
tests/test_cli/test_instructions_packaging.py skip policy: skip ONLY when uv
is absent (via the _uv helper, never @pytest.mark.skipif) — a build/install
that actually runs and FAILS must be a hard failure, never a skip-green.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def _uv(*args: str, **kwargs):
    """Run a uv command; skip the test only if uv itself is unavailable."""
    if shutil.which("uv") is None:
        pytest.skip("uv not available")
    return subprocess.run(["uv", *args], check=True, **kwargs)


def test_mcp_install_from_wheel(tmp_path):
    # Build the wheel
    dist = tmp_path / "dist"
    _uv("build", "--wheel", "-o", str(dist), cwd=REPO)
    wheel = next(dist.glob("*.whl"))

    # Install into an isolated venv OUTSIDE the repo tree
    venv = tmp_path / "venv"
    _uv("venv", str(venv))
    bin_dir = venv / ("Scripts" if (venv / "Scripts").exists() else "bin")
    _uv("pip", "install", "--python", str(bin_dir / "python"), str(wheel))

    # Seed a library entry under the isolated HOME, entirely outside the repo
    library = tmp_path / ".agent-toolkit" / "mcps"
    d = library / "demo"
    d.mkdir(parents=True)
    (d / "config.json").write_text('{"type":"stdio","command":"npx","args":["-y","demo@1.0.0"]}\n')
    (d / "README.md").write_text("# demo\n")
    (library / "demo.toolkit.yaml").write_text(
        "name: demo\ndescription: x.\ntransport: stdio\ninstall_method: npx\nresolved_version: 1.0.0\n"
    )
    project = tmp_path / "proj"
    project.mkdir()

    env = {"HOME": str(tmp_path), "PATH": str(bin_dir)}
    import os
    env = {**os.environ, **env}
    r = subprocess.run(
        [str(bin_dir / "agent-toolkit-cli"), "mcp", "install", "demo", "--harness", "claude-code", "-p"],
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
- **MCPs** — `agent-toolkit-cli mcp add <slug> --npx|--uvx|--docker|--url|--local` authors a
  library entry (version auto-resolved for transparency); `mcp install <slug>` projects it into
  Claude / Codex / OpenCode / Pi by surgically editing each harness's native
  config (manage-by-name, never file ownership; loud atomic writes). `list`,
  `status`, `uninstall`, `remove`, `update` (re-resolve the version + re-project),
  and a read-only `doctor` (orphans, structural drift, env-name presence) are
  supported. Drift `fix`, dry-run `diff`, git-clone-and-build sources, library
  sync/`push`, and the TUI MCPs section land in follow-ups.
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
- Acceptance #3 unlink removes only named entry → Tasks 4/5/9. ✅ **with a recorded deviation:** neighbours are byte-equal for the TOML family only; the JSON family guarantees structural equality + preserved entry order (whole-document `json.dumps` re-serialisation makes byte-equality unachievable there — see Task 4 contract note #1).
- Acceptance #4 list shows install state → Task 8 `list_cmd` (MCP-only view; the cross-kind four-glyph integration is deferred with the TUI). ✅
- Acceptance #6 doctor reports drift / missing env → Task 8 `doctor_cmd`: orphans + **structural drift detection (spec Rule 4)** + env-name-only presence warnings, all read-only. ✅
- Acceptance #8 round-trip byte-equal with comments+unknown sections → Task 5 TOML test (byte-level); JSON family covered structurally per the Acceptance #3 deviation. ✅
- The empty-`{}` / absent-`.mcp.json` failure-mode notes (added 2026-06-07) → Task 4 normalisation tests. ✅
- **Deferred (explicitly out of scope, not gaps):** schema v1alpha2 bump (Acc #9), `diff` (Acc #5), `fix` (Acc #7), TUI (Acc #10), `--force` running-process guard. Recorded in "Out of scope".

**2. Placeholder scan:** No "TBD"/"handle edge cases"/"similar to Task N" — every code step has concrete code. The verb files in Task 8 beyond `install_cmd` are described by behaviour + "mirror the agent sibling" rather than full code; this is deliberate (they are thin and the agent sibling IS the concrete template the engineer reads in Step 1), but it is the one spot a builder must read siblings rather than copy-paste. Flagged here honestly.

**3. Type consistency:** `McpAsset` (library) / `McpAdapter` (Protocol) / `McpLockEntry` (lock) used consistently. `get_adapter(harness)` signature identical across base, install facade, and tests. `config_target(scope=, home=, project=)`, `install(slug, inner_config, scope=, home=, project=)`, `uninstall(slug, scope=, home=, project=)`, `is_installed(...)` — identical across `json_config`, `toml_config`, Protocol, facade, and tests. `scope_and_roots(global_, project, ctx_project, *, read_only=)` → 3-tuple, copied into `commands/mcp/_common.py` with the `mcps-lock.json` probe (verified against `commands/agent/_common.py:20` during critical review — the original plan's 4-tuple/`agent_paths` assumption was wrong and has been corrected in Tasks 6/8).

**One known soft spot the builder must resolve empirically:** the version-resolution subprocesses in `add`/`update` (`npm view`, the PyPI JSON API, `docker image inspect`) — exact output parsing and timeout behaviour can only be pinned against the real tools; the contract that matters is **best-effort, never blocking** (failure → floating + a loud note). `scope_and_roots` is no longer a soft spot (signature verified during critical review and pinned in Tasks 6/8); toolkit-repo resolution is no longer used at all (library root derives from home).

---

## Deferred / Open Questions

### From 2026-06-10 review (#329 critical review — deep tier)

> **Both questions RESOLVED by AJ, 2026-06-10, same session:**
> 1. ~~**Catalog → dedicated `ajanderson1/mcps` repo**~~ **SUPERSEDED same day** by the library model (AJ, mechanism discussion): entries live in a plain local **library at `~/.agent-toolkit/mcps/`** — not a repo clone, no prerequisite repo, no Task 0. `add` authors entries from source flags (`--npx`/`--uvx`/`--docker`/`--url`/`--local`) with best-effort version resolution (transparency, not enforcement); a new `update` verb re-resolves and re-projects; v1 sources exclude git-clone-and-build; `push`/cross-machine sync deferred (git-ify the library + skill-push `divergence()` pattern when needed).
> 2. **Lock → independent `McpLockEntry`, ALIGNED**: renamed `mcps-lock.json` (plural convention), versioned envelope (`"version": 1`), tolerant read reserving the bundle grouping field. Applied throughout Task 6. The intro's old "mcpPath on shared LockEntry" wording was the error; the independent-but-aligned shape is authoritative.
>
> Original entries kept below for the decision record.

1. **[P0 — BLOCKS Tasks 2 & 10 — RESOLVED, see above] Where does the MCP catalog live post-#341?** The plan and spec assume `~/GitHub/agent-toolkit/mcps/` holds ~20 entries shaped `mcps/<slug>/{config.json, README.md}` + `<slug>.toolkit.yaml` sidecars. Verified 2026-06-10: that directory holds exactly TWO full standalone server repos (`mcp_android/`, `mcp_pocketsmith/` — each with `.git`, `src/`, `pyproject.toml`), zero `config.json` files, zero sidecars. The repo also fails `_is_toolkit_repo()` (no `schemas/` dir), so `resolve_library_root()` cannot resolve it. Task 10's real-catalog smoke (`context7`, `playwright`, …) cannot pass against reality. Options include: (a) re-author catalog entries + markers in `agent-toolkit`, (b) a dedicated MCP catalog repo (consistent with the #341 per-category split), (c) per-server-repo metadata. Product decision required before Tasks 2/10 are executable. *(adversarial + feasibility reviewers, confidence 100)*

2. **[P1 — BLOCKS Task 6 — RESOLVED, see above] Lock model: independent `McpLockEntry` vs shared `LockEntry`/`KindBinding`.** Task 6 drafts a bespoke `McpLockEntry` + `{"mcps": {...}}` schema (no version field, no `sourceType`/`ref`/`sha`, filename `mcps-lock.json` breaking the plural convention). The bundle-composite ADR (`docs/solutions/architecture-patterns/clone-and-project-substrate-for-bundle-plugin-capability-2026-06-10.md`) plans "the lock gains a grouping field" ACROSS the per-kind lockfiles and lists MCP as bundle step 1 — a fifth lockfile with an incompatible schema cannot participate without special-casing. Counter-argument (coherence reviewer): MCP's record shape (a LIST of per-harness projections per slug, no canonical path) is genuinely different from the one-path-per-slug shape `LockEntry` assumes, so forcing the shared machinery may distort it. Decide: (a) keep independent entry but adopt `mcps-lock.json` naming + a version field + alignment hooks for the bundle grouping field, or (b) full `KindBinding` + shared `LockEntry` with the projection list in the v3 extras dict. *(coherence + adversarial reviewers, confidence 100 — genuine tradeoff)*
