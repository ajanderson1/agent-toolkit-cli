# v3.0.0 PR1 — kind dimension foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut the install/paths seam along a `kind` dimension via a shared kind-agnostic core + thin per-kind facade, with zero user-visible behaviour change.

**Architecture:** Introduce two new internal modules — `_paths_core.py` (path/lock-filename resolution parameterised by a `KindBinding`) and `_install_core.py` (the kind-agnostic parts of the install engine) — plus a `KindBinding` value object. Re-implement `skill_paths.py` and `skill_install.py` as thin facades that bind their core to `SKILL_BINDING`. `skill_lock.py` stays as-is (already kind-agnostic at the IO layer). Add a coexisting `general-skill` synthetic harness entry alongside the existing `universal` one — the rename and removal of `universal` is PR3.

**Tech Stack:** Python 3.11+ (uv-managed), pytest, ruff. No new dependencies.

**Why two cores not three:** Reading `skill_lock.py` confirms it is already kind-agnostic — `LockFile.skills` is a generic `dict[str, LockEntry]` keyed by slug, and `read_lock`/`write_lock` know nothing about the asset kind. The on-disk filename is set by `library_lock_path()` in `skill_paths.py`. So `_paths_core.py` carries the lock-filename binding; `skill_lock.py` keeps its current shape. The field name `LockFile.skills` becomes a vestigial label (like `xargs` predating UTF-8) rather than getting renamed — preserves byte-identical lockfile output, which is acceptance criterion #4 of the spec.

---

## File Structure

| File | Responsibility | Status |
|---|---|---|
| `src/agent_toolkit_cli/_paths_core.py` | `KindBinding` dataclass; kind-agnostic path/lock-filename helpers. Pure functions, no globals. | **new** |
| `src/agent_toolkit_cli/_install_core.py` | Kind-agnostic parts of the install engine: `InstallError` hierarchy, `InstallPlan`/`InstallResult` dataclasses, `_symlink_or_copy`, `_should_skip_symlink`, `plan()`, `_current_linked_agents`, the kind-agnostic body of `apply()`. Bindings flow through arguments. | **new** |
| `src/agent_toolkit_cli/skill_paths.py` | Facade: imports core, binds `SKILL_BINDING`, re-exports the existing public API verbatim. | **modified** (slim) |
| `src/agent_toolkit_cli/skill_install.py` | Facade: imports core, binds `SKILL_BINDING`, re-exports the existing public API verbatim. Keeps `_universal_bundle_link` and `_project_universal_link` as skill-specific helpers (PR3 generalises them). | **modified** (slim) |
| `src/agent_toolkit_cli/skill_agents.py` | Add the `"general-skill"` synthetic entry alongside the existing `"universal"`. Both resolve to `.agents/skills/`. | **modified** (additive) |
| `src/agent_toolkit_cli/skill_lock.py` | **Unchanged.** Already kind-agnostic at the IO layer. | unchanged |
| `tests/test_cli/test_paths_core.py` | Unit-test the core with a fake `KindBinding`. | **new** |
| `tests/test_cli/test_install_core.py` | Unit-test the core's kind-agnosticism (planning, skip rules) with a fake `KindBinding`. | **new** |
| `tests/test_cli/test_skill_facade_parity.py` | Snapshot test the public-symbol surface of `skill_paths`, `skill_install`, `skill_lock`. | **new** |
| `tests/test_cli/test_skill_agents.py` | Add `general-skill` membership assertions. | **modified** (additive) |

---

## Task ordering

Tests-first, file-by-file. Each task is a TDD micro-cycle: write the failing test, see it fail, make it pass, commit. The order is chosen so dependent files can import their dependencies — `_paths_core.py` first (no deps), then the `skill_paths.py` facade, then `_install_core.py` (depends on paths), then the `skill_install.py` facade, then `skill_agents.py` (orthogonal — could be first, but parking it last keeps the refactor and the catalog change in distinct commits).

---

### Task 1: Define `KindBinding` in `_paths_core.py`

**Files:**
- Create: `src/agent_toolkit_cli/_paths_core.py`
- Test: `tests/test_cli/test_paths_core.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli/test_paths_core.py
from agent_toolkit_cli._paths_core import KindBinding, SKILL_BINDING


def test_kind_binding_is_frozen_dataclass():
    b = KindBinding(
        kind="x",
        canonical_dirname="xs",
        library_subdir="_library/xs",
        lock_filename="xs-lock.json",
        general_harness_name="general-x",
    )
    import dataclasses
    assert dataclasses.is_dataclass(b)
    # Frozen — assignment should raise.
    import pytest
    with pytest.raises(dataclasses.FrozenInstanceError):
        b.kind = "y"  # type: ignore[misc]


def test_skill_binding_is_the_canonical_skill_binding():
    assert SKILL_BINDING.kind == "skill"
    assert SKILL_BINDING.canonical_dirname == "skills"
    assert SKILL_BINDING.library_subdir == "skills"  # under ~/.agent-toolkit/
    assert SKILL_BINDING.lock_filename == "skills-lock.json"
    assert SKILL_BINDING.general_harness_name == "general-skill"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_paths_core.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_toolkit_cli._paths_core'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/agent_toolkit_cli/_paths_core.py
"""Kind-agnostic path/lock-filename core. Bound by per-kind facades.

A `KindBinding` carries everything the path helpers need to know about a
specific asset kind. `SKILL_BINDING` is the only binding PR1 instantiates;
`AGENT_BINDING` arrives in PR2.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KindBinding:
    kind: str                  # "skill" | "agent"
    canonical_dirname: str     # "skills" | "agents" — used in the catalog config's per-harness dir
    library_subdir: str        # "skills" | "agents" — directory name under ~/.agent-toolkit/
    lock_filename: str         # "skills-lock.json" | "agents-lock.json"
    general_harness_name: str  # "general-skill" | "general-agent"


SKILL_BINDING = KindBinding(
    kind="skill",
    canonical_dirname="skills",
    library_subdir="skills",
    lock_filename="skills-lock.json",
    general_harness_name="general-skill",
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_paths_core.py -v`
Expected: PASS, 2 tests.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/_paths_core.py tests/test_cli/test_paths_core.py
git commit -m "feat(_paths_core): introduce KindBinding + SKILL_BINDING

