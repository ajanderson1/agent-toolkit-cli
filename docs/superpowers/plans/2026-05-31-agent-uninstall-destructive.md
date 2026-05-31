# Plan: `agent uninstall` non-destructive (Issue #303)

Spec: `docs/superpowers/specs/2026-05-31-agent-uninstall-destructive-design.md`
Approach: **contract split** — `uninstall()` non-destructive (keeps canonical + lock at both
scopes); new `remove()` owns canonical/lock deletion; `remove_cmd` calls `remove()`.

TDD throughout: flip/add the failing tests first (red), then change source (green), then re-run the
guard tests. The two existing tests that assert the bug are flipped *first* so the suite goes red,
proving the regression guard bites.

## Task 1 — Flip the two destructive assertions to the correct contract (RED)

**Goal:** make the existing round-trip tests assert *preservation* after `uninstall`, so the suite
goes red against current (buggy) source.

1. `tests/test_cli/test_agent_install_roundtrip.py::test_roundtrip_global_removes_projected_files`
   - Keep: `assert not cc.exists()`, `assert not gem.exists()` (projections gone — correct).
   - Replace l.92-93:
     ```python
     assert not canonical.exists(), "canonical not removed on global uninstall"
     assert "rt-agent" not in read_lock(lock_path).skills, "lock entry not dropped"
     ```
     with:
     ```python
     assert canonical.exists(), "uninstall must KEEP the library canonical (#303)"
     assert "rt-agent" in read_lock(lock_path).skills, "uninstall must KEEP the lock entry (#303)"
     ```
   - Update the test docstring + module docstring (lines 1-10 reference the old "removes canonical"
     framing) to state the corrected contract.
2. `tests/test_cli/test_agent_install_roundtrip.py::test_roundtrip_project_removes_projected_files`
   - After the project uninstall, replace the lock-dropped assertion (l.136) with:
     ```python
     assert "rt-agent" in read_lock(lock_path).skills, "project uninstall must KEEP the lock entry (#303)"
     ```
   - Add: `assert canonical.exists()` (project canonical preserved — capture the local return of
     `_seed_project_canonical`).
3. `tests/test_cli/test_cli_agent_group.py::test_install_uninstall_global_round_trip`
   - Replace l.160-163 (`assert "demo-agent" not in lock`) with `assert "demo-agent" in lock` +
     `assert canonical.exists()` (seed returns the canonical path; bind it).

**Verify (red):** `uv run pytest tests/test_cli/test_agent_install_roundtrip.py tests/test_cli/test_cli_agent_group.py -q` → these specific tests FAIL (canonical/lock still deleted by current source). Confirms the guard.

## Task 2 — Add the distinct-effects test (RED)

**Goal:** prove `uninstall` and `remove` differ.

In `tests/test_cli/test_cli_agent_group.py`, add `test_uninstall_vs_remove_distinct_effects`:
- Install `demo-agent -g --harnesses claude-code`.
- Run `agent uninstall demo-agent -g --harnesses claude-code`: assert projection GONE, **canonical
  PRESENT**, **lock entry PRESENT**, and `agent list -g` shows the agent.
- Re-install (proves re-projection from the intact canonical with no re-clone).
- Run `agent remove demo-agent`: assert projection GONE, **canonical GONE**, **lock entry GONE**.

This is the single test the spec's acceptance #4 requires; it fails on current source at the
"canonical PRESENT after uninstall" assertion.

## Task 3 — Make `agent_install.uninstall()` non-destructive (GREEN)

Edit `src/agent_toolkit_cli/agent_install.py::uninstall()`:
- Keep step 1 (per-adapter idempotent projection removal) verbatim.
- **Delete** step 2 (the `remove_entry` lock drop) and step 3 (the global `shutil.rmtree(canonical)`).
- Rewrite the docstring to: *"Detach: remove the requested harnesses' projection files. Keeps the
  library canonical AND the lock entry at both scopes (mirrors `skill uninstall`; the destructive
  path lives in `remove()`)."*
- Remove the now-unused `read_lock/remove_entry/write_lock` + `lock_file_path`/`canonical_agent_dir`
  imports **only if** they're unused after Task 4 (they're reused by `remove()` below, so keep the
  module-level `shutil` import — `remove()` needs it).

## Task 4 — Add `agent_install.remove()` (GREEN)

New function in `agent_install.py` holding the deletion logic moved out of `uninstall()`:
```python
def remove(*, slug, scope, home, project, harnesses) -> None:
    """Full removal: projections + lock entry + canonical (global). Project scope
    preserves the external canonical (doctor reclaims orphans), matching skill remove."""
    uninstall(slug=slug, scope=scope, home=home, project=project, harnesses=harnesses)
    lock_path = lock_file_path(scope=scope, home=home, project=project)
    lock = read_lock(lock_path)
    if slug in lock.skills:
        write_lock(lock_path, remove_entry(lock, slug))
    if scope == "project":
        return
    canonical = canonical_agent_dir(slug, scope=scope, home=home, project=project)
    if canonical.exists():
        shutil.rmtree(canonical)
```
Imports `read_lock, remove_entry, write_lock` from `agent_lock` (already a local import pattern in
the module). Keep them local to the function to mirror the existing style.

## Task 5 — Point `remove_cmd` at the new `remove()` (GREEN)

`src/agent_toolkit_cli/commands/agent/remove_cmd.py`:
- Change the `agent_install.uninstall(...)` call (l.63) to `agent_install.remove(...)` (same kwargs).
- Update the trailing comment (l.68-69) from *"agent_install.uninstall() already removes the lock
  entry and canonical"* to reference `remove()`.
- Dirty git-guard above stays unchanged.

## Task 6 — Full verification (GREEN)

1. `uv run pytest tests/test_cli/test_agent_install_roundtrip.py tests/test_cli/test_cli_agent_group.py -q` → all green (flipped + new tests pass; `test_remove_drops_projections_and_canonical` still green).
2. `uv run pytest -q` → full suite green.
3. `uv run ruff check src tests` → clean (watch for now-unused imports after Task 3).

## Open decision (flagged for reviewer)

Project-scope `uninstall` **keeps** the project lock entry (spec default, user-confirmed). If the
reviewer prefers dropping it for tighter `skill uninstall` parity, it's a one-line guard in
`uninstall()` (drop only when `scope == "project"`) plus a flip of the Task 1.2 assertion. Recorded
here so it isn't silently re-litigated.

## Out of scope

#304 companion minors (status scope-default, `agent add` slug-file validation, TUI label) —
separate issue, not touched here.
