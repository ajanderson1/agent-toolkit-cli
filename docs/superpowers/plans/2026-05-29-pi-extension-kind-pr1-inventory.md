# pi-extension Kind — PR1 (Read-Only Inventory) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the `pi-extension` asset kind's read-only foundation — a `KindBinding`, a `pi_extension_paths` facade, a `pi-extensions-lock.json` path field, a `_pi_settings.py` reader for Pi's `packages[]`/`extensions[]`, and `pi-extension list` / `pi-extension status` CLI verbs that surface a unified inventory of every extension Pi could load.

**Architecture:** Mirror the kind machinery established by the skill kind (PR #267 foundation) and the agent kind (open PR #270, branch `feat/252-v3-pr2-agent-facade-adapters`): a kind-agnostic core (`_paths_core`, `skill_lock`) with a per-kind facade (`pi_extension_paths.py`, `pi_extension_lock.py` re-export) and a click command group cloned from `commands/skill/`. No mutation in PR1 — it reads the lock + Pi `settings.json` + the `extensions/` dirs and prints. The write path (`add`/`install`/`import`/toggle) and the TUI are deferred to PR2/PR3.

**Tech Stack:** Python 3.13, click, dataclasses, pytest + monkeypatch, `uv`. Targets installed Pi `@earendil-works/pi-coding-agent@0.77.0`.

**Spec:** `docs/superpowers/specs/2026-05-29-pi-extension-kind-design.md` (§2 discovery contract, §4 architecture, §5 inventory, §6 verbs `list`/`status`).

**Out of scope (later PRs):** `add`/`install`/`uninstall`/`remove`/`import`/`update`/`push`/`reset`, `doctor`, TUI kind-sidebar + Pi-only grid, any `settings.json` *write*.

---

## File Structure

| File | Responsibility | New/Modify |
|---|---|---|
| `src/agent_toolkit_cli/_paths_core.py` | add `PI_EXTENSION_BINDING` | Modify |
| `src/agent_toolkit_cli/skill_lock.py` | add `pi_extension_path` / `piExtensionPath` field to shared `LockEntry` | Modify |
| `src/agent_toolkit_cli/pi_extension_lock.py` | kind-aligned re-export of lock primitives | Create |
| `src/agent_toolkit_cli/pi_extension_paths.py` | per-kind path facade binding `PI_EXTENSION_BINDING` | Create |
| `src/agent_toolkit_cli/_pi_settings.py` | read Pi `settings.json` `packages[]` / `extensions[]` per scope | Create |
| `src/agent_toolkit_cli/pi_extension_inventory.py` | union store-owned + loose + npm into inventory records | Create |
| `src/agent_toolkit_cli/commands/pi_extension/__init__.py` | click group + registration | Create |
| `src/agent_toolkit_cli/commands/pi_extension/_common.py` | `scope_and_roots` parametrized on `pi-extensions-lock.json` | Create |
| `src/agent_toolkit_cli/commands/pi_extension/list_cmd.py` | `list` verb (`ls` alias) | Create |
| `src/agent_toolkit_cli/commands/pi_extension/status_cmd.py` | `status` verb | Create |
| `src/agent_toolkit_cli/cli.py` | register the `pi-extension` group | Modify |
| `docs/agent-toolkit/harness-matrix.md` | optional: note pi-extension is Pi-only | Modify (Task 9) |
| `tests/test_cli/test_paths_core_pi_extension_binding.py` | binding test | Create |
| `tests/test_cli/test_lock_pi_extension_path.py` | lock round-trip | Create |
| `tests/test_cli/test_pi_settings.py` | settings reader | Create |
| `tests/test_cli/test_pi_extension_inventory.py` | inventory unioning | Create |
| `tests/test_cli/test_cli_pi_extension_list.py` | CLI list/status | Create |

---

## Task 1: `PI_EXTENSION_BINDING` in `_paths_core.py`

**Files:**
- Modify: `src/agent_toolkit_cli/_paths_core.py` (after `SKILL_BINDING`, ~line 29)
- Test: `tests/test_cli/test_paths_core_pi_extension_binding.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli/test_paths_core_pi_extension_binding.py
from pathlib import Path

from agent_toolkit_cli._paths_core import (
    PI_EXTENSION_BINDING,
    library_lock_path_for_kind,
    library_root_for_kind,
)


def test_binding_fields():
    b = PI_EXTENSION_BINDING
    assert b.kind == "pi-extension"
    assert b.canonical_dirname == "pi-extensions"
    assert b.library_subdir == "pi-extensions"
    assert b.lock_filename == "pi-extensions-lock.json"
    assert b.general_harness_name == "general-pi-extension"


def test_library_root(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    root = library_root_for_kind(PI_EXTENSION_BINDING, env={})
    assert root == tmp_path / ".agent-toolkit" / "pi-extensions"


def test_library_lock_path(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    p = library_lock_path_for_kind(PI_EXTENSION_BINDING, env={})
    assert p == tmp_path / ".agent-toolkit" / "pi-extensions-lock.json"


def test_skills_root_override_does_not_leak(monkeypatch, tmp_path):
    # The AGENT_TOOLKIT_SKILLS_ROOT override is skill-only; pi-extension ignores it.
    monkeypatch.setenv("HOME", str(tmp_path))
    root = library_root_for_kind(
        PI_EXTENSION_BINDING, env={"AGENT_TOOLKIT_SKILLS_ROOT": "/should/be/ignored"}
    )
    assert root == tmp_path / ".agent-toolkit" / "pi-extensions"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_paths_core_pi_extension_binding.py -v`
Expected: FAIL — `ImportError: cannot import name 'PI_EXTENSION_BINDING'`

- [ ] **Step 3: Add the binding**

In `src/agent_toolkit_cli/_paths_core.py`, immediately after the `SKILL_BINDING = KindBinding(...)` block, add:

```python
PI_EXTENSION_BINDING = KindBinding(
    kind="pi-extension",
    canonical_dirname="pi-extensions",
    library_subdir="pi-extensions",
    lock_filename="pi-extensions-lock.json",
    general_harness_name="general-pi-extension",
)
```

(No change to `library_root_for_kind` — the `AGENT_TOOLKIT_SKILLS_ROOT` override stays gated on `binding.kind == "skill"`, so pi-extension correctly ignores it. That is what `test_skills_root_override_does_not_leak` asserts.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_paths_core_pi_extension_binding.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/_paths_core.py tests/test_cli/test_paths_core_pi_extension_binding.py
git commit -m "feat(pi-extension): add PI_EXTENSION_BINDING"
```

---

## Task 2: `pi_extension_path` field on the shared `LockEntry`

Mirrors exactly how PR #270 adds `agent_path`/`agentPath`. The lock module stays kind-blind; the new camelCase key must be in both field-sets or it falls into `extras`.

**Files:**
- Modify: `src/agent_toolkit_cli/skill_lock.py` (LockEntry ~line 37; `_V1_ENTRY_FIELDS` ~53; `_V3_ENTRY_FIELDS` ~57; v1 reader ~74; v3 reader ~88; v1 writer ~109; v3 writer ~208)
- Test: `tests/test_cli/test_lock_pi_extension_path.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli/test_lock_pi_extension_path.py
import json

from agent_toolkit_cli.skill_lock import (
    LockEntry,
    LockFile,
    read_lock,
    write_lock,
)


def _entry(**kw) -> LockEntry:
    return LockEntry(source="github.com/o/r", source_type="github", **kw)


def test_field_exists_defaults_none():
    assert _entry().pi_extension_path is None


def test_v1_round_trip_pi_extension_path(tmp_path):
    p = tmp_path / "pi-extensions-lock.json"
    lf = LockFile(version=1, skills={"ext": _entry(pi_extension_path="ext")})
    write_lock(p, lf)
    body = json.loads(p.read_text())
    assert body["skills"]["ext"]["piExtensionPath"] == "ext"
    assert read_lock(p) == lf


def test_v3_round_trip_pi_extension_path(tmp_path):
    p = tmp_path / "pi-extensions-lock.json"
    lf = LockFile(version=3, skills={"ext": _entry(pi_extension_path="ext")})
    write_lock(p, lf)
    body = json.loads(p.read_text())
    assert body["skills"]["ext"]["piExtensionPath"] == "ext"
    assert read_lock(p) == lf


def test_not_swept_into_extras(tmp_path):
    p = tmp_path / "pi-extensions-lock.json"
    p.write_text(json.dumps({
        "version": 1,
        "skills": {"ext": {"source": "x", "sourceType": "github",
                           "piExtensionPath": "ext"}},
    }) + "\n")
    e = read_lock(p).skills["ext"]
    assert e.pi_extension_path == "ext"
    assert "piExtensionPath" not in e.extras
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_lock_pi_extension_path.py -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'pi_extension_path'`

- [ ] **Step 3: Add the field and wire serialization**

In `src/agent_toolkit_cli/skill_lock.py`:

(a) In `LockEntry`, add after `skill_path: str | None = None` (and after `agent_path` if PR #270 has merged):

```python
    pi_extension_path: str | None = None
```

(b) Add `"piExtensionPath"` to **both** sets:

```python
_V1_ENTRY_FIELDS = {
    "source", "sourceType", "ref", "skillPath", "piExtensionPath",
    "upstreamSha", "localSha", "parentUrl", "readOnly",
}
_V3_ENTRY_FIELDS = {
    "source", "sourceType", "sourceUrl", "ref", "skillPath", "piExtensionPath",
    "skillFolderHash", "installedAt", "updatedAt", "pluginName",
    "parentUrl", "readOnly",
}
```

(c) In `_entry_from_dict_v1` and `_entry_from_dict_v3`, add after the `skill_path=d.get("skillPath"),` line:

```python
        pi_extension_path=d.get("piExtensionPath"),
```

(d) In `_entry_to_dict_v1` and `_entry_to_dict_v3`, after the `if e.skill_path is not None:` block, add:

```python
    if e.pi_extension_path is not None:
        out["piExtensionPath"] = e.pi_extension_path
```

- [ ] **Step 4: Run test to verify it passes (and skill lock still passes)**

Run: `uv run pytest tests/test_cli/test_lock_pi_extension_path.py tests/test_cli/test_skill_lock.py -v`
Expected: PASS (existing skill lock tests unaffected)

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/skill_lock.py tests/test_cli/test_lock_pi_extension_path.py
git commit -m "feat(pi-extension): add piExtensionPath field to shared LockEntry"
```

---

## Task 3: `pi_extension_lock.py` re-export facade

Pure re-export so PR2 CLI verbs get a kind-aligned import path (mirrors `agent_lock.py`).

**Files:**
- Create: `src/agent_toolkit_cli/pi_extension_lock.py`
- Test: extend `tests/test_cli/test_lock_pi_extension_path.py`

- [ ] **Step 1: Write the failing test (append)**

```python
def test_pi_extension_lock_reexports():
    from agent_toolkit_cli import pi_extension_lock as pel

    assert pel.LockEntry is not None
    assert pel.LockFile is not None
    assert callable(pel.read_lock)
    assert callable(pel.write_lock)
    assert callable(pel.add_entry)
    assert callable(pel.remove_entry)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_lock_pi_extension_path.py::test_pi_extension_lock_reexports -v`
Expected: FAIL — `ModuleNotFoundError: agent_toolkit_cli.pi_extension_lock`

- [ ] **Step 3: Create the module**

```python
# src/agent_toolkit_cli/pi_extension_lock.py
"""Kind-aligned re-export of the kind-blind lock primitives for the
pi-extension kind. Behaviourally identical to `skill_lock`; exists so
pi-extension call sites read from a kind-named module (mirrors agent_lock)."""
from __future__ import annotations

from agent_toolkit_cli.skill_lock import (
    SUPPORTED_VERSIONS,
    LockEntry,
    LockFile,
    add_entry,
    read_lock,
    remove_entry,
    write_lock,
)

__all__ = [
    "SUPPORTED_VERSIONS",
    "LockEntry",
    "LockFile",
    "add_entry",
    "read_lock",
    "remove_entry",
    "write_lock",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_lock_pi_extension_path.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/pi_extension_lock.py tests/test_cli/test_lock_pi_extension_path.py
git commit -m "feat(pi-extension): add pi_extension_lock re-export facade"
```

---

## Task 4: `pi_extension_paths.py` facade

Mirrors `agent_paths.py`. Provides `Scope`, library/lock paths bound to `PI_EXTENSION_BINDING`, canonical dir, and the two Pi extension projection dirs.

**Files:**
- Create: `src/agent_toolkit_cli/pi_extension_paths.py`
- Test: `tests/test_cli/test_pi_extension_paths.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli/test_pi_extension_paths.py
from pathlib import Path

from agent_toolkit_cli import pi_extension_paths as pep


def test_library_and_lock(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert pep.library_root(env={}) == tmp_path / ".agent-toolkit" / "pi-extensions"
    assert pep.library_pi_extension_path("e", env={}) == (
        tmp_path / ".agent-toolkit" / "pi-extensions" / "e"
    )
    assert pep.library_lock_path(env={}) == (
        tmp_path / ".agent-toolkit" / "pi-extensions-lock.json"
    )


def test_lock_file_path_scopes(tmp_path):
    proj = tmp_path / "proj"
    assert pep.lock_file_path(scope="project", project=proj) == (
        proj / "pi-extensions-lock.json"
    )


def test_pi_extension_dir_global(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert pep.pi_extension_dir("e", scope="global", home=tmp_path) == (
        tmp_path / ".pi" / "agent" / "extensions" / "e"
    )


def test_pi_extension_dir_project(tmp_path):
    proj = tmp_path / "proj"
    assert pep.pi_extension_dir("e", scope="project", project=proj) == (
        proj / ".pi" / "extensions" / "e"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_pi_extension_paths.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create the module**

```python
# src/agent_toolkit_cli/pi_extension_paths.py
"""Path facade for the pi-extension kind. Binds PI_EXTENSION_BINDING to the
kind-agnostic helpers in _paths_core, and owns the Pi-specific projection
dirs (~/.pi/agent/extensions and <project>/.pi/extensions). Mirrors
agent_paths.py / skill_paths.py. Pi-only: there is no per-harness fan-out."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from agent_toolkit_cli._paths_core import (
    PI_EXTENSION_BINDING,
    library_lock_path_for_kind,
    library_root_for_kind,
)
# Reuse the kind-agnostic project-store helpers verbatim.
from agent_toolkit_cli.skill_paths import (
    parent_clone_path,
    project_id,
    project_parents_root,
)

Scope = Literal["project", "global"]

# Pi discovery roots (verified against pi-coding-agent@0.77.0):
#   global:  ~/.pi/agent/extensions/<slug>
#   project: <project>/.pi/extensions/<slug>
_PI_GLOBAL_EXTENSIONS = (".pi", "agent", "extensions")
_PI_PROJECT_EXTENSIONS = (".pi", "extensions")

__all__ = [
    "Scope",
    "library_root",
    "library_pi_extension_path",
    "library_lock_path",
    "canonical_pi_extension_dir",
    "lock_file_path",
    "pi_extension_dir",
    "parent_clone_path",
    "project_id",
    "project_parents_root",
]


def library_root(env: dict[str, str] | None = None) -> Path:
    return library_root_for_kind(PI_EXTENSION_BINDING, env)


def library_pi_extension_path(slug: str, *, env: dict[str, str] | None = None) -> Path:
    return library_root(env) / slug


def library_lock_path(env: dict[str, str] | None = None) -> Path:
    return library_lock_path_for_kind(PI_EXTENSION_BINDING, env)


def canonical_pi_extension_dir(
    slug: str, *, scope: Scope,
    home: Path | None = None, project: Path | None = None,
) -> Path:
    """The owned store copy for a store-owned extension."""
    if scope == "global":
        return library_pi_extension_path(slug)
    if project is None:
        raise ValueError("project scope requires project")
    # Project-scope store copy lives under the per-project store root, like skills.
    from agent_toolkit_cli.skill_paths import library_root as _skill_lib_root
    return (
        _skill_lib_root().parent / "projects" / project_id(project) / "pi-extensions" / slug
    )


def lock_file_path(
    *, scope: Scope, home: Path | None = None, project: Path | None = None,
) -> Path:
    if scope == "global":
        return library_lock_path()
    if project is None:
        raise ValueError("project scope requires project")
    return project / PI_EXTENSION_BINDING.lock_filename


def pi_extension_dir(
    slug: str, *, scope: Scope,
    home: Path | None = None, project: Path | None = None,
) -> Path:
    """Where Pi discovers the extension (symlink target lives here in PR2)."""
    if scope == "global":
        if home is None:
            raise ValueError("global scope requires home")
        return home.joinpath(*_PI_GLOBAL_EXTENSIONS, slug)
    if project is None:
        raise ValueError("project scope requires project")
    return project.joinpath(*_PI_PROJECT_EXTENSIONS, slug)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_pi_extension_paths.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/pi_extension_paths.py tests/test_cli/test_pi_extension_paths.py
git commit -m "feat(pi-extension): add pi_extension_paths facade"
```

---

## Task 5: `_pi_settings.py` — read Pi `settings.json` `packages[]` / `extensions[]`

Read-only in PR1 (writer arrives PR2). Per-scope file resolution per spec §2: global `~/.pi/agent/settings.json`, project `<cwd>/.pi/settings.json`. Fail loud on malformed JSON.

**Files:**
- Create: `src/agent_toolkit_cli/_pi_settings.py`
- Test: `tests/test_cli/test_pi_settings.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli/test_pi_settings.py
import json

import pytest

from agent_toolkit_cli import _pi_settings as ps


def _write(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj))


def test_global_settings_path(tmp_path):
    assert ps.settings_path(scope="global", home=tmp_path) == (
        tmp_path / ".pi" / "agent" / "settings.json"
    )


def test_project_settings_path(tmp_path):
    proj = tmp_path / "proj"
    assert ps.settings_path(scope="project", project=proj) == (
        proj / ".pi" / "settings.json"
    )


def test_read_packages_global(tmp_path):
    _write(tmp_path / ".pi" / "agent" / "settings.json",
           {"packages": ["npm:foo", "git:github.com/o/r"]})
    assert ps.read_packages(scope="global", home=tmp_path) == [
        "npm:foo", "git:github.com/o/r",
    ]


def test_read_extensions_paths(tmp_path):
    _write(tmp_path / ".pi" / "agent" / "settings.json",
           {"extensions": ["./local-ext", "/abs/ext"]})
    assert ps.read_extension_paths(scope="global", home=tmp_path) == [
        "./local-ext", "/abs/ext",
    ]


def test_missing_file_returns_empty(tmp_path):
    assert ps.read_packages(scope="global", home=tmp_path) == []
    assert ps.read_extension_paths(scope="global", home=tmp_path) == []


def test_malformed_json_raises(tmp_path):
    p = tmp_path / ".pi" / "agent" / "settings.json"
    p.parent.mkdir(parents=True)
    p.write_text("{ not json")
    with pytest.raises(ps.PiSettingsError):
        ps.read_packages(scope="global", home=tmp_path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_pi_settings.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create the module**

```python
# src/agent_toolkit_cli/_pi_settings.py
"""Read (PR1) Pi's per-scope settings.json packages[]/extensions[] arrays.

Verified against @earendil-works/pi-coding-agent@0.77.0:
  global  settings: ~/.pi/agent/settings.json
  project settings: <project>/.pi/settings.json
Both carry independent `packages` (registry refs) and `extensions`
(explicit local paths) arrays. PR1 reads only; the writer arrives in PR2.
Fails loud on malformed JSON rather than silently treating it as empty."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

Scope = Literal["project", "global"]

_GLOBAL_SETTINGS = (".pi", "agent", "settings.json")
_PROJECT_SETTINGS = (".pi", "settings.json")


class PiSettingsError(RuntimeError):
    """Pi settings.json could not be parsed."""


def settings_path(
    *, scope: Scope, home: Path | None = None, project: Path | None = None,
) -> Path:
    if scope == "global":
        if home is None:
            raise ValueError("global scope requires home")
        return home.joinpath(*_GLOBAL_SETTINGS)
    if project is None:
        raise ValueError("project scope requires project")
    return project.joinpath(*_PROJECT_SETTINGS)


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        raise PiSettingsError(f"{path}: {exc}") from exc
    if not isinstance(data, dict):
        raise PiSettingsError(f"{path}: top-level value is not an object")
    return data


def _string_list(data: dict, key: str, path: Path) -> list[str]:
    value = data.get(key, [])
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise PiSettingsError(f"{path}: `{key}` is not a list of strings")
    return value


def read_packages(
    *, scope: Scope, home: Path | None = None, project: Path | None = None,
) -> list[str]:
    path = settings_path(scope=scope, home=home, project=project)
    return _string_list(_load(path), "packages", path)


def read_extension_paths(
    *, scope: Scope, home: Path | None = None, project: Path | None = None,
) -> list[str]:
    path = settings_path(scope=scope, home=home, project=project)
    return _string_list(_load(path), "extensions", path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_pi_settings.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/_pi_settings.py tests/test_cli/test_pi_settings.py
git commit -m "feat(pi-extension): add _pi_settings reader for packages[]/extensions[]"
```

---

## Task 6: `pi_extension_inventory.py` — union store-owned + loose + npm

Produces one record per extension Pi could load (spec §5). Origin is a field, not a gate. Reads the kind lock (store-owned + tracked-npm), the `extensions/` dirs (loose/untracked), and `packages[]` (npm). PR1 has no concept of "linked symlink ↔ canonical" yet; `loaded` here means "present on the surface Pi scans".

**Files:**
- Create: `src/agent_toolkit_cli/pi_extension_inventory.py`
- Test: `tests/test_cli/test_pi_extension_inventory.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli/test_pi_extension_inventory.py
import json
from pathlib import Path

from agent_toolkit_cli.pi_extension_inventory import build_inventory


def _pi_global(home: Path) -> Path:
    d = home / ".pi" / "agent" / "extensions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def test_loose_dir_with_index_is_untracked(tmp_path):
    ext = _pi_global(tmp_path) / "loose-ext"
    ext.mkdir()
    (ext / "index.ts").write_text("export default {}")
    # empty global lock
    (tmp_path / ".agent-toolkit").mkdir()
    (tmp_path / ".agent-toolkit" / "pi-extensions-lock.json").write_text(
        json.dumps({"version": 1, "skills": {}}) + "\n"
    )
    records = build_inventory(home=tmp_path)
    rec = {r.slug: r for r in records}["loose-ext"]
    assert rec.origin == "untracked"
    assert rec.global_loaded is True


def test_loose_file_extension(tmp_path):
    (_pi_global(tmp_path) / "hooks.ts").write_text("// x")
    records = build_inventory(home=tmp_path)
    assert {r.slug for r in records} >= {"hooks"}
    assert {r.slug: r for r in records}["hooks"].origin == "untracked"


def test_npm_package_is_tracked_registry(tmp_path):
    s = tmp_path / ".pi" / "agent" / "settings.json"
    s.parent.mkdir(parents=True)
    s.write_text(json.dumps({"packages": ["npm:@scope/rpiv-i18n"]}))
    records = build_inventory(home=tmp_path)
    rec = {r.slug: r for r in records}["@scope/rpiv-i18n"]
    assert rec.origin == "npm"
    assert rec.source == "npm:@scope/rpiv-i18n"
    assert rec.global_loaded is True


def test_store_owned_from_lock(tmp_path):
    lock = tmp_path / ".agent-toolkit" / "pi-extensions-lock.json"
    lock.parent.mkdir(parents=True)
    lock.write_text(json.dumps({
        "version": 1,
        "skills": {"status-bar": {
            "source": "github.com/o/status-bar", "sourceType": "github",
            "piExtensionPath": "status-bar",
        }},
    }) + "\n")
    records = build_inventory(home=tmp_path)
    rec = {r.slug: r for r in records}["status-bar"]
    assert rec.origin == "store-owned"
    assert rec.source == "github.com/o/status-bar"


def test_empty_machine_is_empty(tmp_path):
    assert build_inventory(home=tmp_path) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_pi_extension_inventory.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create the module**

```python
# src/agent_toolkit_cli/pi_extension_inventory.py
"""Build the unified pi-extension inventory (spec §5): one record per
extension Pi could load, across three surfaces — the kind lock
(store-owned + tracked npm), loose entries in Pi's extensions/ dir
(untracked), and packages[] in settings.json (npm). Origin is a field,
not a gate. Read-only; PR2 adds projection/state."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from agent_toolkit_cli import _pi_settings
from agent_toolkit_cli.pi_extension_lock import read_lock
from agent_toolkit_cli.pi_extension_paths import (
    Scope,
    lock_file_path,
    pi_extension_dir,
)

Origin = Literal["store-owned", "untracked", "npm"]

# Pi loads dirs with index.ts/.js or a pi.extensions manifest, plus loose
# .ts/.js files. We classify discovered entries by these rules (0.77.0).
_EXTENSION_FILE_SUFFIXES = (".ts", ".js")


@dataclass
class InventoryRecord:
    slug: str
    origin: Origin
    source: str
    global_loaded: bool = False
    project_loaded: bool = False


def _extensions_root(*, scope: Scope, home: Path | None, project: Path | None) -> Path:
    # pi_extension_dir(slug) is <root>/<slug>; the root is its parent.
    return pi_extension_dir("_", scope=scope, home=home, project=project).parent


def _discover_loose(root: Path) -> list[tuple[str, bool]]:
    """Return (slug, is_loaded) for entries Pi would discover under `root`.

    A directory loads if it has index.ts/.js or package.json; a loose
    *.ts/*.js file loads as its stem. We don't read package.json contents
    in PR1 — presence of the file is enough to call it loadable."""
    out: list[tuple[str, bool]] = []
    if not root.exists():
        return out
    for entry in sorted(root.iterdir()):
        if entry.is_dir() or (entry.is_symlink() and entry.resolve().is_dir()):
            has_entry = any(
                (entry / name).exists()
                for name in ("index.ts", "index.js", "package.json")
            )
            if has_entry:
                out.append((entry.name, True))
        elif entry.suffix in _EXTENSION_FILE_SUFFIXES:
            out.append((entry.stem, True))
    return out


def _npm_slug(spec: str) -> str:
    # "npm:@scope/name" -> "@scope/name"; "git:github.com/o/r" -> "github.com/o/r"
    return spec.split(":", 1)[1] if ":" in spec else spec


def build_inventory(
    *, home: Path | None = None, project: Path | None = None,
) -> list[InventoryRecord]:
    home = home or Path.home()
    by_slug: dict[str, InventoryRecord] = {}
    scopes: list[tuple[Scope, Path | None]] = [("global", None)]
    if project is not None:
        scopes.append(("project", project))

    # 1. Store-owned (from the kind lock).
    for scope, _ in scopes:
        try:
            lock = read_lock(lock_file_path(scope=scope, home=home, project=project))
        except FileNotFoundError:
            continue
        for slug, entry in lock.skills.items():
            rec = by_slug.setdefault(
                slug,
                InventoryRecord(slug=slug, origin="store-owned", source=entry.source),
            )
            rec.origin = "store-owned"
            rec.source = entry.source

    # 2. Loose / untracked entries already in Pi's extensions/ dirs.
    for scope, _ in scopes:
        root = _extensions_root(scope=scope, home=home, project=project)
        for slug, loaded in _discover_loose(root):
            rec = by_slug.setdefault(
                slug, InventoryRecord(slug=slug, origin="untracked", source="local")
            )
            if scope == "global":
                rec.global_loaded = rec.global_loaded or loaded
            else:
                rec.project_loaded = rec.project_loaded or loaded

    # 3. npm packages[] (registry-tracked).
    for scope, _ in scopes:
        for spec in _pi_settings.read_packages(scope=scope, home=home, project=project):
            if not spec.startswith("npm:"):
                continue
            slug = _npm_slug(spec)
            rec = by_slug.setdefault(
                slug, InventoryRecord(slug=slug, origin="npm", source=spec)
            )
            rec.origin = "npm"
            rec.source = spec
            if scope == "global":
                rec.global_loaded = True
            else:
                rec.project_loaded = True

    return [by_slug[k] for k in sorted(by_slug)]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_pi_extension_inventory.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/pi_extension_inventory.py tests/test_cli/test_pi_extension_inventory.py
git commit -m "feat(pi-extension): add unified inventory builder"
```

---

## Task 7: `commands/pi_extension/` group with `_common.py`

Clone the shipped `commands/skill/` shape. `_common.scope_and_roots` is parametrized on the lock filename (the skill version hardcodes `"skills-lock.json"`).

**Files:**
- Create: `src/agent_toolkit_cli/commands/pi_extension/__init__.py`
- Create: `src/agent_toolkit_cli/commands/pi_extension/_common.py`

- [ ] **Step 1: Write the failing test (group exists + scope helper)**

```python
# tests/test_cli/test_cli_pi_extension_list.py  (first half — group wiring)
from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def test_group_registered():
    result = CliRunner().invoke(main, ["pi-extension", "--help"])
    assert result.exit_code == 0
    assert "list" in result.output
    assert "status" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_cli_pi_extension_list.py::test_group_registered -v`
Expected: FAIL — `No such command 'pi-extension'`

- [ ] **Step 3: Create `_common.py`**

```python
# src/agent_toolkit_cli/commands/pi_extension/_common.py
"""Shared helpers for the pi-extension command group. scope_and_roots is the
skill version parametrized on the pi-extensions lock filename."""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli._paths_core import PI_EXTENSION_BINDING

_LOCK_FILENAME = PI_EXTENSION_BINDING.lock_filename


def scope_and_roots(
    global_: bool,
    project: bool,
    ctx_project: Path | None,
    *,
    read_only: bool = False,
):
    if global_ and project:
        raise click.UsageError("use either -g/--global or -p/--project, not both")
    if global_:
        return "global", Path.home(), None
    if project:
        project_root = ctx_project or Path.cwd()
        return "project", None, project_root
    project_root = ctx_project or Path.cwd()
    if read_only and not (project_root / _LOCK_FILENAME).exists():
        return "global", Path.home(), None
    return "project", None, project_root
```

- [ ] **Step 4: Create `__init__.py`**

```python
# src/agent_toolkit_cli/commands/pi_extension/__init__.py
"""`agent-toolkit-cli pi-extension <verb>` — manage Pi extensions as owned
git repos (store-owned) or tracked npm packages. PR1 ships read-only verbs
(list/status); add/install/import/toggle/doctor arrive in PR2."""
from __future__ import annotations

import click

from agent_toolkit_cli.commands.pi_extension.list_cmd import list_cmd
from agent_toolkit_cli.commands.pi_extension.status_cmd import status_cmd


@click.group(name="pi-extension")
def pi_extension() -> None:
    """Manage Pi extensions via owned git repos + pi-extensions-lock.json."""


pi_extension.add_command(list_cmd)
pi_extension.add_command(status_cmd)
pi_extension.add_command(list_cmd, name="ls")
```

- [ ] **Step 5: Register in `cli.py`**

In `src/agent_toolkit_cli/cli.py`, add the import alongside the skill import and register after `main.add_command(skill, name="skills")`:

```python
from agent_toolkit_cli.commands.pi_extension import pi_extension
...
main.add_command(pi_extension)
```

- [ ] **Step 6: Run test (still fails — list_cmd/status_cmd not created)**

Run: `uv run pytest tests/test_cli/test_cli_pi_extension_list.py::test_group_registered -v`
Expected: FAIL — `ImportError: cannot import name 'list_cmd'` (resolved in Task 8). Do NOT commit yet.

---

## Task 8: `list` and `status` verbs

`list` emits the §5 inventory; `status` emits per-extension origin/loaded state. Synthetic-token guard mirrors `list_cmd.py`.

**Files:**
- Create: `src/agent_toolkit_cli/commands/pi_extension/list_cmd.py`
- Create: `src/agent_toolkit_cli/commands/pi_extension/status_cmd.py`
- Test: `tests/test_cli/test_cli_pi_extension_list.py` (extend)

- [ ] **Step 1: Write the failing tests (append)**

```python
import json as _json
from pathlib import Path


def _seed_npm(home: Path):
    s = home / ".pi" / "agent" / "settings.json"
    s.parent.mkdir(parents=True, exist_ok=True)
    s.write_text(_json.dumps({"packages": ["npm:@scope/rpiv-i18n"]}))


def test_list_global_json(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_npm(tmp_path)
    result = CliRunner().invoke(main, ["pi-extension", "list", "-g", "--json"])
    assert result.exit_code == 0
    payload = _json.loads(result.output)
    rows = {r["slug"]: r for r in payload}
    assert rows["@scope/rpiv-i18n"]["origin"] == "npm"


def test_list_global_table(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_npm(tmp_path)
    result = CliRunner().invoke(main, ["pi-extension", "list", "-g"])
    assert result.exit_code == 0
    assert "@scope/rpiv-i18n" in result.output
    assert "npm" in result.output


def test_status_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    result = CliRunner().invoke(main, ["pi-extension", "status", "-g"])
    assert result.exit_code == 0


def test_status_lists_origin(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_npm(tmp_path)
    result = CliRunner().invoke(main, ["pi-extension", "status", "-g"])
    assert result.exit_code == 0
    assert "@scope/rpiv-i18n" in result.output
    assert "npm" in result.output
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_cli/test_cli_pi_extension_list.py -v`
Expected: FAIL — import error (list_cmd missing)

- [ ] **Step 3: Create `list_cmd.py`**

```python
# src/agent_toolkit_cli/commands/pi_extension/list_cmd.py
"""`pi-extension list` — the unified read-only inventory (spec §5)."""
from __future__ import annotations

import json

import click

from agent_toolkit_cli.commands.pi_extension._common import scope_and_roots
from agent_toolkit_cli.pi_extension_inventory import build_inventory


@click.command("list")
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.option("--json", "as_json", is_flag=True, help="Emit JSON.")
@click.pass_context
def list_cmd(ctx, global_, project_flag, as_json):
    """List every Pi extension the toolkit can see (store-owned, untracked, npm)."""
    scope, home, project_root = scope_and_roots(
        global_, project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
        read_only=True,
    )
    records = build_inventory(home=home, project=project_root)
    if as_json:
        click.echo(json.dumps([
            {
                "slug": r.slug, "origin": r.origin, "source": r.source,
                "globalLoaded": r.global_loaded, "projectLoaded": r.project_loaded,
            }
            for r in records
        ], indent=2))
        return
    if not records:
        click.echo("no pi extensions found")
        return
    for r in records:
        g = "✔" if r.global_loaded else "☐"
        p = "✔" if r.project_loaded else "☐"
        click.echo(f"{r.slug}\t{g}\t{p}\t{r.origin}\t{r.source}")
```

- [ ] **Step 4: Create `status_cmd.py`**

```python
# src/agent_toolkit_cli/commands/pi_extension/status_cmd.py
"""`pi-extension status` — per-extension origin + loaded state."""
from __future__ import annotations

import click

from agent_toolkit_cli.commands.pi_extension._common import scope_and_roots
from agent_toolkit_cli.pi_extension_inventory import build_inventory


@click.command("status")
@click.argument("slugs", nargs=-1)
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.pass_context
def status_cmd(ctx, slugs, global_, project_flag):
    """Show origin and loaded-scope for each pi extension."""
    scope, home, project_root = scope_and_roots(
        global_, project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
        read_only=True,
    )
    records = build_inventory(home=home, project=project_root)
    if slugs:
        wanted = set(slugs)
        records = [r for r in records if r.slug in wanted]
    for r in records:
        scopes = []
        if r.global_loaded:
            scopes.append("global")
        if r.project_loaded:
            scopes.append("project")
        loaded = ",".join(scopes) if scopes else "-"
        click.echo(f"{r.slug}\t{r.origin}\t{loaded}")
```

- [ ] **Step 5: Run all pi-extension CLI tests**

Run: `uv run pytest tests/test_cli/test_cli_pi_extension_list.py -v`
Expected: PASS (group_registered + list/status tests)

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/commands/pi_extension/ src/agent_toolkit_cli/cli.py tests/test_cli/test_cli_pi_extension_list.py
git commit -m "feat(pi-extension): add pi-extension list/status read-only verbs"
```

---

## Task 9: Full-suite green + help-text regression

PR1 touches `cli.py` (new group) — the help-text and CLI-surface tests may snapshot the command list.

**Files:**
- Modify (if needed): `tests/test_cli_help.py`, `tests/test_cli/test_cli_skill_help_examples.py`

- [ ] **Step 1: Run the full suite**

Run: `uv run pytest -q`
Expected: all pass except possibly a help-text test that lists top-level commands.

- [ ] **Step 2: If a help-text test fails because it asserts the exact command set**

Read the failing assertion. If it lists top-level groups (e.g. expects `{skill, skills}`), add `pi-extension` to the expected set. Show the diff you make; do not weaken the test to a substring match if it was exact.

- [ ] **Step 3: Re-run full suite**

Run: `uv run pytest -q`
Expected: PASS (all)

- [ ] **Step 4: Run ruff + mypy (repo gates)**

Run: `uv run ruff check src/agent_toolkit_cli/ tests/ && uv run mypy src/agent_toolkit_cli/`
Expected: clean. Fix any type/lint issues inline (e.g. add return types).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "test(pi-extension): full-suite green + help-text for new group"
```

---

## Task 10: Open a PR

- [ ] **Step 1: Push and open the PR**

```bash
git push -u origin feat/pi-extension-kind
gh pr create --title "v3.2.0 PR1: pi-extension kind read-only inventory" \
  --body "$(cat <<'EOF'
## Summary
First slice of the pi-extension asset kind (spec: docs/superpowers/specs/2026-05-29-pi-extension-kind-design.md). Read-only foundation, no mutation.

- `PI_EXTENSION_BINDING` + `pi_extension_paths` facade + `pi_extension_lock` re-export
- `piExtensionPath` field on the shared LockEntry (mirrors agent's `agentPath`, PR #270)
- `_pi_settings.py` reader for Pi `settings.json` packages[]/extensions[] (per-scope, fail-loud)
- `pi_extension_inventory.build_inventory` — unified store-owned + untracked + npm view
- `pi-extension list` / `status` verbs (cloned from commands/skill/)

Targets installed Pi @earendil-works/pi-coding-agent@0.77.0.

## Deferred (PR2/PR3)
add/install/uninstall/remove/import/update/push/reset, doctor, settings.json writer, TUI kind-sidebar + Pi-only grid.

## Test
`uv run pytest -q` green; ruff + mypy clean.
EOF
)"
```

- [ ] **Step 2: Note the dependency**

Comment on the PR (or note in the body) that the `piExtensionPath` change to `skill_lock.py` overlaps PR #270's `agentPath` change — coordinate merge order to avoid a conflict in `_V1_ENTRY_FIELDS`/`_V3_ENTRY_FIELDS`.

---

## Self-Review notes (completed by plan author)

- **Spec coverage:** §2 discovery contract → Tasks 4/5/6 encode the 0.77.0 paths and per-scope settings. §4 architecture (third binding, facade, `_pi_settings.py`) → Tasks 1–5. §5 inventory → Task 6. §6 `list`/`status` → Tasks 7–8. §6 write verbs + §4 TUI → explicitly deferred (PR scope note). §11 resolved items honoured (lock filename `pi-extensions-lock.json` no `kind` field; npm project cell real).
- **Placeholder scan:** every code step contains complete code; no TBD/TODO.
- **Type consistency:** `Scope` literal, `InventoryRecord` fields (`slug/origin/source/global_loaded/project_loaded`), `pi_extension_path`/`piExtensionPath`, `build_inventory(home=, project=)`, `pi_extension_dir`/`canonical_pi_extension_dir`/`lock_file_path` signatures are consistent across Tasks 4–8.
- **Known follow-up flagged in code comments:** PR1's `build_inventory` treats "present on Pi's surface" as `loaded`; PR2 refines to symlink↔canonical state and adds the `extensions[]`-explicit-path classification (spec §11 item 3).