First seam of the v3.0.0 kind dimension (#252). KindBinding is the value
object that future kinds (agent kind in PR2) bind into the shared core.
SKILL_BINDING is the only instance materialised in PR1.

Refs #252"
```

---

### Task 2: Move path helpers into `_paths_core.py`, with binding-driven library root and lock-file path

**Files:**
- Modify: `src/agent_toolkit_cli/_paths_core.py`
- Test: `tests/test_cli/test_paths_core.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli/test_paths_core.py`:

```python
import os
from pathlib import Path
from agent_toolkit_cli._paths_core import (
    KindBinding,
    SKILL_BINDING,
    library_root_for_kind,
    library_lock_path_for_kind,
)


def test_library_root_for_kind_uses_binding_subdir(tmp_path, monkeypatch):
    monkeypatch.delenv("AGENT_TOOLKIT_SKILLS_ROOT", raising=False)
    fake_home = tmp_path / "h"
    monkeypatch.setenv("HOME", str(fake_home))
    # The existing library_root() returns ~/.agent-toolkit/skills/. The
    # kinded helper returns ~/.agent-toolkit/<binding.library_subdir>/.
    expected = fake_home / ".agent-toolkit" / "skills"
    assert library_root_for_kind(SKILL_BINDING, env=dict(os.environ)) == expected


def test_library_root_for_kind_with_fake_kind(tmp_path, monkeypatch):
    monkeypatch.delenv("AGENT_TOOLKIT_SKILLS_ROOT", raising=False)
    fake_home = tmp_path / "h"
    monkeypatch.setenv("HOME", str(fake_home))
    fake = KindBinding(
        kind="x", canonical_dirname="xs", library_subdir="xs",
        lock_filename="xs-lock.json", general_harness_name="general-x",
    )
    assert library_root_for_kind(fake, env=dict(os.environ)) == fake_home / ".agent-toolkit" / "xs"


def test_library_lock_path_for_kind(tmp_path, monkeypatch):
    monkeypatch.delenv("AGENT_TOOLKIT_SKILLS_ROOT", raising=False)
    fake_home = tmp_path / "h"
    monkeypatch.setenv("HOME", str(fake_home))
    assert library_lock_path_for_kind(SKILL_BINDING, env=dict(os.environ)) \
        == fake_home / ".agent-toolkit" / "skills-lock.json"


def test_library_root_for_kind_skill_respects_env_override(tmp_path, monkeypatch):
    """Back-compat: $AGENT_TOOLKIT_SKILLS_ROOT must still override SKILL_BINDING."""
    custom = tmp_path / "elsewhere"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(custom))
    assert library_root_for_kind(SKILL_BINDING, env=dict(os.environ)) == custom
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli/test_paths_core.py -v`
Expected: FAIL — `library_root_for_kind` and `library_lock_path_for_kind` do not exist yet.

- [ ] **Step 3: Implement**

Append to `src/agent_toolkit_cli/_paths_core.py`:

```python
import os
from pathlib import Path


def library_root_for_kind(binding: KindBinding, env: dict[str, str] | None = None) -> Path:
    """Return the library root for a given kind.

    For the skill kind this preserves the existing `$AGENT_TOOLKIT_SKILLS_ROOT`
    override; for other kinds the env override does not apply (intentional —
    other kinds get their own override variable in their own PR if needed).
    Falls back to ~/.agent-toolkit/<binding.library_subdir>/.
    """
    resolved_env = env if env is not None else os.environ
    if binding.kind == "skill":
        override = resolved_env.get("AGENT_TOOLKIT_SKILLS_ROOT", "").strip()
        if override:
            return Path(override)
    # Resolve $HOME from the supplied env so tests are not coupled to the
    # process-wide os.environ when they monkeypatch HOME.
    home = Path(resolved_env.get("HOME") or str(Path.home()))
    return home / ".agent-toolkit" / binding.library_subdir


