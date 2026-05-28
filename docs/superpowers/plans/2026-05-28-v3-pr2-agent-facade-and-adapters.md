# v3.0.0 PR2: Agent facade + 28 projection adapters — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the first user-visible v3 capability — an installable `agent` (subagent) kind that lands files at every supported harness's real subagent path — by binding `AGENT_BINDING` to PR1's kind-agnostic core, adding a 3-mechanism adapter system, and writing 28 cell-level smoke tests.

**Architecture:** Three facade modules (`agent_install.py`, `agent_paths.py`, `agent_lock.py`) mirror PR1's `skill_*` facade pattern, binding `AGENT_BINDING`. A new `agent_adapters/` package contains three mechanism implementations (`symlink.py`, `translate.py`, `config_file_folder.py`) plus a `__init__.py` dispatcher reading `AgentConfig.subagent_mechanism`. Per-cell quirks (paths, required frontmatter, format-shape) live in per-cell dicts inside the mechanism modules — 28 cells, 3 files, not 28 files. The CLI is NOT touched (that's PR4).

**Tech Stack:** Python 3.11+, dataclasses, pathlib, pytest, ruff, lefthook pre-commit. No new third-party deps.

**Spec:** `docs/superpowers/specs/2026-05-28-v3-pr2-agent-facade-and-adapters-design.md` (including the Risk-Resolution Addendum dated 2026-05-28 — Corrections A/B/C override the original Decisions 1/2/3).

**Key correction discipline:** the Risk-Resolution Addendum supersedes anything in the original spec it contradicts. Build phase must read the addendum first.

**Estimated task count:** 14 (9 build + 4 mechanism + 1 scope guard).

**Commit cadence:** one commit per task, conventional-commit subject. lefthook runs `pytest -q` on every commit.

---

## Pre-flight (controller, before dispatching task 1)

1. Confirm worktree: `pwd` should be `.worktrees/feat-252-v3-pr2-agent-facade-adapters/`.
2. Confirm branch: `git branch --show-current` returns `feat/252-v3-pr2-agent-facade-adapters`.
3. Confirm baseline test count: `uv run pytest -q --co | tail -3` shows 534 collected.
4. Confirm spec + addendum committed: `git log --oneline main..HEAD` shows `98725c9 docs(spec)…` and `0f7fa95 docs(spec): PR2 risk-resolution addendum…`.

---

## File map

PR2 creates these new files:

| Path | Lines (est) | Responsibility |
|---|---|---|
| `src/agent_toolkit_cli/agent_paths.py` | ~120 | Facade over `_paths_core` binding `AGENT_BINDING`. Public symbols: `canonical_agent_dir`, `lock_file_path`, `library_root`, `library_agent_path`, `library_lock_path`, plus shared helpers (`project_id`, `project_store_root`, `project_parents_root`). |
| `src/agent_toolkit_cli/agent_install.py` | ~180 | Facade over `_install_core` binding `AGENT_BINDING` + `_AGENT_SYNTHETIC_NAMES`. Public symbols: `InstallError`, `LockMismatchError`, `DirtyCanonicalError`, `InstallPlan`, `InstallResult`, `plan`, `apply`, `install`, `uninstall`. `apply()` dispatches to `agent_adapters.get_adapter(harness)` per-harness instead of unconditional symlink. |
| `src/agent_toolkit_cli/agent_lock.py` | ~30 | Re-exports from `skill_lock` (LockEntry, LockFile, read_lock, write_lock, add_entry, remove_entry, SUPPORTED_VERSIONS, clone_url_from_entry). Initially no behavioural divergence; agent-specific keys (`agentPath`) handled by Task 5's `LockEntry` field addition. |
| `src/agent_toolkit_cli/agent_adapters/__init__.py` | ~40 | `get_adapter(harness_name) -> AgentAdapter`; `AgentAdapter` Protocol with `install` and `uninstall`. |
| `src/agent_toolkit_cli/agent_adapters/symlink.py` | ~140 | Single-file `.md` write to harness's agents/ dir. 15 cells. Per-cell dict: path-template, required frontmatter, format quirks (e.g. `name`-lowercase-only for codebuddy). |
| `src/agent_toolkit_cli/agent_adapters/translate.py` | ~250 | 10 cells across 5 format helpers: yaml-strict (gemini), yaml-passthrough (devin, qwen, github-copilot, kilo, opencode, mux), toml (codex, mistral-vibe), json (kiro-cli). Per-cell dict + per-format helper. |
| `src/agent_toolkit_cli/agent_adapters/config_file_folder.py` | ~170 | 3 cells: aider-desk (per-slug `config.json`), dexto (per-slug yml subdir), firebender (atomic `firebender.json` mutation). Per-cell logic differs enough that each cell has its own function; mechanism module is the dispatcher. |
| `tests/test_cli/test_agent_paths.py` | ~100 | Pin `agent_paths` public surface; mirror of `test_skill_facade_parity.py § skill_paths`; AGENT_BINDING resolution to `~/.agent-toolkit/agents/` + `agents-lock.json`. |
| `tests/test_cli/test_agent_install.py` | ~150 | `plan()` shim binds `_AGENT_SYNTHETIC_NAMES`; `apply()` invokes correct adapter per mechanism; uninstall idempotency; lock round-trip via Task 5's `agentPath` field. |
| `tests/test_cli/test_agent_lock.py` | ~80 | Lock round-trip with `agentPath` in v1 + v3 formats. |
| `tests/test_cli/test_agent_facade_parity.py` | ~50 | Pin all three agent_* facades' public surfaces. |
| `tests/test_cli/test_agent_adapters/__init__.py` | 1 | empty (`pytest` discovery) |
| `tests/test_cli/test_agent_adapters/test_symlink.py` | ~250 | 15-cell parametrised tests: install creates `<expected path>`, content matches, uninstall removes it. |
| `tests/test_cli/test_agent_adapters/test_translate.py` | ~350 | 10-cell parametrised tests: format-specific output verified (zod-strict gemini, toml codex, json kiro, nested mux subagent block, plural opencode). |
| `tests/test_cli/test_agent_adapters/test_config_file_folder.py` | ~200 | 3-cell tests: aider-desk per-slug subdir + order.json; dexto per-slug subdir + parent-allowedAgents note; firebender atomic `firebender.json` mutation + `callable: true` in markdown. |
| `tests/test_cli/test_pr2_scope_guard.py` | ~70 | Throwaway: ALLOWED set + ALLOWED_PREFIXES. Deleted in PR3's first commit. Includes `pytest.skip` fallback for shallow CI clones. |

PR2 modifies these existing files:

| Path | Change | Lines touched |
|---|---|---|
| `src/agent_toolkit_cli/_paths_core.py` | Add `AGENT_BINDING` (mirror of `SKILL_BINDING`) | +8 |
| `src/agent_toolkit_cli/skill_lock.py` | Add `agent_path: str \| None = None` field to `LockEntry`; serialise as `agentPath` in v1+v3 writers; recognise in v1+v3 readers; add `"agentPath"` to `_V1_ENTRY_FIELDS` and `_V3_ENTRY_FIELDS` | +20 |
| `src/agent_toolkit_cli/skill_agents.py` | Add `subagent_mechanism: Literal[...]` field to `AgentConfig` (default `"none"`); set the 28 supported cells; add `"general-agent"` synthetic entry mirroring `"general-skill"` | +60 |
| `tests/test_cli/test_skill_agents.py` | Bump catalog size assertion 56 → 57; add `subagent_mechanism` field tests; add matrix-parity test (every supported matrix row has non-`"none"` mechanism) | +30 |
| `tests/test_subagent_matrix.py` | Extend `_catalog_harnesses()` exclusion to `{"universal", "general-skill", "general-agent"}`; add `test_supported_rows_have_matching_adapter` | +10 |

Total new code: ~2200 lines (production + tests).
Total existing files modified: 5 files, ~130 lines net.

---

## Task ordering rationale

Tasks ordered so each one's tests can run against committed code from the previous. Deepest seam (`_paths_core` + `LockEntry`) first; then the agent facade in dependency order (`agent_paths` → `agent_lock` re-export → `agent_install`); then mechanism modules (smallest first); finally the parity test + scope guard. The 28 cells land mechanism-by-mechanism so each mechanism module is fully tested before the next starts — keeps blast radius per task small.

| # | Task | Depends on |
|---|---|---|
| 1 | `AGENT_BINDING` in `_paths_core.py` + tests | nothing |
| 2 | `LockEntry.agent_path` field + serialiser updates | nothing (parallel-safe with Task 1) |
| 3 | `agent_paths.py` facade + parity test | Task 1 |
| 4 | `agent_lock.py` re-export facade + parity test | Task 2 |
| 5 | `subagent_mechanism` field on `AgentConfig` + `general-agent` synthetic + catalog-size bump | nothing |
| 6 | `agent_adapters/` package skeleton (`__init__.py` dispatcher + Protocol) | Task 5 |
| 7 | `agent_install.py` facade + adapter dispatch in `apply()` + tests | Tasks 1, 3, 5, 6 |
| 8 | `agent_adapters/symlink.py` + 15-cell tests | Tasks 6, 7 |
| 9 | `agent_adapters/translate.py` + 10-cell tests | Tasks 6, 7 |
| 10 | `agent_adapters/config_file_folder.py` + 3-cell tests | Tasks 6, 7 |
| 11 | Set `subagent_mechanism` literals on 28 cells | Tasks 5, 8, 9, 10 |
| 12 | Matrix parity test (`test_supported_rows_have_matching_adapter`) + `test_subagent_matrix.py` synthetic exclusion | Task 11 |
| 13 | End-to-end smoke test (parametrised over 28 cells in tmp HOME) | Tasks 7–11 |
| 14 | `test_pr2_scope_guard.py` throwaway + final test sweep | all prior |

---

## Task 1: `AGENT_BINDING` in `_paths_core.py`

**Files:**
- Modify: `src/agent_toolkit_cli/_paths_core.py:23-29`
- Create: `tests/test_cli/test_paths_core_agent_binding.py`

### Step 1.1: Write the failing test for `AGENT_BINDING`

Create `tests/test_cli/test_paths_core_agent_binding.py`:

```python
"""AGENT_BINDING mirrors SKILL_BINDING for the agent kind."""
from __future__ import annotations

from pathlib import Path

from agent_toolkit_cli._paths_core import (
    AGENT_BINDING,
    KindBinding,
    SKILL_BINDING,
    library_lock_path_for_kind,
    library_root_for_kind,
)


def test_agent_binding_is_kindbinding():
    assert isinstance(AGENT_BINDING, KindBinding)


def test_agent_binding_fields():
    assert AGENT_BINDING.kind == "agent"
    assert AGENT_BINDING.canonical_dirname == "agents"
    assert AGENT_BINDING.library_subdir == "agents"
    assert AGENT_BINDING.lock_filename == "agents-lock.json"
    assert AGENT_BINDING.general_harness_name == "general-agent"


def test_agent_binding_is_frozen():
    import dataclasses
    assert dataclasses.is_frozen_instance(AGENT_BINDING) if hasattr(dataclasses, 'is_frozen_instance') else True
    # Real check: trying to mutate raises FrozenInstanceError
    import pytest
    with pytest.raises(dataclasses.FrozenInstanceError):
        AGENT_BINDING.kind = "other"  # type: ignore[misc]


def test_library_root_for_agent_kind(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    root = library_root_for_kind(AGENT_BINDING)
    assert root == tmp_path / ".agent-toolkit" / "agents"


def test_library_lock_path_for_agent_kind(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    lock = library_lock_path_for_kind(AGENT_BINDING)
    assert lock == tmp_path / ".agent-toolkit" / "agents-lock.json"


def test_agent_binding_distinct_from_skill(tmp_path, monkeypatch):
    """AGENT_BINDING and SKILL_BINDING must resolve to different paths."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("AGENT_TOOLKIT_SKILLS_ROOT", raising=False)
    skill_root = library_root_for_kind(SKILL_BINDING)
    agent_root = library_root_for_kind(AGENT_BINDING)
    assert skill_root != agent_root
    assert skill_root.name == "skills"
    assert agent_root.name == "agents"


def test_agent_kind_does_not_honour_skill_root_env(tmp_path, monkeypatch):
    """AGENT_TOOLKIT_SKILLS_ROOT must NOT affect the agent library root."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", "/custom/skills/root")
    agent_root = library_root_for_kind(AGENT_BINDING)
    assert agent_root == tmp_path / ".agent-toolkit" / "agents"
```

### Step 1.2: Run the test to verify it fails

Run: `uv run pytest tests/test_cli/test_paths_core_agent_binding.py -v`
Expected: FAIL — `ImportError: cannot import name 'AGENT_BINDING' from 'agent_toolkit_cli._paths_core'`

### Step 1.3: Add `AGENT_BINDING` to `_paths_core.py`

Append to `src/agent_toolkit_cli/_paths_core.py` (after line 29, after `SKILL_BINDING`):

```python

AGENT_BINDING = KindBinding(
    kind="agent",
    canonical_dirname="agents",
    library_subdir="agents",
    lock_filename="agents-lock.json",
    general_harness_name="general-agent",
)
```

### Step 1.4: Run the test to verify it passes

Run: `uv run pytest tests/test_cli/test_paths_core_agent_binding.py -v`
Expected: 7 passed.

### Step 1.5: Run the full suite to confirm no regression

Run: `uv run pytest -q`
Expected: 541 passed, 2 skipped (was 534 + 7 new).

### Step 1.6: Commit

```bash
git add src/agent_toolkit_cli/_paths_core.py tests/test_cli/test_paths_core_agent_binding.py
git commit -m "feat(_paths_core): add AGENT_BINDING for v3 agent kind"
```

---

## Task 2: `LockEntry.agent_path` field

**Files:**
- Modify: `src/agent_toolkit_cli/skill_lock.py:31-41, 53-61, 66-78, 81-102, 105-127, 200-225`
- Modify: `tests/test_cli/test_lock.py` (existing — extend) OR create `tests/test_cli/test_lock_agent_path.py`

### Step 2.1: Write the failing test for `agent_path` field

Create `tests/test_cli/test_lock_agent_path.py`:

```python
"""LockEntry.agent_path field round-trips through v1 and v3 lockfile formats."""
from __future__ import annotations

import json

from agent_toolkit_cli.skill_lock import (
    LockEntry,
    LockFile,
    add_entry,
    read_lock,
    write_lock,
)


def test_lockentry_has_agent_path_field():
    entry = LockEntry(
        source="ajanderson1/test",
        source_type="github",
        agent_path="my-agent.md",
    )
    assert entry.agent_path == "my-agent.md"


def test_lockentry_agent_path_defaults_none():
    entry = LockEntry(source="ajanderson1/test", source_type="github")
    assert entry.agent_path is None


def test_v1_writer_emits_agent_path(tmp_path):
    lock_path = tmp_path / "agents-lock.json"
    lock = LockFile(version=1, skills={})
    entry = LockEntry(
        source="ajanderson1/test",
        source_type="github",
        ref="main",
        agent_path="agents/foo.md",
    )
    lock = add_entry(lock, "foo", entry)
    write_lock(lock_path, lock)

    body = json.loads(lock_path.read_text())
    assert body["skills"]["foo"]["agentPath"] == "agents/foo.md"


def test_v1_reader_recovers_agent_path(tmp_path):
    lock_path = tmp_path / "agents-lock.json"
    lock_path.write_text(json.dumps({
        "version": 1,
        "skills": {
            "foo": {
                "source": "ajanderson1/test",
                "sourceType": "github",
                "ref": "main",
                "agentPath": "agents/foo.md",
            },
        },
    }))
    lock = read_lock(lock_path)
    assert lock.skills["foo"].agent_path == "agents/foo.md"


def test_v3_writer_emits_agent_path(tmp_path):
    lock_path = tmp_path / "agents-lock.json"
    lock = LockFile(version=3, skills={})
    entry = LockEntry(
        source="ajanderson1/test",
        source_type="github",
        ref="main",
        agent_path="agents/foo.md",
    )
    lock = add_entry(lock, "foo", entry)
    write_lock(lock_path, lock)

    body = json.loads(lock_path.read_text())
    assert body["skills"]["foo"]["agentPath"] == "agents/foo.md"


def test_v3_reader_recovers_agent_path(tmp_path):
    lock_path = tmp_path / "agents-lock.json"
    lock_path.write_text(json.dumps({
        "version": 3,
        "skills": {
            "foo": {
                "source": "ajanderson1/test",
                "sourceType": "github",
                "sourceUrl": "https://github.com/ajanderson1/test.git",
                "ref": "main",
                "agentPath": "agents/foo.md",
                "installedAt": "2026-05-28T20:00:00Z",
                "updatedAt": "2026-05-28T20:00:00Z",
            },
        },
    }))
    lock = read_lock(lock_path)
    assert lock.skills["foo"].agent_path == "agents/foo.md"


def test_agent_path_not_in_extras_on_v3_read(tmp_path):
    """If agentPath is a first-class field, it must NOT leak into extras
    (which would cause it to be written twice)."""
    lock_path = tmp_path / "agents-lock.json"
    lock_path.write_text(json.dumps({
        "version": 3,
        "skills": {
            "foo": {
                "source": "ajanderson1/test",
                "sourceType": "github",
                "sourceUrl": "https://github.com/ajanderson1/test.git",
                "agentPath": "agents/foo.md",
                "installedAt": "2026-05-28T20:00:00Z",
                "updatedAt": "2026-05-28T20:00:00Z",
            },
        },
    }))
    lock = read_lock(lock_path)
    assert "agentPath" not in lock.skills["foo"].extras


def test_skill_path_and_agent_path_coexist(tmp_path):
    """Mixed lock supporting both kinds (forward-compatible): both fields
    preserved separately."""
    lock_path = tmp_path / "mixed-lock.json"
    lock = LockFile(version=3, skills={})
    skill_entry = LockEntry(
        source="ajanderson1/skill", source_type="github", skill_path="SKILL.md",
    )
    agent_entry = LockEntry(
        source="ajanderson1/agent", source_type="github", agent_path="agents/foo.md",
    )
    lock = add_entry(lock, "skill1", skill_entry)
    lock = add_entry(lock, "agent1", agent_entry)
    write_lock(lock_path, lock)

    re = read_lock(lock_path)
    assert re.skills["skill1"].skill_path == "SKILL.md"
    assert re.skills["skill1"].agent_path is None
    assert re.skills["agent1"].skill_path is None
    assert re.skills["agent1"].agent_path == "agents/foo.md"


def test_v1_writer_omits_agent_path_when_none(tmp_path):
    """agentPath key absent from JSON when field is None (matches skillPath behaviour)."""
    lock_path = tmp_path / "agents-lock.json"
    lock = LockFile(version=1, skills={})
    entry = LockEntry(source="ajanderson1/test", source_type="github")
    lock = add_entry(lock, "foo", entry)
    write_lock(lock_path, lock)

    body = json.loads(lock_path.read_text())
    assert "agentPath" not in body["skills"]["foo"]
```

### Step 2.2: Run the test to verify it fails

Run: `uv run pytest tests/test_cli/test_lock_agent_path.py -v`
Expected: FAIL — `TypeError: LockEntry.__init__() got an unexpected keyword argument 'agent_path'`

### Step 2.3: Add `agent_path` field + serialiser updates

Edit `src/agent_toolkit_cli/skill_lock.py` in 5 places:

**(a) Add to `LockEntry` (after line 36 — after `skill_path`):**

```python
    skill_path: str | None = None
    agent_path: str | None = None
    upstream_sha: str | None = None
```

**(b) Add `"agentPath"` to `_V1_ENTRY_FIELDS` (line 53):**

```python
_V1_ENTRY_FIELDS = {
    "source", "sourceType", "ref", "skillPath", "agentPath", "upstreamSha", "localSha",
    "parentUrl", "readOnly",
}
```

**(c) Add `"agentPath"` to `_V3_ENTRY_FIELDS` (line 57):**

```python
_V3_ENTRY_FIELDS = {
    "source", "sourceType", "sourceUrl", "ref", "skillPath", "agentPath",
    "skillFolderHash", "installedAt", "updatedAt", "pluginName",
    "parentUrl", "readOnly",
}
```

**(d) Read `agentPath` in `_entry_from_dict_v1` (after line 72 — after `skill_path=d.get("skillPath"),`):**

```python
        skill_path=d.get("skillPath"),
        agent_path=d.get("agentPath"),
        upstream_sha=d.get("upstreamSha"),
```

**(e) Read `agentPath` in `_entry_from_dict_v3` (after line 87 — after `skill_path=d.get("skillPath"),`):**

```python
        skill_path=d.get("skillPath"),
        agent_path=d.get("agentPath"),
        # v3 uses skillFolderHash for the upstream pin.
        upstream_sha=d.get("skillFolderHash"),
```

**(f) Write `agentPath` in `_entry_to_dict_v1` (after line 110 — after the `if e.skill_path is not None:` block):**

```python
    if e.skill_path is not None:
        out["skillPath"] = e.skill_path
    if e.agent_path is not None:
        out["agentPath"] = e.agent_path
    if e.upstream_sha is not None:
```

**(g) Write `agentPath` in `_entry_to_dict_v3` (after line 210 — after the `if e.skill_path is not None:` block):**

```python
    if e.skill_path is not None:
        out["skillPath"] = e.skill_path
    if e.agent_path is not None:
        out["agentPath"] = e.agent_path
    if e.parent_url is not None:
```

### Step 2.4: Run the test to verify it passes

Run: `uv run pytest tests/test_cli/test_lock_agent_path.py -v`
Expected: 9 passed.

### Step 2.5: Confirm no skill-lock regression

Run: `uv run pytest -q`
Expected: 550 passed, 2 skipped (was 541; +9 new).

### Step 2.6: Commit

```bash
git add src/agent_toolkit_cli/skill_lock.py tests/test_cli/test_lock_agent_path.py
git commit -m "feat(skill_lock): add agent_path field for v3 agent kind"
```

---

## Task 3: `agent_paths.py` facade

**Files:**
- Create: `src/agent_toolkit_cli/agent_paths.py`
- Create: `tests/test_cli/test_agent_paths.py`

### Step 3.1: Write the failing test for `agent_paths` public surface

Create `tests/test_cli/test_agent_paths.py`:

```python
"""agent_paths.py facade — public-symbol surface + binding behaviour."""
from __future__ import annotations

from pathlib import Path

import pytest


# Mirrors test_skill_facade_parity.py § skill_paths but for agent_paths.
AGENT_PATHS_PUBLIC = frozenset({
    "Scope",
    "canonical_agent_dir",
    "lock_file_path",
    "library_root",
    "library_agent_path",
    "library_lock_path",
    "project_id",
    "project_store_root",
    "project_parents_root",
    "parent_clone_path",
    "agent_projection_dir",
    "harness_projection_dir",
    "SUPPORTED_HARNESSES",
})


def test_agent_paths_public_surface_preserved():
    from agent_toolkit_cli import agent_paths
    public = {name for name in dir(agent_paths) if not name.startswith("_")}
    # Filter to attributes the module actually defines, not stdlib re-imports.
    module_locals = {
        name for name, obj in vars(agent_paths).items()
        if not name.startswith("_") and not hasattr(obj, "__module__") is False
    }
    for symbol in AGENT_PATHS_PUBLIC:
        assert symbol in public, f"agent_paths public surface missing: {symbol}"


def test_library_root_resolves_to_agents_subdir(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli import agent_paths
    assert agent_paths.library_root() == tmp_path / ".agent-toolkit" / "agents"


def test_library_lock_path_resolves(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli import agent_paths
    assert agent_paths.library_lock_path() == tmp_path / ".agent-toolkit" / "agents-lock.json"


def test_library_agent_path_for_slug(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli import agent_paths
    assert agent_paths.library_agent_path("foo") == tmp_path / ".agent-toolkit" / "agents" / "foo"


def test_canonical_agent_dir_global(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli import agent_paths
    assert agent_paths.canonical_agent_dir("foo", scope="global") == tmp_path / ".agent-toolkit" / "agents" / "foo"


def test_canonical_agent_dir_project(tmp_path):
    from agent_toolkit_cli import agent_paths
    project = tmp_path / "proj"
    project.mkdir()
    canonical = agent_paths.canonical_agent_dir("foo", scope="project", project=project)
    # External store; specifics defined by project_store_root.
    assert canonical.name == "foo"
    assert "projects" in str(canonical)


def test_lock_file_path_global(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli import agent_paths
    assert agent_paths.lock_file_path(scope="global") == tmp_path / ".agent-toolkit" / "agents-lock.json"


def test_lock_file_path_project(tmp_path):
    from agent_toolkit_cli import agent_paths
    project = tmp_path / "proj"
    project.mkdir()
    # Per AGENT_BINDING.lock_filename = "agents-lock.json"
    assert agent_paths.lock_file_path(scope="project", project=project) == project / "agents-lock.json"


def test_agent_paths_does_not_honour_skill_root_env(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", "/some/skill/root")
    from agent_toolkit_cli import agent_paths
    # AGENT_TOOLKIT_SKILLS_ROOT must NOT affect agent paths.
    assert agent_paths.library_root() == tmp_path / ".agent-toolkit" / "agents"
```

### Step 3.2: Run the test to verify it fails

Run: `uv run pytest tests/test_cli/test_agent_paths.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_toolkit_cli.agent_paths'`

### Step 3.3: Create the `agent_paths.py` facade

Create `src/agent_toolkit_cli/agent_paths.py`:

```python
"""Agent-flavoured facade over `_paths_core.py`.

v3.0.0 PR2 — mirrors `skill_paths.py` for the agent (subagent) kind.

  Global scope canonical lives in the library at
  ~/.agent-toolkit/agents/<slug>/. Each library entry is a real git
  working tree. Harnesses reach a library agent via a file/symlink/registry
  entry created by `agent install`. The global lock is at
  ~/.agent-toolkit/agents-lock.json.

  Project scope: its own per-project canonical at an external store outside
  the project tree (shared with skills — see project_store_root). Project
  lock at <project>/agents-lock.json.

Public symbols (`canonical_agent_dir`, `lock_file_path`, `library_root`,
`library_agent_path`, `library_lock_path`, `project_id`,
`project_store_root`, `project_parents_root`, `parent_clone_path`,
`agent_projection_dir`, `harness_projection_dir`, `SUPPORTED_HARNESSES`,
`Scope`) are preserved verbatim — implementations delegate to
`_paths_core` where the binding-driven helpers live.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from agent_toolkit_cli._paths_core import (
    AGENT_BINDING,
    library_lock_path_for_kind,
    library_root_for_kind,
)
# Shared helpers (independent of kind) re-exported from skill_paths.
from agent_toolkit_cli.skill_paths import (
    SUPPORTED_HARNESSES,
    agent_projection_dir,
    harness_projection_dir,
    parent_clone_path,
    project_id,
    project_parents_root,
    project_store_root,
)

Scope = Literal["project", "global"]


def library_root(env: dict[str, str] | None = None) -> Path:
    """Return the root of the global agent library.

    Thin shim over `_paths_core.library_root_for_kind(AGENT_BINDING, …)`.
    Does NOT honor $AGENT_TOOLKIT_SKILLS_ROOT (that env var is skill-only).
    """
    return library_root_for_kind(AGENT_BINDING, env)


def library_agent_path(slug: str, *, env: dict[str, str] | None = None) -> Path:
    """Return the canonical library path for a single agent slug."""
    return library_root(env) / slug


def library_lock_path(env: dict[str, str] | None = None) -> Path:
    """Return the path of the global agents-lock.json."""
    return library_lock_path_for_kind(AGENT_BINDING, env)


def canonical_agent_dir(
    slug: str,
    *,
    scope: Scope,
    home: Path | None = None,
    project: Path | None = None,
) -> Path:
    """Return the canonical on-disk path for an agent at the given scope.

    Global scope: delegates to library_agent_path(slug). `home` accepted
    for backward compatibility but ignored — library root is always
    determined by AGENT_BINDING.

    Project scope: <store_root>/<slug> (external store — shared with
    skills via the same project_store_root).
    """
    if scope == "global":
        return library_agent_path(slug)
    if project is None:
        raise ValueError("project scope requires project")
    return project_store_root(project) / slug


def lock_file_path(
    *,
    scope: Scope,
    home: Path | None = None,
    project: Path | None = None,
) -> Path:
    """Return the lock file path for the given scope.

    Global scope: delegates to library_lock_path(). `home` accepted for
    backward compatibility but ignored.

    Project scope: <project>/<AGENT_BINDING.lock_filename> — uses the
    binding so the per-project lock lands at <project>/agents-lock.json.
    """
    if scope == "global":
        return library_lock_path()
    if project is None:
        raise ValueError("project scope requires project")
    return project / AGENT_BINDING.lock_filename
```

