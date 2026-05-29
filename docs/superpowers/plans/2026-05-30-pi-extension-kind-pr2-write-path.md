# pi-extension Kind — PR2 (Write Path) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Every task ships a failing test FIRST, then the implementation, then a green run, then a commit. No task is "done" until its run-to-pass step is green.

**Goal:** Add the **write path** for the `pi-extension` asset kind on top of PR1's read-only inventory: `add` (global-only clone-into-store / npm-record), `install` / `uninstall` (projection toggle at Pi **global + project**), `remove`, a `settings.json` `packages[]` **writer** (never shells out to `pi`), `import`, `update`, `push`, `reset`, and `doctor`. Two row behaviours per spec §3: **store-owned** (git/https/ssh/local → clone into `~/.agent-toolkit/pi-extensions/<slug>/`, symlink into Pi's `extensions/` dirs) and **registry-tracked** (`npm:<spec>` → toggle a `packages[]` entry, no clone).

**Architecture:** Mirror the skill kind's facade-over-core split. The kind-agnostic projection engine (`_install_core`), lock primitives (`skill_lock`), git ownership (`skill_git`, `skill_ownership`), and source parsing (`skill_source`) are reused **unchanged** — bound to `PI_EXTENSION_BINDING` via a new `pi_extension_install.py` facade. The one genuinely new mutating surface is the `_pi_settings.py` **writer** for `packages[]`. The TUI is explicitly out of scope (issue #273 "Out of scope: TUI toggles").

**Tech Stack:** Python 3.13, click, dataclasses, pytest + monkeypatch + tmp_path, `uv`. Targets installed Pi `@earendil-works/pi-coding-agent@0.77.0`. Test runner: `uv run pytest`. Gates: `uv run ruff check` + `uv run mypy src/agent_toolkit_cli/`.

**Spec:** `docs/superpowers/specs/2026-05-29-pi-extension-kind-design.md` (§3 two behaviours, §6 verbs, §8 error handling, §11 item 3 the one open design question).

**Issue:** #273 (v3.2.0 pi-extension kind — write path PR2).

---

## ⚠️ PRECONDITION — read before starting

