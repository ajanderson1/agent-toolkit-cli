# Plan: instructions uninstall empty-lock fix (#312)

**Date:** 2026-06-02  
**Spec:** `docs/superpowers/specs/2026-06-02-instructions-uninstall-lock-design.md`

---

## Goal

After `instructions uninstall` removes the last entry from the lock, delete the lock file entirely rather than writing back an empty `{}` object.

## Tasks

### Task 1: Fix `instructions_install.uninstall()`

**File:** `src/agent_toolkit_cli/instructions_install.py`

Replace the final `write_lock` call with a delete-when-empty guard:

```python
# Before
write_lock(lock_path, new)

# After
if new.instructions:
    write_lock(lock_path, new)
elif lock_path.exists():
    lock_path.unlink()
```

This is a single-line conceptual change (3 lines of code total). No interface changes, no new imports.

### Task 2: Extend `test_uninstall_removes_pointers` test

**File:** `tests/test_cli/test_instructions_install.py`

The existing `test_uninstall_removes_pointers` test already verifies:
- Symlinks removed
- `read_lock(lock_path).instructions == {}`

Add an assertion that the lock file is absent:

```python
assert not lock_path.exists()
```

### Task 3: Add a dedicated round-trip test

Add `test_install_uninstall_roundtrip_leaves_no_lock_file` that:
1. Installs via `apply()` with a lock file pre-written.
2. Calls `uninstall()`.
3. Asserts `not lock_path.exists()`.

This is the canonical regression test for #312.

## Execution order

1. Fix `instructions_install.py` (Task 1).
2. Add/extend tests (Tasks 2–3).
3. Run `uv run pytest -q` locally — all tests green.
4. Commit.

## Risk

Low. The change is 3 lines in a single function. No public API surface changes. Existing tests cover the surrounding behavior. The new test catches the regression directly.