def library_lock_path_for_kind(binding: KindBinding, env: dict[str, str] | None = None) -> Path:
    """Return the global lock-file path for a given kind.

    Lives at <library_root>.parent / <binding.lock_filename>, e.g.
    ~/.agent-toolkit/skills-lock.json by default.
    """
    return library_root_for_kind(binding, env).parent / binding.lock_filename
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli/test_paths_core.py -v`
Expected: PASS — 5 tests now (2 from Task 1 + 3 new).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/_paths_core.py tests/test_cli/test_paths_core.py
git commit -m "feat(_paths_core): binding-driven library root + lock path

library_root_for_kind() and library_lock_path_for_kind() centralise the
kind-aware path resolution. SKILL_BINDING preserves the existing
\$AGENT_TOOLKIT_SKILLS_ROOT override; other kinds opt in to their own
override if/when their PR adds one.

Refs #252"
```

---

### Task 3: Slim `skill_paths.py` to a facade over `_paths_core.py`

**Files:**
- Modify: `src/agent_toolkit_cli/skill_paths.py`
- Test: `tests/test_cli/test_skill_facade_parity.py` (new)

- [ ] **Step 1: Capture the current public-symbol set (sanity)**

Run: `uv run python -c "import agent_toolkit_cli.skill_paths as m; print([n for n in dir(m) if not n.startswith('__')])"`

Expected output (record verbatim — used in the parity test):

```
['HOME', 'Literal', 'Path', 'SUPPORTED_HARNESSES', 'Scope', '_SHORTCUT_TO_AGENT', '_root', 'agent_projection_dir', 'canonical_skill_dir', 'hashlib', 'harness_projection_dir', 'lock_file_path', 'library_lock_path', 'library_root', 'library_skill_path', 'os', 'parent_clone_path', 'project_id', 'project_parents_root', 'project_store_root']
```