**PR1 IS merged on `origin/main`** (PR #286, commit `aff5467 feat: pi-extension kind PR1 — read-only inventory (list/status) (#273)`). It shipped: `PI_EXTENSION_BINDING` in `_paths_core.py`, `piExtensionPath` on the shared `LockEntry` in `skill_lock.py`, and the modules `_pi_settings.py` (reader), `pi_extension_paths.py`, `pi_extension_lock.py`, `pi_extension_inventory.py`, plus the `commands/pi_extension/` group with `list`/`status` verbs.

**Caveat for the builder:** the *local* checkout this plan was authored against was a stale `main` (sitting at release 2.14.2, before #286). If your working tree also lacks the PR1 files, your local `main` is just behind — **do NOT conclude PR1 is unbuilt.** Fetch and branch from the up-to-date `origin/main`. Before executing ANY task here:

- [ ] **Sync and branch from current origin/main:** `git fetch origin && git switch -c feat/273-pi-extension-write-path origin/main`.
- [ ] **Verify PR1 is present in your working tree.** Run:
  `uv run python -c "from agent_toolkit_cli._paths_core import PI_EXTENSION_BINDING; from agent_toolkit_cli.skill_lock import LockEntry; assert LockEntry(source='x',source_type='y').pi_extension_path is None; from agent_toolkit_cli import pi_extension_paths, pi_extension_lock, _pi_settings, pi_extension_inventory; print('PR1 present')"`
  Expected: `PR1 present`. If it raises, your checkout is still stale — re-fetch; do not start patching `_paths_core`/`skill_lock` (PR1 already did).

**Confirmed PR1 API surface this plan builds on (verified by reading commit `aff5467`):**
- `_pi_settings`: `settings_path(*, scope, home=, project=)`, `read_packages(...)`, `read_extension_paths(...)`, `PiSettingsError`, and the private helpers `_load(path)` (returns `{}` if missing; raises `PiSettingsError` on bad JSON / non-dict top-level) and `_string_list(data, key, path)` (returns `[]` for a missing key; raises on present-but-not-`list[str]`). **Task 1's writer reuses `_load`, `_string_list`, `settings_path` verbatim — confirmed they exist with these signatures.**
- `pi_extension_paths`: `library_root`, `library_pi_extension_path(slug, *, env=)`, `library_lock_path(env=)`, `canonical_pi_extension_dir`, `lock_file_path(*, scope, home=, project=)`, `pi_extension_dir(slug, *, scope, home=, project=)`, `Scope`.
- `pi_extension_lock`: re-exports `LockEntry`, `LockFile`, `read_lock`, `write_lock`, `add_entry`, `remove_entry` (the shared `skill_lock` primitives) — `LockEntry.pi_extension_path` field present.
- `pi_extension_inventory.build_inventory(*, home=, project=)` → `list[InventoryRecord(slug, origin, source, global_loaded, project_loaded)]`. **IMPORTANT for Task 7:** in merged PR1, store-owned `global_loaded`/`project_loaded` are set ONLY by `_discover_loose` finding the projected symlink in Pi's `extensions/` dir (the lock pass sets origin/source only, never `loaded`). `_discover_loose` flags a symlinked dir as loaded iff it contains `index.ts`, `index.js`, or `package.json`. See Task 7's builder note.

**Also note (spec §12 / agent-kind divergence):** the spec's §4 references a future `agent_install.py` + `agent_adapters/` as the parity model. **These do not exist on any branch yet** (the `feat/252-v3-pr2-agent-facade-adapters` worktree has no `agent_adapters/` directory). Do **not** import from a non-existent agent facade. The reuse target this plan binds to is the **skill** facade + the **kind-agnostic core** (`_install_core`, `skill_lock`, `skill_git`), both confirmed present on `main`. The "agent kind's AgentProjectionConflictError" the brief references is realised here as the core's existing **conflicting-symlink / conflicting-non-symlink `InstallError`** guards in `skill_install.apply()` (lines 182-221) and `_install_core._symlink_or_copy` (line 53, "refusing to overwrite existing path"). We reuse those, not a non-existent agent class.

---

## Blast radius & safety (READ FIRST)

This PR mutates real user state. Ranked by blast radius:

1. **`settings.json` writer — HIGHEST RISK.** `~/.pi/agent/settings.json` (global) and `<proj>/.pi/settings.json` (project) are the user's **real, hand-maintained Pi config**. A bad write can brick the user's Pi launch or silently drop unrelated config (model keys, MCP entries, hooks, theme). The writer MUST: (a) read-modify-write only the `packages[]` array, preserving every other key byte-for-key; (b) preserve a missing trailing newline / 2-space indent best-effort; (c) **fail loud** on malformed existing JSON rather than overwrite; (d) write atomically (temp + `os.replace`) so a crash never truncates; (e) **never** create a settings.json that didn't exist unless we are genuinely adding the first package (and even then, write `{"packages": [...]}` only). Task 3 is dedicated to this with extra-key-survival round-trip tests. **Never touch the real `~/.pi` in tests — tmp fixtures only** (enforced by `monkeypatch.setenv("HOME", tmp_path)` + explicit `home=`/`project=` params everywhere).

2. **Projection symlinks into `~/.pi/agent/extensions/` and `<proj>/.pi/extensions/`.** A wrong symlink, or clobbering a user-authored extension dir, breaks Pi discovery. Mitigated by the foreign-file guard (Task 4): refuse to overwrite any existing path in `extensions/` that is not already **our** symlink (mirrors `skill_install.apply()` conflicting-symlink/non-symlink guards + `_symlink_or_copy`'s refuse-to-overwrite). Round-trip install→uninstall→assert-gone at BOTH scopes (Tasks 5, 6) is mandatory and non-negotiable — prior v3 PRs shipped broken because this was missing (#283).

3. **Lock honesty (#283 class of bug).** The lock must be written **only after** a successful clone + projection. On any failure mid-operation, roll back partial state and leave the lock untouched. Tasks 4-6 assert "lock NOT written when projection fails" and "lock written only after symlink exists."

Cross-cutting non-negotiables (spec §8, brief):
- **Never call `pi install` / `pi remove`.** npm toggling only edits `packages[]`. All tests run with `pi` absent from PATH (don't invoke it; nothing in this PR shells to `pi`).
- **Scope safety.** Project writes target `<cwd>/.pi/`; global writes target `~/.pi/agent/`. Never cross them.
- **Fail loud.** Malformed settings raises `PiSettingsError`; conflicting projection raises `InstallError` with a `doctor` hint; dirty `remove` raises without `--force`.

---

## Scope decision: split into PR2a + PR2b

PR2 as specced is **too large for one reviewable PR** (9 verbs + a config writer + doctor, each with round-trip + idempotency + guard tests). Proposed split:

| Slice | Verbs | Rationale (one line) |
|---|---|---|
| **PR2a — core write path (THIS PLAN, fully detailed)** | `_pi_settings` writer, `add`, `install`, `uninstall`, `remove` | The minimal end-to-end "own it, project it, toggle it, drop it" loop — the highest-blast-radius surfaces (settings writer + projection round-trip) land and bake first. |
| **PR2b — git lifecycle + adoption + reconciliation (planned at outline depth here, §"PR2b outline")** | `import`, `update`, `push`, `reset`, `doctor` | Pure reuse of the skill facade's already-shipped git verbs bound to the new kind; lower novelty, lower risk, and gated behind PR2a's projection foundation. |

**This plan fully specifies PR2a** (the first shippable slice, Tasks 1-9) and gives PR2b a builder-ready task outline (it is mostly "clone the skill verb command module, swap the binding"). A builder may execute PR2a to a green, mergeable PR with zero further design. PR2b can be promoted to a full task-by-task plan once PR2a merges.

---

## Where the spec §11 item 3 decision plugs in

**§11 item 3** (the `extensions[]` explicit-path classification) is the ONE open design question. It asks: when Pi's `settings.json` carries an `extensions[]` array of explicit local paths, should the inventory/`import` treat those as **tracked `local:<path>` rows** (prior-gen #109) or as **untracked-importable** (spec's stated default)?

- **It does NOT block PR2a.** PR2a's verbs (`add`, `install`, `uninstall`, `remove`, settings writer) operate on **`packages[]`** (npm) and on the **`extensions/` directory symlinks** (store-owned). None of them read or write `extensions[]`. PR2a can ship with zero dependency on the §11 decision.
- **It plugs into PR2b's `import` and `doctor`** — specifically the task that decides how `import` adopts `extensions[]` entries and how `doctor` flags orphaned `extensions[]` entries. See **PR2b outline → Task B3 (`import`)** and the marker `[§11-DECISION POINT]` there.
- **Plan is written to accept either resolution with a one-line edit:** PR2b Task B3 isolates the classification in a single helper `_classify_extensions_entry(path) -> Origin` whose body is the only thing that changes between the two resolutions. The two bodies are both written out in the outline; pick one.

**Plan author's recommended resolution (NOT final — defer to the decision agent):** treat `extensions[]` entries as **untracked-importable** (the spec's default). Reasoning: the owned-store model prefers *adoption into the store* over a parallel "tracked but not owned" path channel; a tracked `local:<path>` row would be a third capability tier (toggle-only, like npm, but pointing at an arbitrary on-disk path the toolkit doesn't own) that adds inventory-state surface for marginal benefit. Untracked-importable keeps exactly two tiers (owned vs not-yet-owned) and lets `import` pull the path into the store, after which it becomes a normal store-owned row. The only case this loses is "user wants Pi to load a path they explicitly do NOT want adopted" — which `doctor` can still surface as an informational untracked row.

---

## File Structure (PR2a)

| File | Responsibility | New/Modify |
|---|---|---|
| `src/agent_toolkit_cli/_pi_settings.py` | add `add_package` / `remove_package` **writer** (preserve-keys, atomic, fail-loud) | Modify |
| `src/agent_toolkit_cli/pi_extension_install.py` | facade over `_install_core`: store-owned projection into Pi's two `extensions/` dirs + foreign-file guard + lock-after-projection | Create |
| `src/agent_toolkit_cli/pi_extension_add.py` | `add` core: classify source, clone-into-store (store-owned) or record npm lock entry; global-only | Create |
| `src/agent_toolkit_cli/commands/pi_extension/__init__.py` | register new verbs on the existing group | Modify |
| `src/agent_toolkit_cli/commands/pi_extension/_common.py` | reuse PR1 `scope_and_roots` (read_only defaults to False for write verbs) | Modify (if needed) |
| `src/agent_toolkit_cli/commands/pi_extension/add_cmd.py` | `add <source>` verb (global-only) | Create |
| `src/agent_toolkit_cli/commands/pi_extension/install_cmd.py` | `install <slug> [-g/-p]` verb | Create |
| `src/agent_toolkit_cli/commands/pi_extension/uninstall_cmd.py` | `uninstall <slug> [-g/-p]` verb | Create |
| `src/agent_toolkit_cli/commands/pi_extension/remove_cmd.py` | `remove <slug>` verb (dirty-guard) | Create |
| `tests/test_cli/test_pi_settings_writer.py` | settings writer: extra-key survival, atomic, fail-loud | Create |
| `tests/test_cli/test_pi_extension_install.py` | projection round-trip BOTH scopes, idempotency, foreign-file guard, lock honesty | Create |
| `tests/test_cli/test_pi_extension_add.py` | add: store-owned clone + npm record, global-only | Create |
| `tests/test_cli/test_cli_pi_extension_write.py` | end-to-end CLI: add→install→uninstall→remove round-trip + npm toggle | Create |

---

## Task 1: `_pi_settings.add_package` / `remove_package` — the SAFE writer (highest blast radius)

This is the single riskiest surface in the whole project. It read-modify-writes the user's real Pi config. The implementation MUST preserve every key it does not own, fail loud on malformed input, and write atomically.

**Files:**
- Modify: `src/agent_toolkit_cli/_pi_settings.py` (append writer fns after the PR1 readers)
- Test: `tests/test_cli/test_pi_settings_writer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli/test_pi_settings_writer.py
import json

import pytest

from agent_toolkit_cli import _pi_settings as ps


def _seed(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2) + "\n")


def _global(home):
    return home / ".pi" / "agent" / "settings.json"


def test_add_package_preserves_all_other_keys(tmp_path):
    p = _global(tmp_path)
    _seed(p, {
        "model": "claude-opus",
        "mcpServers": {"foo": {"command": "x"}},
        "packages": ["npm:existing"],
        "theme": "dark",
    })
    ps.add_package("npm:@scope/new", scope="global", home=tmp_path)
    body = json.loads(p.read_text())
    # Other keys survive byte-for-value.
    assert body["model"] == "claude-opus"
    assert body["mcpServers"] == {"foo": {"command": "x"}}
    assert body["theme"] == "dark"
    # packages gained the new spec, kept the old, order preserved + appended.
    assert body["packages"] == ["npm:existing", "npm:@scope/new"]


def test_add_package_is_idempotent(tmp_path):
    p = _global(tmp_path)
    _seed(p, {"packages": ["npm:foo"]})
    ps.add_package("npm:foo", scope="global", home=tmp_path)
    body = json.loads(p.read_text())
    assert body["packages"] == ["npm:foo"]  # no duplicate


def test_add_package_creates_minimal_file_when_absent(tmp_path):
    # No settings.json at all -> create exactly {"packages": [spec]}.
    ps.add_package("npm:foo", scope="global", home=tmp_path)
    body = json.loads(_global(tmp_path).read_text())
    assert body == {"packages": ["npm:foo"]}


def test_add_package_creates_packages_key_when_other_keys_exist(tmp_path):
    p = _global(tmp_path)
    _seed(p, {"model": "x"})  # no packages key yet
    ps.add_package("npm:foo", scope="global", home=tmp_path)
    body = json.loads(p.read_text())
    assert body["model"] == "x"
    assert body["packages"] == ["npm:foo"]


def test_remove_package_preserves_other_keys(tmp_path):
    p = _global(tmp_path)
    _seed(p, {"model": "x", "packages": ["npm:foo", "npm:bar"]})
    ps.remove_package("npm:foo", scope="global", home=tmp_path)
    body = json.loads(p.read_text())
    assert body["model"] == "x"
    assert body["packages"] == ["npm:bar"]


def test_remove_package_absent_is_noop(tmp_path):
    p = _global(tmp_path)
    _seed(p, {"packages": ["npm:bar"]})
    ps.remove_package("npm:foo", scope="global", home=tmp_path)
    assert json.loads(p.read_text())["packages"] == ["npm:bar"]


def test_remove_package_on_missing_file_is_noop(tmp_path):
    # Nothing to remove, nothing to create.
    ps.remove_package("npm:foo", scope="global", home=tmp_path)
    assert not _global(tmp_path).exists()


def test_add_package_malformed_existing_raises_and_does_not_clobber(tmp_path):
    p = _global(tmp_path)
    p.parent.mkdir(parents=True)
    original = "{ this is not json"
    p.write_text(original)
    with pytest.raises(ps.PiSettingsError):
        ps.add_package("npm:foo", scope="global", home=tmp_path)
    # The bad file is LEFT UNTOUCHED — we never overwrite config we can't parse.
    assert p.read_text() == original


def test_add_package_non_object_top_level_raises(tmp_path):
    p = _global(tmp_path)
    p.parent.mkdir(parents=True)
    p.write_text("[1, 2, 3]")
    with pytest.raises(ps.PiSettingsError):
        ps.add_package("npm:foo", scope="global", home=tmp_path)


def test_add_package_packages_not_list_raises(tmp_path):
    p = _global(tmp_path)
    _seed(p, {"packages": "not-a-list"})
    with pytest.raises(ps.PiSettingsError):
        ps.add_package("npm:foo", scope="global", home=tmp_path)


def test_project_scope_writes_project_file_only(tmp_path):
    proj = tmp_path / "proj"
    ps.add_package("npm:foo", scope="project", project=proj)
    proj_settings = proj / ".pi" / "settings.json"
    assert json.loads(proj_settings.read_text())["packages"] == ["npm:foo"]
    # global file untouched / absent
    assert not (tmp_path / ".pi" / "agent" / "settings.json").exists()


def test_atomic_write_no_partial_temp_left(tmp_path):
    p = _global(tmp_path)
    _seed(p, {"packages": []})
    ps.add_package("npm:foo", scope="global", home=tmp_path)
    # No stray temp sibling left behind.
    siblings = [x.name for x in p.parent.iterdir()]
    assert siblings == ["settings.json"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_pi_settings_writer.py -v`
Expected: FAIL — `AttributeError: module 'agent_toolkit_cli._pi_settings' has no attribute 'add_package'`

- [ ] **Step 3: Implement the writer**

Append to `src/agent_toolkit_cli/_pi_settings.py` (after the PR1 readers). This deliberately reuses the PR1 `_load` (which already raises `PiSettingsError` on malformed JSON and non-dict top-level) and the PR1 `settings_path`. The `_string_list` validator is reused to reject a non-list `packages`.

```python
import os


def _write_atomic(path: Path, data: dict) -> None:
    """Atomically write `data` as 2-space-indented JSON + trailing newline.

    Temp sibling + os.replace so a crash mid-write never truncates the user's
    real Pi config (same posture as skill_lock.write_lock)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2) + "\n"
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def _load_for_write(path: Path) -> dict:
    """Like _load but tuned for the write path: a malformed existing file
    MUST raise (never silently overwrite). _load already raises PiSettingsError
    on bad JSON / non-dict; an absent file returns {} so we can create one."""
    return _load(path)  # PR1 _load: {} if missing, raises on malformed/non-dict


def add_package(
    spec: str, *, scope: Scope,
    home: Path | None = None, project: Path | None = None,
) -> None:
    """Add `spec` to the per-scope settings.json packages[] (idempotent).

    Preserves every other key. Creates the file (and the packages key) only
    when needed. Raises PiSettingsError without touching the file if the
    existing settings.json is unparseable."""
    path = settings_path(scope=scope, home=home, project=project)
    data = _load_for_write(path)
    packages = _string_list(data, "packages", path)  # raises if present & not list[str]
    if spec in packages:
        return
    data["packages"] = [*packages, spec]
    _write_atomic(path, data)


def remove_package(
    spec: str, *, scope: Scope,
    home: Path | None = None, project: Path | None = None,
) -> None:
    """Remove `spec` from packages[]. No-op if absent or file missing.
    Preserves every other key. Raises on malformed existing settings.json."""
    path = settings_path(scope=scope, home=home, project=project)
    if not path.exists():
        return
    data = _load_for_write(path)
    packages = _string_list(data, "packages", path)
    if spec not in packages:
        return
    data["packages"] = [p for p in packages if p != spec]
    _write_atomic(path, data)
```

> NOTE on `_string_list` for an absent key: PR1's `_string_list(data, "packages", path)` returns `[]` when `packages` is missing (it defaults `value = data.get(key, [])`). That is exactly what `add_package`'s "create packages key" path needs. Confirm PR1's `_string_list` signature matches; if PR1 named it differently, adapt the call. The behaviour required: missing → `[]`; present-and-not-list-of-str → raise.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_pi_settings_writer.py -v`
Expected: PASS (12 tests). Also run the PR1 reader tests to confirm no regression: `uv run pytest tests/test_cli/test_pi_settings.py -v`.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/_pi_settings.py tests/test_cli/test_pi_settings_writer.py
git commit -m "feat(pi-extension): add safe settings.json packages[] writer"
```

---

## Task 2: `pi_extension_install.py` facade — store-owned projection (plan + apply)

A thin facade over `_install_core` bound to the Pi extension dirs. Unlike skills, pi-extension has **no per-harness fan-out and no universal bundle** — it projects exactly one symlink per scope into Pi's `extensions/` dir. We therefore do NOT reuse the skill `apply()` (which is agent/symlink-matrix-shaped); we write a small Pi-specific `plan`/`apply` that reuses the core's **guard primitives** and the **lock-after-projection** ordering. This is the load-bearing safety task.

**Files:**
- Create: `src/agent_toolkit_cli/pi_extension_install.py`
- Test: `tests/test_cli/test_pi_extension_install.py` (Steps in Tasks 4-6 below add the round-trip/idempotency/guard cases; this task ships the plan/apply primitives + their unit tests)

- [ ] **Step 1: Write the failing test (plan/apply primitives)**

```python
# tests/test_cli/test_pi_extension_install.py
import json
from pathlib import Path

import pytest

from agent_toolkit_cli import pi_extension_install as pei
from agent_toolkit_cli import pi_extension_paths as pep
from agent_toolkit_cli.pi_extension_lock import LockEntry, read_lock, write_lock, LockFile


def _store_owned(home: Path, slug: str) -> Path:
    """Create a fake store-owned canonical dir + global lock entry."""
    canonical = pep.library_pi_extension_path(slug, env={})
    canonical.mkdir(parents=True)
    (canonical / "index.ts").write_text("export default {}")
    lock_path = pep.library_lock_path(env={})
    lf = read_lock(lock_path)
    lf = LockFile(version=lf.version, skills={
        **lf.skills,
        slug: LockEntry(source="github.com/o/" + slug, source_type="github",
                        pi_extension_path=slug),
    })
    write_lock(lock_path, lf)
    return canonical


def test_plan_install_global_adds(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _store_owned(tmp_path, "ext")
    p = pei.plan(slug="ext", scope="global", action="install", home=tmp_path)
    assert p.create is True
    assert p.remove is False
    assert p.link == pep.pi_extension_dir("ext", scope="global", home=tmp_path)


def test_plan_install_already_linked_is_noop(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    canonical = _store_owned(tmp_path, "ext")
    link = pep.pi_extension_dir("ext", scope="global", home=tmp_path)
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(canonical)
    p = pei.plan(slug="ext", scope="global", action="install", home=tmp_path)
    assert p.create is False and p.remove is False  # idempotent


def test_apply_install_creates_symlink_and_writes_lock_last(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    canonical = _store_owned(tmp_path, "ext")
    p = pei.plan(slug="ext", scope="global", action="install", home=tmp_path)
    pei.apply(p, home=tmp_path)
    link = pep.pi_extension_dir("ext", scope="global", home=tmp_path)
    assert link.is_symlink()
    assert link.resolve() == canonical.resolve()
    # project-scope lock entry tracking the projection is written (global scope:
    # the global library lock already has the store entry; projection state is
    # recorded by presence of the symlink — assert the symlink IS the truth).


def test_apply_install_refuses_foreign_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _store_owned(tmp_path, "ext")
    link = pep.pi_extension_dir("ext", scope="global", home=tmp_path)
    link.parent.mkdir(parents=True, exist_ok=True)
    link.mkdir()  # user-authored real dir squatting the slug
    (link / "index.ts").write_text("user's own ext")
    p = pei.plan(slug="ext", scope="global", action="install", home=tmp_path)
    with pytest.raises(pei.InstallError):
        pei.apply(p, home=tmp_path)
    # The user's dir is left intact.
    assert (link / "index.ts").read_text() == "user's own ext"


def test_apply_install_refuses_foreign_symlink(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _store_owned(tmp_path, "ext")
    other = tmp_path / "somewhere-else"
    other.mkdir()
    link = pep.pi_extension_dir("ext", scope="global", home=tmp_path)
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(other)  # symlink, but not OURS
    p = pei.plan(slug="ext", scope="global", action="install", home=tmp_path)
    with pytest.raises(pei.InstallError):
        pei.apply(p, home=tmp_path)
    assert link.resolve() == other.resolve()  # untouched
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_pi_extension_install.py -v`
Expected: FAIL — `ModuleNotFoundError: agent_toolkit_cli.pi_extension_install`

- [ ] **Step 3: Create the facade**

```python
# src/agent_toolkit_cli/pi_extension_install.py
"""Store-owned projection for the pi-extension kind.

Pi extensions have NO per-harness fan-out and NO universal bundle: a
store-owned extension projects exactly ONE symlink per scope into Pi's
discovery dir (~/.pi/agent/extensions/<slug> global, <proj>/.pi/extensions/<slug>
project). This module reuses the kind-agnostic guard posture from
_install_core (refuse to overwrite a foreign path; write lock only after a
successful projection) without reusing the skill agent-matrix apply().

Registry-tracked (npm) rows are NOT handled here — they go through
_pi_settings.add_package / remove_package. This module is store-owned only.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from agent_toolkit_cli._install_core import InstallError  # reuse the base error + posture
from agent_toolkit_cli.pi_extension_paths import (
    Scope,
    canonical_pi_extension_dir,
    library_pi_extension_path,
    pi_extension_dir,
)

Action = Literal["install", "uninstall"]


def _doctor_hint(slug: str, scope: Scope) -> str:
    flag = "-g" if scope == "global" else "-p"
    return (
        f"\n  Run: agent-toolkit-cli pi-extension doctor {flag}"
        f"  (clears stray symlinks)"
    )


@dataclass(frozen=True)
class ProjectionPlan:
    slug: str
    scope: Scope
    action: Action
    link: Path          # where Pi discovers it
    canonical: Path     # the store copy
    create: bool        # apply should create the symlink
    remove: bool        # apply should remove the symlink

    def is_noop(self) -> bool:
        return not self.create and not self.remove


def _canonical_for(slug: str, scope: Scope, home: Path | None, project: Path | None) -> Path:
    # Global store-owned canonical lives in the global library regardless of the
    # PROJECTION scope: project-scope install symlinks <proj>/.pi/extensions/<slug>
    # at the SAME global store copy (add is global-only; project install reuses it).
    return library_pi_extension_path(slug)


def plan(
    *, slug: str, scope: Scope, action: Action,
    home: Path | None = None, project: Path | None = None,
) -> ProjectionPlan:
    link = pi_extension_dir(slug, scope=scope, home=home, project=project)
    canonical = _canonical_for(slug, scope, home, project)
    already_ours = (
        link.is_symlink()
        and link.exists()
        and link.resolve() == canonical.resolve()
    )
    if action == "install":
        return ProjectionPlan(
            slug=slug, scope=scope, action=action, link=link, canonical=canonical,
            create=not already_ours, remove=False,
        )
    # uninstall
    return ProjectionPlan(
        slug=slug, scope=scope, action=action, link=link, canonical=canonical,
        create=False, remove=already_ours,
    )


def apply(plan: ProjectionPlan, *, home: Path | None = None, project: Path | None = None) -> None:
    """Realise the projection. Foreign-file guard + lock-after-projection.

    create:  refuse if a non-ours path squats the link; else symlink.
    remove:  only unlink if it is OUR symlink (plan.remove already gated that).
    """
    link = plan.link
    canonical = plan.canonical

    if plan.create:
        if not canonical.exists():
            raise InstallError(
                f"{plan.slug}: store copy missing at {canonical}; "
                f"run `pi-extension add` first"
            )
        link.parent.mkdir(parents=True, exist_ok=True)
        if link.is_symlink():
            if link.resolve() != canonical.resolve():
                raise InstallError(
                    f"{plan.slug}: conflicting symlink at {link}: points to "
                    f"{link.resolve()}, expected {canonical}"
                    + _doctor_hint(plan.slug, plan.scope)
                )
            # already ours — idempotent, nothing to do
        elif link.exists():
            raise InstallError(
                f"{plan.slug}: conflicting non-symlink at {link}; refusing to "
                f"overwrite a user-authored extension"
                + _doctor_hint(plan.slug, plan.scope)
            )
        else:
            link.symlink_to(canonical, target_is_directory=True)

    if plan.remove:
        if link.is_symlink():
            link.unlink()
        elif link.exists():
            raise InstallError(
                f"{plan.slug}: cannot uninstall {link}: not a symlink "
                f"(user-authored?); refusing to delete"
            )
        # absent → already uninstalled, no-op
```

> **Lock honesty note for the CLI verbs (Tasks 5/6):** `apply()` here mutates ONLY the symlink, never the lock. The CLI `install_cmd`/`uninstall_cmd` call `apply()` FIRST and only on success record/clear projection state. For PR2a the **symlink presence IS the projection truth** at global scope (the global library lock already carries the store entry from `add`). At **project** scope the install verb writes a project lock entry (`<proj>/pi-extensions-lock.json`) AFTER `apply()` succeeds and removes it AFTER a successful uninstall — see Task 5/6. This ordering is the #283 fix: never write the lock before the projection exists.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_pi_extension_install.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/pi_extension_install.py tests/test_cli/test_pi_extension_install.py
git commit -m "feat(pi-extension): store-owned projection facade with foreign-file guard"
```

---

## Task 3: `pi_extension_add.py` — `add` core (store-owned clone / npm record), global-only

`add` is global-only by construction (spec §6, same as `skill add`). Store-owned sources clone into the global library + record a store-owned lock entry (`pi_extension_path=slug`). npm sources record a registry-tracked lock entry (no clone) — `source="npm:<spec>"`, `source_type="npm"`, no `pi_extension_path`.

**Files:**
- Create: `src/agent_toolkit_cli/pi_extension_add.py`
- Test: `tests/test_cli/test_pi_extension_add.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli/test_pi_extension_add.py
import json
from pathlib import Path

import pytest

from agent_toolkit_cli import pi_extension_add as pea
from agent_toolkit_cli import pi_extension_paths as pep
from agent_toolkit_cli.pi_extension_lock import read_lock


def test_add_npm_records_registry_entry_no_clone(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    pea.add(source="npm:@scope/rpiv-i18n", slug=None, env={})
    lock = read_lock(pep.library_lock_path(env={}))
    entry = lock.skills["@scope/rpiv-i18n"]
    assert entry.source == "npm:@scope/rpiv-i18n"
    assert entry.source_type == "npm"
    assert entry.pi_extension_path is None  # not stored
    # No store dir created.
    assert not pep.library_pi_extension_path("@scope/rpiv-i18n", env={}).exists()


def test_add_store_owned_clones_and_records(tmp_path, monkeypatch, git_sandbox):
    monkeypatch.setenv("HOME", str(tmp_path))
    # git_sandbox.upstream is a bare repo with SKILL.md seeded; reuse as a
    # generic git source. Add as a store-owned extension named "demo".
    pea.add(source=str(git_sandbox.upstream), slug="demo", env=git_sandbox.env)
    canonical = pep.library_pi_extension_path("demo", env={})
    assert canonical.exists()
    lock = read_lock(pep.library_lock_path(env={}))
    entry = lock.skills["demo"]
    assert entry.source_type != "npm"
    assert entry.pi_extension_path == "demo"


def test_add_lock_written_only_after_clone(tmp_path, monkeypatch):
    # A clone failure (bad source) must NOT leave a lock entry behind (#283).
    monkeypatch.setenv("HOME", str(tmp_path))
    with pytest.raises(Exception):
        pea.add(source="git:does-not-exist-xyz", slug="ghost", env={})
    lock = read_lock(pep.library_lock_path(env={}))
    assert "ghost" not in lock.skills


def test_add_npm_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    pea.add(source="npm:foo", slug=None, env={})
    pea.add(source="npm:foo", slug=None, env={})
    lock = read_lock(pep.library_lock_path(env={}))
    assert list(lock.skills) == ["foo"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_pi_extension_add.py -v`
Expected: FAIL — `ModuleNotFoundError: agent_toolkit_cli.pi_extension_add`

- [ ] **Step 3: Create the add core**

```python
# src/agent_toolkit_cli/pi_extension_add.py
"""`pi-extension add <source>` core: global-only.

Source classification (spec §3):
  npm:<spec>            -> registry-tracked: record a lock entry, NO clone.
  git:/https/ssh/local  -> store-owned: clone into the global library, record
                           a lock entry with pi_extension_path=<slug>.

Mirrors skill_add's global-only posture. Lock is written ONLY after a
successful clone (store-owned) — never before (#283)."""
from __future__ import annotations

from pathlib import Path

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.pi_extension_lock import (
    LockEntry, add_entry, read_lock, write_lock,
)
from agent_toolkit_cli.pi_extension_paths import library_lock_path, library_pi_extension_path
from agent_toolkit_cli.skill_source import parse_source  # reuse the source parser


class AddError(RuntimeError):
    """pi-extension add failed."""


def _npm_slug(spec: str) -> str:
    # "npm:@scope/name" -> "@scope/name"
    return spec.split(":", 1)[1]


def add(*, source: str, slug: str | None, env: dict[str, str] | None = None) -> str:
    """Add a Pi extension to the global library. Returns the slug."""
    lock_path = library_lock_path(env={})

    if source.startswith("npm:"):
        ext_slug = slug or _npm_slug(source)
        lock = read_lock(lock_path)
        if ext_slug in lock.skills and lock.skills[ext_slug].source == source:
            return ext_slug  # idempotent
        entry = LockEntry(source=source, source_type="npm")
        write_lock(lock_path, add_entry(lock, ext_slug, entry))
        return ext_slug

    # Store-owned: parse + clone into the library, THEN write the lock.
    parsed = parse_source(source)  # ParsedSource: .url, .type, .owner_repo, .ref, .slug
    ext_slug = slug or parsed.slug
    canonical = library_pi_extension_path(ext_slug, env={})
    if canonical.exists():
        # Already present — verify source matches, else refuse (mirror skill add).
        lock = read_lock(lock_path)
        existing = lock.skills.get(ext_slug)
        requested = parsed.owner_repo or parsed.url
        if existing is not None and existing.source != requested:
            raise AddError(
                f"{ext_slug}: library already has a different source "
                f"({existing.source!r}); run `pi-extension remove {ext_slug}` first"
            )
        return ext_slug

    canonical.parent.mkdir(parents=True, exist_ok=True)
    skill_git.clone(parsed.url, canonical, ref=parsed.ref, env=env)  # may raise -> no lock write

    # Clone succeeded -> safe to record the lock entry.
    if skill_git.is_git_repo(canonical):
        upstream_sha = skill_git.remote_head_sha(canonical, ref=parsed.ref or "main", env=env)
        local_sha = skill_git.head_sha(canonical, env=env)
    else:
        upstream_sha = local_sha = None
    lock = read_lock(lock_path)
    entry = LockEntry(
        source=parsed.owner_repo or parsed.url,
        source_type=parsed.type,
        ref=parsed.ref,
        pi_extension_path=ext_slug,
        upstream_sha=upstream_sha,
        local_sha=local_sha,
    )
    write_lock(lock_path, add_entry(lock, ext_slug, entry))
    return ext_slug
```

> **Builder note:** verify `skill_source.parse_source` exists with fields `.url/.type/.owner_repo/.ref/.slug`. If the parser's public function or field names differ on `main`, adapt the call — the contract needed is: "given a git/https/ssh/local source string, return a clonable url, a source_type string, an owner/repo (or None), an optional ref, and a default slug." If `parse_source` cannot derive a slug for local paths, require `--slug` for local sources (raise `AddError` asking for it).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_pi_extension_add.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/pi_extension_add.py tests/test_cli/test_pi_extension_add.py
git commit -m "feat(pi-extension): add core (store-owned clone / npm record, global-only)"
```

---

## Task 4: `add_cmd` verb + foreign-file guard E2E

Wire the `add` core to a CLI verb on the existing PR1 group. Global-only: no `-p` flag (mirror `skill add`).

**Files:**
- Create: `src/agent_toolkit_cli/commands/pi_extension/add_cmd.py`
- Modify: `src/agent_toolkit_cli/commands/pi_extension/__init__.py` (register `add_cmd`)
- Test: `tests/test_cli/test_cli_pi_extension_write.py` (first cases)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli/test_cli_pi_extension_write.py
import json
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from agent_toolkit_cli import pi_extension_paths as pep
from agent_toolkit_cli.pi_extension_lock import read_lock


def test_add_npm_via_cli(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    r = CliRunner().invoke(main, ["pi-extension", "add", "npm:@scope/foo"])
    assert r.exit_code == 0, r.output
    lock = read_lock(pep.library_lock_path(env={}))
    assert lock.skills["@scope/foo"].source_type == "npm"


def test_add_has_no_project_flag(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    r = CliRunner().invoke(main, ["pi-extension", "add", "npm:x", "-p"])
    assert r.exit_code != 0  # global-only: -p is not a valid option
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_cli/test_cli_pi_extension_write.py -v`
Expected: FAIL — `No such command 'add'` (or option/exit mismatch).

- [ ] **Step 3: Create `add_cmd.py`**

```python
# src/agent_toolkit_cli/commands/pi_extension/add_cmd.py
"""`pi-extension add <source>` — global-only (mirror `skill add`)."""
from __future__ import annotations

import click

from agent_toolkit_cli import pi_extension_add


@click.command("add")
@click.argument("source")
@click.option("--slug", default=None, help="Override the derived slug.")
def add_cmd(source: str, slug: str | None) -> None:
    """Add a Pi extension to the global library (clone or npm record)."""
    try:
        ext_slug = pi_extension_add.add(source=source, slug=slug, env=None)
    except (pi_extension_add.AddError, Exception) as exc:  # noqa: BLE001 fail loud
        raise click.ClickException(str(exc)) from exc
    click.echo(f"added {ext_slug}")
```

> Tighten the `except` to the concrete error types once you confirm what `skill_git.clone` raises (likely `skill_git.GitError`); the brief mandates fail-loud, so surface the message via `ClickException` (non-zero exit), do not swallow.

- [ ] **Step 4: Register in `__init__.py`**

Add to `src/agent_toolkit_cli/commands/pi_extension/__init__.py`:

```python
from agent_toolkit_cli.commands.pi_extension.add_cmd import add_cmd
...
pi_extension.add_command(add_cmd)
```

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/test_cli/test_cli_pi_extension_write.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/commands/pi_extension/ tests/test_cli/test_cli_pi_extension_write.py
git commit -m "feat(pi-extension): add CLI verb (global-only)"
```

---

## Task 5: `install` / `uninstall` verbs — projection toggle, BOTH scopes, round-trip (MANDATORY)

This is the mandatory install→uninstall→assert-gone round-trip at **both** Pi scopes, plus idempotency and the npm-toggle path. **Do not skip any assertion here** — this is the exact gap that shipped broken in prior v3 PRs.

**Files:**
- Create: `src/agent_toolkit_cli/commands/pi_extension/install_cmd.py`
- Create: `src/agent_toolkit_cli/commands/pi_extension/uninstall_cmd.py`
- Modify: `src/agent_toolkit_cli/commands/pi_extension/__init__.py`
- Test: `tests/test_cli/test_cli_pi_extension_write.py` (extend)

- [ ] **Step 1: Write the failing tests (append)**

```python
import pytest
from agent_toolkit_cli import _pi_settings


def _add_store_owned(tmp_path, env, upstream):
    """Add a store-owned ext named 'demo' to the global library via CLI."""
    r = CliRunner().invoke(main, ["pi-extension", "add", str(upstream), "--slug", "demo"])
    assert r.exit_code == 0, r.output


# ---- store-owned projection round-trip at GLOBAL scope ----

def test_store_owned_install_uninstall_global_round_trip(tmp_path, monkeypatch, git_sandbox):
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path))  # keep HOME as tmp, not fake-home
    _add_store_owned(tmp_path, git_sandbox.env, git_sandbox.upstream)

    link = pep.pi_extension_dir("demo", scope="global", home=tmp_path)
    canonical = pep.library_pi_extension_path("demo", env={})

    r = CliRunner().invoke(main, ["pi-extension", "install", "demo", "-g"])
    assert r.exit_code == 0, r.output
    assert link.is_symlink() and link.resolve() == canonical.resolve()

    r = CliRunner().invoke(main, ["pi-extension", "uninstall", "demo", "-g"])
    assert r.exit_code == 0, r.output
    assert not link.exists() and not link.is_symlink()   # ASSERT GONE
    assert canonical.exists()                            # store copy preserved


# ---- store-owned projection round-trip at PROJECT scope ----

def test_store_owned_install_uninstall_project_round_trip(tmp_path, monkeypatch, git_sandbox):
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path))
    _add_store_owned(tmp_path, git_sandbox.env, git_sandbox.upstream)

    proj = tmp_path / "proj"
    proj.mkdir()
    link = pep.pi_extension_dir("demo", scope="project", project=proj)
    canonical = pep.library_pi_extension_path("demo", env={})

    r = CliRunner().invoke(main, ["pi-extension", "install", "demo", "-p"],
                           obj={"project_root": proj})
    assert r.exit_code == 0, r.output
    assert link.is_symlink() and link.resolve() == canonical.resolve()
    # project lock entry written AFTER projection
    proj_lock = read_lock(proj / "pi-extensions-lock.json")
    assert "demo" in proj_lock.skills

    r = CliRunner().invoke(main, ["pi-extension", "uninstall", "demo", "-p"],
                           obj={"project_root": proj})
    assert r.exit_code == 0, r.output
    assert not link.exists() and not link.is_symlink()   # ASSERT GONE
    assert canonical.exists()                            # global store preserved
    proj_lock = read_lock(proj / "pi-extensions-lock.json")
    assert "demo" not in proj_lock.skills                # lock entry cleared


# ---- idempotency ----

def test_double_install_is_idempotent(tmp_path, monkeypatch, git_sandbox):
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path))
    _add_store_owned(tmp_path, git_sandbox.env, git_sandbox.upstream)
    r1 = CliRunner().invoke(main, ["pi-extension", "install", "demo", "-g"])
    r2 = CliRunner().invoke(main, ["pi-extension", "install", "demo", "-g"])
    assert r1.exit_code == 0 and r2.exit_code == 0, (r1.output, r2.output)
    link = pep.pi_extension_dir("demo", scope="global", home=tmp_path)
    assert link.is_symlink()


def test_double_uninstall_is_safe(tmp_path, monkeypatch, git_sandbox):
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path))
    _add_store_owned(tmp_path, git_sandbox.env, git_sandbox.upstream)
    CliRunner().invoke(main, ["pi-extension", "install", "demo", "-g"])
    r1 = CliRunner().invoke(main, ["pi-extension", "uninstall", "demo", "-g"])
    r2 = CliRunner().invoke(main, ["pi-extension", "uninstall", "demo", "-g"])
    assert r1.exit_code == 0 and r2.exit_code == 0, (r1.output, r2.output)


# ---- npm toggle round-trip (settings.json packages[]) ----

def test_npm_install_uninstall_global_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    CliRunner().invoke(main, ["pi-extension", "add", "npm:@scope/foo"])

    r = CliRunner().invoke(main, ["pi-extension", "install", "@scope/foo", "-g"])
    assert r.exit_code == 0, r.output
    assert "npm:@scope/foo" in _pi_settings.read_packages(scope="global", home=tmp_path)

    r = CliRunner().invoke(main, ["pi-extension", "uninstall", "@scope/foo", "-g"])
    assert r.exit_code == 0, r.output
    assert "npm:@scope/foo" not in _pi_settings.read_packages(scope="global", home=tmp_path)


def test_npm_install_project_scope(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    CliRunner().invoke(main, ["pi-extension", "add", "npm:bar"])
    proj = tmp_path / "proj"; proj.mkdir()
    r = CliRunner().invoke(main, ["pi-extension", "install", "bar", "-p"],
                           obj={"project_root": proj})
    assert r.exit_code == 0, r.output
    assert "npm:bar" in _pi_settings.read_packages(scope="project", project=proj)
    # global settings untouched
    assert "npm:bar" not in _pi_settings.read_packages(scope="global", home=tmp_path)


# ---- foreign-file guard at the CLI boundary ----

def test_install_refuses_foreign_dir_at_cli(tmp_path, monkeypatch, git_sandbox):
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path))
    _add_store_owned(tmp_path, git_sandbox.env, git_sandbox.upstream)
    link = pep.pi_extension_dir("demo", scope="global", home=tmp_path)
    link.parent.mkdir(parents=True, exist_ok=True)
    link.mkdir()
    (link / "index.ts").write_text("user ext")
    r = CliRunner().invoke(main, ["pi-extension", "install", "demo", "-g"])
    assert r.exit_code != 0
    assert "doctor" in r.output.lower() or "conflict" in r.output.lower()
    assert (link / "index.ts").read_text() == "user ext"  # untouched
```

> **Builder note on `obj={"project_root": proj}`:** PR1's `_common.scope_and_roots` reads `ctx.obj.get("project_root")`. The PR1 list/status tests rely on cwd; for write verbs we pass an explicit project root via the click context `obj` so tests don't `chdir`. Confirm the group's `@click.pass_context` plumbs `ctx.obj`. If PR1 instead derives project from `Path.cwd()`, use `monkeypatch.chdir(proj)` in the project-scope tests and drop the `obj=` kwarg. Match whatever PR1 shipped.

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_cli/test_cli_pi_extension_write.py -v`
Expected: FAIL — `No such command 'install'`.

- [ ] **Step 3: Create `install_cmd.py`**

```python
# src/agent_toolkit_cli/commands/pi_extension/install_cmd.py
"""`pi-extension install <slug> [-g/-p]` — toggle a projection ON.

store-owned -> symlink into Pi's extensions/ dir (lock-after-projection).
npm         -> add the spec to settings.json packages[] (no symlink).
"""
from __future__ import annotations

import click

from agent_toolkit_cli import _pi_settings, pi_extension_install
from agent_toolkit_cli.commands.pi_extension._common import scope_and_roots
from agent_toolkit_cli.pi_extension_lock import (
    LockEntry, add_entry, read_lock, write_lock,
)
from agent_toolkit_cli.pi_extension_paths import library_lock_path, lock_file_path


@click.command("install")
@click.argument("slug")
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.pass_context
def install_cmd(ctx, slug, global_, project_flag):
    """Project a Pi extension into the chosen scope."""
    scope, home, project = scope_and_roots(
        global_, project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
    )
    glob_lock = read_lock(library_lock_path(env={}))
    entry = glob_lock.skills.get(slug)
    if entry is None:
        raise click.ClickException(
            f"{slug}: not in the global library; run `pi-extension add` first"
        )

    if entry.source_type == "npm":
        _pi_settings.add_package(entry.source, scope=scope, home=home, project=project)
        click.echo(f"installed {slug} (npm) [{scope}]")
        return

    # store-owned: project the symlink FIRST, then record project lock state.
    p = pi_extension_install.plan(slug=slug, scope=scope, action="install",
                                  home=home, project=project)
    try:
        pi_extension_install.apply(p, home=home, project=project)
    except pi_extension_install.InstallError as exc:
        raise click.ClickException(str(exc)) from exc

    if scope == "project" and project is not None:
        proj_lock_path = lock_file_path(scope="project", project=project)
        proj_lock = read_lock(proj_lock_path)
        if slug not in proj_lock.skills:
            write_lock(proj_lock_path, add_entry(proj_lock, slug, LockEntry(
                source=entry.source, source_type=entry.source_type,
                ref=entry.ref, pi_extension_path=entry.pi_extension_path,
            )))
    click.echo(f"installed {slug} [{scope}]")
```

- [ ] **Step 4: Create `uninstall_cmd.py`**

```python
# src/agent_toolkit_cli/commands/pi_extension/uninstall_cmd.py
"""`pi-extension uninstall <slug> [-g/-p]` — toggle a projection OFF.
Keeps the store copy (and the global library lock entry). npm -> drop the
packages[] entry."""
from __future__ import annotations

import click

from agent_toolkit_cli import _pi_settings, pi_extension_install
from agent_toolkit_cli.commands.pi_extension._common import scope_and_roots
from agent_toolkit_cli.pi_extension_lock import read_lock, remove_entry, write_lock
from agent_toolkit_cli.pi_extension_paths import library_lock_path, lock_file_path


@click.command("uninstall")
@click.argument("slug")
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.pass_context
def uninstall_cmd(ctx, slug, global_, project_flag):
    """Remove a Pi extension's projection from the chosen scope."""
    scope, home, project = scope_and_roots(
        global_, project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
    )
    glob_lock = read_lock(library_lock_path(env={}))
    entry = glob_lock.skills.get(slug)

    if entry is not None and entry.source_type == "npm":
        _pi_settings.remove_package(entry.source, scope=scope, home=home, project=project)
        click.echo(f"uninstalled {slug} (npm) [{scope}]")
        return

    p = pi_extension_install.plan(slug=slug, scope=scope, action="uninstall",
                                  home=home, project=project)
    try:
        pi_extension_install.apply(p, home=home, project=project)
    except pi_extension_install.InstallError as exc:
        raise click.ClickException(str(exc)) from exc

    if scope == "project" and project is not None:
        proj_lock_path = lock_file_path(scope="project", project=project)
        proj_lock = read_lock(proj_lock_path)
        if slug in proj_lock.skills:
            write_lock(proj_lock_path, remove_entry(proj_lock, slug))
    click.echo(f"uninstalled {slug} [{scope}]")
```

- [ ] **Step 5: Register both in `__init__.py`**

```python
from agent_toolkit_cli.commands.pi_extension.install_cmd import install_cmd
from agent_toolkit_cli.commands.pi_extension.uninstall_cmd import uninstall_cmd
...
pi_extension.add_command(install_cmd)
pi_extension.add_command(uninstall_cmd)
```

- [ ] **Step 6: Run to verify they pass**

Run: `uv run pytest tests/test_cli/test_cli_pi_extension_write.py -v`
Expected: PASS (all round-trip + idempotency + npm + guard cases).

- [ ] **Step 7: Commit**

```bash
git add src/agent_toolkit_cli/commands/pi_extension/ tests/test_cli/test_cli_pi_extension_write.py
git commit -m "feat(pi-extension): install/uninstall projection toggle (both scopes, round-trip)"
```

---

## Task 6: `remove` verb — drop store copy + lock entry, dirty-guard

`remove` deletes the global store copy and its lock entry (spec §6), but refuses if the store copy has uncommitted edits unless `--force` (mirror skill `remove`). It must also refuse / warn if the extension is still projected somewhere (a stray symlink would dangle).

**Files:**
- Create: `src/agent_toolkit_cli/commands/pi_extension/remove_cmd.py`
- Modify: `src/agent_toolkit_cli/commands/pi_extension/__init__.py`
- Test: `tests/test_cli/test_cli_pi_extension_write.py` (extend)

- [ ] **Step 1: Write the failing tests (append)**

```python
import shutil


def test_remove_drops_store_and_lock(tmp_path, monkeypatch, git_sandbox):
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path))
    _add_store_owned(tmp_path, git_sandbox.env, git_sandbox.upstream)
    canonical = pep.library_pi_extension_path("demo", env={})
    assert canonical.exists()

    r = CliRunner().invoke(main, ["pi-extension", "remove", "demo"])
    assert r.exit_code == 0, r.output
    assert not canonical.exists()
    lock = read_lock(pep.library_lock_path(env={}))
    assert "demo" not in lock.skills


def test_remove_npm_drops_lock_no_store(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    CliRunner().invoke(main, ["pi-extension", "add", "npm:foo"])
    r = CliRunner().invoke(main, ["pi-extension", "remove", "foo"])
    assert r.exit_code == 0, r.output
    assert "foo" not in read_lock(pep.library_lock_path(env={})).skills


def test_remove_dirty_store_refused_without_force(tmp_path, monkeypatch, git_sandbox):
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path))
    _add_store_owned(tmp_path, git_sandbox.env, git_sandbox.upstream)
    canonical = pep.library_pi_extension_path("demo", env={})
    (canonical / "DIRTY.txt").write_text("uncommitted")
    r = CliRunner().invoke(main, ["pi-extension", "remove", "demo"])
    assert r.exit_code != 0
    assert canonical.exists()  # not deleted
    # --force overrides
    r2 = CliRunner().invoke(main, ["pi-extension", "remove", "demo", "--force"])
    assert r2.exit_code == 0, r2.output
    assert not canonical.exists()


def test_remove_unknown_slug_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    r = CliRunner().invoke(main, ["pi-extension", "remove", "nope"])
    assert r.exit_code != 0
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_cli/test_cli_pi_extension_write.py -k remove -v`
Expected: FAIL — `No such command 'remove'`.

- [ ] **Step 3: Create `remove_cmd.py`**

```python
# src/agent_toolkit_cli/commands/pi_extension/remove_cmd.py
"""`pi-extension remove <slug>` — drop the store copy + global lock entry.
Dirty-guard: refuse if the store copy has uncommitted git changes unless
--force. npm rows: just drop the lock entry (nothing stored)."""
from __future__ import annotations

import shutil

import click

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.pi_extension_lock import read_lock, remove_entry, write_lock
from agent_toolkit_cli.pi_extension_paths import library_lock_path, library_pi_extension_path


@click.command("remove")
@click.argument("slug")
@click.option("--force", is_flag=True, help="Remove even if the store copy is dirty.")
def remove_cmd(slug: str, force: bool) -> None:
    """Remove a Pi extension from the global library."""
    lock_path = library_lock_path(env={})
    lock = read_lock(lock_path)
    entry = lock.skills.get(slug)
    if entry is None:
        raise click.ClickException(f"{slug}: not in the global library")

    if entry.source_type != "npm":
        canonical = library_pi_extension_path(slug, env={})
        if canonical.exists() and skill_git.is_git_repo(canonical):
            if skill_git.is_dirty(canonical) and not force:
                raise click.ClickException(
                    f"{slug}: store copy has uncommitted changes; "
                    f"push/commit them or re-run with --force"
                )
        if canonical.exists():
            shutil.rmtree(canonical)

    write_lock(lock_path, remove_entry(lock, slug))
    click.echo(f"removed {slug}")
```

> **Builder note:** confirm `skill_git.is_dirty` exists (the skill `remove`/`doctor` path uses a dirty check — find its exact name in `skill_git.py`; it may be `is_dirty`, `has_uncommitted_changes`, or similar). If the helper name differs, use it. Do NOT add a new git-dirty implementation — reuse the existing one.

- [ ] **Step 4: Register in `__init__.py`**

```python
from agent_toolkit_cli.commands.pi_extension.remove_cmd import remove_cmd
...
pi_extension.add_command(remove_cmd)
```

- [ ] **Step 5: Run to verify they pass**

Run: `uv run pytest tests/test_cli/test_cli_pi_extension_write.py -v`
Expected: PASS (all write-path cases).

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/commands/pi_extension/ tests/test_cli/test_cli_pi_extension_write.py
git commit -m "feat(pi-extension): remove verb with dirty-guard"
```

---

## Task 7: End-to-end happy-path round-trip + inventory reflects state

A single integration test that walks the full PR2a loop and confirms PR1's `list`/`status` reflects the new state. This catches integration drift between the write verbs and the read inventory.

**Files:**
- Test: `tests/test_cli/test_cli_pi_extension_write.py` (extend)

- [ ] **Step 1: Write the failing test (append)**

```python
def test_full_loop_store_owned_then_inventory(tmp_path, monkeypatch, git_sandbox):
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path))
    runner = CliRunner()

    # add -> not yet projected
    assert runner.invoke(main, ["pi-extension", "add", str(git_sandbox.upstream),
                                "--slug", "demo"]).exit_code == 0
    out = runner.invoke(main, ["pi-extension", "list", "-g", "--json"])
    rows = {r["slug"]: r for r in json.loads(out.output)}
    assert rows["demo"]["origin"] == "store-owned"
    assert rows["demo"]["globalLoaded"] is False  # added, not installed

    # install -> projected, inventory shows loaded
    assert runner.invoke(main, ["pi-extension", "install", "demo", "-g"]).exit_code == 0
    out = runner.invoke(main, ["pi-extension", "list", "-g", "--json"])
    rows = {r["slug"]: r for r in json.loads(out.output)}
    assert rows["demo"]["globalLoaded"] is True

    # uninstall -> gone from projection, still store-owned
    assert runner.invoke(main, ["pi-extension", "uninstall", "demo", "-g"]).exit_code == 0
    out = runner.invoke(main, ["pi-extension", "list", "-g", "--json"])
    rows = {r["slug"]: r for r in json.loads(out.output)}
    assert rows["demo"]["origin"] == "store-owned"
    assert rows["demo"]["globalLoaded"] is False

    # remove -> gone entirely
    assert runner.invoke(main, ["pi-extension", "remove", "demo"]).exit_code == 0
    out = runner.invoke(main, ["pi-extension", "list", "-g", "--json"])
    assert "demo" not in {r["slug"] for r in json.loads(out.output)}


def test_full_loop_npm_then_inventory(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    runner = CliRunner()
    assert runner.invoke(main, ["pi-extension", "add", "npm:@scope/foo"]).exit_code == 0
    assert runner.invoke(main, ["pi-extension", "install", "@scope/foo", "-g"]).exit_code == 0
    out = runner.invoke(main, ["pi-extension", "list", "-g", "--json"])
    rows = {r["slug"]: r for r in json.loads(out.output)}
    assert rows["@scope/foo"]["origin"] == "npm"
    assert rows["@scope/foo"]["globalLoaded"] is True
```

> **Builder note:** PR1's inventory reads `loaded` as "present on the surface Pi scans" (its docstring says PR1 treats presence as loaded; for npm rows it sets loaded from packages[] presence). After `add` (store-owned), there is no symlink yet, so `globalLoaded` should be False; after `install` the symlink exists, so PR1's `_discover_loose` will find it. **Verify PR1's inventory actually treats a store symlink as `globalLoaded=True` and an added-but-not-installed store row as `globalLoaded=False`.** If PR1's inventory keys store-owned `loaded` off the lock rather than off the symlink, this test's pre-install assertion (`globalLoaded is False`) may fail — in that case the correct fix is in the inventory's store-owned loaded computation (it should reflect the *symlink*, not mere lock presence), and that fix belongs in this PR as a small inventory adjustment with its own test. Flag it; do not weaken the assertion.

- [ ] **Step 2: Run to verify it fails (or surfaces an inventory mismatch)**

Run: `uv run pytest tests/test_cli/test_cli_pi_extension_write.py -k full_loop -v`

- [ ] **Step 3: Implement any inventory `loaded`-from-symlink adjustment if Step 2 reveals the gap**

If the inventory needs to compute store-owned `globalLoaded`/`projectLoaded` from the actual symlink (not lock presence), make the minimal change in `pi_extension_inventory.py` and add a focused unit test in `tests/test_cli/test_pi_extension_inventory.py`. Keep it small and well-commented.

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_cli/test_cli_pi_extension_write.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "test(pi-extension): full write-path loop + inventory state reflection"
```

---

## Task 8: Pi-only matrix-parity guard for the write verbs

Spec §9: assert `pi-extension` is Pi-only and the write verbs never touch any non-Pi harness dir. This mirrors the subagent matrix-parity test (`tests/test_subagent_matrix.py`).

**Files:**
- Test: `tests/test_cli/test_pi_extension_pi_only.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli/test_pi_extension_pi_only.py
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from agent_toolkit_cli import pi_extension_paths as pep


def test_install_touches_only_pi_dirs(tmp_path, monkeypatch, git_sandbox):
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path))
    runner = CliRunner()
    runner.invoke(main, ["pi-extension", "add", str(git_sandbox.upstream), "--slug", "demo"])
    runner.invoke(main, ["pi-extension", "install", "demo", "-g"])

    # The ONLY harness dir written under HOME is ~/.pi; no ~/.claude, ~/.codex,
    # ~/.config/opencode, ~/.gemini, ~/.agents are created by a pi-extension install.
    for foreign in (".claude", ".codex", ".gemini", ".agents"):
        assert not (tmp_path / foreign / "skills" / "demo").exists()
        assert not (tmp_path / foreign / "extensions" / "demo").exists()
    # The Pi dir IS written.
    assert pep.pi_extension_dir("demo", scope="global", home=tmp_path).is_symlink()
```

- [ ] **Step 2: Run to verify it fails / passes**

Run: `uv run pytest tests/test_cli/test_pi_extension_pi_only.py -v`
Expected: This should PASS once Task 5 lands (the install only writes `~/.pi`). If it fails (some foreign dir got created), that's a real bug — fix it. The test exists as a regression guard.

- [ ] **Step 3: Commit**

```bash
git add tests/test_cli/test_pi_extension_pi_only.py
git commit -m "test(pi-extension): Pi-only matrix-parity guard for write verbs"
```

---

## Task 9: Full-suite green + gates + PR

**Files:**
- Modify (if needed): `tests/test_cli_help.py`, `tests/test_cli_skill_help_examples.py` (if they snapshot the verb list of the `pi-extension` group)

- [ ] **Step 1: Full suite**

Run: `uv run pytest -q`
Expected: all pass except possibly a help-text test that snapshots the `pi-extension` subcommand list (PR1 shipped list/status; this PR adds add/install/uninstall/remove).

- [ ] **Step 2: Fix help-text snapshot if it asserts the verb set**

If a test asserts the exact `pi-extension` subcommand set, add `add`, `install`, `uninstall`, `remove`. Show the diff; do not weaken an exact assertion to a substring match.

- [ ] **Step 3: Gates**

Run: `uv run ruff check src/agent_toolkit_cli/ tests/ && uv run mypy src/agent_toolkit_cli/`
Expected: clean. Fix type/lint inline (add return types, tighten `except`).

- [ ] **Step 4: Re-run full suite**

Run: `uv run pytest -q`
Expected: PASS (all).

- [ ] **Step 5: Commit + PR**

```bash
git add -A
git commit -m "test(pi-extension): full-suite green + help-text for write verbs"
git push -u origin feat/273-pi-extension-write-path
gh pr create --title "v3.2.0 PR2a: pi-extension write path (add/install/uninstall/remove + settings writer)" \
  --body "$(cat <<'EOF'
## Summary
First write-path slice of the pi-extension kind (issue #273, spec §3/§6/§8). Builds on PR1's read-only inventory.

- `_pi_settings` packages[] WRITER: preserves all other settings.json keys, atomic, fail-loud on malformed config (highest blast radius — see plan §"Blast radius").
- `pi_extension_install`: store-owned projection (one symlink per scope into Pi's extensions/ dir) with foreign-file guard + lock-after-projection (#283 class fix).
- `add` (global-only): clone git/https/ssh/local into the store, or record npm:<spec> (no clone).
- `install`/`uninstall` (-g/-p): projection toggle at Pi global + project; npm rows toggle packages[].
- `remove`: drop store copy + lock entry, dirty-guard.
- install→uninstall→assert-gone round-trip at BOTH scopes; double-install/uninstall idempotency; Pi-only matrix-parity guard.

Never calls `pi install`/`pi remove`. Never touches real ~/.pi (tmp fixtures only).

## Deferred to PR2b
import, update, push, reset, doctor (git-lifecycle + adoption + reconciliation). The spec §11 item 3 (extensions[] explicit-path classification) plugs into PR2b's import/doctor — see the plan.

## Test
`uv run pytest -q` green; ruff + mypy clean.
EOF
)"
```

---

## PR2b outline (planned at outline depth — promote to a full plan after PR2a merges)

PR2b is largely "clone the shipped skill verb command module, swap `skill_*` → `pi_extension_*` binding." Each verb already exists for skills in `commands/skill/{import_cmd,update_cmd,push_cmd,reset_cmd,doctor_cmd}.py` and reuses `skill_git` + the lock primitives — bind them to `PI_EXTENSION_BINDING` / `pi_extension_paths`.

- **Task B1 — `update <slug>`** (merge-aware upstream pull for store-owned git rows; no-op for npm).
  Reuse `skill_git.fetch` + `skill_git.merge` against the store canonical, exactly as `skill update`. npm rows: print "npm rows have no upstream; no-op." Tests: behind/ahead/diverged/conflict fixtures already exist in `conftest.py` (`make_behind`, `make_ahead`, `make_diverged`, `make_conflict`) — reuse them.

- **Task B2 — `push <slug>`** (push local commits upstream; fork semantics, no-op for npm).
  Reuse the skill `push` path including the #280 clean-gap fallback (when the tree is clean but local commits are ahead of origin, fall back to raw `git push origin main`). npm rows: error "nothing to push for an npm row."

- **Task B3 — `import [--latest]`** `[§11-DECISION POINT]`.
  Adopt pre-existing git/local extensions in Pi's `extensions/` dir into the store (read-only library reconstruction, monorepo parent-symlink reuse from `skill_source`); record npm `packages[]` entries as tracked lock rows.
  **The §11 item 3 decision lives in a single helper here:**
  ```python
  def _classify_extensions_entry(path: str) -> Origin:
      # OPTION A (plan author's recommendation, spec default): untracked-importable.
      return "untracked"
      # OPTION B (#109): tracked local row.
      # return "local"   # and emit a LockEntry(source=f"local:{path}", source_type="local")
  ```
  Swap the body to the resolved option; everything else in `import` is unaffected. Tests: a fixture `.pi/agent/settings.json` with an `extensions[]` array + assert the chosen classification; a fixture `extensions/` tree (store symlink + loose `.ts` + `index.ts` dir + `package.json`-manifest dir) asserting each is adopted/classified correctly (spec §9 discovery fixture).

- **Task B4 — `reset <slug>`** (discard local edits to the store copy; reuse skill `reset`). npm: error.

- **Task B5 — `doctor`** `[§11-DECISION POINT]` (informational only).
  Detect: stray symlinks in `extensions/` not backed by a store entry; orphaned `packages[]` entries (lock has no matching row); orphaned `extensions[]` entries with missing paths; store-vs-projection drift (lock store-owned row with no symlink, or symlink with no store copy). Reuse the `skill_doctor` reconciliation skeleton. The `extensions[]` orphan check's classification depends on the §11 decision (same helper as B3). `doctor -g`/`-p` clears stray symlinks (mirror the skill `doctor` stray-symlink clearance from PR #229).

PR2b mandatory tests mirror PR2a's safety bar: round-trip where applicable, idempotent re-`doctor`, never-touch-real-`~/.pi`, fail-loud on malformed settings.

---

## Self-Review notes (completed by plan author)

- **Spec coverage (PR2a):** §3 two behaviours → Tasks 1 (npm writer) + 2/3 (store-owned clone+projection). §6 `add`/`install`/`uninstall`/`remove` → Tasks 3-6. §8 fail-loud/no-`pi`/scope-safety → Tasks 1 (malformed raise), 5 (npm never shells to pi), 5/8 (scope + Pi-only). §6 `import`/`update`/`push`/`reset`/`doctor` → PR2b outline. §9 testing (round-trip, idempotency, malformed JSON, Pi-only parity) → Tasks 1/5/6/8.
- **Mandatory brief requirements:** (1) install→uninstall→assert-gone at BOTH scopes → Task 5 (two dedicated tests). (2) Idempotency → Task 2 (plan no-op) + Task 5 (double install/uninstall). (3) Foreign-file guard → Task 2 (unit) + Task 5 (CLI), reusing the core conflicting-symlink/non-symlink posture. (4) settings.json writer safety → Task 1 (extra-key survival, atomic, fail-loud, no-clobber-on-malformed). (5) Lock honesty → Task 2 note + Task 3 (`test_add_lock_written_only_after_clone`) + Task 5 (project lock after projection). (6) Never call `pi`, never touch real `~/.pi` → all tests use `monkeypatch.setenv("HOME", tmp_path)` + explicit `home=`/`project=`.
- **§11 item 3:** does NOT block PR2a; plugs into PR2b Tasks B3/B5 via the single `_classify_extensions_entry` helper; both option bodies written out; recommendation (untracked-importable) noted as non-final.
- **Placeholder scan:** every PR2a code step contains complete code; the only "verify against PR1/main" flags are explicit builder notes about API names (`parse_source`, `skill_git.is_dirty`, `scope_and_roots` ctx plumbing) that the builder confirms against the merged PR1 — these are integration checks, not unresolved design.
- **Honesty flag:** PR1 is not yet merged on main; the PRECONDITION section gates execution on it. The "agent_install.py / agent_adapters" parity model from the spec does not exist on any branch — this plan binds to the confirmed-present skill facade + kind-agnostic core instead, and realises the brief's "AgentProjectionConflictError" as the existing core conflicting-path `InstallError` guards.