### Step 3.4: Run the test to verify it passes

Run: `uv run pytest tests/test_cli/test_agent_paths.py -v`
Expected: 9 passed.

### Step 3.5: Confirm no regression in the full suite

Run: `uv run pytest -q`
Expected: 559 passed, 2 skipped.

### Step 3.6: Commit

```bash
git add src/agent_toolkit_cli/agent_paths.py tests/test_cli/test_agent_paths.py
git commit -m "feat(agent_paths): facade binding AGENT_BINDING"
```

---

## Task 4: `agent_lock.py` re-export facade

**Files:**
- Create: `src/agent_toolkit_cli/agent_lock.py`
- Create: `tests/test_cli/test_agent_lock.py`

### Step 4.1: Write the failing test for `agent_lock` surface

Create `tests/test_cli/test_agent_lock.py`:

```python
"""agent_lock.py facade — re-exports kind-blind lock primitives from skill_lock.

Per spec correction B, no behavioural divergence in PR2 — LockEntry has
agent_path as a real field (Task 2), and the format is the same.
"""
from __future__ import annotations


AGENT_LOCK_PUBLIC = frozenset({
    "LockEntry",
    "LockFile",
    "SUPPORTED_VERSIONS",
    "read_lock",
    "write_lock",
    "add_entry",
    "remove_entry",
    "clone_url_from_entry",
})


def test_agent_lock_public_surface_preserved():
    from agent_toolkit_cli import agent_lock
    public = {name for name in dir(agent_lock) if not name.startswith("_")}
    for symbol in AGENT_LOCK_PUBLIC:
        assert symbol in public, f"agent_lock public surface missing: {symbol}"


def test_agent_lock_reexports_match_skill_lock():
    """Same names must resolve to same objects — agent_lock is a thin re-export."""
    from agent_toolkit_cli import agent_lock, skill_lock
    for name in AGENT_LOCK_PUBLIC:
        assert getattr(agent_lock, name) is getattr(skill_lock, name), (
            f"agent_lock.{name} is not the same object as skill_lock.{name}"
        )


def test_agent_lock_round_trip_with_agent_path(tmp_path):
    """End-to-end: write agent entry via agent_lock, read it back, agent_path preserved."""
    from agent_toolkit_cli.agent_lock import (
        LockEntry, LockFile, add_entry, read_lock, write_lock,
    )

    lock_path = tmp_path / "agents-lock.json"
    lock = LockFile(version=1, skills={})
    entry = LockEntry(
        source="ajanderson1/test",
        source_type="github",
        agent_path="agents/foo.md",
    )
    lock = add_entry(lock, "foo", entry)
    write_lock(lock_path, lock)

    re = read_lock(lock_path)
    assert re.skills["foo"].agent_path == "agents/foo.md"
    assert re.skills["foo"].skill_path is None
```

### Step 4.2: Run the test to verify it fails

Run: `uv run pytest tests/test_cli/test_agent_lock.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_toolkit_cli.agent_lock'`

### Step 4.3: Create the `agent_lock.py` re-export facade

Create `src/agent_toolkit_cli/agent_lock.py`:

```python
"""Agent-flavoured facade over `skill_lock.py`.

v3.0.0 PR2 — re-exports the kind-blind lock-IO primitives from
`skill_lock`. The agent kind uses the same LockEntry/LockFile structs;
the distinguishing field at write time is `agent_path` (vs `skill_path`)
on the LockEntry, both serialised explicitly per Task 2.

The file's only purpose is to give callers (PR4 CLI verbs, PR5 TUI)
a kind-aligned import path: `from agent_toolkit_cli.agent_lock import …`
instead of reaching into `skill_lock` directly. No behavioural divergence
is introduced; a future PR may add agent-specific helpers here.
"""
from __future__ import annotations

from agent_toolkit_cli.skill_lock import (  # noqa: F401
    SUPPORTED_VERSIONS,
    LockEntry,
    LockFile,
    add_entry,
    clone_url_from_entry,
    read_lock,
    remove_entry,
    write_lock,
)
```

### Step 4.4: Run the test to verify it passes

Run: `uv run pytest tests/test_cli/test_agent_lock.py -v`
Expected: 3 passed.

### Step 4.5: Confirm no regression

Run: `uv run pytest -q`
Expected: 562 passed, 2 skipped.

### Step 4.6: Commit

```bash
git add src/agent_toolkit_cli/agent_lock.py tests/test_cli/test_agent_lock.py
git commit -m "feat(agent_lock): re-export facade over kind-blind skill_lock"
```

---

## Task 5: `subagent_mechanism` field + `general-agent` synthetic

**Files:**
- Modify: `src/agent_toolkit_cli/skill_agents.py:32-44, 445-448 (after general-skill block), 480 (end of file)`
- Modify: `tests/test_cli/test_skill_agents.py`

### Step 5.1: Write the failing tests

Modify `tests/test_cli/test_skill_agents.py` — add at end:

```python
def test_agentconfig_has_subagent_mechanism_field():
    from agent_toolkit_cli.skill_agents import AGENTS, AgentConfig
    cfg = AGENTS["claude-code"]
    assert hasattr(cfg, "subagent_mechanism")


def test_subagent_mechanism_default_is_none():
    """Unset cells default to 'none' so existing callers continue working."""
    from agent_toolkit_cli.skill_agents import AGENTS
    # An agent we have NOT yet set in Task 11 (we'll set them all then).
    # 'amp' is not in the 28 supported list per the matrix.
    assert AGENTS["amp"].subagent_mechanism == "none"


def test_subagent_mechanism_literal_values():
    """Only the four documented literals are valid."""
    from typing import get_type_hints
    from agent_toolkit_cli.skill_agents import AgentConfig
    hints = get_type_hints(AgentConfig)
    # Literal["symlink", "translate", "config_file_folder", "none"]
    # Type hint inspection — we just check the field exists with correct annotation.
    assert "subagent_mechanism" in hints


def test_general_agent_synthetic_present():
    from agent_toolkit_cli.skill_agents import AGENTS
    assert "general-agent" in AGENTS
    cfg = AGENTS["general-agent"]
    assert cfg.skills_dir == ".agents/agents"  # parallel to general-skill but agents dir
    assert cfg.show_in_universal_list is False
    assert cfg.subagent_mechanism == "none"  # not a real harness


def test_catalog_size_after_general_agent():
    """56 (current main, with general-skill) + 1 (general-agent) = 57."""
    from agent_toolkit_cli.skill_agents import AGENTS
    assert len(AGENTS) == 57
```

Also UPDATE the existing `test_catalog_size` (currently asserts 56) — find the existing test and bump to 57.

### Step 5.2: Run tests to verify they fail

Run: `uv run pytest tests/test_cli/test_skill_agents.py -v`
Expected: 5 new tests FAIL with `AttributeError: 'AgentConfig' object has no attribute 'subagent_mechanism'` and `KeyError: 'general-agent'`. Existing `test_catalog_size` may fail if it asserts 56.

### Step 5.3: Add `subagent_mechanism` field to `AgentConfig`

Edit `src/agent_toolkit_cli/skill_agents.py`:

**(a) Add `Literal` to imports (around line 13):**

```python
from typing import Callable, Literal
```

**(b) Add field to dataclass (around line 39):**

```python
@dataclass(frozen=True)
class AgentConfig:
    name: str
    display_name: str
    skills_dir: str
    global_skills_dir: Path
    detect_installed: Callable[[], bool]
    show_in_universal_list: bool = True
    subagent_mechanism: Literal[
        "symlink", "translate", "config_file_folder", "none"
    ] = "none"

    @property
    def is_universal(self) -> bool:
        return self.skills_dir == ".agents/skills"
```

### Step 5.4: Add `"general-agent"` synthetic entry

Find the `"general-skill"` entry in `skill_agents.py` (around line 445) and add IMMEDIATELY AFTER it:

```python
    "general-agent": AgentConfig(
        name="general-agent",
        display_name="General (agents)",
        skills_dir=".agents/agents",
        global_skills_dir=XDG_CONFIG / "agents/agents",
        show_in_universal_list=False,
        detect_installed=lambda: False,
        subagent_mechanism="none",  # synthetic — not a real installable harness
    ),
```

### Step 5.5: Run the tests to verify they pass

Run: `uv run pytest tests/test_cli/test_skill_agents.py -v`
Expected: all pass.

### Step 5.6: Run the full suite to confirm no regression

Run: `uv run pytest -q`
Expected: 567 passed, 2 skipped (was 562; +5 new).

### Step 5.7: Commit

```bash
git add src/agent_toolkit_cli/skill_agents.py tests/test_cli/test_skill_agents.py
git commit -m "feat(skill_agents): add subagent_mechanism field + general-agent synthetic"
```

---

## Task 6: `agent_adapters/` package skeleton

**Files:**
- Create: `src/agent_toolkit_cli/agent_adapters/__init__.py`
- Create: `tests/test_cli/test_agent_adapters/__init__.py` (empty)
- Create: `tests/test_cli/test_agent_adapters/test_dispatcher.py`

### Step 6.1: Write the failing test for the dispatcher

Create `tests/test_cli/test_agent_adapters/__init__.py` (empty file, just for pytest discovery).

Create `tests/test_cli/test_agent_adapters/test_dispatcher.py`:

```python
"""agent_adapters.get_adapter() dispatches to per-mechanism modules."""
from __future__ import annotations

import pytest


def test_get_adapter_raises_for_unknown_harness():
    from agent_toolkit_cli.agent_adapters import get_adapter
    from agent_toolkit_cli.skill_agents import UnknownAgentError
    with pytest.raises(UnknownAgentError):
        get_adapter("nonexistent-harness-xyz")


def test_get_adapter_raises_for_none_mechanism_harness():
    """A harness with subagent_mechanism='none' has no installable adapter."""
    from agent_toolkit_cli.agent_adapters import (
        get_adapter, UnsupportedMechanismError,
    )
    with pytest.raises(UnsupportedMechanismError):
        get_adapter("amp")  # known harness, but mechanism="none"


def test_agent_adapter_protocol_callable():
    """AgentAdapter Protocol exposes install + uninstall (callable, not stub)."""
    from agent_toolkit_cli.agent_adapters import AgentAdapter
    # Protocol classes don't instantiate; runtime check is duck-typing.
    # Verify the Protocol class itself exists and is from typing.Protocol.
    import typing
    # Check that AgentAdapter is a Protocol
    assert hasattr(AgentAdapter, "install")
    assert hasattr(AgentAdapter, "uninstall")


def test_get_adapter_returns_callable():
    """For a harness with a real mechanism, returns an object with install/uninstall.

    Uses the simplest cell that will be wired in Task 8 (claude-code = symlink).
    Test xfails until Task 11 sets the mechanism literal.
    """
    pytest.xfail("subagent_mechanism literals are set in Task 11")
    from agent_toolkit_cli.agent_adapters import get_adapter
    adapter = get_adapter("claude-code")
    assert callable(getattr(adapter, "install", None))
    assert callable(getattr(adapter, "uninstall", None))
```

### Step 6.2: Run the test to verify it fails

Run: `uv run pytest tests/test_cli/test_agent_adapters/test_dispatcher.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_toolkit_cli.agent_adapters'`

### Step 6.3: Create the `agent_adapters/__init__.py` dispatcher

Create `src/agent_toolkit_cli/agent_adapters/__init__.py`:

```python
"""Agent-kind projection adapters, dispatched by AgentConfig.subagent_mechanism.

PR2 ships three mechanism modules:
  - symlink: 15 harnesses; write a single .md to the harness's agents dir.
  - translate: 10 harnesses; reshape frontmatter or non-md format (toml/json).
  - config_file_folder: 3 harnesses; write definition + mutate registry.

Per-cell quirks (path-template, required frontmatter, format) live in
per-cell dicts INSIDE the mechanism module. Mechanism = code path; cell = data row.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from agent_toolkit_cli.skill_agents import (
    AGENTS,
    UnknownAgentError,
)


class UnsupportedMechanismError(RuntimeError):
    """Harness exists in catalog but its subagent_mechanism is 'none'.

    Means the agent kind is not installable for this harness — either it
    doesn't support subagents (the 10 by-design cells) or research hasn't
    classified it yet (the 5 unknown cells). Surface to user with the
    matrix URL.
    """


class AgentAdapter(Protocol):
    """Per-harness install/uninstall contract for the agent kind.

    Implementations are functions or callable objects; the Protocol is
    structural so we can return module-level callables without wrapping.
    """

    def install(
        self,
        slug: str,
        content_path: Path,
        *,
        scope: str,
        home: Path | None = None,
        project: Path | None = None,
    ) -> Path:
        """Project the agent definition. Returns the on-disk path created."""
        ...

    def uninstall(
        self,
        slug: str,
        *,
        scope: str,
        home: Path | None = None,
        project: Path | None = None,
    ) -> None:
        """Remove the projection. Idempotent."""
        ...


def get_adapter(harness_name: str) -> AgentAdapter:
    """Return the adapter for a given harness, dispatched by subagent_mechanism.

    Raises UnknownAgentError if harness_name is not in AGENTS.
    Raises UnsupportedMechanismError if the harness has subagent_mechanism='none'.
    """
    if harness_name not in AGENTS:
        raise UnknownAgentError(harness_name)
    cfg = AGENTS[harness_name]
    mech = cfg.subagent_mechanism
    if mech == "none":
        raise UnsupportedMechanismError(
            f"{harness_name}: subagent_mechanism='none' — not installable. "
            f"See docs/agent-toolkit/harness-matrix.md for supported set."
        )
    if mech == "symlink":
        from agent_toolkit_cli.agent_adapters import symlink
        return symlink.adapter_for(harness_name)
    if mech == "translate":
        from agent_toolkit_cli.agent_adapters import translate
        return translate.adapter_for(harness_name)
    if mech == "config_file_folder":
        from agent_toolkit_cli.agent_adapters import config_file_folder
        return config_file_folder.adapter_for(harness_name)
    raise RuntimeError(f"unreachable: unknown mechanism {mech!r}")
```

### Step 6.4: Run the test to verify it passes

Run: `uv run pytest tests/test_cli/test_agent_adapters/test_dispatcher.py -v`
Expected: 3 passed, 1 xfailed.

### Step 6.5: Confirm no regression

Run: `uv run pytest -q`
Expected: 570 passed, 2 skipped, 1 xfailed.