(Imports like `os`, `hashlib`, `Path`, `Literal` are in `dir()` because they're module-level imports — the parity test will assert on a curated set of public names, not the full `dir()`.)

- [ ] **Step 2: Write the failing facade-parity test**

Create `tests/test_cli/test_skill_facade_parity.py`:

```python
"""Facade parity: the public-symbol surface of skill_paths / skill_install /
skill_lock must not regress during the kind-dimension refactor.

If a name is removed from this set, downstream callers (tests + CLI verbs)
will break. Renames or moves are a PR-level decision, not a refactor side
effect — fail loudly here so the diff has to be self-aware.
"""
from __future__ import annotations

SKILL_PATHS_PUBLIC = {
    "Scope",
    "canonical_skill_dir",
    "lock_file_path",
    "library_root",
    "library_skill_path",
    "library_lock_path",
    "project_id",
    "project_store_root",
    "project_parents_root",
    "parent_clone_path",
    "agent_projection_dir",
    "harness_projection_dir",
    "SUPPORTED_HARNESSES",
}


def test_skill_paths_public_surface_preserved():
    import agent_toolkit_cli.skill_paths as m
    actual = set(dir(m))
    missing = SKILL_PATHS_PUBLIC - actual
    assert not missing, f"skill_paths lost public names: {sorted(missing)}"
```

- [ ] **Step 3: Run test to verify it passes against the unrefactored module**

Run: `uv run pytest tests/test_cli/test_skill_facade_parity.py -v`
Expected: PASS (before the refactor — the test is a guard, not an indicator of refactor progress).

- [ ] **Step 4: Refactor `skill_paths.py` to a facade**

Replace `src/agent_toolkit_cli/skill_paths.py` body with:

```python
"""Skill-flavoured facade over `_paths_core.py`.

Public symbols (`canonical_skill_dir`, `lock_file_path`, `library_root`,
`library_skill_path`, `library_lock_path`, `project_id`,
`project_store_root`, `project_parents_root`, `parent_clone_path`,
`agent_projection_dir`, `harness_projection_dir`, `SUPPORTED_HARNESSES`,
`Scope`) are preserved verbatim — implementations delegate to
`_paths_core` where the binding-driven helpers live.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Literal

from agent_toolkit_cli._paths_core import (
    SKILL_BINDING,
    library_lock_path_for_kind,
    library_root_for_kind,
)
from agent_toolkit_cli.skill_agents import AGENTS, UnknownAgentError

Scope = Literal["project", "global"]


def _root(scope: Scope, home: Path | None, project: Path | None) -> Path:
    if scope == "global":
        if home is None:
            raise ValueError("global scope requires home")
        return home
    if project is None:
        raise ValueError("project scope requires project")
    return project


def library_root(env: dict[str, str] | None = None) -> Path:
    """Return the root of the global skill library.

    Thin shim over `_paths_core.library_root_for_kind(SKILL_BINDING, …)`.
    Honors $AGENT_TOOLKIT_SKILLS_ROOT for backward compatibility.
    """
    return library_root_for_kind(SKILL_BINDING, env)


def library_skill_path(slug: str, *, env: dict[str, str] | None = None) -> Path:
    return library_root(env) / slug


def library_lock_path(env: dict[str, str] | None = None) -> Path:
    """Global skills-lock.json path. Thin shim over the kinded helper."""
    return library_lock_path_for_kind(SKILL_BINDING, env)


def canonical_skill_dir(
    slug: str,
    *,
    scope: Scope,
    home: Path | None = None,
    project: Path | None = None,
) -> Path:
    if scope == "global":
        return library_skill_path(slug)
    if project is None:
        raise ValueError("project scope requires project")
    return project_store_root(project) / slug


def lock_file_path(
    *,
    scope: Scope,
    home: Path | None = None,
    project: Path | None = None,
) -> Path:
    if scope == "global":
        return library_lock_path()
    if project is None:
        raise ValueError("project scope requires project")
    # Per-project lock filename follows the binding so PR2's agent lock at
    # project scope lands at <project>/agents-lock.json automatically.
    return project / SKILL_BINDING.lock_filename


def project_id(project: Path) -> str:
    real = project.resolve()
    abs_str = str(real)
    sanitized = "".join(
        c if (c.isalnum() or c in "._-") else "-" for c in abs_str
    ).strip("-")
    digest = hashlib.sha256(abs_str.encode()).hexdigest()[:6]
    return f"{sanitized}-{digest}"


def project_store_root(project: Path, *, env: dict[str, str] | None = None) -> Path:
    return library_root(env).parent / "projects" / project_id(project) / "skills"


def parent_clone_path(
    owner: str, repo: str, *, ref: str | None,
    env: dict[str, str] | None = None,
    root: Path | None = None,
) -> Path:
    base = root if root is not None else library_root(env)
    leaf = repo if ref is None else f"{repo}@{ref}"
    return base / "_parents" / owner / leaf


def project_parents_root(project: Path) -> Path:
    return project_store_root(project)


def agent_projection_dir(
    agent_name: str, slug: str, *,
    scope: Scope, home: Path | None, project: Path | None,
) -> Path:
    if agent_name not in AGENTS:
        raise UnknownAgentError(agent_name)
    cfg = AGENTS[agent_name]
    if scope == "global":
        return cfg.global_skills_dir / slug
    project_root = _root(scope, home, project)
    return project_root / cfg.skills_dir / slug


_SHORTCUT_TO_AGENT = {
    "claude":   "claude-code",
    "codex":    "codex",
    "opencode": "opencode",
    "gemini":   "gemini-cli",
    "pi":       "pi",
}

SUPPORTED_HARNESSES: tuple[str, ...] = tuple(_SHORTCUT_TO_AGENT.keys())


def harness_projection_dir(
    harness: str, slug: str, *,
    scope: Scope, home: Path | None, project: Path | None,
) -> Path:
    if harness not in _SHORTCUT_TO_AGENT:
        raise ValueError(f"unknown harness: {harness}")
    return agent_projection_dir(
        _SHORTCUT_TO_AGENT[harness], slug,
        scope=scope, home=home, project=project,
    )
```

- [ ] **Step 5: Run the full path-touching test suite to verify no regression**

Run: `uv run pytest tests/test_cli/test_paths_core.py tests/test_cli/test_skill_facade_parity.py tests/test_cli/ -k "paths or install or lock" -v`
Expected: PASS — facade parity holds and existing path tests still pass.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/skill_paths.py tests/test_cli/test_skill_facade_parity.py
git commit -m "refactor(skill_paths): thin facade over _paths_core

skill_paths.py now binds SKILL_BINDING and delegates library_root/
library_lock_path to _paths_core. Public surface preserved verbatim
(facade parity test pins this). lock_file_path() at project scope uses
binding.lock_filename so PR2's agent lock at project scope is one line.

Refs #252"
```

---

### Task 4: Add `general-skill` synthetic harness in `skill_agents.py`

**Files:**
- Modify: `src/agent_toolkit_cli/skill_agents.py:432-440` (the `universal` entry block)
- Test: `tests/test_cli/test_skill_agents.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli/test_skill_agents.py`:

```python
def test_general_skill_entry_exists_and_resolves_to_dotagents_skills():
    from agent_toolkit_cli.skill_agents import AGENTS
    assert "general-skill" in AGENTS
    cfg = AGENTS["general-skill"]
    assert cfg.skills_dir == ".agents/skills"
    assert cfg.show_in_universal_list is False
    assert cfg.is_universal is True  # by skills_dir membership


def test_universal_and_general_skill_coexist_with_same_dir():
    """PR1 ships both. The `universal` synthetic is removed in PR3."""
    from agent_toolkit_cli.skill_agents import AGENTS
    assert AGENTS["universal"].skills_dir == AGENTS["general-skill"].skills_dir
    assert AGENTS["universal"].global_skills_dir == AGENTS["general-skill"].global_skills_dir


def test_get_universal_agents_does_not_include_general_skill():
    """Both `universal` and `general-skill` set show_in_universal_list=False,
    so neither appears in the legacy 'universal agents' listing."""
    from agent_toolkit_cli.skill_agents import get_universal_agents
    listed = get_universal_agents()
    assert "universal" not in listed
    assert "general-skill" not in listed
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli/test_skill_agents.py::test_general_skill_entry_exists_and_resolves_to_dotagents_skills -v`
Expected: FAIL — `KeyError: 'general-skill'`.

- [ ] **Step 3: Add the `general-skill` entry**

In `src/agent_toolkit_cli/skill_agents.py`, immediately after the `"universal":` block (line ~439), before the closing `}`:

```python
    "general-skill": AgentConfig(
        name="general-skill",
        display_name="General (skills)",
        skills_dir=".agents/skills",
        global_skills_dir=XDG_CONFIG / "agents/skills",
        show_in_universal_list=False,
        detect_installed=lambda: False,
    ),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli/test_skill_agents.py -v`
Expected: PASS — the three new tests pass; pre-existing tests untouched.

- [ ] **Step 5: Run the full test suite to confirm no test depended on `len(AGENTS) == 54` or similar invariant**

Run: `uv run pytest tests/ -x -q 2>&1 | tail -30`
Expected: PASS for the whole suite, or a single specific failure pinpointing where an `len(AGENTS)` assertion lived. If a test failure surfaces and is *only* asserting the catalog size, update the constant in that test from `54` to `55` and add a comment: `# +1 for general-skill (PR1 of v3.0.0, coexists with universal)`.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/skill_agents.py tests/test_cli/test_skill_agents.py
git commit -m "feat(skill_agents): add general-skill synthetic alongside universal

