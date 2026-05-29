# `instructions` Kind — Phase B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the `instructions` asset kind end-to-end in one PR: lockfile model, INSTRUCTIONS_BINDING binding + facade, single symlink adapter for the 7 verdict harnesses, CLI verb group (`install` / `uninstall` / `list` / `status` / `doctor`), and doctor learning the kind — all guarded by Phase A's matrix parity test.

**Architecture:** Mirrors the v3.1.0 agent-kind layout file-for-file (`instructions_paths.py` / `instructions_lock.py` / `instructions_install.py` + `instructions_adapters/symlink.py`), with two principled divergences from PR2: (1) **own lockfile dataclass** (`InstructionsLockFile` with `[[instructions]]` entries — repo/ref/commit fields don't apply), (2) **project-default scope** (skills/agents default global outside a project; instruction-file pointers are inherently project-rooted). One mechanism only — `symlink`. The 39 `native` harnesses cost zero adapter code.

**Tech Stack:** Python 3.13, click for CLI, pytest for TDD, ruff for lint. The KindBinding seam (`_paths_core.KindBinding`) and the kind-agnostic `_install_core` are already in place from PR1 (#267); PR2 (#268) proves the pattern on the agent kind. This plan adds the third binding.

**Resolved upfront (closes the spec's open questions):**
- **Global canonical AGENTS.md path** — `~/.agent-toolkit/AGENTS.md`. Lives next to the existing `~/.agent-toolkit/skills/` and `~/.agent-toolkit/skills-lock.json`. Toolkit-owned, no harness coupling.
- **Lock shape** — parallel `instructions-lock.json` file with its own `InstructionsLockFile` dataclass. NOT a new field on `LockEntry`: `instructions` entries have no `source`/`ref`/`upstream_sha`/`local_sha` (no upstream repo), so reusing LockEntry would be lying about shape. Symmetry with PR2's `agent_path` field is structural (parallel files per kind), not field-level.
- **CLI shape** — parallel `instructions` command group (`agent-toolkit-cli instructions install/uninstall/list/status/doctor`), mirroring the agent group PR2 introduces. Three-way symmetry across the three kinds.
- **TUI** — explicitly OUT OF SCOPE for this plan. v2 has no TUI (stripped back); it returns in a separate roadmap slot. CLI-only delivery.

---

## File Structure

```
src/agent_toolkit_cli/
├── _paths_core.py                              # MODIFY: add INSTRUCTIONS_BINDING constant
├── instructions_paths.py                       # NEW: facade — canonical paths, project_id, AGENTS.md resolution
├── instructions_lock.py                        # NEW: InstructionsLockFile + read/write + add/remove entry
├── instructions_install.py                     # NEW: plan() / apply() / uninstall() — pointer reconciliation
├── instructions_adapters/
│   ├── __init__.py                             # NEW: get_adapter(harness) dispatcher
│   └── symlink.py                              # NEW: the one adapter — 7 cells, one mechanism
├── commands/
│   └── instructions/
│       ├── __init__.py                         # NEW: click group registration
│       ├── install_cmd.py                      # NEW
│       ├── uninstall_cmd.py                    # NEW
│       ├── list_cmd.py                         # NEW
│       ├── status_cmd.py                       # NEW
│       └── doctor_cmd.py                       # NEW
└── cli.py                                       # MODIFY: register `instructions` group

tests/test_cli/
├── test_instructions_paths.py                  # NEW
├── test_instructions_lock.py                   # NEW
├── test_instructions_install.py                # NEW
├── test_instructions_install_e2e.py            # NEW: 7 parametrised end-to-end pointer tests
├── test_instructions_adapters/
│   ├── __init__.py                             # NEW
│   ├── test_dispatcher.py                      # NEW
│   └── test_symlink.py                         # NEW
└── test_instructions_cli.py                    # NEW: click CliRunner over all 5 verbs

tests/
└── test_instructions_matrix.py                 # ALREADY EXISTS (Phase A) — no changes
```

**File boundaries (why this decomposition):**

- `instructions_paths.py` separate from `instructions_lock.py` mirrors `skill_paths`/`skill_lock` — paths and lockfile evolve independently.
- `instructions_install.py` (plan/apply/uninstall) is the kind-blind dispatcher that calls `instructions_adapters.get_adapter(harness)`. Same shape as `agent_install.py` from PR2.
- One adapter module (`symlink.py`) for all 7 cells — they share a single mechanism. No package-per-cell explosion.
- Click subcommand-per-file mirrors `commands/skill/` exactly.

---

## Task 1: INSTRUCTIONS_BINDING in `_paths_core.py`

**Files:**
- Modify: `src/agent_toolkit_cli/_paths_core.py` (add after `SKILL_BINDING`, line 30)
- Test: `tests/test_cli/test_paths_core_instructions_binding.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli/test_paths_core_instructions_binding.py
"""INSTRUCTIONS_BINDING parallels SKILL_BINDING and AGENT_BINDING."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_toolkit_cli._paths_core import (
    INSTRUCTIONS_BINDING,
    KindBinding,
    library_lock_path_for_kind,
    library_root_for_kind,
)


def test_instructions_binding_is_a_kindbinding():
    assert isinstance(INSTRUCTIONS_BINDING, KindBinding)


def test_instructions_binding_field_values():
    """The fields the catalog/library/lock layout depends on."""
    assert INSTRUCTIONS_BINDING.kind == "instructions"
    assert INSTRUCTIONS_BINDING.canonical_dirname == "instructions"
    assert INSTRUCTIONS_BINDING.library_subdir == "instructions"
    assert INSTRUCTIONS_BINDING.lock_filename == "instructions-lock.json"
    assert INSTRUCTIONS_BINDING.general_harness_name == "general-instructions"


def test_library_root_for_instructions_kind(monkeypatch, tmp_path):
    """Library root resolves to ~/.agent-toolkit/instructions/."""
    monkeypatch.setenv("HOME", str(tmp_path))
    root = library_root_for_kind(INSTRUCTIONS_BINDING)
    assert root == tmp_path / ".agent-toolkit" / "instructions"


def test_library_lock_path_for_instructions_kind(monkeypatch, tmp_path):
    """Lock lives at ~/.agent-toolkit/instructions-lock.json."""
    monkeypatch.setenv("HOME", str(tmp_path))
    lock = library_lock_path_for_kind(INSTRUCTIONS_BINDING)
    assert lock == tmp_path / ".agent-toolkit" / "instructions-lock.json"


def test_instructions_binding_does_not_honour_skill_env_override(monkeypatch, tmp_path):
    """The SKILLS_ROOT env override is skill-specific; instructions ignores it."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", "/some/other/path")
    root = library_root_for_kind(INSTRUCTIONS_BINDING)
    assert root == tmp_path / ".agent-toolkit" / "instructions"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_cli/test_paths_core_instructions_binding.py -v
```

Expected: ImportError — `cannot import name 'INSTRUCTIONS_BINDING'`.

- [ ] **Step 3: Add the constant**

Edit `src/agent_toolkit_cli/_paths_core.py`. After the `AGENT_BINDING` block (PR2 introduces it; if PR2 hasn't merged yet, add INSTRUCTIONS_BINDING after SKILL_BINDING at line 30):

```python
INSTRUCTIONS_BINDING = KindBinding(
    kind="instructions",
    canonical_dirname="instructions",
    library_subdir="instructions",
    lock_filename="instructions-lock.json",
    general_harness_name="general-instructions",
)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_cli/test_paths_core_instructions_binding.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/_paths_core.py tests/test_cli/test_paths_core_instructions_binding.py
git commit -m "feat(_paths_core): add INSTRUCTIONS_BINDING for v3 instructions kind"
```

---

## Task 2: `instructions_paths.py` facade

**Files:**
- Create: `src/agent_toolkit_cli/instructions_paths.py`
- Test: `tests/test_cli/test_instructions_paths.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli/test_instructions_paths.py
"""instructions_paths facade — paths + canonical AGENTS.md resolution."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_toolkit_cli import instructions_paths


def test_library_root(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert instructions_paths.library_root() == tmp_path / ".agent-toolkit" / "instructions"


def test_library_lock_path(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert instructions_paths.library_lock_path() == tmp_path / ".agent-toolkit" / "instructions-lock.json"


def test_global_canonical_agents_md(monkeypatch, tmp_path):
    """The canonical global AGENTS.md lives at ~/.agent-toolkit/AGENTS.md."""
    monkeypatch.setenv("HOME", str(tmp_path))
    assert instructions_paths.global_canonical_agents_md() == tmp_path / ".agent-toolkit" / "AGENTS.md"


def test_project_canonical_agents_md(tmp_path):
    """Project canonical is `<project>/AGENTS.md` — sibling of the pointers."""
    project = tmp_path / "myproj"
    project.mkdir()
    assert instructions_paths.project_canonical_agents_md(project) == project / "AGENTS.md"


def test_project_lock_path(tmp_path):
    """Project lock at <project>/instructions-lock.json."""
    project = tmp_path / "myproj"
    project.mkdir()
    assert instructions_paths.project_lock_path(project) == project / "instructions-lock.json"


def test_lock_file_path_global_scope(monkeypatch, tmp_path):
    """`lock_file_path(scope, project_root)` dispatch matches skill_paths shape."""
    monkeypatch.setenv("HOME", str(tmp_path))
    assert instructions_paths.lock_file_path("global", None) == tmp_path / ".agent-toolkit" / "instructions-lock.json"


def test_lock_file_path_project_scope(tmp_path):
    project = tmp_path / "myproj"
    project.mkdir()
    assert instructions_paths.lock_file_path("project", project) == project / "instructions-lock.json"


def test_lock_file_path_project_scope_requires_root():
    """Project scope without a project_root is a programmer error."""
    with pytest.raises(ValueError, match="project scope requires project_root"):
        instructions_paths.lock_file_path("project", None)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_cli/test_instructions_paths.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Create the facade**

```python
# src/agent_toolkit_cli/instructions_paths.py
"""Instructions-flavoured facade over `_paths_core.py`.

v3.0.0 — mirrors `skill_paths.py` and `agent_paths.py` for the instructions
(AGENTS.md pointer-symlink) kind.

Differences from skill/agent paths:
- **No `canonical_<kind>_dir`** — instructions has no per-slug subdir. The
  asset is a single file (`AGENTS.md`); pointers live next to it.
- **`global_canonical_agents_md()` / `project_canonical_agents_md()`** — the
  asset's resolved location at each scope. These are what pointers symlink TO.
- **No `project_store_root` / parent-clone helpers** — there is no upstream
  repo to clone.

Public symbols:
    library_root, library_lock_path, project_lock_path,
    global_canonical_agents_md, project_canonical_agents_md,
    lock_file_path
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from agent_toolkit_cli._paths_core import (
    INSTRUCTIONS_BINDING,
    library_lock_path_for_kind,
    library_root_for_kind,
)

Scope = Literal["global", "project"]


def library_root() -> Path:
    """Library root: ~/.agent-toolkit/instructions/.

    Reserved for future use (e.g. canonical-content backups). Phase B does not
    write here — the canonical lives at the parent (~/.agent-toolkit/AGENTS.md).
    """
    return library_root_for_kind(INSTRUCTIONS_BINDING)


def library_lock_path() -> Path:
    """Global lock at ~/.agent-toolkit/instructions-lock.json."""
    return library_lock_path_for_kind(INSTRUCTIONS_BINDING)


def project_lock_path(project_root: Path) -> Path:
    """Project lock at <project_root>/instructions-lock.json."""
    return project_root / "instructions-lock.json"


def global_canonical_agents_md() -> Path:
    """The canonical global AGENTS.md: ~/.agent-toolkit/AGENTS.md.

    This is what global-scope pointers (e.g. ~/.claude/CLAUDE.md) symlink to.
    The toolkit never creates this file — the user authors it. install()
    refuses if it does not exist.
    """
    return library_root().parent / "AGENTS.md"


def project_canonical_agents_md(project_root: Path) -> Path:
    """The canonical project AGENTS.md: <project_root>/AGENTS.md.

    Pointers (e.g. <project_root>/CLAUDE.md) symlink to this file. install()
    refuses if it does not exist.
    """
    return project_root / "AGENTS.md"


def lock_file_path(scope: Scope, project_root: Path | None) -> Path:
    """Dispatch to global or project lock by scope. Matches skill_paths shape."""
    if scope == "global":
        return library_lock_path()
    if scope == "project":
        if project_root is None:
            raise ValueError("project scope requires project_root")
        return project_lock_path(project_root)
    raise ValueError(f"unknown scope: {scope!r}")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_cli/test_instructions_paths.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/instructions_paths.py tests/test_cli/test_instructions_paths.py
git commit -m "feat(instructions_paths): facade binding INSTRUCTIONS_BINDING + canonical AGENTS.md resolution"
```

---

## Task 3: `instructions_lock.py` — own dataclass + read/write

**Files:**
- Create: `src/agent_toolkit_cli/instructions_lock.py`
- Test: `tests/test_cli/test_instructions_lock.py`

**Why a new lockfile (not LockEntry extension):** `LockEntry` (skill_lock.py:32) has `source`, `source_type`, `ref`, `upstream_sha`, `local_sha`, `parent_url` — all *repo-fetched* concepts. `instructions` has no upstream repo. Crowbarring an `instructions_path` field on `LockEntry` would mean every other field is meaningless. A separate `InstructionsLockFile` is structurally honest.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli/test_instructions_lock.py
"""InstructionsLockFile shape + round-trip + add/remove entries."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_toolkit_cli.instructions_lock import (
    InstructionsLockEntry,
    InstructionsLockFile,
    add_entry,
    read_lock,
    remove_entry,
    write_lock,
)


def test_lockentry_shape():
    """Entry carries scope, source path, and the list of ON harnesses."""
    entry = InstructionsLockEntry(
        scope="project",
        source="AGENTS.md",
        harnesses=["claude-code", "gemini-cli"],
    )
    assert entry.scope == "project"
    assert entry.source == "AGENTS.md"
    assert entry.harnesses == ["claude-code", "gemini-cli"]


def test_lockfile_default_empty():
    lock = InstructionsLockFile(version=1, instructions={})
    assert lock.version == 1
    assert lock.instructions == {}


def test_read_lock_missing_file_returns_empty(tmp_path):
    """A missing lock file is not an error — it's an empty lock."""
    lock = read_lock(tmp_path / "instructions-lock.json")
    assert lock == InstructionsLockFile(version=1, instructions={})


def test_write_then_read_roundtrip(tmp_path):
    lock = InstructionsLockFile(
        version=1,
        instructions={
            "AGENTS.md": InstructionsLockEntry(
                scope="project",
                source="AGENTS.md",
                harnesses=["claude-code"],
            ),
        },
    )
    path = tmp_path / "instructions-lock.json"
    write_lock(path, lock)
    assert read_lock(path) == lock


def test_serialised_shape(tmp_path):
    """The on-disk JSON must match the documented shape exactly."""
    lock = InstructionsLockFile(
        version=1,
        instructions={
            "AGENTS.md": InstructionsLockEntry(
                scope="project",
                source="AGENTS.md",
                harnesses=["claude-code", "gemini-cli"],
            ),
        },
    )
    path = tmp_path / "instructions-lock.json"
    write_lock(path, lock)
    raw = json.loads(path.read_text())
    assert raw == {
        "version": 1,
        "instructions": {
            "AGENTS.md": {
                "scope": "project",
                "source": "AGENTS.md",
                "harnesses": ["claude-code", "gemini-cli"],
            },
        },
    }


def test_add_entry():
    lock = InstructionsLockFile(version=1, instructions={})
    new = add_entry(
        lock,
        "AGENTS.md",
        InstructionsLockEntry(scope="project", source="AGENTS.md", harnesses=["claude-code"]),
    )
    assert "AGENTS.md" in new.instructions
    assert new.instructions["AGENTS.md"].harnesses == ["claude-code"]
    # original unchanged (immutable update pattern)
    assert lock.instructions == {}


def test_remove_entry():
    lock = InstructionsLockFile(
        version=1,
        instructions={
            "AGENTS.md": InstructionsLockEntry(scope="project", source="AGENTS.md", harnesses=["claude-code"]),
        },
    )
    new = remove_entry(lock, "AGENTS.md")
    assert new.instructions == {}


def test_remove_missing_entry_is_noop():
    lock = InstructionsLockFile(version=1, instructions={})
    assert remove_entry(lock, "AGENTS.md") == lock


def test_unknown_version_raises(tmp_path):
    path = tmp_path / "instructions-lock.json"
    path.write_text(json.dumps({"version": 99, "instructions": {}}))
    with pytest.raises(ValueError, match="unsupported instructions-lock version"):
        read_lock(path)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_cli/test_instructions_lock.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement the lockfile**

```python
# src/agent_toolkit_cli/instructions_lock.py
"""Instructions kind lockfile model — own dataclass, own read/write.

Differs deliberately from skill_lock.LockEntry: an instructions entry has no
`source`/`ref`/`upstream_sha` because the kind has no upstream repo. Sharing
LockEntry would mean every other field is meaningless for instructions; a
separate file is honest about shape.

On-disk shape (v1):

    {
      "version": 1,
      "instructions": {
        "<slug>": {
          "scope": "project" | "global",
          "source": "AGENTS.md",
          "harnesses": ["claude-code", "gemini-cli", ...]
        }
      }
    }

`slug` is always the source filename for now (we manage one AGENTS.md per
lockfile per scope). Keyed-by-slug shape is forward-compatible with future
multi-file support.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Literal

SUPPORTED_VERSIONS: tuple[int, ...] = (1,)

Scope = Literal["project", "global"]


@dataclass
class InstructionsLockEntry:
    scope: Scope
    source: str          # relative to scope root, e.g. "AGENTS.md"
    harnesses: list[str] = field(default_factory=list)


@dataclass
class InstructionsLockFile:
    version: int
    instructions: dict[str, InstructionsLockEntry]


def read_lock(path: Path) -> InstructionsLockFile:
    """Read a lock file. Missing file → empty lock."""
    if not path.exists():
        return InstructionsLockFile(version=1, instructions={})
    raw = json.loads(path.read_text())
    version = int(raw.get("version", 1))
    if version not in SUPPORTED_VERSIONS:
        raise ValueError(
            f"unsupported instructions-lock version: {version} (supported: {SUPPORTED_VERSIONS})"
        )
    entries: dict[str, InstructionsLockEntry] = {}
    for slug, d in raw.get("instructions", {}).items():
        entries[slug] = InstructionsLockEntry(
            scope=d["scope"],
            source=d["source"],
            harnesses=list(d.get("harnesses", [])),
        )
    return InstructionsLockFile(version=version, instructions=entries)


def write_lock(path: Path, lock: InstructionsLockFile) -> None:
    """Write a lock file. Creates parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": lock.version,
        "instructions": {
            slug: {
                "scope": entry.scope,
                "source": entry.source,
                "harnesses": list(entry.harnesses),
            }
            for slug, entry in lock.instructions.items()
        },
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")


def add_entry(
    lock: InstructionsLockFile, slug: str, entry: InstructionsLockEntry
) -> InstructionsLockFile:
    """Return a new lock with `slug` set to `entry`. Original untouched."""
    new_entries = dict(lock.instructions)
    new_entries[slug] = entry
    return replace(lock, instructions=new_entries)


def remove_entry(lock: InstructionsLockFile, slug: str) -> InstructionsLockFile:
    """Return a new lock without `slug`. No-op if absent."""
    if slug not in lock.instructions:
        return lock
    new_entries = {k: v for k, v in lock.instructions.items() if k != slug}
    return replace(lock, instructions=new_entries)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_cli/test_instructions_lock.py -v
```

Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/instructions_lock.py tests/test_cli/test_instructions_lock.py
git commit -m "feat(instructions_lock): InstructionsLockFile model + read/write/add/remove"
```

---

## Task 4: `instructions_adapters/symlink.py` — the one adapter

**Files:**
- Create: `src/agent_toolkit_cli/instructions_adapters/__init__.py`
- Create: `src/agent_toolkit_cli/instructions_adapters/symlink.py`
- Test: `tests/test_cli/test_instructions_adapters/__init__.py`
- Test: `tests/test_cli/test_instructions_adapters/test_symlink.py`

Cell data is the Phase A matrix's 7 symlink-verdict rows.

- [ ] **Step 1: Write the failing test for cell paths**

```python
# tests/test_cli/test_instructions_adapters/__init__.py
```

```python
# tests/test_cli/test_instructions_adapters/test_symlink.py
"""Per-harness symlink adapter for the instructions kind.

Drops a same-name pointer symlink (CLAUDE.md, GEMINI.md, etc.) at each
harness's expected path, pointing at the canonical AGENTS.md.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_toolkit_cli.instructions_adapters import symlink


def test_cells_match_phase_a_symlink_verdict_set():
    """The 7 cells must exactly match the symlink-verdict set in the matrix."""
    expected = {
        "augment", "claude-code", "codebuddy",
        "gemini-cli", "iflow-cli", "replit", "tabnine-cli",
    }
    assert set(symlink.CELLS) == expected


def test_each_cell_has_global_and_project_template():
    for harness, cell in symlink.CELLS.items():
        assert "global" in cell, f"{harness}: missing 'global' template"
        assert "project" in cell, f"{harness}: missing 'project' template"
        assert "{POINTER_NAME}" in (cell["global"] + cell["project"]), (
            f"{harness}: at least one template must use {{POINTER_NAME}}"
        )


def test_install_creates_project_pointer_symlink(tmp_path):
    """install(): a fresh project pointer is symlink → canonical AGENTS.md."""
    project = tmp_path / "proj"
    project.mkdir()
    canonical = project / "AGENTS.md"
    canonical.write_text("# AGENTS.md\nproject canon\n")

    adapter = symlink.adapter_for("claude-code")
    adapter.install(scope="project", project_root=project, canonical=canonical, home=None)

    pointer = project / "CLAUDE.md"
    assert pointer.is_symlink()
    assert pointer.resolve() == canonical.resolve()


def test_install_creates_global_pointer_symlink(tmp_path):
    """install(): a fresh global pointer is at ~/.claude/CLAUDE.md → ~/.agent-toolkit/AGENTS.md."""
    home = tmp_path / "home"
    home.mkdir()
    canonical = home / ".agent-toolkit" / "AGENTS.md"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("# AGENTS.md\nglobal canon\n")

    adapter = symlink.adapter_for("claude-code")
    adapter.install(scope="global", project_root=None, canonical=canonical, home=home)

    pointer = home / ".claude" / "CLAUDE.md"
    assert pointer.is_symlink()
    assert pointer.resolve() == canonical.resolve()


def test_install_is_idempotent_when_pointer_already_correct(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    canonical = project / "AGENTS.md"
    canonical.write_text("# canon\n")

    adapter = symlink.adapter_for("claude-code")
    adapter.install(scope="project", project_root=project, canonical=canonical, home=None)
    adapter.install(scope="project", project_root=project, canonical=canonical, home=None)  # no error

    pointer = project / "CLAUDE.md"
    assert pointer.resolve() == canonical.resolve()


def test_install_refuses_when_pointer_is_real_file(tmp_path):
    """No-clobber: never overwrite a real file. Raise; user must intervene."""
    project = tmp_path / "proj"
    project.mkdir()
    canonical = project / "AGENTS.md"
    canonical.write_text("# canon\n")
    pointer = project / "CLAUDE.md"
    pointer.write_text("# user-authored content\n")  # NOT a symlink

    adapter = symlink.adapter_for("claude-code")
    with pytest.raises(symlink.PointerConflictError, match="CLAUDE.md.*real file"):
        adapter.install(scope="project", project_root=project, canonical=canonical, home=None)

    # File contents preserved.
    assert pointer.read_text() == "# user-authored content\n"


def test_install_refuses_when_pointer_is_foreign_symlink(tmp_path):
    """No-clobber: never replace a symlink pointing elsewhere."""
    project = tmp_path / "proj"
    project.mkdir()
    canonical = project / "AGENTS.md"
    canonical.write_text("# canon\n")
    other = project / "OTHER.md"
    other.write_text("other\n")
    pointer = project / "CLAUDE.md"
    pointer.symlink_to(other)

    adapter = symlink.adapter_for("claude-code")
    with pytest.raises(symlink.PointerConflictError, match="CLAUDE.md.*points elsewhere"):
        adapter.install(scope="project", project_root=project, canonical=canonical, home=None)

    # Symlink target preserved.
    assert pointer.resolve() == other.resolve()


def test_uninstall_removes_our_pointer(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    canonical = project / "AGENTS.md"
    canonical.write_text("# canon\n")

    adapter = symlink.adapter_for("claude-code")
    adapter.install(scope="project", project_root=project, canonical=canonical, home=None)
    pointer = project / "CLAUDE.md"
    assert pointer.is_symlink()

    adapter.uninstall(scope="project", project_root=project, canonical=canonical, home=None)
    assert not pointer.exists()


def test_uninstall_leaves_foreign_symlink_alone(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    canonical = project / "AGENTS.md"
    canonical.write_text("# canon\n")
    other = project / "OTHER.md"
    other.write_text("other\n")
    pointer = project / "CLAUDE.md"
    pointer.symlink_to(other)

    adapter = symlink.adapter_for("claude-code")
    adapter.uninstall(scope="project", project_root=project, canonical=canonical, home=None)

    assert pointer.is_symlink()
    assert pointer.resolve() == other.resolve()


def test_uninstall_leaves_real_file_alone(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    canonical = project / "AGENTS.md"
    canonical.write_text("# canon\n")
    pointer = project / "CLAUDE.md"
    pointer.write_text("real file\n")

    adapter = symlink.adapter_for("claude-code")
    adapter.uninstall(scope="project", project_root=project, canonical=canonical, home=None)

    assert pointer.exists()
    assert not pointer.is_symlink()
    assert pointer.read_text() == "real file\n"


def test_adapter_for_unknown_harness_raises():
    with pytest.raises(symlink.UnknownHarnessError, match="unknown"):
        symlink.adapter_for("notarealharness")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_cli/test_instructions_adapters/test_symlink.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement the adapter**

```python
# src/agent_toolkit_cli/instructions_adapters/__init__.py
"""Adapter dispatcher for the instructions kind.

Only one mechanism exists (`symlink`), so the dispatcher is trivially thin —
get_adapter(harness) just delegates to symlink.adapter_for(harness).
Kept as a layer for symmetry with the agent kind's mechanism-dispatcher
(which has 3 mechanisms) and to give a clean import boundary for the CLI.
"""
from __future__ import annotations

from agent_toolkit_cli.instructions_adapters import symlink

SUPPORTED_HARNESSES: frozenset[str] = frozenset(symlink.CELLS)


def get_adapter(harness: str) -> "symlink.Adapter":
    """Return the symlink adapter bound to `harness`. Raises UnknownHarnessError."""
    return symlink.adapter_for(harness)
```

```python
# src/agent_toolkit_cli/instructions_adapters/symlink.py
"""Symlink mechanism: drop a same-name pointer at each harness's slot.

7 cells. Per-cell paths live in CELLS below. The adapter is a closure factory:
adapter_for(harness) returns a small object with .install() / .uninstall().

Sources: Phase A matrix at docs/agent-toolkit/harness-matrix.md
§ "Instruction-file (`instructions` kind) support — all harnesses"
(symlink-verdict rows, verified 2026-05-29).

Templates use {HOME}, {PROJECT}, {POINTER_NAME} placeholders.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


class PointerConflictError(RuntimeError):
    """A real file or foreign symlink occupies the pointer slot; refused."""


class UnknownHarnessError(KeyError):
    """`harness` is not in the instructions-kind CELLS table."""


Scope = Literal["project", "global"]


# Per-harness pointer path templates + the own-name file each harness reads.
# Sources cited inline; full Phase A evidence in instructions-fragments/.
CELLS: dict[str, dict[str, str]] = {
    # CLAUDE.md is the default-loaded root file across the Auggie precedence chain.
    "augment":     {"pointer_name": "CLAUDE.md",
                    "global":  "{HOME}/.augment/CLAUDE.md",
                    "project": "{PROJECT}/{POINTER_NAME}"},
    # https://code.claude.com/docs/en/memory — "Claude Code reads CLAUDE.md, not AGENTS.md".
    "claude-code": {"pointer_name": "CLAUDE.md",
                    "global":  "{HOME}/.claude/{POINTER_NAME}",
                    "project": "{PROJECT}/{POINTER_NAME}"},
    "codebuddy":   {"pointer_name": "CODEBUDDY.md",
                    "global":  "{HOME}/.codebuddy/{POINTER_NAME}",
                    "project": "{PROJECT}/{POINTER_NAME}"},
    # google-gemini/gemini-cli memoryTool.ts DEFAULT_CONTEXT_FILENAME = 'GEMINI.md'.
    "gemini-cli":  {"pointer_name": "GEMINI.md",
                    "global":  "{HOME}/.gemini/{POINTER_NAME}",
                    "project": "{PROJECT}/{POINTER_NAME}"},
    "iflow-cli":   {"pointer_name": "IFLOW.md",
                    "global":  "{HOME}/.iflow/{POINTER_NAME}",
                    "project": "{PROJECT}/{POINTER_NAME}"},
    # Replit Agent auto-creates and reads replit.md at project root only.
    "replit":      {"pointer_name": "replit.md",
                    "global":  "",  # no global
                    "project": "{PROJECT}/{POINTER_NAME}"},
    "tabnine-cli": {"pointer_name": "TABNINE.md",
                    "global":  "{HOME}/.tabnine/{POINTER_NAME}",
                    "project": "{PROJECT}/{POINTER_NAME}"},
}


def _expand(template: str, *, home: Path | None, project: Path | None, pointer_name: str) -> Path:
    """Expand {HOME}/{PROJECT}/{POINTER_NAME}. Fail-loud on missing inputs."""
    out = template.replace("{POINTER_NAME}", pointer_name)
    if "{HOME}" in out:
        if home is None:
            raise ValueError(f"_expand: template {template!r} needs home= but None was passed")
        out = out.replace("{HOME}", str(home))
    if "{PROJECT}" in out:
        if project is None:
            raise ValueError(f"_expand: template {template!r} needs project= but None was passed")
        out = out.replace("{PROJECT}", str(project))
    return Path(out)


def _pointer_path(
    harness: str, scope: Scope, project_root: Path | None, home: Path | None
) -> Path:
    cell = CELLS[harness]
    template = cell[scope]
    if not template:
        raise ValueError(
            f"harness {harness!r} has no {scope} pointer slot (project-only or global-only)"
        )
    return _expand(template, home=home, project=project_root, pointer_name=cell["pointer_name"])


@dataclass(frozen=True)
class Adapter:
    """Per-harness install/uninstall closure."""
    harness: str

    def install(
        self,
        *,
        scope: Scope,
        project_root: Path | None,
        canonical: Path,
        home: Path | None,
    ) -> None:
        """Create the pointer symlink → canonical. Refuse on conflict."""
        pointer = _pointer_path(self.harness, scope, project_root, home)
        pointer.parent.mkdir(parents=True, exist_ok=True)
        if pointer.is_symlink():
            current = pointer.resolve()
            if current == canonical.resolve():
                return  # idempotent no-op
            raise PointerConflictError(
                f"{pointer.name} points elsewhere ({current}); refused. "
                "Remove it manually and re-run install."
            )
        if pointer.exists():
            raise PointerConflictError(
                f"{pointer.name} is a real file at {pointer}; refused. "
                "Move or delete it manually and re-run install."
            )
        pointer.symlink_to(canonical)

    def uninstall(
        self,
        *,
        scope: Scope,
        project_root: Path | None,
        canonical: Path,
        home: Path | None,
    ) -> None:
        """Remove only our exact pointer. Real files and foreign symlinks untouched."""
        pointer = _pointer_path(self.harness, scope, project_root, home)
        if not pointer.is_symlink():
            return  # real file or absent — leave alone
        if pointer.resolve() != canonical.resolve():
            return  # foreign symlink — not ours
        pointer.unlink()


def adapter_for(harness: str) -> Adapter:
    if harness not in CELLS:
        raise UnknownHarnessError(f"unknown harness for instructions kind: {harness!r}")
    return Adapter(harness=harness)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_cli/test_instructions_adapters/test_symlink.py -v
```

Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/instructions_adapters tests/test_cli/test_instructions_adapters
git commit -m "feat(instructions_adapters): symlink adapter for 7 verdict harnesses + no-clobber"
```

---

## Task 5: Dispatcher exhaustiveness test

**Files:**
- Create: `tests/test_cli/test_instructions_adapters/test_dispatcher.py`

Guards against drift between Phase A's symlink set and the adapter's CELLS table. Each side has its own SSOT (matrix doc + parity test for one; CELLS dict for the other), so a separate guard test enforces equivalence.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli/test_instructions_adapters/test_dispatcher.py
"""The adapter's CELLS table must equal the Phase A symlink-verdict set."""
from __future__ import annotations

import re
from pathlib import Path

from agent_toolkit_cli.instructions_adapters import (
    SUPPORTED_HARNESSES,
    get_adapter,
)
from agent_toolkit_cli.instructions_adapters.symlink import (
    Adapter,
    UnknownHarnessError,
)

_DOC = Path(__file__).resolve().parents[3] / "docs/agent-toolkit/harness-matrix.md"
_SECTION_HEADING = "## Instruction-file (`instructions` kind) support — all harnesses"
_ROW_RE = re.compile(
    r"^\|\s*`(?P<harness>[a-z][a-z0-9-]*)`\s*\|"
    r"(?P<verdict>[^|]+)\|"
)


def _matrix_symlink_set() -> set[str]:
    text = _DOC.read_text(encoding="utf-8")
    section = text.split(_SECTION_HEADING, 1)[1]
    section = re.split(r"^## ", section, maxsplit=1, flags=re.MULTILINE)[0]
    out: set[str] = set()
    for line in section.splitlines():
        m = _ROW_RE.match(line.strip())
        if not m:
            continue
        if m.group("verdict").strip().lower().startswith("symlink"):
            out.add(m.group("harness"))
    return out


def test_supported_harnesses_matches_matrix_symlink_set():
    """The adapter table is the implementation; the matrix is the contract."""
    assert SUPPORTED_HARNESSES == _matrix_symlink_set()


def test_get_adapter_returns_adapter_instance():
    for harness in SUPPORTED_HARNESSES:
        adapter = get_adapter(harness)
        assert isinstance(adapter, Adapter)
        assert adapter.harness == harness


def test_get_adapter_unknown_harness_raises():
    import pytest
    with pytest.raises(UnknownHarnessError):
        get_adapter("notreal")
```

- [ ] **Step 2: Run test to verify it passes**

(Already implemented in Task 4; this test must pass against the existing code.)

```bash
uv run pytest tests/test_cli/test_instructions_adapters/test_dispatcher.py -v
```

Expected: 3 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/test_cli/test_instructions_adapters/test_dispatcher.py
git commit -m "test(instructions_adapters): dispatcher exhaustiveness guard vs Phase A matrix"
```

---

## Task 6: `instructions_install.py` — plan / apply / uninstall

**Files:**
- Create: `src/agent_toolkit_cli/instructions_install.py`
- Test: `tests/test_cli/test_instructions_install.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli/test_instructions_install.py
"""instructions_install — plan/apply/uninstall over the symlink adapter."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_toolkit_cli import instructions_install, instructions_paths
from agent_toolkit_cli.instructions_lock import (
    InstructionsLockEntry,
    InstructionsLockFile,
    read_lock,
    write_lock,
)


@pytest.fixture
def project(tmp_path):
    p = tmp_path / "proj"
    p.mkdir()
    (p / "AGENTS.md").write_text("# project AGENTS.md\n")
    return p


def test_apply_creates_pointers_for_lock_harnesses(project):
    """apply() reconciles filesystem to match the lock's harnesses[] list."""
    lock_path = project / "instructions-lock.json"
    write_lock(
        lock_path,
        InstructionsLockFile(
            version=1,
            instructions={
                "AGENTS.md": InstructionsLockEntry(
                    scope="project",
                    source="AGENTS.md",
                    harnesses=["claude-code", "gemini-cli"],
                ),
            },
        ),
    )

    instructions_install.apply(scope="project", project_root=project, home=None)

    assert (project / "CLAUDE.md").is_symlink()
    assert (project / "CLAUDE.md").resolve() == (project / "AGENTS.md").resolve()
    assert (project / "GEMINI.md").is_symlink()


def test_apply_refuses_when_canonical_missing(tmp_path):
    """install/apply must refuse if there is no AGENTS.md to point to."""
    project = tmp_path / "proj"
    project.mkdir()
    # No AGENTS.md.
    lock_path = project / "instructions-lock.json"
    write_lock(
        lock_path,
        InstructionsLockFile(
            version=1,
            instructions={
                "AGENTS.md": InstructionsLockEntry(
                    scope="project", source="AGENTS.md", harnesses=["claude-code"],
                ),
            },
        ),
    )

    with pytest.raises(instructions_install.CanonicalMissingError, match="AGENTS.md"):
        instructions_install.apply(scope="project", project_root=project, home=None)


def test_apply_with_empty_lock_is_noop(project):
    """No lock entry → no pointers created."""
    instructions_install.apply(scope="project", project_root=project, home=None)
    assert not (project / "CLAUDE.md").exists()


def test_uninstall_removes_pointers(project):
    """uninstall() removes only pointers we own; lock entry is cleared."""
    lock_path = project / "instructions-lock.json"
    write_lock(
        lock_path,
        InstructionsLockFile(
            version=1,
            instructions={
                "AGENTS.md": InstructionsLockEntry(
                    scope="project", source="AGENTS.md",
                    harnesses=["claude-code", "gemini-cli"],
                ),
            },
        ),
    )
    instructions_install.apply(scope="project", project_root=project, home=None)
    assert (project / "CLAUDE.md").is_symlink()

    instructions_install.uninstall(scope="project", project_root=project, home=None)

    assert not (project / "CLAUDE.md").exists()
    assert not (project / "GEMINI.md").exists()
    # Lock entry cleared at project scope.
    assert read_lock(lock_path).instructions == {}


def test_apply_prunes_pointer_removed_from_lock(project):
    """If a harness is removed from the lock, apply() removes its pointer too."""
    lock_path = project / "instructions-lock.json"
    write_lock(
        lock_path,
        InstructionsLockFile(
            version=1,
            instructions={
                "AGENTS.md": InstructionsLockEntry(
                    scope="project", source="AGENTS.md",
                    harnesses=["claude-code", "gemini-cli"],
                ),
            },
        ),
    )
    instructions_install.apply(scope="project", project_root=project, home=None)
    assert (project / "GEMINI.md").is_symlink()

    # Update lock: drop gemini-cli.
    write_lock(
        lock_path,
        InstructionsLockFile(
            version=1,
            instructions={
                "AGENTS.md": InstructionsLockEntry(
                    scope="project", source="AGENTS.md", harnesses=["claude-code"],
                ),
            },
        ),
    )
    instructions_install.apply(scope="project", project_root=project, home=None)

    assert (project / "CLAUDE.md").is_symlink()
    assert not (project / "GEMINI.md").exists()


def test_apply_skips_unsupported_harness_in_lock(project):
    """A harness not in the symlink-verdict set is ignored (warns later via CLI)."""
    lock_path = project / "instructions-lock.json"
    write_lock(
        lock_path,
        InstructionsLockFile(
            version=1,
            instructions={
                "AGENTS.md": InstructionsLockEntry(
                    scope="project", source="AGENTS.md",
                    harnesses=["claude-code", "codex"],  # codex is `native`, not symlink
                ),
            },
        ),
    )
    # Should not raise; just skips codex.
    instructions_install.apply(scope="project", project_root=project, home=None)
    assert (project / "CLAUDE.md").is_symlink()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_cli/test_instructions_install.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement the install engine**

```python
# src/agent_toolkit_cli/instructions_install.py
"""Reconcile filesystem pointers to match the instructions lockfile.

Public surface:
    apply(scope, project_root, home)     — reconcile pointers ON for `scope`
    uninstall(scope, project_root, home) — remove pointers + clear lock entry
    plan(scope, project_root, home)      — return diff without touching disk

`apply` is idempotent and pruning: it creates pointers for lock-listed
harnesses that aren't on disk, removes ours-but-no-longer-listed pointers,
and leaves foreign / real-file slots alone (delegated to the adapter).

Unsupported harnesses in the lock (`native` / `gap` / `by-design` / `unknown`)
are silently skipped — surfacing them is the CLI's job (it has access to
`click.echo`). This module returns structured plans, not user-facing text.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from agent_toolkit_cli import instructions_paths
from agent_toolkit_cli.instructions_adapters import SUPPORTED_HARNESSES, get_adapter
from agent_toolkit_cli.instructions_lock import (
    InstructionsLockEntry,
    InstructionsLockFile,
    add_entry,
    read_lock,
    remove_entry,
    write_lock,
)

Scope = Literal["project", "global"]


class CanonicalMissingError(RuntimeError):
    """No AGENTS.md at the resolved canonical path — pointer install refused."""


@dataclass
class PointerAction:
    harness: str
    pointer: Path
    action: Literal["create", "remove", "noop-already-correct", "skip-foreign", "skip-unsupported"]


@dataclass
class Plan:
    canonical: Path
    actions: list[PointerAction]


def _resolve_canonical(scope: Scope, project_root: Path | None) -> Path:
    if scope == "project":
        if project_root is None:
            raise ValueError("project scope requires project_root")
        return instructions_paths.project_canonical_agents_md(project_root)
    return instructions_paths.global_canonical_agents_md()


def _list_currently_owned(
    canonical: Path, scope: Scope, project_root: Path | None, home: Path | None
) -> set[str]:
    """For each supported harness, return those whose pointer symlinks at canonical."""
    from agent_toolkit_cli.instructions_adapters.symlink import (
        CELLS,
        _pointer_path,
    )
    owned: set[str] = set()
    for harness in SUPPORTED_HARNESSES:
        # Some cells are project-only or global-only — _pointer_path raises for those.
        try:
            pointer = _pointer_path(harness, scope, project_root, home)
        except ValueError:
            continue
        if pointer.is_symlink() and pointer.resolve() == canonical.resolve():
            owned.add(harness)
    return owned


def plan(
    *, scope: Scope, project_root: Path | None, home: Path | None
) -> Plan:
    """Return a Plan describing what apply() would do. No disk changes."""
    canonical = _resolve_canonical(scope, project_root)
    lock_path = instructions_paths.lock_file_path(scope, project_root)
    lock = read_lock(lock_path)

    wanted: set[str] = set()
    for entry in lock.instructions.values():
        wanted.update(h for h in entry.harnesses if h in SUPPORTED_HARNESSES)

    owned = _list_currently_owned(canonical, scope, project_root, home)

    from agent_toolkit_cli.instructions_adapters.symlink import _pointer_path
    actions: list[PointerAction] = []
    for harness in sorted(wanted - owned):
        try:
            ptr = _pointer_path(harness, scope, project_root, home)
        except ValueError:
            continue
        actions.append(PointerAction(harness=harness, pointer=ptr, action="create"))
    for harness in sorted(owned - wanted):
        ptr = _pointer_path(harness, scope, project_root, home)
        actions.append(PointerAction(harness=harness, pointer=ptr, action="remove"))
    for harness in sorted(owned & wanted):
        ptr = _pointer_path(harness, scope, project_root, home)
        actions.append(PointerAction(harness=harness, pointer=ptr, action="noop-already-correct"))
    return Plan(canonical=canonical, actions=actions)


def apply(*, scope: Scope, project_root: Path | None, home: Path | None) -> Plan:
    """Reconcile filesystem to match the lock. Returns the plan that was applied.

    Refuses if canonical AGENTS.md is missing.
    """
    canonical = _resolve_canonical(scope, project_root)
    if not canonical.exists():
        raise CanonicalMissingError(
            f"no AGENTS.md at {canonical} to point to; create it before running install"
        )

    p = plan(scope=scope, project_root=project_root, home=home)
    for act in p.actions:
        if act.action == "create":
            get_adapter(act.harness).install(
                scope=scope, project_root=project_root,
                canonical=canonical, home=home,
            )
        elif act.action == "remove":
            get_adapter(act.harness).uninstall(
                scope=scope, project_root=project_root,
                canonical=canonical, home=home,
            )
        # noop-already-correct: nothing to do.
    return p


def uninstall(
    *, scope: Scope, project_root: Path | None, home: Path | None
) -> None:
    """Remove all our pointers and clear the lock entry at this scope."""
    canonical = _resolve_canonical(scope, project_root)
    owned = _list_currently_owned(canonical, scope, project_root, home)
    for harness in owned:
        get_adapter(harness).uninstall(
            scope=scope, project_root=project_root,
            canonical=canonical, home=home,
        )
    lock_path = instructions_paths.lock_file_path(scope, project_root)
    lock = read_lock(lock_path)
    new = lock
    for slug in list(lock.instructions.keys()):
        new = remove_entry(new, slug)
    write_lock(lock_path, new)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_cli/test_instructions_install.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/instructions_install.py tests/test_cli/test_instructions_install.py
git commit -m "feat(instructions_install): plan/apply/uninstall pointer reconciliation"
```

---

## Task 7: E2E parametrised install test across all 7 cells

**Files:**
- Create: `tests/test_cli/test_instructions_install_e2e.py`

Builds confidence by exercising every cell end-to-end with the real `apply()` path. Phase A's matrix is the parameter source.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli/test_instructions_install_e2e.py
"""End-to-end: apply() lays the correct pointer per Phase A cell."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_toolkit_cli import instructions_install
from agent_toolkit_cli.instructions_adapters.symlink import CELLS
from agent_toolkit_cli.instructions_lock import (
    InstructionsLockEntry,
    InstructionsLockFile,
    write_lock,
)


@pytest.mark.parametrize(
    "harness",
    [h for h, cell in CELLS.items() if cell["project"]],
)
def test_project_scope_pointer_created(tmp_path, harness):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# canon\n")
    write_lock(
        project / "instructions-lock.json",
        InstructionsLockFile(
            version=1,
            instructions={
                "AGENTS.md": InstructionsLockEntry(
                    scope="project", source="AGENTS.md", harnesses=[harness],
                ),
            },
        ),
    )

    instructions_install.apply(scope="project", project_root=project, home=None)

    pointer_name = CELLS[harness]["pointer_name"]
    pointer = project / pointer_name
    assert pointer.is_symlink(), f"{harness}: expected symlink at {pointer}"
    assert pointer.resolve() == (project / "AGENTS.md").resolve()


@pytest.mark.parametrize(
    "harness",
    [h for h, cell in CELLS.items() if cell["global"]],
)
def test_global_scope_pointer_created(tmp_path, monkeypatch, harness):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    canonical = home / ".agent-toolkit" / "AGENTS.md"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("# canon\n")
    write_lock(
        home / ".agent-toolkit" / "instructions-lock.json",
        InstructionsLockFile(
            version=1,
            instructions={
                "AGENTS.md": InstructionsLockEntry(
                    scope="global", source="AGENTS.md", harnesses=[harness],
                ),
            },
        ),
    )

    instructions_install.apply(scope="global", project_root=None, home=home)

    # The actual global pointer location varies per cell; reconstruct it.
    from agent_toolkit_cli.instructions_adapters.symlink import _pointer_path
    pointer = _pointer_path(harness, "global", None, home)
    assert pointer.is_symlink(), f"{harness}: expected symlink at {pointer}"
    assert pointer.resolve() == canonical.resolve()
```

- [ ] **Step 2: Run tests**

```bash
uv run pytest tests/test_cli/test_instructions_install_e2e.py -v
```

Expected: All parametrised tests pass — project-scope sweep covers 7 cells; global-scope sweep covers 6 (replit has no global).

- [ ] **Step 3: Commit**

```bash
git add tests/test_cli/test_instructions_install_e2e.py
git commit -m "test(instructions_install): parametrised e2e across all 7 symlink cells"
```

---

## Task 8: CLI scaffolding — `instructions` group registered

**Files:**
- Create: `src/agent_toolkit_cli/commands/instructions/__init__.py`
- Modify: `src/agent_toolkit_cli/cli.py` (import + add_command)
- Test: `tests/test_cli/test_instructions_cli.py` (skeleton)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli/test_instructions_cli.py
"""CLI surface: `agent-toolkit-cli instructions <verb>` smoke."""
from __future__ import annotations

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def test_instructions_group_registered():
    runner = CliRunner()
    result = runner.invoke(main, ["instructions", "--help"])
    assert result.exit_code == 0, result.output
    assert "install" in result.output
    assert "uninstall" in result.output
    assert "list" in result.output
    assert "status" in result.output
    assert "doctor" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_cli/test_instructions_cli.py::test_instructions_group_registered -v
```

Expected: FAIL — `No such command 'instructions'`.

- [ ] **Step 3: Scaffold the group**

```python
# src/agent_toolkit_cli/commands/instructions/__init__.py
"""`agent-toolkit-cli instructions ...` command group."""
from __future__ import annotations

import click

from .doctor_cmd import doctor_cmd
from .install_cmd import install_cmd
from .list_cmd import list_cmd
from .status_cmd import status_cmd
from .uninstall_cmd import uninstall_cmd


@click.group(help="Manage harness-aware pointers to a canonical AGENTS.md.")
def instructions() -> None:
    """Root for the instructions-kind verb group."""


instructions.add_command(install_cmd, name="install")
instructions.add_command(uninstall_cmd, name="uninstall")
instructions.add_command(list_cmd, name="list")
instructions.add_command(status_cmd, name="status")
instructions.add_command(doctor_cmd, name="doctor")
```

Stub each verb file (we implement them in Tasks 9–13):

```python
# src/agent_toolkit_cli/commands/instructions/install_cmd.py
import click

@click.command(help="Install per-harness pointers to AGENTS.md.")
def install_cmd() -> None:
    raise click.ClickException("not yet implemented (Task 9)")
```

```python
# src/agent_toolkit_cli/commands/instructions/uninstall_cmd.py
import click

@click.command(help="Remove our pointers; leave foreign files alone.")
def uninstall_cmd() -> None:
    raise click.ClickException("not yet implemented (Task 10)")
```

```python
# src/agent_toolkit_cli/commands/instructions/list_cmd.py
import click

@click.command(help="Per-harness verdict for the instructions kind.")
def list_cmd() -> None:
    raise click.ClickException("not yet implemented (Task 11)")
```

```python
# src/agent_toolkit_cli/commands/instructions/status_cmd.py
import click

@click.command(help="Pointer state vs the lockfile.")
def status_cmd() -> None:
    raise click.ClickException("not yet implemented (Task 12)")
```

```python
# src/agent_toolkit_cli/commands/instructions/doctor_cmd.py
import click

@click.command(help="Find conflicting/orphan/stray pointers.")
def doctor_cmd() -> None:
    raise click.ClickException("not yet implemented (Task 13)")
```

Edit `src/agent_toolkit_cli/cli.py` to register the group:

```python
# Add to imports (after `from agent_toolkit_cli.commands.skill import skill`):
from agent_toolkit_cli.commands.instructions import instructions

# Inside the main group setup (after `main.add_command(skill)` if present, or
# wherever subcommands are registered):
main.add_command(instructions)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_cli/test_instructions_cli.py::test_instructions_group_registered -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/instructions src/agent_toolkit_cli/cli.py tests/test_cli/test_instructions_cli.py
git commit -m "feat(cli): scaffold instructions command group with 5 verb stubs"
```

---

## Task 9: `instructions install` verb

**Files:**
- Modify: `src/agent_toolkit_cli/commands/instructions/install_cmd.py`
- Test: `tests/test_cli/test_instructions_cli.py` (add cases)

The CLI verb wires user intent (which harnesses to enable, which scope) into the lockfile, then calls `instructions_install.apply()` to reconcile. It writes the lock entry if missing, mutates it to reflect `--harness` adds.

- [ ] **Step 1: Write the failing test**

```python
# Append to tests/test_cli/test_instructions_cli.py
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def test_install_creates_pointer_for_named_harness(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# canon\n")
    monkeypatch.chdir(project)

    runner = CliRunner()
    result = runner.invoke(main, [
        "instructions", "install",
        "--scope", "project",
        "--harness", "claude-code",
    ])
    assert result.exit_code == 0, result.output

    pointer = project / "CLAUDE.md"
    assert pointer.is_symlink()

    lock = json.loads((project / "instructions-lock.json").read_text())
    assert lock["instructions"]["AGENTS.md"]["harnesses"] == ["claude-code"]


def test_install_refuses_when_canonical_missing(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    # No AGENTS.md.
    monkeypatch.chdir(project)

    runner = CliRunner()
    result = runner.invoke(main, [
        "instructions", "install",
        "--scope", "project",
        "--harness", "claude-code",
    ])
    assert result.exit_code != 0
    assert "AGENTS.md" in result.output


def test_install_rejects_native_harness_with_clear_message(tmp_path, monkeypatch):
    """`codex` is `native` — no pointer needed. CLI should refuse explicitly."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# canon\n")
    monkeypatch.chdir(project)

    runner = CliRunner()
    result = runner.invoke(main, [
        "instructions", "install",
        "--scope", "project",
        "--harness", "codex",
    ])
    assert result.exit_code != 0
    assert "native" in result.output.lower()
    assert "no pointer needed" in result.output.lower()


def test_install_all_default_targets_all_symlink_harnesses(tmp_path, monkeypatch):
    """No --harness flag → install for every symlink-verdict harness."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# canon\n")
    monkeypatch.chdir(project)

    runner = CliRunner()
    result = runner.invoke(main, ["instructions", "install", "--scope", "project"])
    assert result.exit_code == 0, result.output

    # All project-slot symlink cells should be pointers now.
    from agent_toolkit_cli.instructions_adapters.symlink import CELLS
    for harness, cell in CELLS.items():
        if cell["project"]:
            pointer_name = cell["pointer_name"]
            assert (project / pointer_name).is_symlink(), f"missing pointer: {harness} → {pointer_name}"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_cli/test_instructions_cli.py -v -k install
```

Expected: failures — stub raises `not yet implemented`.

- [ ] **Step 3: Implement the install verb**

```python
# src/agent_toolkit_cli/commands/instructions/install_cmd.py
"""`instructions install` — write lock + reconcile filesystem."""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli import instructions_install, instructions_paths
from agent_toolkit_cli.instructions_adapters import SUPPORTED_HARNESSES
from agent_toolkit_cli.instructions_lock import (
    InstructionsLockEntry,
    add_entry,
    read_lock,
    write_lock,
)
from agent_toolkit_cli.skill_agents import AGENTS


@click.command(help="Install per-harness pointers to AGENTS.md.")
@click.option(
    "--scope",
    type=click.Choice(["project", "global"]),
    default="project",
    help="Lock scope. Project default mirrors the spec — pointers are project-rooted.",
)
@click.option(
    "--harness",
    "harnesses",
    multiple=True,
    help="Specific harness(es) to install. Repeat for multiple. "
    "Default: all symlink-verdict harnesses.",
)
@click.pass_context
def install_cmd(ctx: click.Context, scope: str, harnesses: tuple[str, ...]) -> None:
    project_root = _resolve_project_root(ctx, scope)
    targets = list(harnesses) or sorted(SUPPORTED_HARNESSES)

    # Validate every requested harness BEFORE writing the lock.
    for h in targets:
        if h in SUPPORTED_HARNESSES:
            continue
        if h in AGENTS:
            # In catalog but not symlink-verdict → tell them why.
            raise click.ClickException(
                f"{h!r}: this harness is `native` (reads AGENTS.md by default) — "
                "no pointer needed. See harness-matrix.md."
            )
        raise click.ClickException(f"{h!r}: not in the harness catalog")

    lock_path = instructions_paths.lock_file_path(scope, project_root)
    lock = read_lock(lock_path)
    existing = lock.instructions.get("AGENTS.md")
    new_harnesses = sorted({*(existing.harnesses if existing else []), *targets})
    new = add_entry(
        lock,
        "AGENTS.md",
        InstructionsLockEntry(
            scope=scope,
            source="AGENTS.md",
            harnesses=new_harnesses,
        ),
    )
    write_lock(lock_path, new)

    try:
        plan = instructions_install.apply(
            scope=scope, project_root=project_root, home=None
        )
    except instructions_install.CanonicalMissingError as exc:
        raise click.ClickException(str(exc)) from exc

    for act in plan.actions:
        if act.action == "create":
            click.echo(f"created  {act.harness:14s}  {act.pointer}")
        elif act.action == "noop-already-correct":
            click.echo(f"ok       {act.harness:14s}  {act.pointer}")
        elif act.action == "remove":
            click.echo(f"removed  {act.harness:14s}  {act.pointer}")


def _resolve_project_root(ctx: click.Context, scope: str) -> Path | None:
    """For project scope, derive root from the top-level --project-root or cwd."""
    if scope == "global":
        return None
    obj = ctx.find_root().params.get("project_root")
    return obj if obj else Path.cwd()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_cli/test_instructions_cli.py -v -k install
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/instructions/install_cmd.py tests/test_cli/test_instructions_cli.py
git commit -m "feat(cli): instructions install — lock + reconcile + native-harness guard"
```

---

## Task 10: `instructions uninstall` verb

**Files:**
- Modify: `src/agent_toolkit_cli/commands/instructions/uninstall_cmd.py`
- Test: `tests/test_cli/test_instructions_cli.py` (add cases)

- [ ] **Step 1: Write the failing test**

```python
# Append to tests/test_cli/test_instructions_cli.py
def test_uninstall_removes_pointers_and_clears_lock(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# canon\n")
    monkeypatch.chdir(project)

    runner = CliRunner()
    runner.invoke(main, ["instructions", "install", "--scope", "project", "--harness", "claude-code"])
    assert (project / "CLAUDE.md").is_symlink()

    result = runner.invoke(main, ["instructions", "uninstall", "--scope", "project"])
    assert result.exit_code == 0, result.output

    assert not (project / "CLAUDE.md").exists()
    lock = json.loads((project / "instructions-lock.json").read_text())
    assert lock["instructions"] == {}


def test_uninstall_leaves_foreign_files_alone(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# canon\n")
    # User has authored their own CLAUDE.md.
    (project / "CLAUDE.md").write_text("user authored\n")
    monkeypatch.chdir(project)

    runner = CliRunner()
    result = runner.invoke(main, ["instructions", "uninstall", "--scope", "project"])
    # No lock entry to clear, no symlink to remove — exits cleanly.
    assert result.exit_code == 0

    assert (project / "CLAUDE.md").read_text() == "user authored\n"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_cli/test_instructions_cli.py -v -k uninstall
```

Expected: failures.

- [ ] **Step 3: Implement the uninstall verb**

```python
# src/agent_toolkit_cli/commands/instructions/uninstall_cmd.py
"""`instructions uninstall` — remove our pointers, clear lock entry."""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli import instructions_install


@click.command(help="Remove pointers we own; leave foreign files and symlinks alone.")
@click.option(
    "--scope",
    type=click.Choice(["project", "global"]),
    default="project",
    help="Lock scope.",
)
@click.pass_context
def uninstall_cmd(ctx: click.Context, scope: str) -> None:
    project_root = None
    if scope == "project":
        obj = ctx.find_root().params.get("project_root")
        project_root = obj if obj else Path.cwd()

    instructions_install.uninstall(
        scope=scope, project_root=project_root, home=None
    )
    click.echo(f"uninstalled instructions pointers at {scope} scope")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_cli/test_instructions_cli.py -v -k uninstall
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/instructions/uninstall_cmd.py tests/test_cli/test_instructions_cli.py
git commit -m "feat(cli): instructions uninstall — remove ours, leave foreign alone"
```

---

## Task 11: `instructions list` verb

**Files:**
- Modify: `src/agent_toolkit_cli/commands/instructions/list_cmd.py`
- Test: `tests/test_cli/test_instructions_cli.py` (add cases)

`list` is informational — print the Phase A matrix verdict per harness. Sourced from the in-tree matrix doc, so the CLI doesn't drift if the doc is updated.

- [ ] **Step 1: Write the failing test**

```python
# Append to tests/test_cli/test_instructions_cli.py
def test_list_shows_verdict_per_harness():
    runner = CliRunner()
    result = runner.invoke(main, ["instructions", "list"])
    assert result.exit_code == 0, result.output

    # Spot-check: must include the 7 symlink-verdict harnesses and at least
    # one native and one gap harness.
    for h in ("claude-code", "gemini-cli", "codex", "continue"):
        assert h in result.output, f"missing {h} in output"
    assert "symlink" in result.output
    assert "native" in result.output


def test_list_json_format():
    runner = CliRunner()
    result = runner.invoke(main, ["instructions", "list", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    by_harness = {row["harness"]: row for row in data}
    assert by_harness["claude-code"]["verdict"] == "symlink"
    assert by_harness["codex"]["verdict"] == "native"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_cli/test_instructions_cli.py -v -k list
```

Expected: failures.

- [ ] **Step 3: Implement the list verb**

```python
# src/agent_toolkit_cli/commands/instructions/list_cmd.py
"""`instructions list` — per-harness verdict from the Phase A matrix."""
from __future__ import annotations

import json as _json
import re
from pathlib import Path

import click

_DOC = Path(__file__).resolve().parents[3] / "docs/agent-toolkit/harness-matrix.md"
_SECTION_HEADING = "## Instruction-file (`instructions` kind) support — all harnesses"
_ROW_RE = re.compile(
    r"^\|\s*`(?P<harness>[a-z][a-z0-9-]*)`\s*\|"
    r"(?P<verdict>[^|]+)\|"
    r"(?P<default>[^|]*)\|"
    r"(?P<paths>[^|]*)\|"
)


def _parse_matrix() -> list[dict[str, str]]:
    text = _DOC.read_text(encoding="utf-8")
    section = text.split(_SECTION_HEADING, 1)[1]
    section = re.split(r"^## ", section, maxsplit=1, flags=re.MULTILINE)[0]
    rows: list[dict[str, str]] = []
    for line in section.splitlines():
        m = _ROW_RE.match(line.strip())
        if m is None:
            continue
        rows.append({
            "harness": m.group("harness"),
            "verdict": m.group("verdict").strip(),
            "default_file": m.group("default").strip(),
            "paths": m.group("paths").strip(),
        })
    rows.sort(key=lambda r: r["harness"])
    return rows


@click.command(help="Per-harness verdict for the instructions kind.")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["table", "json"]),
    default="table",
)
def list_cmd(fmt: str) -> None:
    rows = _parse_matrix()
    if fmt == "json":
        click.echo(_json.dumps(rows, indent=2))
        return
    width = max(len(r["harness"]) for r in rows)
    click.echo(f"{'HARNESS':<{width}}  VERDICT          DEFAULT FILE")
    for r in rows:
        click.echo(f"{r['harness']:<{width}}  {r['verdict']:<15}  {r['default_file']}")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_cli/test_instructions_cli.py -v -k list
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/instructions/list_cmd.py tests/test_cli/test_instructions_cli.py
git commit -m "feat(cli): instructions list — verdict per harness (table + json)"
```

---

## Task 12: `instructions status` verb

**Files:**
- Modify: `src/agent_toolkit_cli/commands/instructions/status_cmd.py`
- Test: `tests/test_cli/test_instructions_cli.py` (add cases)

`status` reports actual pointer state vs the lock — for each lock-listed harness, is the pointer present / missing / conflicting?

- [ ] **Step 1: Write the failing test**

```python
# Append to tests/test_cli/test_instructions_cli.py
def test_status_reports_present_and_missing(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# canon\n")
    monkeypatch.chdir(project)

    runner = CliRunner()
    runner.invoke(main, ["instructions", "install", "--scope", "project", "--harness", "claude-code"])

    # Remove the pointer to simulate drift.
    (project / "CLAUDE.md").unlink()

    result = runner.invoke(main, ["instructions", "status", "--scope", "project"])
    assert result.exit_code == 0
    assert "claude-code" in result.output
    assert "missing" in result.output.lower()


def test_status_reports_conflict_when_pointer_points_elsewhere(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# canon\n")
    (project / "OTHER.md").write_text("other\n")
    monkeypatch.chdir(project)

    runner = CliRunner()
    runner.invoke(main, ["instructions", "install", "--scope", "project", "--harness", "claude-code"])

    # Replace our symlink with one pointing at OTHER.md.
    (project / "CLAUDE.md").unlink()
    (project / "CLAUDE.md").symlink_to(project / "OTHER.md")

    result = runner.invoke(main, ["instructions", "status", "--scope", "project"])
    assert "conflict" in result.output.lower()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_cli/test_instructions_cli.py -v -k status
```

Expected: failures.

- [ ] **Step 3: Implement the status verb**

```python
# src/agent_toolkit_cli/commands/instructions/status_cmd.py
"""`instructions status` — pointer state vs lock."""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli import instructions_paths
from agent_toolkit_cli.instructions_adapters import SUPPORTED_HARNESSES
from agent_toolkit_cli.instructions_adapters.symlink import _pointer_path
from agent_toolkit_cli.instructions_lock import read_lock


@click.command(help="Pointer state vs lock (present / missing / conflict).")
@click.option(
    "--scope",
    type=click.Choice(["project", "global"]),
    default="project",
)
@click.pass_context
def status_cmd(ctx: click.Context, scope: str) -> None:
    project_root: Path | None = None
    home: Path | None = None
    if scope == "project":
        obj = ctx.find_root().params.get("project_root")
        project_root = obj if obj else Path.cwd()
        canonical = instructions_paths.project_canonical_agents_md(project_root)
    else:
        canonical = instructions_paths.global_canonical_agents_md()

    lock_path = instructions_paths.lock_file_path(scope, project_root)
    lock = read_lock(lock_path)

    wanted: set[str] = set()
    for entry in lock.instructions.values():
        wanted.update(h for h in entry.harnesses if h in SUPPORTED_HARNESSES)

    for harness in sorted(wanted):
        try:
            pointer = _pointer_path(harness, scope, project_root, home)
        except ValueError as exc:
            click.echo(f"{harness:14s}  skip      {exc}")
            continue
        if not pointer.exists() and not pointer.is_symlink():
            click.echo(f"{harness:14s}  missing   {pointer}")
        elif pointer.is_symlink() and pointer.resolve() == canonical.resolve():
            click.echo(f"{harness:14s}  ok        {pointer}")
        elif pointer.is_symlink():
            click.echo(f"{harness:14s}  conflict  {pointer} → {pointer.resolve()}")
        else:
            click.echo(f"{harness:14s}  conflict  {pointer} (real file)")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_cli/test_instructions_cli.py -v -k status
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/instructions/status_cmd.py tests/test_cli/test_instructions_cli.py
git commit -m "feat(cli): instructions status — present/missing/conflict per lock entry"
```

---

## Task 13: `instructions doctor` verb

**Files:**
- Modify: `src/agent_toolkit_cli/commands/instructions/doctor_cmd.py`
- Test: `tests/test_cli/test_instructions_cli.py` (add cases)

Doctor learns the kind — surface stray pointers, orphans (lock entry but no canonical), and conflicting symlinks. Exits non-zero if any finding.

- [ ] **Step 1: Write the failing test**

```python
# Append to tests/test_cli/test_instructions_cli.py
def test_doctor_reports_orphan_pointer_when_canonical_gone(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# canon\n")
    monkeypatch.chdir(project)

    runner = CliRunner()
    runner.invoke(main, ["instructions", "install", "--scope", "project", "--harness", "claude-code"])
    (project / "AGENTS.md").unlink()  # canonical gone; pointer dangles

    result = runner.invoke(main, ["instructions", "doctor", "--scope", "project"])
    assert result.exit_code != 0
    assert "orphan" in result.output.lower()


def test_doctor_clean_exit_zero(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# canon\n")
    monkeypatch.chdir(project)

    runner = CliRunner()
    runner.invoke(main, ["instructions", "install", "--scope", "project", "--harness", "claude-code"])

    result = runner.invoke(main, ["instructions", "doctor", "--scope", "project"])
    assert result.exit_code == 0, result.output
    assert "clean" in result.output.lower()


def test_doctor_reports_conflict(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# canon\n")
    monkeypatch.chdir(project)

    runner = CliRunner()
    runner.invoke(main, ["instructions", "install", "--scope", "project", "--harness", "claude-code"])
    # Replace symlink with a real file.
    (project / "CLAUDE.md").unlink()
    (project / "CLAUDE.md").write_text("user authored\n")

    result = runner.invoke(main, ["instructions", "doctor", "--scope", "project"])
    assert result.exit_code != 0
    assert "conflict" in result.output.lower()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_cli/test_instructions_cli.py -v -k doctor
```

Expected: failures.

- [ ] **Step 3: Implement the doctor verb**

```python
# src/agent_toolkit_cli/commands/instructions/doctor_cmd.py
"""`instructions doctor` — find conflicting/orphan/stray pointers."""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli import instructions_paths
from agent_toolkit_cli.instructions_adapters import SUPPORTED_HARNESSES
from agent_toolkit_cli.instructions_adapters.symlink import _pointer_path
from agent_toolkit_cli.instructions_lock import read_lock


@click.command(help="Find conflicting/orphan/stray pointers vs the lock.")
@click.option(
    "--scope",
    type=click.Choice(["project", "global"]),
    default="project",
)
@click.pass_context
def doctor_cmd(ctx: click.Context, scope: str) -> None:
    project_root: Path | None = None
    home: Path | None = None
    if scope == "project":
        obj = ctx.find_root().params.get("project_root")
        project_root = obj if obj else Path.cwd()
        canonical = instructions_paths.project_canonical_agents_md(project_root)
    else:
        canonical = instructions_paths.global_canonical_agents_md()

    findings: list[str] = []

    lock_path = instructions_paths.lock_file_path(scope, project_root)
    lock = read_lock(lock_path)
    wanted: set[str] = set()
    for entry in lock.instructions.values():
        wanted.update(h for h in entry.harnesses if h in SUPPORTED_HARNESSES)

    # Orphan: lock says ON but canonical is gone.
    if wanted and not canonical.exists():
        findings.append(f"orphan: canonical AGENTS.md missing at {canonical}")

    # Conflict: lock says ON but pointer is a real file or points elsewhere.
    for harness in sorted(wanted):
        try:
            pointer = _pointer_path(harness, scope, project_root, home)
        except ValueError:
            continue
        if pointer.exists() and not pointer.is_symlink():
            findings.append(
                f"conflict: {harness} pointer at {pointer} is a real file (not ours)"
            )
        elif pointer.is_symlink() and pointer.resolve() != canonical.resolve():
            findings.append(
                f"conflict: {harness} pointer at {pointer} → {pointer.resolve()} (not canonical)"
            )

    # Stray: a pointer-shaped symlink at a harness slot, pointing at canonical,
    # but not recorded in the lock. (Manual mkdir + ln scenario.)
    for harness in sorted(SUPPORTED_HARNESSES - wanted):
        try:
            pointer = _pointer_path(harness, scope, project_root, home)
        except ValueError:
            continue
        if (
            pointer.is_symlink()
            and pointer.resolve() == canonical.resolve()
        ):
            findings.append(
                f"stray: {harness} pointer at {pointer} points at canonical "
                "but isn't recorded in the lock"
            )

    if not findings:
        click.echo("clean — no findings at this scope")
        return
    for f in findings:
        click.echo(f)
    ctx.exit(1)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_cli/test_instructions_cli.py -v -k doctor
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/instructions/doctor_cmd.py tests/test_cli/test_instructions_cli.py
git commit -m "feat(cli): instructions doctor — orphan/conflict/stray findings, non-zero on dirty"
```

---

## Task 14: Full-suite green + PR-prep

**Files:**
- All tests

Final sanity pass + PR.

- [ ] **Step 1: Run the whole suite**

```bash
uv run pytest -q
```

Expected: all tests pass (including Phase A's parity test, both kind matrix tests).

- [ ] **Step 2: Run linter**

```bash
uv run ruff check src/agent_toolkit_cli/instructions* src/agent_toolkit_cli/commands/instructions tests/test_cli/test_instructions*
```

Expected: clean on the new files (pre-existing errors elsewhere on main, if any, are unrelated).

- [ ] **Step 3: Smoke the CLI end-to-end manually**

```bash
cd /tmp && mkdir -p smoke-instructions && cd smoke-instructions
echo "# AGENTS.md\nproject canon" > AGENTS.md
uv run --project /Users/ajanderson/GitHub/projects/agent-toolkit-cli agent-toolkit-cli instructions install --scope project --harness claude-code --harness gemini-cli
ls -la CLAUDE.md GEMINI.md
cat instructions-lock.json
uv run --project /Users/ajanderson/GitHub/projects/agent-toolkit-cli agent-toolkit-cli instructions status --scope project
uv run --project /Users/ajanderson/GitHub/projects/agent-toolkit-cli agent-toolkit-cli instructions doctor --scope project
uv run --project /Users/ajanderson/GitHub/projects/agent-toolkit-cli agent-toolkit-cli instructions uninstall --scope project
ls -la
```

Expected: CLAUDE.md and GEMINI.md created as symlinks → AGENTS.md; status reports `ok`; doctor reports `clean`; uninstall removes pointers.

- [ ] **Step 4: Commit any incidental fixes from Steps 1–3**

```bash
git status
# If any files modified, commit them with a clear message.
```

- [ ] **Step 5: Open PR**

```bash
git push -u origin <branch>
gh pr create --base main --title "v3.0.0: instructions kind — pointer adapter + CLI + lock" --body-file <pr-body>
```

PR body must:
- Reference #269.
- Note the divergences from PR2 (own lock dataclass; project-default scope).
- Call out TUI as out-of-scope (deferred).
- Link Phase A PR (#270) as the contract this implements against.

---

## Self-Review

**Spec coverage check:**

| Spec section | Tasks |
|---|---|
| Mechanism model — `native` is general, only `symlink` is an action | T4 (CELLS table), T5 (matrix parity), T11 (list verb shows verdicts) |
| Data model — own lock with thin entries | T3 |
| Canonical source resolution — project + global | T2 (`project_canonical_agents_md`, `global_canonical_agents_md`) |
| Scope default diverges from skills — project default | T2 (`lock_file_path` requires project_root for project scope); T9/T12/T13 (`--scope project` default) |
| Precondition — canonical must already exist | T6 (`CanonicalMissingError`), T9 (CLI surfaces it) |
| Per-kind "general" set | T11 (list verb shows `native` rows as the general column) |
| Idempotency + no-clobber | T4 (`PointerConflictError`), T6 (idempotent re-apply) |
| CLI surface — install/uninstall/list/status/doctor | T8–T13 |
| TUI | OUT OF SCOPE — noted in header. No TUI exists in v2. |

**Placeholder scan:** No "TBD" / "later" / "appropriate error handling" / "implement later" in the plan. Every code block is full code. Every command is a runnable command with expected output.

**Type consistency:**
- `InstructionsLockEntry` / `InstructionsLockFile` used identically across T3, T6, T7, T9, T10, T12.
- `_pointer_path` signature `(harness, scope, project_root, home)` consistent across T4, T6, T11, T12, T13.
- `Scope = Literal["project", "global"]` consistent across all modules.
- Adapter methods `install` / `uninstall` keyword-only args `(scope, project_root, canonical, home)` consistent in T4, T6, T7.
- `apply()` / `uninstall()` (engine) keyword-only `(scope, project_root, home)` consistent in T6, T7, T9, T10.
- `CELLS[harness]` shape `{"pointer_name": str, "global": str, "project": str}` consistent across T4, T7, T11.

No drift detected.