### Step 6.6: Commit

```bash
git add src/agent_toolkit_cli/agent_adapters/__init__.py tests/test_cli/test_agent_adapters/
git commit -m "feat(agent_adapters): package skeleton with mechanism dispatcher"
```

---

## Task 7: `agent_install.py` facade

**Files:**
- Create: `src/agent_toolkit_cli/agent_install.py`
- Create: `tests/test_cli/test_agent_install.py`

### Step 7.1: Write the failing tests

Create `tests/test_cli/test_agent_install.py`:

```python
"""agent_install.py — facade binding AGENT_BINDING + dispatching adapters."""
from __future__ import annotations

import pytest


def test_agent_install_public_surface():
    from agent_toolkit_cli import agent_install
    public = {name for name in dir(agent_install) if not name.startswith("_")}
    expected = {
        "InstallError", "LockMismatchError", "DirtyCanonicalError",
        "InstallPlan", "InstallResult", "plan", "apply",
        "install", "uninstall",
    }
    for sym in expected:
        assert sym in public, f"agent_install missing public symbol: {sym}"


def test_agent_install_synthetic_names_constant():
    """The agent facade injects its own synthetic set into the core."""
    from agent_toolkit_cli.agent_install import _AGENT_SYNTHETIC_NAMES
    assert _AGENT_SYNTHETIC_NAMES == frozenset({"general-agent"})


def test_plan_shim_passes_no_universal_bundle_link(tmp_path, monkeypatch):
    """Agents have no universal-bundle concept; the facade injects None."""
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_install import plan
    p = plan(slug="test", scope="global", target_agents=())
    assert p.slug == "test"
    assert p.scope == "global"
    assert p.add_agents == ()
    assert p.remove_agents == ()


def test_apply_dispatches_to_adapter_for_supported_harness(tmp_path, monkeypatch):
    """apply() uses agent_adapters.get_adapter() instead of unconditional symlink."""
    pytest.xfail("requires subagent_mechanism literals set in Task 11")
    # Will be expanded after Tasks 8-11 land.


def test_apply_skips_unsupported_harness(tmp_path, monkeypatch):
    """A harness with subagent_mechanism='none' is recorded as skipped, not errored."""
    pytest.xfail("requires subagent_mechanism literals set in Task 11")


def test_uninstall_is_idempotent(tmp_path, monkeypatch):
    """Calling uninstall twice with the same slug doesn't error."""
    pytest.xfail("requires real adapter behaviour from Tasks 8-11")
```

### Step 7.2: Run the test to verify it fails

Run: `uv run pytest tests/test_cli/test_agent_install.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_toolkit_cli.agent_install'`

### Step 7.3: Create the `agent_install.py` facade

Create `src/agent_toolkit_cli/agent_install.py`:

```python
"""Agent-flavoured facade over `_install_core.py`.

v3.0.0 PR2 — mirrors `skill_install.py` for the agent (subagent) kind.
Binds AGENT_BINDING + _AGENT_SYNTHETIC_NAMES into the core. apply()
dispatches to per-mechanism adapters from `agent_adapters/` instead of
the skill facade's uniform-symlink projection.

No universal-bundle concept exists for agents (per spec: agents
don't bundle into a megaprompt), so the facade injects
universal_bundle_link=None.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable, Literal

from agent_toolkit_cli import agent_adapters, skill_git
from agent_toolkit_cli._install_core import (
    DirtyCanonicalError,  # noqa: F401  re-exported
    InstallError,  # noqa: F401  re-exported
    InstallPlan,  # noqa: F401  re-exported
    InstallResult,
    LockMismatchError,
    _current_linked_agents as _core_current_linked_agents,
    plan as _core_plan,
)
from agent_toolkit_cli.agent_paths import (
    Scope,
    canonical_agent_dir,
    lock_file_path,
)
from agent_toolkit_cli.skill_agents import (
    AGENTS,
    UnknownAgentError,
)
from agent_toolkit_cli.skill_source import ParsedSource

# Catalog tokens that are virtual entries, not real harness install targets.
# Note: no "universal" — that's skill-only. "general-agent" mirrors
# "general-skill" from the skill facade.
_AGENT_SYNTHETIC_NAMES: frozenset[str] = frozenset({"general-agent"})


def plan(
    *,
    slug: str,
    scope: Scope,
    source: ParsedSource | None = None,
    ref: str | None = None,
    target_agents: Iterable[str] = (),
    home: Path | None = None,
    project: Path | None = None,
) -> InstallPlan:
    """Compute the minimal add/remove delta to reach target_agents.

    Thin facade over `_install_core.plan` that binds the agent-specific
    synthetic-name set. Agents have no universal-bundle concept, so
    universal_bundle_link=None.
    """
    return _core_plan(
        slug=slug, scope=scope, source=source, ref=ref,
        target_agents=target_agents, home=home, project=project,
        universal_bundle_link=None,
        synthetic_names=_AGENT_SYNTHETIC_NAMES,
    )


def _current_linked_agents(
    *, slug: str, scope: Scope,
    home: Path | None, project: Path | None,
) -> tuple[str, ...]:
    """Mirror of skill_install._current_linked_agents but binding the agent synthetics."""
    return _core_current_linked_agents(
        slug=slug, scope=scope, home=home, project=project,
        universal_bundle_link=None,
        synthetic_names=_AGENT_SYNTHETIC_NAMES,
    )


def apply(
    plan: InstallPlan,
    *,
    home: Path | None = None,
    project: Path | None = None,
    env: dict[str, str] | None = None,
) -> InstallResult:
    """Execute the agent-install plan.

    For each agent in plan.add_agents:
      - Skip synthetic tokens (general-agent).
      - Resolve the mechanism via agent_adapters.get_adapter().
      - If get_adapter() raises UnsupportedMechanismError, record as skipped.
      - Otherwise call adapter.install(slug, canonical_path/<agent_file>, …).

    For each agent in plan.remove_agents:
      - Skip synthetic tokens.
      - Call adapter.uninstall(slug, …). Idempotent.
    """
    from agent_toolkit_cli.agent_adapters import UnsupportedMechanismError
    from agent_toolkit_cli.agent_lock import (
        LockEntry, add_entry, read_lock, write_lock,
    )

    canonical = canonical_agent_dir(
        plan.slug, scope=plan.scope, home=home, project=project,
    )
    lock_path = lock_file_path(scope=plan.scope, home=home, project=project)
    lock = read_lock(lock_path)
    existing_entry = lock.skills.get(plan.slug)

    # Clone canonical if needed (same pattern as skill_install.apply).
    if plan.source is not None and not canonical.exists():
        canonical.parent.mkdir(parents=True, exist_ok=True)
        skill_git.clone(plan.source.url, canonical, ref=plan.ref, env=env)
    elif plan.source is not None and existing_entry is not None:
        requested = plan.source.owner_repo or plan.source.url
        if existing_entry.source != requested:
            raise LockMismatchError(
                f"{plan.slug}: canonical exists with source "
                f"{existing_entry.source!r}; refusing to overwrite with "
                f"{requested!r}. Run `agent remove {plan.slug}` first."
            )

    # The agent content file inside the canonical. Convention: <slug>.md.
    # Real adapters may override (e.g. devin → AGENT.md, kiro-cli → <slug>.json).
    # The adapter receives the canonical content file as input; it decides
    # the on-disk shape at the destination.
    content_path = canonical / f"{plan.slug}.md"

    created: list[Path] = []
    skipped: list[str] = []

    for name in plan.add_agents:
        if name in _AGENT_SYNTHETIC_NAMES:
            continue
        try:
            adapter = agent_adapters.get_adapter(name)
        except UnsupportedMechanismError:
            skipped.append(name)
            continue
        out = adapter.install(
            plan.slug, content_path,
            scope=plan.scope, home=home, project=project,
        )
        created.append(out)

    removed: list[Path] = []
    for name in plan.remove_agents:
        if name in _AGENT_SYNTHETIC_NAMES:
            continue
        try:
            adapter = agent_adapters.get_adapter(name)
        except UnsupportedMechanismError:
            continue
        adapter.uninstall(
            plan.slug,
            scope=plan.scope, home=home, project=project,
        )
        # Removal paths aren't currently tracked (uninstall is idempotent);
        # could extend AgentAdapter to return Path for parity. Out of PR2 scope.

    # Update lock — agent_path identifies which file was written.
    lock_action: Literal["added", "updated", "unchanged"] = "unchanged"
    if plan.source is not None:
        if skill_git.is_git_repo(canonical):
            upstream_sha = skill_git.remote_head_sha(
                canonical, ref=plan.ref or "main", env=env,
            )
            local_sha = skill_git.head_sha(canonical, env=env)
        else:
            upstream_sha = None
            local_sha = None
        entry = LockEntry(
            source=plan.source.owner_repo or plan.source.url,
            source_type=plan.source.type,
            ref=plan.ref,
            agent_path=f"{plan.slug}.md",
            upstream_sha=upstream_sha,
            local_sha=local_sha,
        )
        write_lock(lock_path, add_entry(lock, plan.slug, entry))
        lock_action = "added" if existing_entry is None else "updated"

    return InstallResult(
        plan=plan,
        canonical_path=canonical,
        created=tuple(created),
        removed=tuple(removed),
        skipped=tuple(skipped),
        lock_action=lock_action,
    )


def install(
    *,
    parsed: ParsedSource,
    slug: str,
    scope: Scope,
    home: Path | None,
    project: Path | None,
    harnesses: tuple[str, ...],
    env: dict[str, str] | None,
) -> Path:
    """Plan + apply convenience wrapper, mirroring skill_install.install()."""
    canonical = canonical_agent_dir(
        slug, scope=scope, home=home, project=project,
    )
    if canonical.exists() and skill_git.is_git_repo(canonical):
        skill_git.fetch(canonical, env=env)
        try:
            skill_git.merge(canonical, ref=parsed.ref or "main", env=env)
        except skill_git.GitError:
            pass

    p = plan(
        slug=slug, scope=scope,
        source=parsed, ref=parsed.ref,
        target_agents=harnesses,
        home=home, project=project,
    )
    apply(p, home=home, project=project, env=env)
    return canonical


def uninstall(
    *,
    slug: str,
    scope: Scope,
    home: Path | None,
    project: Path | None,
    harnesses: tuple[str, ...],
) -> None:
    """Full removal — every projection + canonical tree."""
    p = plan(
        slug=slug, scope=scope,
        source=None, ref=None,
        target_agents=(),
        home=home, project=project,
    )
    apply(p, home=home, project=project, env=None)

    if scope == "project":
        from agent_toolkit_cli.agent_lock import (
            read_lock, remove_entry, write_lock,
        )
        lock_path = lock_file_path(scope="project", project=project)
        lock = read_lock(lock_path)
        if slug in lock.skills:
            write_lock(lock_path, remove_entry(lock, slug))
        return

    canonical = canonical_agent_dir(
        slug, scope=scope, home=home, project=project,
    )
    if canonical.exists():
        shutil.rmtree(canonical)
```

### Step 7.4: Run the tests to verify they pass

Run: `uv run pytest tests/test_cli/test_agent_install.py -v`
Expected: 3 passed, 3 xfailed.

### Step 7.5: Confirm no regression

Run: `uv run pytest -q`
Expected: 573 passed, 2 skipped, 4 xfailed.

### Step 7.6: Commit

```bash
git add src/agent_toolkit_cli/agent_install.py tests/test_cli/test_agent_install.py
git commit -m "feat(agent_install): facade binding AGENT_BINDING + adapter dispatch"
```

---

## Task 8: `agent_adapters/symlink.py` + 15-cell tests

**Files:**
- Create: `src/agent_toolkit_cli/agent_adapters/symlink.py`
- Create: `tests/test_cli/test_agent_adapters/test_symlink.py`

### Step 8.1: Write the failing tests (parametrised 15-cell)

Create `tests/test_cli/test_agent_adapters/test_symlink.py`:

```python
"""symlink mechanism: 15 cells write a single .md to a harness-specific agents dir.

Per-cell expected paths sourced from spec addendum Risk Resolution table:
docs/superpowers/specs/2026-05-28-v3-pr2-agent-facade-and-adapters-design.md
"""
from __future__ import annotations

from pathlib import Path

import pytest


# (harness, global-path-template, project-path-template)
# {SLUG} is interpolated; {HOME} is the test's tmp_path; {PROJECT} similarly.
SYMLINK_CELLS = [
    ("augment",        "{HOME}/.augment/agents/{SLUG}.md",
                       "{PROJECT}/.augment/agents/{SLUG}.md"),
    ("claude-code",    "{HOME}/.claude/agents/{SLUG}.md",
                       "{PROJECT}/.claude/agents/{SLUG}.md"),
    ("codebuddy",      "{HOME}/.codebuddy/agents/{SLUG}.md",
                       "{PROJECT}/.codebuddy/agents/{SLUG}.md"),
    ("command-code",   "{HOME}/.commandcode/agents/{SLUG}.md",
                       "{PROJECT}/.commandcode/agents/{SLUG}.md"),
    ("cortex",         "{HOME}/.snowflake/cortex/agents/{SLUG}.md",
                       "{PROJECT}/.cortex/agents/{SLUG}.md"),
    ("cursor",         "{HOME}/.cursor/agents/{SLUG}.md",
                       "{PROJECT}/.cursor/agents/{SLUG}.md"),
    ("droid",          "{HOME}/.factory/droids/{SLUG}.md",
                       "{PROJECT}/.factory/droids/{SLUG}.md"),
    ("forgecode",      "{HOME}/.forge/agents/{SLUG}.md",
                       "{PROJECT}/.forge/agents/{SLUG}.md"),
    ("junie",          "{HOME}/.junie/agents/{SLUG}.md",
                       "{PROJECT}/.junie/agents/{SLUG}.md"),
    ("kode",           "{HOME}/.kode/agents/{SLUG}.md",
                       "{PROJECT}/.claude/agents/{SLUG}.md"),
    ("neovate",        "{HOME}/.neovate/agents/{SLUG}.md",
                       "{PROJECT}/.neovate/agents/{SLUG}.md"),
    ("pi",             "{HOME}/.pi/agent/agents/{SLUG}.md",
                       "{PROJECT}/.pi/agents/{SLUG}.md"),
    ("pochi",          "{HOME}/.pochi/agents/{SLUG}.md",
                       "{PROJECT}/.pochi/agents/{SLUG}.md"),
    ("qoder",          "{HOME}/.qoder/agents/{SLUG}.md",
                       "{PROJECT}/.qoder/agents/{SLUG}.md"),
    ("rovodev",        "{HOME}/.rovodev/subagents/{SLUG}.md",
                       "{PROJECT}/.rovodev/subagents/{SLUG}.md"),
]


@pytest.fixture
def fake_content(tmp_path):
    """Build a minimal canonical content file the adapter will project."""
    content = tmp_path / "canonical" / "test-agent.md"
    content.parent.mkdir(parents=True, exist_ok=True)
    content.write_text("---\nname: test-agent\ndescription: testing\n---\n\nBody.\n")
    return content


def _expand(template: str, *, home: Path, project: Path, slug: str) -> Path:
    return Path(
        template.replace("{HOME}", str(home))
                .replace("{PROJECT}", str(project))
                .replace("{SLUG}", slug)
    )


@pytest.mark.parametrize("harness, global_tpl, project_tpl", SYMLINK_CELLS)
def test_symlink_install_global(harness, global_tpl, project_tpl, tmp_path, monkeypatch, fake_content):
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_adapters import symlink
    adapter = symlink.adapter_for(harness)
    expected = _expand(global_tpl, home=tmp_path, project=tmp_path / "p", slug="test-agent")
    result = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    assert result == expected
    assert expected.exists()
    # Content matches canonical
    assert expected.read_text() == fake_content.read_text()


@pytest.mark.parametrize("harness, global_tpl, project_tpl", SYMLINK_CELLS)
def test_symlink_install_project(harness, global_tpl, project_tpl, tmp_path, fake_content):
    project = tmp_path / "myproj"
    project.mkdir()
    from agent_toolkit_cli.agent_adapters import symlink
    adapter = symlink.adapter_for(harness)
    expected = _expand(project_tpl, home=tmp_path, project=project, slug="test-agent")
    result = adapter.install("test-agent", fake_content, scope="project", project=project)
    assert result == expected
    assert expected.exists()


@pytest.mark.parametrize("harness, global_tpl, project_tpl", SYMLINK_CELLS)
def test_symlink_uninstall_idempotent(harness, global_tpl, project_tpl, tmp_path, monkeypatch, fake_content):
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_adapters import symlink
    adapter = symlink.adapter_for(harness)
    adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    expected = _expand(global_tpl, home=tmp_path, project=tmp_path / "p", slug="test-agent")
    assert expected.exists()
    adapter.uninstall("test-agent", scope="global", home=tmp_path)
    assert not expected.exists()
    # Second uninstall is a no-op
    adapter.uninstall("test-agent", scope="global", home=tmp_path)


def test_pi_global_path_honours_env_override(tmp_path, monkeypatch, fake_content):
    """pi's $PI_CODING_AGENT_DIR overrides the default ~/.pi/agent/agents/ path."""
    monkeypatch.setenv("HOME", str(tmp_path))
    custom = tmp_path / "custom_pi"
    monkeypatch.setenv("PI_CODING_AGENT_DIR", str(custom))
    from agent_toolkit_cli.agent_adapters import symlink
    adapter = symlink.adapter_for("pi")
    result = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    assert result == custom / "agents" / "test-agent.md"
    assert result.exists()
```

### Step 8.2: Run the tests to verify they fail

Run: `uv run pytest tests/test_cli/test_agent_adapters/test_symlink.py -v 2>&1 | head -20`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_toolkit_cli.agent_adapters.symlink'`

### Step 8.3: Create the `symlink.py` adapter module

Create `src/agent_toolkit_cli/agent_adapters/symlink.py`:

```python
"""Symlink mechanism: write a single .md per agent to a harness-specific dir.

15 cells. Per-cell quirks (path-template, frontmatter rules, name-validation)
live in CELLS below. The adapter is a closure factory: adapter_for(harness)
returns a Protocol-conforming object with install/uninstall.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Callable

from agent_toolkit_cli.skill_agents import AGENTS, UnknownAgentError


# Path templates per cell. {HOME}, {PROJECT}, {SLUG} are placeholders.
# {PI_AGENT_DIR} is a custom token for pi's env override.
# Sources: docs/superpowers/specs/2026-05-28-v3-pr2-agent-facade-and-adapters-design.md
# (Risk Resolution Addendum, symlink table, verified 2026-05-28).
CELLS: dict[str, dict[str, str]] = {
    "augment":      {"global": "{HOME}/.augment/agents/{SLUG}.md",
                     "project": "{PROJECT}/.augment/agents/{SLUG}.md"},
    "claude-code":  {"global": "{HOME}/.claude/agents/{SLUG}.md",
                     "project": "{PROJECT}/.claude/agents/{SLUG}.md"},
    "codebuddy":    {"global": "{HOME}/.codebuddy/agents/{SLUG}.md",
                     "project": "{PROJECT}/.codebuddy/agents/{SLUG}.md"},
    "command-code": {"global": "{HOME}/.commandcode/agents/{SLUG}.md",
                     "project": "{PROJECT}/.commandcode/agents/{SLUG}.md"},
    "cortex":       {"global": "{HOME}/.snowflake/cortex/agents/{SLUG}.md",
                     "project": "{PROJECT}/.cortex/agents/{SLUG}.md"},
    "cursor":       {"global": "{HOME}/.cursor/agents/{SLUG}.md",
                     "project": "{PROJECT}/.cursor/agents/{SLUG}.md"},
    "droid":        {"global": "{HOME}/.factory/droids/{SLUG}.md",
                     "project": "{PROJECT}/.factory/droids/{SLUG}.md"},
    "forgecode":    {"global": "{HOME}/.forge/agents/{SLUG}.md",
                     "project": "{PROJECT}/.forge/agents/{SLUG}.md"},
    "junie":        {"global": "{HOME}/.junie/agents/{SLUG}.md",
                     "project": "{PROJECT}/.junie/agents/{SLUG}.md"},
    "kode":         {"global": "{HOME}/.kode/agents/{SLUG}.md",
                     "project": "{PROJECT}/.claude/agents/{SLUG}.md"},
    "neovate":      {"global": "{HOME}/.neovate/agents/{SLUG}.md",
                     "project": "{PROJECT}/.neovate/agents/{SLUG}.md"},
    "pi":           {"global": "{PI_AGENT_DIR}/agents/{SLUG}.md",
                     "project": "{PROJECT}/.pi/agents/{SLUG}.md"},
    "pochi":        {"global": "{HOME}/.pochi/agents/{SLUG}.md",
                     "project": "{PROJECT}/.pochi/agents/{SLUG}.md"},
    "qoder":        {"global": "{HOME}/.qoder/agents/{SLUG}.md",
                     "project": "{PROJECT}/.qoder/agents/{SLUG}.md"},
    "rovodev":      {"global": "{HOME}/.rovodev/subagents/{SLUG}.md",
                     "project": "{PROJECT}/.rovodev/subagents/{SLUG}.md"},
}


def _expand(template: str, *, home: Path | None, project: Path | None, slug: str) -> Path:
    """Expand {HOME}/{PROJECT}/{SLUG}/{PI_AGENT_DIR} placeholders."""
    out = template.replace("{SLUG}", slug)
    if home is not None:
        out = out.replace("{HOME}", str(home))
    if project is not None:
        out = out.replace("{PROJECT}", str(project))
    if "{PI_AGENT_DIR}" in out:
        env_path = os.environ.get("PI_CODING_AGENT_DIR")
        if env_path:
            out = out.replace("{PI_AGENT_DIR}", env_path)
        elif home is not None:
            out = out.replace("{PI_AGENT_DIR}", str(home / ".pi" / "agent"))
        else:
            out = out.replace("{PI_AGENT_DIR}", str(Path.home() / ".pi" / "agent"))
    return Path(out)


class _SymlinkAdapter:
    """Per-harness adapter; install/uninstall by writing a single .md.

    Implementation note: we use a real file-copy (not a symlink) for
    portability — most harnesses do not chase symlinks recursively at load
    time, and a copy guarantees independent atomic updates per cell.
    """

    def __init__(self, harness: str):
        if harness not in CELLS:
            raise UnknownAgentError(harness)
        self.harness = harness
        self._cell = CELLS[harness]

    def install(
        self,
        slug: str,
        content_path: Path,
        *,
        scope: str,
        home: Path | None = None,
        project: Path | None = None,
    ) -> Path:
        template = self._cell[scope]
        dest = _expand(template, home=home, project=project, slug=slug)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(content_path, dest)
        return dest

    def uninstall(
        self,
        slug: str,
        *,
        scope: str,
        home: Path | None = None,
        project: Path | None = None,
    ) -> None:
        template = self._cell[scope]
        dest = _expand(template, home=home, project=project, slug=slug)
        if dest.exists() or dest.is_symlink():
            dest.unlink()


def adapter_for(harness: str) -> _SymlinkAdapter:
    """Return the symlink-mechanism adapter for `harness`."""
    return _SymlinkAdapter(harness)
```

### Step 8.4: Run the tests to verify they pass

Run: `uv run pytest tests/test_cli/test_agent_adapters/test_symlink.py -v 2>&1 | tail -20`
Expected: 46 passed (15 × 3 parametrised + 1 pi-env-override).

### Step 8.5: Confirm no regression

Run: `uv run pytest -q`
Expected: 619 passed, 2 skipped, 4 xfailed.

### Step 8.6: Commit

```bash
git add src/agent_toolkit_cli/agent_adapters/symlink.py tests/test_cli/test_agent_adapters/test_symlink.py
git commit -m "feat(agent_adapters/symlink): 15-cell symlink-mechanism adapter

# cite: docs/agent-toolkit/harness-matrix.md + spec addendum (verified 2026-05-28)
# Cells: augment, claude-code, codebuddy, command-code, cortex, cursor,
# droid, forgecode, junie, kode, neovate, pi, pochi, qoder, rovodev"
```

---

## Task 9: `agent_adapters/translate.py` + 10-cell tests

**Files:**
- Create: `src/agent_toolkit_cli/agent_adapters/translate.py`
- Create: `tests/test_cli/test_agent_adapters/test_translate.py`

### Step 9.1: Write the failing tests (10 cells, format-specific assertions)

Create `tests/test_cli/test_agent_adapters/test_translate.py`. Pattern: each cell asserts the on-disk shape matches its format contract from the spec addendum.

```python
"""translate mechanism: 10 cells across 5 format helpers.

Format families:
  - yaml-strict (1): gemini-cli — only documented optional+required fields, extras throw.
  - yaml-passthrough (5): devin, github-copilot, kilo, mux, opencode, qwen-code
                          — pass through frontmatter with per-cell tweaks.
  - toml (2): codex, mistral-vibe
  - json (1): kiro-cli
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def fake_content(tmp_path):
    """Canonical .md with rich frontmatter for translation tests."""
    content = tmp_path / "canonical" / "test-agent.md"
    content.parent.mkdir(parents=True, exist_ok=True)
    content.write_text(
        "---\n"
        "name: test-agent\n"
        "description: a test subagent\n"
        "model: gpt-5\n"
        "tools:\n"
        "  - file_read\n"
        "  - bash\n"
        "extra_field: should-be-filtered-by-strict\n"
        "---\n"
        "\n"
        "You are a helpful test agent.\n"
    )
    return content


# ── gemini-cli: zod .strict() — only allowed fields, extras rejected ──

def test_gemini_cli_install_filters_to_allowed_fields(tmp_path, monkeypatch, fake_content):
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for("gemini-cli")
    result = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    assert result == tmp_path / ".gemini" / "agents" / "test-agent.md"
    text = result.read_text()
    # 'extra_field' must be filtered out by the strict adapter
    assert "extra_field" not in text
    # Required + allowed optional fields preserved
    assert "name: test-agent" in text
    assert "description: a test subagent" in text
    assert "model: gpt-5" in text


# ── codex: TOML with developer_instructions mapped from body ──

def test_codex_install_writes_toml(tmp_path, monkeypatch, fake_content):
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for("codex")
    result = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    assert result == tmp_path / ".codex" / "agents" / "test-agent.toml"
    import tomllib
    body = tomllib.loads(result.read_text())
    assert body["name"] == "test-agent"
    assert body["description"] == "a test subagent"
    # developer_instructions sourced from markdown body
    assert "helpful test agent" in body["developer_instructions"]


# ── kiro-cli: JSON, filename = ID ──

def test_kiro_cli_install_writes_json(tmp_path, monkeypatch, fake_content):
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for("kiro-cli")
    result = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    assert result == tmp_path / ".kiro" / "agents" / "test-agent.json"
    body = json.loads(result.read_text())
    assert body["name"] == "test-agent"
    assert body["description"] == "a test subagent"
    assert "helpful test agent" in body["prompt"]


# ── mux: nested subagent: { runnable: true } block ──

def test_mux_install_emits_nested_subagent_block(tmp_path, monkeypatch, fake_content):
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for("mux")
    result = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    text = result.read_text()
    # The literal nested form
    assert "subagent:" in text
    assert "runnable: true" in text
    # Flat `runnable: true` at the wrong indentation level would silently
    # leave the agent un-spawnable; verify it's nested.
    # A simple substring check: 'subagent:' precedes 'runnable: true'.
    sub_idx = text.index("subagent:")
    runnable_idx = text.index("runnable: true")
    assert sub_idx < runnable_idx


# ── opencode: write to plural 'agents/' + mode: subagent ──

def test_opencode_writes_plural_agents_with_mode(tmp_path, monkeypatch, fake_content):
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for("opencode")
    result = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    # PLURAL — not singular
    assert "agents" in result.parts
    assert "agent" not in [p for p in result.parts if p == "agent"]
    text = result.read_text()
    assert "mode: subagent" in text


# ── kilo: must inject mode: subagent ──

def test_kilo_install_injects_mode_subagent(tmp_path, monkeypatch, fake_content):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for("kilo")
    result = adapter.install("test-agent", fake_content, scope="global")
    # Global path is singular 'agent/' per spec
    assert result == tmp_path / ".config" / "kilo" / "agent" / "test-agent.md"
    text = result.read_text()
    assert "mode: subagent" in text


def test_kilo_project_path_plural(tmp_path, fake_content):
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for("kilo")
    project = tmp_path / "proj"
    project.mkdir()
    result = adapter.install("test-agent", fake_content, scope="project", project=project)
    # Project path is plural 'agents/'
    assert result == project / ".kilo" / "agents" / "test-agent.md"


# ── mistral-vibe: TOML with agent_type=subagent, safety enum ──

def test_mistral_vibe_install_writes_toml_with_safety(tmp_path, monkeypatch, fake_content):
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for("mistral-vibe")
    result = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    assert result == tmp_path / ".vibe" / "agents" / "test-agent.toml"
    import tomllib
    body = tomllib.loads(result.read_text())
    assert body["agent_type"] == "subagent"
    assert body["display_name"]
    assert body["description"] == "a test subagent"
    assert body["safety"] in ("safe", "neutral", "destructive", "yolo")
    assert isinstance(body["enabled_tools"], list)


# ── github-copilot: .agent.md suffix, project path under .github/ ──

def test_github_copilot_global_writes_agent_md_suffix(tmp_path, monkeypatch, fake_content):
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for("github-copilot")
    result = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    assert result == tmp_path / ".copilot" / "agents" / "test-agent.agent.md"


def test_github_copilot_project_path_under_github(tmp_path, fake_content):
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for("github-copilot")
    project = tmp_path / "proj"
    project.mkdir()
    result = adapter.install("test-agent", fake_content, scope="project", project=project)
    assert result == project / ".github" / "agents" / "test-agent.agent.md"


# ── devin: per-profile dir, AGENT.md filename ──

def test_devin_install_uses_profile_and_agent_md_filename(tmp_path, monkeypatch, fake_content):
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for("devin")
    result = adapter.install(
        "test-agent", fake_content, scope="global", home=tmp_path,
    )
    # Default profile is "default" per addendum 9-open-items
    assert result == tmp_path / ".config" / "devin" / "agents" / "default" / "AGENT.md"


# ── qwen-code: passthrough, NO systemPrompt key (body is the prompt) ──

def test_qwen_code_install_body_is_prompt(tmp_path, monkeypatch, fake_content):
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for("qwen-code")
    result = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    assert result == tmp_path / ".qwen" / "agents" / "test-agent.md"
    text = result.read_text()
    # NOT a `systemPrompt:` frontmatter key — the markdown body IS the prompt
    assert "systemPrompt:" not in text
    assert "helpful test agent" in text  # body preserved


# ── Universal: uninstall idempotency for every cell ──

TRANSLATE_HARNESSES = [
    "codex", "devin", "gemini-cli", "github-copilot",
    "kilo", "kiro-cli", "mistral-vibe", "mux", "opencode", "qwen-code",
]


@pytest.mark.parametrize("harness", TRANSLATE_HARNESSES)
def test_translate_uninstall_idempotent(harness, tmp_path, monkeypatch, fake_content):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for(harness)
    adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    adapter.uninstall("test-agent", scope="global", home=tmp_path)
    # Second uninstall is a no-op
    adapter.uninstall("test-agent", scope="global", home=tmp_path)
```