First half of the per-kind general-* model. Coexists with the existing
'universal' synthetic for PR1 (no behaviour change — both resolve to
.agents/skills). The rename and the removal of 'universal' are PR3.

Refs #252"
```

---

### Task 5: Carve `_install_core.py` out of `skill_install.py` (kind-agnostic body)

**Files:**
- Create: `src/agent_toolkit_cli/_install_core.py`
- Modify: `src/agent_toolkit_cli/skill_install.py` (will become thinner in Task 6 — Task 5 only moves shared logic)
- Test: `tests/test_cli/test_install_core.py`

This is the largest task; split into sub-steps.

- [ ] **Step 1: Write the failing test that asserts the core can be imported and instantiated against a non-skill binding**

Create `tests/test_cli/test_install_core.py`:

```python
"""Direct tests against _install_core to prove kind-agnosticism.

These tests use a synthetic KindBinding to confirm the core does not hard-
code 'skill' anywhere; they do not exercise file-system side effects.
"""
from __future__ import annotations

import pytest

from agent_toolkit_cli._install_core import (
    InstallError,
    LockMismatchError,
    DirtyCanonicalError,
    InstallPlan,
    InstallResult,
)
from agent_toolkit_cli._paths_core import KindBinding


FAKE_BINDING = KindBinding(
    kind="x",
    canonical_dirname="xs",
    library_subdir="xs",
    lock_filename="xs-lock.json",
    general_harness_name="general-x",
)


def test_install_core_error_hierarchy():
    assert issubclass(LockMismatchError, InstallError)
    assert issubclass(DirtyCanonicalError, InstallError)
    assert issubclass(InstallError, RuntimeError)


def test_install_plan_dataclass_shape_unchanged():
    """Snapshot the public field set so PR2 cannot accidentally rename one."""
    import dataclasses
    fields = {f.name for f in dataclasses.fields(InstallPlan)}
    assert fields == {
        "slug", "scope", "source", "ref", "add_agents", "remove_agents",
    }


def test_install_result_dataclass_shape_unchanged():
    import dataclasses
    fields = {f.name for f in dataclasses.fields(InstallResult)}
    assert fields == {
        "plan", "canonical_path", "created", "removed", "skipped", "lock_action",
    }


def test_install_core_has_no_hardcoded_skill_string():
    """Defensive: the core's source must not reference the word 'skill' in a
    way that would couple it to the skill kind. A few existing identifiers
    (e.g. 'skill_path' which is a v1 lock field name) are grandfathered via an
    allowlist."""
    import inspect
    import agent_toolkit_cli._install_core as core
    src = inspect.getsource(core)
    # Allowed: references to the skill_lock module (still kind-agnostic IO)
    # and to the v1 lock-field name skill_path. Anything else is a smell.
    for line in src.splitlines():
        if "skill" not in line.lower():
            continue
        allowed = (
            "skill_lock" in line
            or "skill_path" in line  # v1 LockEntry field
            or "skill_git" in line   # cross-kind git helpers (PR2 will rename)
            or line.lstrip().startswith("#")
            or line.lstrip().startswith('"""')
            or line.lstrip().startswith("'''")
        )
        assert allowed, f"unwhitelisted 'skill' in _install_core: {line!r}"
```

- [ ] **Step 2: Run the new test to confirm it fails**

Run: `uv run pytest tests/test_cli/test_install_core.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_toolkit_cli._install_core'`.

- [ ] **Step 3: Create `_install_core.py` with the moved code**

Create `src/agent_toolkit_cli/_install_core.py` by moving the kind-agnostic pieces out of `skill_install.py`. The contents below are the full file — copy verbatim, then in Task 6 we'll delete the moved blocks from `skill_install.py`.

