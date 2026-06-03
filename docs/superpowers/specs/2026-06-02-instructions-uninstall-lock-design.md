# Spec: instructions uninstall leaves empty lock file (#312)

**Date:** 2026-06-02  
**Slug:** instructions-uninstall-lock  
**Type:** chore  
**Issue:** #312

---

## Problem

`instructions uninstall` removes all lock entries but then calls `write_lock(lock_path, new)` even when `new.instructions` is empty, leaving a file like:

```json
{
  "version": 1,
  "instructions": {}
}
```

in the user's project root (or `~/.agent-toolkit/`). This is a cosmetic issue — the lock is our own data structure, no user content is at risk — but "leave no trace" is the expected contract: a full uninstall should leave no footprint.

## Current behavior (root cause)

`src/agent_toolkit_cli/instructions_install.py`, `uninstall()` (~line 149):

```python
for slug in list(lock.instructions.keys()):
    new = remove_entry(new, slug)
write_lock(lock_path, new)   # writes {} instead of deleting
```

## Cross-kind audit

- `skill uninstall`: in `skill_install.uninstall()`, the project-scope path does `write_lock(lock_path, remove_entry(lock, slug))` — but only when the slug is in the lock, and only writes the residual. Does NOT explicitly delete when empty. However, skill uninstall removes ONE slug (caller loops), so it may leave a residual if multiple slugs exist.
- `agent remove`: in `agent_install.remove()`, does `write_lock(lock_path, remove_entry(lock, slug))` — same pattern.

Neither `skill` nor `agent` explicitly deletes the lock file when empty. However:
- Skills and agents typically have multiple entries, so the "last entry" case is rarer.
- `instructions` is more likely to have only a single entry (one `AGENTS.md` per scope) so the empty-lock case is the normal full-uninstall path.

**Decision:** Apply delete-when-empty to `instructions uninstall` per the issue request. Cross-kind normalization of `skill`/`agent` is explicitly out of scope (#312 out-of-scope clause).

## Proposed fix

In `instructions_install.uninstall()`, replace:

```python
write_lock(lock_path, new)
```

with:

```python
if new.instructions:
    write_lock(lock_path, new)
elif lock_path.exists():
    lock_path.unlink()
```

This:
1. Deletes the lock file when the last entry is removed (the bug fix).
2. Preserves the existing behavior when entries remain (a partial uninstall leaves the residual lock intact).
3. Is idempotent: if the file is already gone, `lock_path.unlink()` is guarded by the `exists()` check.

## Acceptance criteria

1. `instructions install` + `instructions uninstall` (project scope) leaves NO `instructions-lock.json` behind.
2. `instructions install` + `instructions uninstall` (global scope) leaves NO `instructions-lock.json` behind.
3. Partial uninstall (multiple entries, remove one) leaves the file with the remaining entries.
4. Tests: extend the existing install→uninstall round-trip test to assert `lock_path.exists() == False`.

## Out of scope

- Normalizing `skill uninstall` / `agent remove` empty-lock behavior (#312 explicitly OOS).
- Any changes to the clobber-safety contract (verified working in v3.5.2).

## Files to change

| File | Change |
|---|---|
| `src/agent_toolkit_cli/instructions_install.py` | Replace `write_lock` with delete-when-empty guard |
| `tests/test_cli/test_instructions_install.py` | Add / extend test asserting lock file absent after full uninstall |