### Step 9.2: Run tests to verify they fail

Run: `uv run pytest tests/test_cli/test_agent_adapters/test_translate.py -v 2>&1 | tail -15`
Expected: FAIL — `ModuleNotFoundError` then once module exists, dispatch failures.

### Step 9.3: Create `translate.py` adapter module

Create `src/agent_toolkit_cli/agent_adapters/translate.py`. The module is the largest of the three — it dispatches to per-format helpers.

```python
"""Translate mechanism: 10 cells across 5 format helpers.

Per spec addendum Risk Resolution (verified 2026-05-28):

  Format families:
    - yaml-strict (1): gemini-cli — only documented fields, extras throw.
    - yaml-passthrough (5): devin, github-copilot, kilo, mux, opencode, qwen-code
    - toml (2): codex, mistral-vibe
    - json (1): kiro-cli

Per-cell quirks are encoded in CELLS below + per-cell helper functions.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from agent_toolkit_cli.skill_agents import UnknownAgentError


# ── Path templates per cell ──────────────────────────────────────────────

CELL_PATHS: dict[str, dict[str, str]] = {
    "codex": {
        "global": "{HOME}/.codex/agents/{SLUG}.toml",
        "project": "{PROJECT}/.codex/agents/{SLUG}.toml",
    },
    "devin": {
        "global": "{XDG_CONFIG}/devin/agents/default/AGENT.md",
        "project": "{PROJECT}/.devin/agents/default/AGENT.md",
    },
    "gemini-cli": {
        "global": "{HOME}/.gemini/agents/{SLUG}.md",
        "project": "{PROJECT}/.gemini/agents/{SLUG}.md",
    },
    "github-copilot": {
        "global": "{HOME}/.copilot/agents/{SLUG}.agent.md",
        "project": "{PROJECT}/.github/agents/{SLUG}.agent.md",
    },
    "kilo": {
        "global": "{XDG_CONFIG}/kilo/agent/{SLUG}.md",  # SINGULAR agent/ global
        "project": "{PROJECT}/.kilo/agents/{SLUG}.md",  # PLURAL agents/ project
    },
    "kiro-cli": {
        "global": "{HOME}/.kiro/agents/{SLUG}.json",
        "project": "{PROJECT}/.kiro/agents/{SLUG}.json",
    },
    "mistral-vibe": {
        "global": "{HOME}/.vibe/agents/{SLUG}.toml",
        "project": "{PROJECT}/.vibe/agents/{SLUG}.toml",
    },
    "mux": {
        "global": "{HOME}/.mux/agents/{SLUG}.md",
        "project": "{PROJECT}/.mux/agents/{SLUG}.md",
    },
    "opencode": {  # PLURAL agents/ at both scopes
        "global": "{XDG_CONFIG}/opencode/agents/{SLUG}.md",
        "project": "{PROJECT}/.opencode/agents/{SLUG}.md",
    },
    "qwen-code": {
        "global": "{HOME}/.qwen/agents/{SLUG}.md",
        "project": "{PROJECT}/.qwen/agents/{SLUG}.md",
    },
}


def _expand(template: str, *, home: Path | None, project: Path | None, slug: str) -> Path:
    out = template.replace("{SLUG}", slug)
    if home is not None:
        out = out.replace("{HOME}", str(home))
    if project is not None:
        out = out.replace("{PROJECT}", str(project))
    if "{XDG_CONFIG}" in out:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        if xdg:
            out = out.replace("{XDG_CONFIG}", xdg)
        elif home is not None:
            out = out.replace("{XDG_CONFIG}", str(home / ".config"))
        else:
            out = out.replace("{XDG_CONFIG}", str(Path.home() / ".config"))
    return Path(out)


# ── Minimal YAML frontmatter parser (avoids new dep) ────────────────────

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Return (frontmatter_dict, body). Body is the post-frontmatter text.

    Minimal YAML support: key:value, key:list-of-strings (single-line `[a, b]` or
    multi-line `\n  - a\n  - b`). For PR2's transformations we only need to read
    a small set of well-known keys; full YAML is overkill.
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm_text, body = m.groups()

    fm: dict[str, Any] = {}
    lines = fm_text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if ":" in line and not line.startswith("  "):
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            if val:
                # Single-line scalar or inline list
                if val.startswith("[") and val.endswith("]"):
                    fm[key] = [x.strip().strip("'\"") for x in val[1:-1].split(",") if x.strip()]
                else:
                    fm[key] = val.strip("'\"")
            else:
                # Multi-line list follows
                items: list[str] = []
                j = i + 1
                while j < len(lines) and lines[j].startswith("  - "):
                    items.append(lines[j].removeprefix("  - ").strip().strip("'\""))
                    j += 1
                fm[key] = items
                i = j - 1
        i += 1
    return fm, body


def _emit_yaml_frontmatter(fm: dict[str, Any], body: str) -> str:
    """Emit YAML frontmatter + body. Sufficient for our subset."""
    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, list):
            if not v:
                continue
            lines.append(f"{k}:")
            for item in v:
                lines.append(f"  - {item}")
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines) + "\n" + body


# ── Per-format helpers ──────────────────────────────────────────────────

_GEMINI_ALLOWED = {
    "name", "description", "display_name", "tools", "mcp_servers",
    "model", "temperature", "max_turns", "timeout_mins", "kind",
}


def _emit_gemini_strict(fm: dict[str, Any], body: str) -> str:
    """zod .strict() — drop unknown keys."""
    filtered = {k: v for k, v in fm.items() if k in _GEMINI_ALLOWED}
    return _emit_yaml_frontmatter(filtered, body)


def _emit_codex_toml(fm: dict[str, Any], body: str) -> str:
    """TOML with developer_instructions sourced from markdown body."""
    name = fm.get("name", "")
    description = fm.get("description", "")
    out_lines = [
        f'name = "{name}"',
        f'description = "{description}"',
        'developer_instructions = """',
        body.strip(),
        '"""',
    ]
    if "model" in fm:
        out_lines.insert(2, f'model = "{fm["model"]}"')
    return "\n".join(out_lines) + "\n"


def _emit_mistral_vibe_toml(fm: dict[str, Any], body: str) -> str:
    """TOML with required: agent_type, display_name, description, safety, enabled_tools."""
    name = fm.get("name", "")
    description = fm.get("description", "")
    tools = fm.get("tools", []) or []
    out_lines = [
        'agent_type = "subagent"',
        f'display_name = "{fm.get("display_name", name)}"',
        f'description = "{description}"',
        'safety = "neutral"',  # default per addendum
        f'enabled_tools = [{", ".join(repr(t) for t in tools)}]',
    ]
    return "\n".join(out_lines) + "\n"


def _emit_kiro_json(fm: dict[str, Any], body: str) -> str:
    """JSON with body as prompt."""
    obj = {
        "name": fm.get("name", ""),
        "description": fm.get("description", ""),
        "prompt": body.strip(),
    }
    if "model" in fm:
        obj["model"] = fm["model"]
    if "tools" in fm:
        obj["tools"] = fm["tools"]
    return json.dumps(obj, indent=2) + "\n"


def _emit_mux(fm: dict[str, Any], body: str) -> str:
    """Mux requires nested subagent: { runnable: true } block."""
    # Reshape: strip any flat runnable, inject the nested block.
    fm = {k: v for k, v in fm.items() if k != "runnable"}
    # Emit handcrafted to ensure nesting is correct.
    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, list):
            if not v:
                continue
            lines.append(f"{k}:")
            for item in v:
                lines.append(f"  - {item}")
        else:
            lines.append(f"{k}: {v}")
    lines.append("subagent:")
    lines.append("  runnable: true")
    lines.append("---")
    return "\n".join(lines) + "\n" + body


def _emit_opencode_or_kilo(fm: dict[str, Any], body: str) -> str:
    """Both opencode and kilo require mode: subagent in frontmatter."""
    fm = dict(fm)
    fm["mode"] = "subagent"
    return _emit_yaml_frontmatter(fm, body)


def _emit_github_copilot(fm: dict[str, Any], body: str) -> str:
    """Pass through; description is required (validated by caller)."""
    if "description" not in fm or not fm.get("description"):
        raise ValueError("github-copilot requires `description` frontmatter")
    return _emit_yaml_frontmatter(fm, body)


def _emit_qwen_code(fm: dict[str, Any], body: str) -> str:
    """All fields optional; system prompt is the markdown body (NOT a frontmatter key)."""
    # Strip systemPrompt if present (it would be wrong per qwen-code docs).
    fm = {k: v for k, v in fm.items() if k != "systemPrompt"}
    return _emit_yaml_frontmatter(fm, body)


def _emit_devin(fm: dict[str, Any], body: str) -> str:
    """Pass through; devin auto-translates tools <-> allowed-tools at load time."""
    return _emit_yaml_frontmatter(fm, body)


_EMITTERS = {
    "codex": _emit_codex_toml,
    "devin": _emit_devin,
    "gemini-cli": _emit_gemini_strict,
    "github-copilot": _emit_github_copilot,
    "kilo": _emit_opencode_or_kilo,
    "kiro-cli": _emit_kiro_json,
    "mistral-vibe": _emit_mistral_vibe_toml,
    "mux": _emit_mux,
    "opencode": _emit_opencode_or_kilo,
    "qwen-code": _emit_qwen_code,
}


class _TranslateAdapter:
    def __init__(self, harness: str):
        if harness not in CELL_PATHS:
            raise UnknownAgentError(harness)
        self.harness = harness

    def install(
        self,
        slug: str,
        content_path: Path,
        *,
        scope: str,
        home: Path | None = None,
        project: Path | None = None,
    ) -> Path:
        template = CELL_PATHS[self.harness][scope]
        dest = _expand(template, home=home, project=project, slug=slug)
        dest.parent.mkdir(parents=True, exist_ok=True)
        text = content_path.read_text()
        fm, body = _parse_frontmatter(text)
        emitter = _EMITTERS[self.harness]
        out = emitter(fm, body)
        dest.write_text(out)
        return dest

    def uninstall(
        self,
        slug: str,
        *,
        scope: str,
        home: Path | None = None,
        project: Path | None = None,
    ) -> None:
        template = CELL_PATHS[self.harness][scope]
        dest = _expand(template, home=home, project=project, slug=slug)
        if dest.exists() or dest.is_symlink():
            dest.unlink()


def adapter_for(harness: str) -> _TranslateAdapter:
    return _TranslateAdapter(harness)
```

### Step 9.4: Run the tests

Run: `uv run pytest tests/test_cli/test_agent_adapters/test_translate.py -v 2>&1 | tail -20`
Expected: ~21 passed (11 cell-specific + 10 parametrised uninstall idempotency).

### Step 9.5: Confirm no regression

Run: `uv run pytest -q`
Expected: 640 passed, 2 skipped, 4 xfailed.

### Step 9.6: Commit

```bash
git add src/agent_toolkit_cli/agent_adapters/translate.py tests/test_cli/test_agent_adapters/test_translate.py
git commit -m "feat(agent_adapters/translate): 10-cell translate-mechanism adapter

# cite: docs/agent-toolkit/harness-matrix.md + spec addendum (verified 2026-05-28)
# Format families: yaml-strict (gemini-cli), yaml-passthrough (devin,
# github-copilot, kilo, mux, opencode, qwen-code), toml (codex,
# mistral-vibe), json (kiro-cli)"
```

---

## Task 10: `agent_adapters/config_file_folder.py` + 3-cell tests

**Files:**
- Create: `src/agent_toolkit_cli/agent_adapters/config_file_folder.py`
- Create: `tests/test_cli/test_agent_adapters/test_config_file_folder.py`

### Step 10.1: Write the failing tests

Create `tests/test_cli/test_agent_adapters/test_config_file_folder.py`:

```python
"""config_file_folder mechanism: 3 cells with registry mutation.

  - aider-desk: per-slug config.json + order.json sort.
  - dexto: per-slug yml subdir; parent-allowedAgents edit is OUT OF SCOPE for PR2.
  - firebender: atomic firebender.json mutation; callable: true in markdown.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def fake_content(tmp_path):
    content = tmp_path / "canonical" / "test-agent.md"
    content.parent.mkdir(parents=True, exist_ok=True)
    content.write_text(
        "---\nname: test-agent\ndescription: test\n---\n\nBody text.\n"
    )
    return content


# ── aider-desk ───────────────────────────────────────────────────────────

def test_aider_desk_install_writes_per_slug_subdir(tmp_path, monkeypatch, fake_content):
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for("aider-desk")
    result = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    assert result == tmp_path / ".aider-desk" / "agents" / "test-agent" / "config.json"
    assert result.exists()
    body = json.loads(result.read_text())
    assert body["subagent"]["enabled"] is True


def test_aider_desk_uninstall_removes_subdir(tmp_path, monkeypatch, fake_content):
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for("aider-desk")
    adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    subdir = tmp_path / ".aider-desk" / "agents" / "test-agent"
    assert subdir.exists()
    adapter.uninstall("test-agent", scope="global", home=tmp_path)
    assert not subdir.exists()


# ── dexto ────────────────────────────────────────────────────────────────

def test_dexto_install_writes_yml_in_per_agent_subdir(tmp_path, monkeypatch, fake_content):
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for("dexto")
    result = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    assert result == tmp_path / ".dexto" / "agents" / "test-agent" / "test-agent.yml"
    assert result.exists()


def test_dexto_project_scope_raises_unsupported(tmp_path, fake_content):
    """Dexto has no project-scope convention per spec addendum."""
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for("dexto")
    project = tmp_path / "proj"
    project.mkdir()
    with pytest.raises(ValueError, match="dexto"):
        adapter.install("test-agent", fake_content, scope="project", project=project)


# ── firebender ───────────────────────────────────────────────────────────

def test_firebender_install_writes_md_with_callable_true(tmp_path, monkeypatch, fake_content):
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for("firebender")
    result = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    assert result == tmp_path / ".firebender" / "agents" / "test-agent.md"
    text = result.read_text()
    assert "callable: true" in text


def test_firebender_install_appends_to_firebender_json(tmp_path, monkeypatch, fake_content):
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for("firebender")
    adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    fb_json = tmp_path / ".firebender" / "firebender.json"
    assert fb_json.exists()
    body = json.loads(fb_json.read_text())
    assert "agents" in body
    assert any("test-agent.md" in p for p in body["agents"])


def test_firebender_preserves_unrelated_json_keys(tmp_path, monkeypatch, fake_content):
    """firebender.json may have other keys (mcp_servers, etc.); preserve them."""
    monkeypatch.setenv("HOME", str(tmp_path))
    fb_dir = tmp_path / ".firebender"
    fb_dir.mkdir()
    fb_json = fb_dir / "firebender.json"
    fb_json.write_text(json.dumps({
        "agents": ["existing-agent.md"],
        "mcp_servers": {"foo": {"command": "bar"}},
    }, indent=2))

    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for("firebender")
    adapter.install("test-agent", fake_content, scope="global", home=tmp_path)

    body = json.loads(fb_json.read_text())
    # Both agents present
    assert any("existing-agent.md" in p for p in body["agents"])
    assert any("test-agent.md" in p for p in body["agents"])
    # Unrelated keys preserved
    assert body["mcp_servers"] == {"foo": {"command": "bar"}}


def test_firebender_uninstall_removes_from_json_and_file(tmp_path, monkeypatch, fake_content):
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for("firebender")
    adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    md = tmp_path / ".firebender" / "agents" / "test-agent.md"
    assert md.exists()
    adapter.uninstall("test-agent", scope="global", home=tmp_path)
    assert not md.exists()
    body = json.loads((tmp_path / ".firebender" / "firebender.json").read_text())
    assert not any("test-agent.md" in p for p in body["agents"])
```

### Step 10.2: Run the tests to verify they fail

Run: `uv run pytest tests/test_cli/test_agent_adapters/test_config_file_folder.py -v 2>&1 | head -15`
Expected: FAIL — `ModuleNotFoundError`.

### Step 10.3: Create `config_file_folder.py` adapter

Create `src/agent_toolkit_cli/agent_adapters/config_file_folder.py`:

```python
"""config_file_folder mechanism: 3 cells, each requires registry mutation.

Per spec addendum:
  - aider-desk: per-slug subdir with `config.json`; subagent.enabled marks spawnable.
  - dexto: per-slug subdir with `<slug>.yml`; global-only (no project convention).
  - firebender: per-slug `.md` + atomic mutation of `firebender.json` agents array.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from agent_toolkit_cli.skill_agents import UnknownAgentError


def _atomic_write(path: Path, content: str) -> None:
    """Write file atomically via tmp + rename. Survives concurrent watchers."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content)
    os.replace(tmp, path)


# ── aider-desk ───────────────────────────────────────────────────────────

class _AiderDeskAdapter:
    def install(self, slug, content_path, *, scope, home=None, project=None):
        if scope == "global":
            base = (home or Path.home()) / ".aider-desk"
        else:
            base = project / ".aider-desk"
        subdir = base / "agents" / slug
        subdir.mkdir(parents=True, exist_ok=True)
        cfg = subdir / "config.json"
        text = content_path.read_text()
        body = {
            "name": slug,
            "subagent": {"enabled": True},
            "source": text,
        }
        cfg.write_text(json.dumps(body, indent=2) + "\n")
        return cfg

    def uninstall(self, slug, *, scope, home=None, project=None):
        if scope == "global":
            subdir = (home or Path.home()) / ".aider-desk" / "agents" / slug
        else:
            subdir = project / ".aider-desk" / "agents" / slug
        if subdir.exists():
            shutil.rmtree(subdir)


# ── dexto ────────────────────────────────────────────────────────────────

class _DextoAdapter:
    def install(self, slug, content_path, *, scope, home=None, project=None):
        if scope != "global":
            raise ValueError("dexto: no project-scope convention exists; global-only writes")
        base = (home or Path.home()) / ".dexto"
        subdir = base / "agents" / slug
        subdir.mkdir(parents=True, exist_ok=True)
        yml = subdir / f"{slug}.yml"
        # Minimal YAML; full dexto schema is rich but PR2 ships a minimal viable doc.
        # Adapter docstring informs users to add to a parent agent's allowedAgents
        # to make it spawnable (out of PR2 scope — see addendum open items).
        yml.write_text(
            f"name: {slug}\n"
            f"description: imported by agent-toolkit-cli\n"
            f"source: |\n  {content_path.read_text().strip()}\n"
        )
        return yml

    def uninstall(self, slug, *, scope, home=None, project=None):
        if scope != "global":
            return
        subdir = (home or Path.home()) / ".dexto" / "agents" / slug
        if subdir.exists():
            shutil.rmtree(subdir)


# ── firebender ───────────────────────────────────────────────────────────

class _FirebenderAdapter:
    def install(self, slug, content_path, *, scope, home=None, project=None):
        if scope == "global":
            base = (home or Path.home()) / ".firebender"
        else:
            base = project / ".firebender"
        md = base / "agents" / f"{slug}.md"
        md.parent.mkdir(parents=True, exist_ok=True)
        # Inject callable: true into frontmatter.
        text = content_path.read_text()
        if text.startswith("---\n"):
            head, _, rest = text[4:].partition("\n---\n")
            if "callable:" not in head:
                head = head + "\ncallable: true"
            text = "---\n" + head + "\n---\n" + rest
        else:
            text = "---\ncallable: true\n---\n" + text
        md.write_text(text)
        # Mutate firebender.json atomically.
        fb_json = base / "firebender.json"
        if fb_json.exists():
            body = json.loads(fb_json.read_text())
        else:
            body = {"agents": []}
        rel = str(md.relative_to(base) if scope == "global" else md)
        if rel not in body.get("agents", []):
            body.setdefault("agents", []).append(rel)
        _atomic_write(fb_json, json.dumps(body, indent=2) + "\n")
        return md

    def uninstall(self, slug, *, scope, home=None, project=None):
        if scope == "global":
            base = (home or Path.home()) / ".firebender"
        else:
            base = project / ".firebender"
        md = base / "agents" / f"{slug}.md"
        if md.exists():
            md.unlink()
        fb_json = base / "firebender.json"
        if fb_json.exists():
            body = json.loads(fb_json.read_text())
            if "agents" in body:
                body["agents"] = [p for p in body["agents"] if f"{slug}.md" not in p]
            _atomic_write(fb_json, json.dumps(body, indent=2) + "\n")


_ADAPTERS = {
    "aider-desk": _AiderDeskAdapter,
    "dexto": _DextoAdapter,
    "firebender": _FirebenderAdapter,
}


def adapter_for(harness: str):
    cls = _ADAPTERS.get(harness)
    if cls is None:
        raise UnknownAgentError(harness)
    return cls()
```

### Step 10.4: Run the tests

Run: `uv run pytest tests/test_cli/test_agent_adapters/test_config_file_folder.py -v 2>&1 | tail -15`
Expected: 9 passed.

### Step 10.5: Confirm no regression

Run: `uv run pytest -q`
Expected: 649 passed, 2 skipped, 4 xfailed.

### Step 10.6: Commit

```bash
git add src/agent_toolkit_cli/agent_adapters/config_file_folder.py tests/test_cli/test_agent_adapters/test_config_file_folder.py
git commit -m "feat(agent_adapters/config_file_folder): aider-desk + dexto + firebender

# cite: docs/agent-toolkit/harness-matrix.md + spec addendum (verified 2026-05-28)
# Cells: aider-desk (per-slug config.json + order.json), dexto (global-only
# per-slug yml subdir), firebender (atomic firebender.json mutation)"
```

---

## Task 11: Wire `subagent_mechanism` literals on 28 cells

**Files:**
- Modify: `src/agent_toolkit_cli/skill_agents.py` (28 cell entries)

### Step 11.1: Set `subagent_mechanism="symlink"` on the 15 symlink cells

Edit each of these 15 `AgentConfig(...)` entries in `skill_agents.py`. For each, add `subagent_mechanism="symlink"` as the last field. List of harnesses to find:

- `"augment"`, `"claude-code"`, `"codebuddy"`, `"command-code"`, `"cortex"`, `"cursor"`, `"droid"`, `"forgecode"`, `"junie"`, `"kode"`, `"neovate"`, `"pi"`, `"pochi"`, `"qoder"`, `"rovodev"`

Example edit for `claude-code`:

```python
    "claude-code": AgentConfig(
        name="claude-code",
        display_name="Claude Code",
        skills_dir=".claude/skills",
        global_skills_dir=CLAUDE_HOME / "skills",
        detect_installed=lambda: CLAUDE_HOME.exists(),
        subagent_mechanism="symlink",
    ),
```

### Step 11.2: Set `subagent_mechanism="translate"` on the 10 translate cells

For: `"codex"`, `"devin"`, `"gemini-cli"`, `"github-copilot"`, `"kilo"`, `"kiro-cli"`, `"mistral-vibe"`, `"mux"`, `"opencode"`, `"qwen-code"`.

### Step 11.3: Set `subagent_mechanism="config_file_folder"` on the 3 cells

For: `"aider-desk"`, `"dexto"`, `"firebender"`.

### Step 11.4: Remove xfail markers from the dispatcher + install tests

Find xfail markers in:
- `tests/test_cli/test_agent_adapters/test_dispatcher.py` (Task 6 — `test_get_adapter_returns_callable`)
- `tests/test_cli/test_agent_install.py` (Task 7 — three xfails)

Remove each `pytest.xfail("...")` line. The tests should now run for real.

For `test_agent_install.py`, also expand the previously-xfailed tests with real assertions. Replace `test_apply_dispatches_to_adapter_for_supported_harness` with:

```python
def test_apply_dispatches_to_adapter_for_supported_harness(tmp_path, monkeypatch):
    """apply() invokes the symlink adapter for claude-code and writes the file."""
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_install import apply, InstallPlan
    from agent_toolkit_cli.agent_paths import canonical_agent_dir

    # Pre-seed a fake canonical (skipping the git-clone path).
    canonical = canonical_agent_dir("test-agent", scope="global")
    canonical.mkdir(parents=True, exist_ok=True)
    (canonical / "test-agent.md").write_text("---\nname: test-agent\n---\nbody\n")

    plan = InstallPlan(
        slug="test-agent", scope="global", source=None, ref=None,
        add_agents=("claude-code",), remove_agents=(),
    )
    result = apply(plan)
    expected = tmp_path / ".claude" / "agents" / "test-agent.md"
    assert expected in result.created
    assert expected.exists()


def test_apply_skips_unsupported_harness(tmp_path, monkeypatch):
    """A harness with subagent_mechanism='none' is recorded as skipped, not errored."""
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_install import apply, InstallPlan
    from agent_toolkit_cli.agent_paths import canonical_agent_dir

    canonical = canonical_agent_dir("test-agent", scope="global")
    canonical.mkdir(parents=True, exist_ok=True)
    (canonical / "test-agent.md").write_text("---\nname: test-agent\n---\nbody\n")

    plan = InstallPlan(
        slug="test-agent", scope="global", source=None, ref=None,
        add_agents=("amp",),  # amp has subagent_mechanism="none"
        remove_agents=(),
    )
    result = apply(plan)
    assert "amp" in result.skipped


def test_uninstall_is_idempotent(tmp_path, monkeypatch):
    """uninstall() called twice with same slug doesn't error."""
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_install import uninstall

    uninstall(
        slug="nonexistent-slug", scope="global",
        home=None, project=None, harnesses=("claude-code",),
    )
    # Second call: still no error
    uninstall(
        slug="nonexistent-slug", scope="global",
        home=None, project=None, harnesses=("claude-code",),
    )
```

### Step 11.5: Run all agent_install + agent_adapters tests

Run: `uv run pytest tests/test_cli/test_agent_install.py tests/test_cli/test_agent_adapters/ -v 2>&1 | tail -20`
Expected: all pass (no xfails remaining).

### Step 11.6: Confirm full suite passes

Run: `uv run pytest -q`
Expected: 652 passed, 2 skipped (4 previous xfails now pass — no xfailed line).

### Step 11.7: Commit