```python
"""Kind-agnostic install engine. Bound by per-kind facades (skill_install,
future agent_install). All public symbols are re-exported from the facades
so existing call sites keep working.

PR1 boundary: any helper that has to know whether the asset is a skill or
an agent (e.g. _universal_bundle_link, _project_universal_link) lives in
the facade, NOT here. The core takes a KindBinding when it needs to know
the canonical dirname, lock filename, or general-harness name.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

from agent_toolkit_cli.skill_agents import (
    AGENTS, UnknownAgentError, get_agent,
)
from agent_toolkit_cli.skill_paths import (
    Scope,
    agent_projection_dir,
    canonical_skill_dir,
)
from agent_toolkit_cli.skill_source import ParsedSource


class InstallError(RuntimeError):
    """Base error for install failures."""


def _doctor_hint(slug: str, scope: str) -> str:
    flag = "-g" if scope == "global" else "-p"
    return f"\n  Run: agent-toolkit-cli skill doctor {flag}  (removes stray symlinks)"


class LockMismatchError(InstallError):
    """Canonical exists on disk but lock entry source differs from request."""


class DirtyCanonicalError(InstallError):
    """Full-remove requested against dirty canonical without --force."""


def _symlink_or_copy(src: Path, dest: Path) -> str:
    if dest.exists() or dest.is_symlink():
        raise InstallError(f"{dest}: refusing to overwrite existing path")
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        dest.symlink_to(src, target_is_directory=True)
        return "symlink"
    except OSError:
        shutil.copytree(src, dest)
        return "copy"


@dataclass(frozen=True)
class InstallPlan:
    slug: str
    scope: Scope
    source: ParsedSource | None
    ref: str | None
    add_agents: tuple[str, ...]
    remove_agents: tuple[str, ...]

    def is_noop(self) -> bool:
        return (self.source is None
                and not self.add_agents
                and not self.remove_agents)


@dataclass(frozen=True)
class InstallResult:
    plan: InstallPlan
    canonical_path: Path
    created: tuple[Path, ...]
    removed: tuple[Path, ...]
    skipped: tuple[str, ...]
    lock_action: Literal["added", "updated", "unchanged"]


def _should_skip_symlink(
    *, agent_name: str, scope: Scope, project: Path | None,
) -> tuple[bool, str]:
    cfg = get_agent(agent_name)
    if cfg.is_universal and scope == "global":
        return True, "universal-global"
    return False, ""


def plan(
    *,
    slug: str,
    scope: Scope,
    source: ParsedSource | None = None,
    ref: str | None = None,
    target_agents: Iterable[str] = (),
    home: Path | None = None,
    project: Path | None = None,
    universal_bundle_link: callable | None = None,
) -> InstallPlan:
    """Compute the minimal add/remove delta to reach target_agents.

    `universal_bundle_link` is injected by the facade — it is the kind-
    specific function that returns the per-slug bundle path (e.g.
    `~/.agents/skills/<slug>` for skills). Defaults to None for callers
    that do not need it (most plan-only computations).
    """
    for n in target_agents:
        if n not in AGENTS:
            raise UnknownAgentError(n)
    current = _current_linked_agents(
        slug=slug, scope=scope, home=home, project=project,
        universal_bundle_link=universal_bundle_link,
    )
    target = tuple(target_agents)
    add = tuple(n for n in target if n not in current)
    remove = tuple(n for n in current if n not in target)
    return InstallPlan(
        slug=slug, scope=scope, source=source, ref=ref,
        add_agents=add, remove_agents=remove,
    )


def _current_linked_agents(
    *, slug: str, scope: Scope,
    home: Path | None, project: Path | None,
    universal_bundle_link: callable | None = None,
) -> tuple[str, ...]:
    canonical = canonical_skill_dir(
        slug, scope=scope, home=home, project=project,
    )
    canonical_real = canonical.resolve() if canonical.exists() else canonical

    linked: list[str] = []

    if scope == "global" and universal_bundle_link is not None:
        bundle_link = universal_bundle_link(slug)
        if bundle_link.is_symlink() and bundle_link.resolve() == canonical_real:
            linked.append("universal")

    for name in AGENTS:
        if name == "universal":
            continue
        # PR1: general-skill is a synthetic with show_in_universal_list=False;
        # it should not appear in the linked-agents enumeration any more than
        # 'universal' does. PR3 will unify these.
        if name == "general-skill":
            continue

        skip, _ = _should_skip_symlink(
            agent_name=name, scope=scope, project=project,
        )
        if skip:
            continue

        link = agent_projection_dir(
            name, slug, scope=scope, home=home, project=project,
        )
        if link.is_symlink() and link.resolve() == canonical_real:
            linked.append(name)
    return tuple(linked)
```

- [ ] **Step 4: Run the new core tests**

Run: `uv run pytest tests/test_cli/test_install_core.py -v`
Expected: PASS — 4 tests.

- [ ] **Step 5: Commit (the core only; facade still re-defines these names — Task 6 dedupes)**

```bash
git add src/agent_toolkit_cli/_install_core.py tests/test_cli/test_install_core.py
git commit -m "feat(_install_core): move kind-agnostic install primitives into core

InstallError/LockMismatchError/DirtyCanonicalError, InstallPlan/
InstallResult, _symlink_or_copy, _should_skip_symlink, plan(),
_current_linked_agents now live in _install_core.py. plan() and
_current_linked_agents take an optional universal_bundle_link callable
injected by the facade — the kind-specific path stays in skill_install.

skill_install.py is not yet a facade; Task 6 (next commit) deletes the
moved definitions and re-exports from _install_core.

Refs #252"
```

---

### Task 6: Slim `skill_install.py` to a facade

**Files:**
- Modify: `src/agent_toolkit_cli/skill_install.py`
- Test: `tests/test_cli/test_skill_facade_parity.py` (extend)

