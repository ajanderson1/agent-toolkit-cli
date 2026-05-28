---
issue: 252
slice: PR1 of v3.0.0 (kind dimension foundation)
date: 2026-05-28
status: draft
upstream-spec: docs/superpowers/specs/2026-05-27-v3-agents-refold-design.md
---

# v3.0.0 PR1 — kind dimension foundation

**Slice of #252.** First of five PRs that together reintroduce the `agent`
asset kind. This slice lays the architectural foundation — install/paths/lock
factored along a `kind` dimension — but ships **no user-visible behaviour
change**. Subsequent PRs (adapters, rename, CLI, TUI) build on the seams this
PR cuts.

**This spec assumes the three open architecture decisions in the upstream v3
design spec are resolved** (recorded in the cycle's `flow.log`):

| Open decision | Resolution |
|---|---|
| Generalize-in-place vs parallel `agent_*` modules | **Hybrid**: shared kind-agnostic core (`_install_core.py`, `_paths_core.py`, `_lock_core.py`) + thin per-kind facades (`skill_*` keep their names; `agent_*` introduced in PR2). |
| CLI: parallel `agent` verb group vs `--kind` flag | **Parallel `agent` group**. PR1 does **not** introduce any new CLI surface; PR4 does. |
| `general` model: one synthetic entry vs distinct entries | **Distinct `general-skill` / `general-agent`** harness entries. No `kind` field in the lock schema. PR1 adds the `general-skill` entry only (and renames internal helpers to disambiguate); `general-agent` and the `universal`→`general` user-facing rename are PR3. |

## What ships

A refactor with three observable artefacts and zero behaviour change:

1. **`_install_core.py`, `_paths_core.py`, `_lock_core.py`** — kind-agnostic
   implementations of the engine, path resolution, and lockfile IO. These
   contain everything that does not care whether the asset being installed is
   a skill or an agent.

2. **`skill_install.py`, `skill_paths.py`, `skill_lock.py`** — slimmed-down
   facades that bind their core to `kind="skill"`. Same public symbols, same
   docstrings, same exceptions. **All existing call sites are unchanged.**

3. **`general-skill` harness entry in `skill_agents.py`** — a
   `show_in_universal_list=False` synthetic entry that resolves the same
   `.agents/skills/` path the current `universal` synthetic does. Coexists
   with `universal` for this PR. The internal helper
   `_resolve_universal_dir()` is split so future `general-agent` (PR3) and
   the eventual `universal` removal (PR3) can land without touching this
   PR's seams.

The change is a **behaviour-preserving refactor**. The full PR1 acceptance
criterion is: every existing test in `tests/` passes unchanged; no callers
of any `skill_*` module need to be edited; lockfiles written before the PR
remain readable, and lockfiles written after the PR remain readable by the
pre-PR code.

## Why this is its own PR

Two reasons.

**One**, it cuts seams without growing surface area. Every other Phase B PR
needs install/paths/lock to be kind-parameterised. If the seam is wrong, all
four downstream PRs are wrong. Shipping the seam alone keeps the diff small
enough to actually review against the spec.

**Two**, the resolved decision #1 above is the load-bearing one. The Phase B
spec is explicit that this is "the central Phase B architecture decision."
Doing the hybrid factoring in a separate PR forces the architecture to prove
itself against the existing skill test suite before any agent code arrives
to confuse the failure mode.

## Scope (in)

| Change | Where | Notes |
|---|---|---|
| Extract install engine to kind-agnostic core | `src/agent_toolkit_cli/_install_core.py` (new) | Pure functions: planning, symlink creation, lock-mismatch detection. No reference to the string `"skill"` or `"agent"`. |
| Extract path resolution to kind-agnostic core | `src/agent_toolkit_cli/_paths_core.py` (new) | `canonical_dir(kind, ...)`, `lock_file_path(kind, ...)`, `library_root_for_kind(kind, env)`. |
| Extract lockfile IO to kind-agnostic core | `src/agent_toolkit_cli/_lock_core.py` (new) | `read_lock(path, supported_versions=...)`, `write_lock(path, lock)`. **`LockFile.skills` dict retained as-is**; it is keyed by slug, agnostic of kind because there is one lock file per kind (`skills-lock.json`, future `agents-lock.json`). |
| Slim `skill_install.py` to facade | existing file | Public symbols (`InstallError`, `LockMismatchError`, `DirtyCanonicalError`, `InstallPlan`, `InstallResult`, `plan`, `apply`, `install`, `uninstall`, `migrate_project_canonical`, `ensure_project_canonical`) re-exported from the core, bound to `kind="skill"`. |
| Slim `skill_paths.py` to facade | existing file | Same: public symbols (`canonical_skill_dir`, `lock_file_path`, `library_root`, `library_skill_path`, `project_id`, `project_store_root`, `parent_clone_path`, `project_parents_root`, `library_lock_path`, `agent_projection_dir`, `harness_projection_dir`) re-exported. |
| Slim `skill_lock.py` to facade | existing file | `LockEntry`, `LockFile`, `read_lock`, `write_lock`, `add_entry`, `remove_entry`, `clone_url_from_entry`, `SUPPORTED_VERSIONS` re-exported. |
| Add `general-skill` harness entry | `src/agent_toolkit_cli/skill_agents.py` | Mirrors the existing `"universal"` entry (same `skills_dir`, same `show_in_universal_list=False`). Tests added. **`"universal"` remains in place** — its removal is PR3. |
| New unit tests for core dispatch | `tests/test_cli/test_install_core.py`, `test_paths_core.py`, `test_lock_core.py` (new) | Each test instantiates the core with a fake kind, verifies the kind is honoured in path resolution and is not leaked into errors/log messages. |
| New unit test for facade parity | `tests/test_cli/test_skill_facade_parity.py` (new) | Verifies `skill_install`, `skill_paths`, `skill_lock` re-export the same public symbol set as before (snapshot test). |

## Scope (out — deferred to later slices)

| Deferred to | What |
|---|---|
| PR2 | `harness_adapters/` for the 28 supported subagent cells (symlink / translate / config_file+folder / dual-symlink). Parity test ↔ matrix. |
| PR2 | `agent_install.py`, `agent_paths.py`, `agent_lock.py` facades. PR1 ships the core; PR2 ships the agent facade that binds it. |
| PR3 | `universal` → `general` rename. Includes `is_universal`→`is_general`, `get_universal_agents`→`get_general_agents`, `show_in_universal_list`→`show_in_general_list`, removal of the `"universal"` synthetic, addition of `general-agent`, TUI/CLI label updates. |
| PR4 | `agent` command group (`agent-toolkit-cli agent add|install|uninstall|remove|import|list|status|update|push|reset`) + `doctor` learning the agent kind. |
| PR5 | TUI `KindsSidebar` (Skills/Agents, per-kind counts, `1`/`2` hotkeys). |

## Public API contract (what must not break)

Every name in the table below remains callable from outside the module with
the same signature, the same return type, and the same exception types. The
implementations move; the import path does not.

| Module | Names preserved |
|---|---|
| `skill_install` | `InstallError`, `LockMismatchError`, `DirtyCanonicalError`, `InstallPlan`, `InstallResult`, `plan`, `apply`, `install`, `uninstall`, `migrate_project_canonical`, `ensure_project_canonical` |
| `skill_paths` | `canonical_skill_dir`, `lock_file_path`, `library_root`, `library_skill_path`, `project_id`, `project_store_root`, `parent_clone_path`, `project_parents_root`, `library_lock_path`, `agent_projection_dir`, `harness_projection_dir`, `_SHORTCUT_TO_AGENT`, `_root` (the underscored ones are touched by tests, hence preserved) |
| `skill_lock` | `LockEntry`, `LockFile`, `SUPPORTED_VERSIONS`, `read_lock`, `write_lock`, `add_entry`, `remove_entry`, `clone_url_from_entry`, `_apply_insteadof` |

The facade parity test enforces this by `dir()`-snapshotting each module
before/after; any removed symbol is a test failure.

## Internal API design (core surface)

The cores deal in two abstractions: a `KindBinding` value object (carries the
kind name plus the canonical directory name, e.g. `"skills"`/`"agents"`) and
plain functions that take it explicitly. **No global state.** Facades create
one `KindBinding` at module load and pass it into every core call.

```python
# _paths_core.py
@dataclass(frozen=True)
class KindBinding:
    kind: str                  # "skill" | "agent"
    canonical_dirname: str     # "skills" | "agents"
    library_subdir: str        # "_library/skills" | "_library/agents"
    lock_filename: str         # "skills-lock.json" | "agents-lock.json"
    general_harness_name: str  # "general-skill" | "general-agent"

SKILL_BINDING = KindBinding(
    kind="skill",
    canonical_dirname="skills",
    library_subdir="_library/skills",
    lock_filename="skills-lock.json",
    general_harness_name="general-skill",
)
# AGENT_BINDING introduced in PR2.

def canonical_dir(binding: KindBinding, scope: Scope, home: Path | None,
                  project: Path | None) -> Path: ...
def lock_file_path(binding: KindBinding, scope: Scope, ...) -> Path: ...
```

The facade is then trivial:

```python
# skill_paths.py
from ._paths_core import (
    SKILL_BINDING, canonical_dir as _canonical_dir, ...
)

def canonical_skill_dir(scope, home, project) -> Path:
    return _canonical_dir(SKILL_BINDING, scope, home, project)
```

This shape is what makes the hybrid hybrid: the facade is mechanical, the
core is testable in isolation, and **the only thing PR2 has to write to add
agents is `AGENT_BINDING` + an `agent_paths.py` mirror.**

## Test plan

| Layer | Tests |
|---|---|
| Behaviour preservation | The entire existing `tests/` suite passes unchanged. This is the load-bearing criterion. |
| Core dispatch | New `tests/test_cli/test_paths_core.py` constructs a `KindBinding(kind="x", canonical_dirname="x", ...)` and asserts `canonical_dir` resolves to the right path. Symmetric tests for `_install_core` and `_lock_core`. |
| Facade parity | New `tests/test_cli/test_skill_facade_parity.py` snapshot-tests the public-symbol set of `skill_install`, `skill_paths`, `skill_lock`. Failure means a name escaped during the refactor. |
| `general-skill` entry | New test in `tests/test_cli/test_skill_agents.py` asserts `AGENTS["general-skill"].skills_dir == ".agents/skills"` and `show_in_universal_list is False`. Asserts `"universal"` still resolves to the same directory (coexistence). |
| Lock round-trip | New `tests/test_cli/test_lock_core.py` writes a lock via the core, reads it back via the facade, and asserts equality. Repeated for v1 and v3 schemas. |

## Migration & compatibility

- **Lockfiles:** schema is unchanged. v1 and v3 lockfiles written before the
  PR remain readable. Lockfiles written after the PR remain readable by the
  pre-PR code, because no fields are added or removed.
- **Library layout on disk:** unchanged. `~/.agent-toolkit/skills/` keeps the
  same path; `_library/skills` keeps the same path. `_library/agents` is
  defined in `AGENT_BINDING` (PR2) but not created on disk by PR1.
- **`general-skill` vs `universal`:** both resolve to `.agents/skills/`. They
  are duplicates by design for one PR. The `universal` synthetic is the one
  removed in PR3, after the rename lands.
- **Import-path stability:** every existing `from agent_toolkit_cli.skill_*
  import ...` continues to work.

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| A facade re-export forgets a symbol and a downstream module breaks | Medium | Facade parity test snapshots `dir(module)` before/after. |
| A circular import between core and facade | Low | Core does not import facade. Facade imports core. One-way; lint with `tach` if available. |
| `_install_core.py` ends up doing nothing because `_universal_bundle_link` is skill-specific | Medium | Keep skill-specific helpers in `skill_install.py`. Core takes a `general_harness_name` from the binding so the helper becomes kind-agnostic in PR2. |
| Lock module facade misses `_apply_insteadof` (private but used by tests) | Low | Parity test catches this. |

## Out-of-scope reminders for the reviewer

If the diff contains any of the following, the reviewer should reject and
ask me to split the PR — they belong in later slices, not here:

- Any new CLI verb or `--kind` flag.
- The string `agents-lock.json` materialised on disk (it should appear only
  as a constant in `_paths_core.py`).
- Any rename of `universal`, `is_universal`, `get_universal_agents`, or
  `show_in_universal_list`.
- Any new file under `harness_adapters/`.
- Any TUI change.

## Acceptance criteria

1. `uv run pytest` passes on the worktree branch with **zero modifications**
   to existing tests.
2. `dir(skill_install)`, `dir(skill_paths)`, `dir(skill_lock)` each contain
   every public name listed in "Public API contract" above (enforced by the
   parity test).
3. `AGENTS["general-skill"]` exists; `AGENTS["universal"]` is unchanged.
4. A lockfile written by `skill_lock.write_lock` is byte-identical to one
   written by the pre-refactor `skill_lock.write_lock` for the same input.
   (Snapshot test fixture.)
5. PR-only check: `git diff --stat origin/main...HEAD` shows no edits to
   `src/agent_toolkit_cli/skill_add.py`, `skill_install_cmd.py`,
   `skill_import_cmd.py`, `skill_list_cmd.py`, `skill_status_cmd.py`,
   `skill_push_cmd.py`, `skill_update_cmd.py`, `skill_remove_cmd.py`,
   `doctor.py`, or anything under `src/agent_toolkit_tui/`. Callers do not
   move in PR1.

## After this PR

PR2 begins by writing `AGENT_BINDING`, `agent_install.py`, `agent_paths.py`,
`agent_lock.py` — each ~30-line facade pointing at the core PR1 builds.
That's the test of whether the seam was cut in the right place.