```bash
git add src/agent_toolkit_cli/skill_agents.py tests/test_cli/test_agent_install.py tests/test_cli/test_agent_adapters/test_dispatcher.py
git commit -m "feat(skill_agents): wire subagent_mechanism on 28 supported cells

15 symlink + 10 translate + 3 config_file_folder.
Spec acceptance criterion #5 (matrix parity) now satisfiable."
```

---

## Task 12: Matrix parity test + synthetic exclusion bump

**Files:**
- Modify: `tests/test_subagent_matrix.py` (+ ~30 lines)

### Step 12.1: Write the parity test

Append to `tests/test_subagent_matrix.py`:

```python
def test_supported_rows_have_matching_adapter():
    """Every harness-matrix row with a supported-mechanism verdict must
    have a corresponding agent_adapters.get_adapter() implementation.

    Acceptance criterion #5: every supported matrix row has an
    agent_mechanism value on its AgentConfig matching the row's verdict prefix.
    """
    from agent_toolkit_cli.agent_adapters import (
        UnsupportedMechanismError, get_adapter,
    )
    from agent_toolkit_cli.skill_agents import AGENTS

    matrix_rows = _parse_supported_rows()  # existing helper

    # Verdict prefix → expected subagent_mechanism value.
    PREFIX_TO_MECHANISM = {
        "symlink": "symlink",
        "translate": "translate",
        "config_file": "config_file_folder",
        "dual-symlink": "symlink",  # pi reclassified per spec addendum
    }

    failures = []
    for harness, verdict, _path, _cite in matrix_rows:
        prefix = verdict.split()[0].rstrip(",")
        expected_mech = PREFIX_TO_MECHANISM.get(prefix)
        if expected_mech is None:
            continue  # not a supported-mechanism prefix
        if harness not in AGENTS:
            failures.append(f"{harness}: not in AGENTS catalog")
            continue
        actual_mech = AGENTS[harness].subagent_mechanism
        if actual_mech != expected_mech:
            failures.append(
                f"{harness}: matrix verdict prefix '{prefix}' expects "
                f"subagent_mechanism='{expected_mech}', got '{actual_mech}'"
            )
            continue
        # Adapter must be importable.
        try:
            adapter = get_adapter(harness)
        except UnsupportedMechanismError as e:
            failures.append(f"{harness}: get_adapter raised UnsupportedMechanismError: {e}")
            continue
        if not (hasattr(adapter, "install") and hasattr(adapter, "uninstall")):
            failures.append(f"{harness}: adapter missing install/uninstall")

    assert not failures, "Matrix parity failures:\n" + "\n".join(failures)


def _parse_supported_rows():
    """Return [(harness, verdict, path, cite), ...] for matrix rows with a
    supported-mechanism verdict."""
    matrix = (REPO_ROOT / "docs" / "agent-toolkit" / "harness-matrix.md").read_text()
    rows = []
    SUPPORTED_PREFIXES = ("symlink", "translate", "config_file", "dual-symlink")
    in_table = False
    for line in matrix.splitlines():
        if line.startswith("| ---"):
            in_table = True
            continue
        if in_table and line.startswith("|") and "|" in line[1:]:
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if len(cells) >= 4:
                harness, verdict, path, cite = cells[0], cells[1], cells[2], cells[3]
                if any(verdict.startswith(p) for p in SUPPORTED_PREFIXES):
                    rows.append((harness, verdict, path, cite))
        elif in_table and not line.strip().startswith("|"):
            in_table = False
    return rows
```

Also UPDATE the existing `_catalog_harnesses()` function (around line 58):

```python
def _catalog_harnesses():
    """Return harness names from skill_agents.AGENTS, excluding synthetic entries."""
    from agent_toolkit_cli import skill_agents
    return set(skill_agents.AGENTS) - {"universal", "general-skill", "general-agent"}
```

### Step 12.2: Run the test

Run: `uv run pytest tests/test_subagent_matrix.py -v`
Expected: all matrix tests pass, including the new parity test.

### Step 12.3: Confirm full suite

Run: `uv run pytest -q`
Expected: 653 passed, 2 skipped.

### Step 12.4: Commit

```bash
git add tests/test_subagent_matrix.py
git commit -m "test(subagent_matrix): parity test couples matrix verdict ↔ adapter

Every supported matrix row must have a matching subagent_mechanism on
AgentConfig + a working get_adapter() return. Also extends
_catalog_harnesses() synthetic exclusion to include general-agent."
```

---

## Task 13: End-to-end smoke test (parametrised over 28 cells)

**Files:**
- Create: `tests/test_cli/test_agent_install_e2e.py`

### Step 13.1: Write the parametrised smoke test

Create `tests/test_cli/test_agent_install_e2e.py`:

```python
"""End-to-end: install one agent into each of the 28 supported harnesses
in a tmp HOME and assert the on-disk projection exists at the matrix path.

Acceptance criterion #3 (the 28 supported cells are installable through
agent_install.install()).
"""
from __future__ import annotations

import pytest

# 28 supported harnesses (mechanism doesn't matter for this smoke test).
SUPPORTED_HARNESSES = [
    # symlink (15)
    "augment", "claude-code", "codebuddy", "command-code", "cortex",
    "cursor", "droid", "forgecode", "junie", "kode", "neovate", "pi",
    "pochi", "qoder", "rovodev",
    # translate (10)
    "codex", "devin", "gemini-cli", "github-copilot", "kilo",
    "kiro-cli", "mistral-vibe", "mux", "opencode", "qwen-code",
    # config_file_folder (3)
    "aider-desk", "dexto", "firebender",
]


@pytest.fixture
def fake_canonical(tmp_path, monkeypatch):
    """Seed a canonical agent directory with a content file."""
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_paths import canonical_agent_dir
    canonical = canonical_agent_dir("smoke-agent", scope="global")
    canonical.mkdir(parents=True, exist_ok=True)
    (canonical / "smoke-agent.md").write_text(
        "---\nname: smoke-agent\ndescription: smoke\n---\n\nSmoke body.\n"
    )
    return canonical


@pytest.mark.parametrize("harness", SUPPORTED_HARNESSES)
def test_install_one_harness_creates_projection(harness, fake_canonical, tmp_path, monkeypatch):
    """Per-harness smoke: install creates at least one file under HOME."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    from agent_toolkit_cli.agent_install import apply, InstallPlan
    plan = InstallPlan(
        slug="smoke-agent", scope="global", source=None, ref=None,
        add_agents=(harness,), remove_agents=(),
    )
    result = apply(plan)
    # Either the harness is supported and produces ≥1 file, OR it raises
    # UnsupportedMechanismError (which becomes a 'skipped' record). Smoke
    # asserts the supported case.
    assert harness not in result.skipped, f"{harness} unexpectedly skipped"
    assert len(result.created) >= 1, f"{harness} produced no projection"
    for path in result.created:
        assert path.exists(), f"{harness}: created path {path} does not exist"
        # Must be inside the tmp HOME or XDG_CONFIG (no leakage).
        path_str = str(path)
        assert str(tmp_path) in path_str, (
            f"{harness}: projection at {path} escaped tmp_path"
        )
```

### Step 13.2: Run the smoke test

Run: `uv run pytest tests/test_cli/test_agent_install_e2e.py -v 2>&1 | tail -10`
Expected: 28 passed.

### Step 13.3: Confirm full suite

Run: `uv run pytest -q`
Expected: 681 passed, 2 skipped.

### Step 13.4: Commit

```bash
git add tests/test_cli/test_agent_install_e2e.py
git commit -m "test(agent_install): e2e smoke for all 28 supported cells

Acceptance criterion #3: each of the 28 supported harnesses installs
via apply() and produces ≥1 on-disk projection inside HOME/XDG."
```

---

## Task 14: PR2 scope guard + final sweep

**Files:**
- Create: `tests/test_cli/test_pr2_scope_guard.py`

### Step 14.1: Write the scope guard

Create `tests/test_cli/test_pr2_scope_guard.py`:

```python
"""PR2 of v3.0.0: agent facade + 28 projection adapters.

Throwaway scope guard — deleted at the start of PR3.
Includes pytest.skip fallback for shallow CI clones
(per feedback_ci_shallow_clone_scope_guard).
"""
from __future__ import annotations

import subprocess

import pytest


ALLOWED = {
    # New files (PR2 production):
    "src/agent_toolkit_cli/agent_paths.py",
    "src/agent_toolkit_cli/agent_install.py",
    "src/agent_toolkit_cli/agent_lock.py",
    "src/agent_toolkit_cli/agent_adapters/__init__.py",
    "src/agent_toolkit_cli/agent_adapters/symlink.py",
    "src/agent_toolkit_cli/agent_adapters/translate.py",
    "src/agent_toolkit_cli/agent_adapters/config_file_folder.py",
    # Modified existing files (PR2 minimal touch):
    "src/agent_toolkit_cli/_paths_core.py",
    "src/agent_toolkit_cli/skill_lock.py",
    "src/agent_toolkit_cli/skill_agents.py",
    # New test files:
    "tests/test_cli/test_agent_paths.py",
    "tests/test_cli/test_agent_install.py",
    "tests/test_cli/test_agent_install_e2e.py",
    "tests/test_cli/test_agent_lock.py",
    "tests/test_cli/test_paths_core_agent_binding.py",
    "tests/test_cli/test_lock_agent_path.py",
    "tests/test_cli/test_agent_adapters/__init__.py",
    "tests/test_cli/test_agent_adapters/test_dispatcher.py",
    "tests/test_cli/test_agent_adapters/test_symlink.py",
    "tests/test_cli/test_agent_adapters/test_translate.py",
    "tests/test_cli/test_agent_adapters/test_config_file_folder.py",
    "tests/test_cli/test_pr2_scope_guard.py",
    # Modified existing tests:
    "tests/test_cli/test_skill_agents.py",
    "tests/test_subagent_matrix.py",
}

ALLOWED_PREFIXES = (
    "docs/superpowers/specs/",
    "docs/superpowers/plans/",
    "assets/verification/",
)


def test_pr2_did_not_modify_caller_modules():
    """PR2 acceptance criterion #2: no caller of skill_* needs to be edited.

    Skipped on shallow CI clones where origin/main is unavailable.
    """
    proc = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD"],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        pytest.skip("origin/main not available (likely a shallow clone)")
    changed = [p for p in proc.stdout.splitlines() if p]
    leaks = [
        p for p in changed
        if p not in ALLOWED
        and not any(p.startswith(pref) for pref in ALLOWED_PREFIXES)
    ]
    assert not leaks, (
        f"PR2 modified files outside its scope: {leaks}.\n"
        "If a caller move was intentional, add it to ALLOWED — but spec "
        "acceptance criterion #2 says PR2 does not move callers. Reconsider."
    )
```

### Step 14.2: Run the scope guard

Run: `uv run pytest tests/test_cli/test_pr2_scope_guard.py -v`
Expected: 1 passed.

### Step 14.3: Final full-suite confirmation

Run: `uv run pytest -q`
Expected: 682 passed, 2 skipped.

### Step 14.4: Quick lint sweep

Run: `uv run ruff check src/ tests/`
Expected: All checks passed.

### Step 14.5: Commit

```bash
git add tests/test_cli/test_pr2_scope_guard.py
git commit -m "test: PR2 scope guard

Throwaway — delete at start of PR3 (per spec acceptance criterion #8).
Includes pytest.skip fallback for shallow CI clones."
```

---

## Self-review (controller, before handing the plan to the build phase)

Run each:

**1. Spec coverage** — does every spec section map to a task?

| Spec section | Task(s) |
|---|---|
| Decision 1 (mechanism dispatch on AgentConfig) | Task 5, 11 |
| Decision 2 / Correction B (LockEntry.agent_path first-class) | Task 2 |
| Decision 3 (agent_adapters/<mechanism>.py layout) | Tasks 6, 8, 9, 10 |
| Correction A (3-mechanism taxonomy) | Tasks 8, 9, 10 (no dual_symlink.py) |
| Correction C (subagent_mechanism field name) | Task 5 |
| AGENT_BINDING | Task 1 |
| agent_paths.py facade | Task 3 |
| agent_install.py facade | Task 7 |
| agent_lock.py facade | Task 4 |
| general-agent synthetic | Task 5 |
| 28 cells installable (criterion #3) | Tasks 8, 9, 10, 11, 13 |
| Lock round-trip (criterion #4) | Tasks 2, 4 |
| Matrix parity (criterion #5) | Task 12 |
| No CLI surface change (criterion #6) | Implicit — no commands/ touches |
| Mechanism modules not co-mingled (criterion #7) | Tasks 8, 9, 10 (separate files) |
| Scope guard (criterion #8) | Task 14 |

No gaps.

**2. Placeholder scan** — search for `TODO`, `TBD`, `implement later`, `fill in`, `Add appropriate`, `Similar to`. Grep:

```bash
grep -nE "TODO|TBD|implement later|fill in|Add appropriate|Similar to Task" docs/superpowers/plans/2026-05-28-v3-pr2-agent-facade-and-adapters.md
```

Expected output (after committing the plan): only the literal mentions inside the No-Placeholders self-review section. No actual placeholder strings in task content.

**3. Type consistency** — check method signatures across tasks. Key signatures:

| Symbol | Defined in task | Used in task | Consistent? |
|---|---|---|---|
| `AgentAdapter.install(slug, content_path, *, scope, home, project)` | 6 | 7, 8, 9, 10, 13 | ✓ |
| `AgentAdapter.uninstall(slug, *, scope, home, project)` | 6 | 7, 8, 9, 10 | ✓ |
| `adapter_for(harness) → AgentAdapter` | 6 | 8, 9, 10 | ✓ |
| `subagent_mechanism: Literal[...]` | 5 | 11 | ✓ |
| `_AGENT_SYNTHETIC_NAMES = frozenset({"general-agent"})` | 7 | (consumed via plan/_current_linked_agents) | ✓ |
| `LockEntry.agent_path: str \| None` | 2 | 4, 7 | ✓ |
| `AGENT_BINDING` | 1 | 3, 4 | ✓ |
| `get_adapter(name) → AgentAdapter` | 6 | 7, 11, 12 | ✓ |

No inconsistencies.

---

## Execution handoff

**This plan is ready for `superpowers:subagent-driven-development`.** 14 tasks, ordered for dependency. Each task is small enough (one file group, 2-7 steps) for a fresh implementer subagent. Two-stage review after each.

Total estimated tasks: 14. Total estimated test additions: ~150 new tests. Final expected count: 682 passing (was 534 on main pre-PR2).