- [ ] **Step 1: Capture the current public-symbol set of `skill_install`**

Run: `uv run python -c "import agent_toolkit_cli.skill_install as m; print(sorted([n for n in dir(m) if not n.startswith('_') or n in {'_universal_bundle_link','_project_universal_link'}]))"`

Expected (record verbatim — used in the parity test):

```
['DirtyCanonicalError', 'InstallError', 'InstallPlan', 'InstallResult', 'LockMismatchError', 'Scope', '_project_universal_link', '_universal_bundle_link', 'agent_projection_dir', 'apply', 'canonical_skill_dir', 'click', 'ensure_project_canonical', 'install', 'lock_file_path', 'migrate_project_canonical', 'plan', 'uninstall']
```

- [ ] **Step 2: Extend the facade-parity test**

Append to `tests/test_cli/test_skill_facade_parity.py`:

```python
SKILL_INSTALL_PUBLIC = {
    "InstallError",
    "LockMismatchError",
    "DirtyCanonicalError",
    "InstallPlan",
    "InstallResult",
    "plan",
    "apply",
    "install",
    "uninstall",
    "migrate_project_canonical",
    "ensure_project_canonical",
    "_universal_bundle_link",     # used by tests + ensure_project_canonical
    "_project_universal_link",    # used by ensure_project_canonical
}


def test_skill_install_public_surface_preserved():
    import agent_toolkit_cli.skill_install as m
    actual = set(dir(m))
    missing = SKILL_INSTALL_PUBLIC - actual
    assert not missing, f"skill_install lost public names: {sorted(missing)}"


SKILL_LOCK_PUBLIC = {
    "LockEntry",
    "LockFile",
    "SUPPORTED_VERSIONS",
    "read_lock",
    "write_lock",
    "add_entry",
    "remove_entry",
    "clone_url_from_entry",
    "_apply_insteadof",  # private but referenced in skill_import tests
}


def test_skill_lock_public_surface_preserved():
    import agent_toolkit_cli.skill_lock as m
    actual = set(dir(m))
    missing = SKILL_LOCK_PUBLIC - actual
    assert not missing, f"skill_lock lost public names: {sorted(missing)}"
```

- [ ] **Step 3: Run the parity tests against the pre-refactor `skill_install` to confirm baseline**

Run: `uv run pytest tests/test_cli/test_skill_facade_parity.py -v`
Expected: PASS (all three tests — skill_paths, skill_install, skill_lock surfaces all present).

- [ ] **Step 4: Refactor `skill_install.py` — delete the moved definitions, replace with re-exports**

In `src/agent_toolkit_cli/skill_install.py`:

1. **Delete** lines 36–198 (everything from `class InstallError` through the end of `_current_linked_agents`). These now live in `_install_core.py`.
2. **Replace** the docstring's module-level summary with a facade-flavoured one (preserve the v2.2 symlink-rules comment block — it documents skill-specific behaviour that the facade owns).
3. **Add** re-exports at the top:

```python
from agent_toolkit_cli._install_core import (
    InstallError,
    LockMismatchError,
    DirtyCanonicalError,
    InstallPlan,
    InstallResult,
    _symlink_or_copy,
    _should_skip_symlink,
    plan as _core_plan,
    _current_linked_agents as _core_current_linked_agents,
)
```

4. **Replace** the top-level `plan()` function (the one removed in step 1) with a thin shim that binds `_universal_bundle_link`:

```python
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
    return _core_plan(
        slug=slug, scope=scope, source=source, ref=ref,
        target_agents=target_agents, home=home, project=project,
        universal_bundle_link=_universal_bundle_link,
    )
```

5. **Replace** any internal call to `_current_linked_agents(...)` inside `apply()`, `install()`, `uninstall()`, `migrate_project_canonical`, `ensure_project_canonical` with `_core_current_linked_agents(..., universal_bundle_link=_universal_bundle_link)`.

6. **Keep** `_universal_bundle_link` and `_project_universal_link` exactly as they are — these are the skill-kind-specific helpers the facade owns.

- [ ] **Step 5: Run the full pytest suite**

Run: `uv run pytest tests/ -x -q 2>&1 | tail -40`
Expected: PASS — every existing test passes unchanged (the load-bearing spec criterion). If any test fails, diagnose:

  - If it's an import error → a moved symbol wasn't re-exported. Add to the import block in step 4.
  - If it's a behavioural diff in `apply()` → check whether you missed wiring `universal_bundle_link=_universal_bundle_link` into a `_current_linked_agents` call.
  - If it's a parity test failure → the re-export list is missing a name; copy from step 1's output.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/skill_install.py tests/test_cli/test_skill_facade_parity.py
git commit -m "refactor(skill_install): thin facade over _install_core

skill_install.py now imports InstallError/LockMismatchError/
DirtyCanonicalError, InstallPlan/InstallResult, _symlink_or_copy,
_should_skip_symlink, plan, _current_linked_agents from _install_core.
The skill-specific helpers (_universal_bundle_link,
_project_universal_link) stay here — they own the .agents/skills path
that defines skill universality. plan() injects them when delegating to
the core so the seam is honest.

Facade parity tests pin the public surface of skill_install + skill_lock
(skill_paths was pinned in Task 3). All existing tests pass unchanged.

Refs #252"
```

---

### Task 7: Final sweep — full suite, lint, and a no-callers-moved guard

**Files:**
- (no file changes — diagnostic only, then commit cleanups if any)
- Test: `tests/test_cli/test_pr1_scope_guard.py` (new — PR1-specific guard)

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest tests/ -q 2>&1 | tail -20`
Expected: PASS for the whole suite, no skips that weren't skipped on `main`.

- [ ] **Step 2: Run the linter**

Run: `uv run ruff check src/ tests/ 2>&1 | tail -20`
Expected: no new findings vs `main`. If new findings appear, fix them (typically unused imports left over after the refactor).

- [ ] **Step 3: Write a PR1 scope-guard test**

This test enforces the spec's acceptance criterion #5 — that PR1 does not touch caller modules.

Create `tests/test_cli/test_pr1_scope_guard.py`:

```python
"""PR1 of v3.0.0: refactor-only, no caller moves.

This test is throwaway — delete it in PR2. It exists to catch a sloppy
diff that drifts beyond the seam-cutting scope while PR1 is in review.
"""
from __future__ import annotations

import subprocess


# Files PR1 is allowed to modify.
ALLOWED = {
    # New files:
    "src/agent_toolkit_cli/_paths_core.py",
    "src/agent_toolkit_cli/_install_core.py",
    # Refactored:
    "src/agent_toolkit_cli/skill_paths.py",
    "src/agent_toolkit_cli/skill_install.py",
    # Additive:
    "src/agent_toolkit_cli/skill_agents.py",
    # Tests:
    "tests/test_cli/test_paths_core.py",
    "tests/test_cli/test_install_core.py",
    "tests/test_cli/test_skill_facade_parity.py",
    "tests/test_cli/test_skill_agents.py",
    "tests/test_cli/test_pr1_scope_guard.py",
    # Docs (any plan / spec / changelog files):
    # captured by prefix match below.
}

ALLOWED_PREFIXES = (
    "docs/superpowers/specs/",
    "docs/superpowers/plans/",
    "docs/agent-toolkit/",
    "assets/verification/",
)


def test_pr1_did_not_modify_caller_modules():
    proc = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD"],
        capture_output=True, text=True, check=True,
    )
    changed = [p for p in proc.stdout.splitlines() if p]
    leaks = [
        p for p in changed
        if p not in ALLOWED
        and not any(p.startswith(pref) for pref in ALLOWED_PREFIXES)
    ]
    assert not leaks, (
        f"PR1 modified files outside its scope: {leaks}.\n"
        "If a caller move was intentional, add it to ALLOWED — but the spec "
        "(acceptance criterion #5) says PR1 doesn't move callers. Reconsider "
        "before adding."
    )
```

- [ ] **Step 4: Run the scope guard**

Run: `uv run pytest tests/test_cli/test_pr1_scope_guard.py -v`
Expected: PASS — `git diff --name-only origin/main...HEAD` lists only files in ALLOWED + ALLOWED_PREFIXES.

If it fails, the leak list points at the file you need to either revert or justify. The most common honest-leak case is `pyproject.toml` if you bumped a dependency — that goes in ALLOWED.

- [ ] **Step 5: Commit the scope guard**

```bash
git add tests/test_cli/test_pr1_scope_guard.py
git commit -m "test: PR1 scope guard

Throwaway test that fails CI if PR1's diff strays beyond the kind-
dimension seam. Delete this file as the first commit of PR2.

Refs #252"
```

---

## Self-Review checklist (run before handing off)

1. **Spec coverage.** Each spec section maps to a task:
   - "_paths_core.py" → Tasks 1 & 2.
   - "_install_core.py" → Task 5.
   - "Lock core" → not extracted (rationale in plan header); spec acceptance #4 (byte-identical lockfile output) is still satisfied because `skill_lock.py` is unchanged.
   - "skill_paths.py facade" → Task 3.
   - "skill_install.py facade" → Task 6.
   - "general-skill entry" → Task 4.
   - "Facade parity test" → Tasks 3 + 6.
   - "Core dispatch tests" → Tasks 2 + 5.
   - "Lock round-trip test" → not needed (no extraction; existing lock tests cover round-trip).
   - "general-skill coexists with universal" → Task 4.
   - "Scope guard for PR1" → Task 7.

2. **Placeholder scan.** No "TBD", "implement later", "add appropriate X". Every step has the code or the exact command.

3. **Type / name consistency.** `KindBinding` field names match across Tasks 1, 2, 5. `SKILL_BINDING.lock_filename` referenced in Task 3 matches its definition in Task 1. `universal_bundle_link` callable referenced in Task 5 matches its injection in Task 6.

4. **Spec deviation explicitly recorded.** The plan header explains why `_lock_core.py` is not created — supported by reading `skill_lock.py` and confirming `LockFile.skills` is already kind-agnostic. The spec's "lock round-trip" test becomes "existing lock tests still pass" because no lock code changes. This is a deliberate plan-time scope reduction; if the reviewer objects, the test from spec Task "Lock round-trip" can be added as a no-op equality check in 5 minutes.
