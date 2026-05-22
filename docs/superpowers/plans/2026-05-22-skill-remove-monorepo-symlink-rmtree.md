# Plan: skill remove handles monorepo symlinks (#207)

Spec: [`docs/superpowers/specs/2026-05-22-skill-remove-monorepo-symlink-rmtree-design.md`](../specs/2026-05-22-skill-remove-monorepo-symlink-rmtree-design.md)

## Steps

### 1. Add `_cleanup_parent_clone_if_orphaned` helper

Location: `src/agent_toolkit_cli/commands/skill/__init__.py` (near
`_remove_all_global_symlinks`).

```python
def _cleanup_parent_clone_if_orphaned(
    parent_clone: Path,
    lock: LockFile,
) -> bool:
    """Remove `parent_clone` if no current lock entry's library symlink targets it.

    Returns True if the parent clone was removed. Callers pass the lock state
    *after* the symlink has been unlinked so the about-to-be-removed slug does
    not count as a reference.
    """
```

Implementation notes:
- Walk `lock.skills.keys()`.
- For each slug, compute `library_skill_path(slug)`. If it `is_symlink()`,
  resolve with `os.readlink` to a `Path` (absolute), and check whether the
  parent-clone path is an ancestor (`parent_clone in target.parents`).
- If any sibling matches → return `False`.
- Otherwise → `shutil.rmtree(parent_clone, ignore_errors=False)` and return
  `True`.

### 2. Branch on symlink in `remove_cmd`

At `__init__.py:583-586`, replace:

```python
_remove_all_global_symlinks(slug)
if library_dir.exists():
    shutil.rmtree(library_dir)
```

with:

```python
_remove_all_global_symlinks(slug)
parent_clone_to_check: Path | None = None
if library_dir.is_symlink():
    target = Path(os.readlink(library_dir))
    if not target.is_absolute():
        target = (library_dir.parent / target).resolve(strict=False)
    parent_clone_to_check = _enclosing_parent_clone(target)
    library_dir.unlink()
elif library_dir.exists():
    shutil.rmtree(library_dir)
```

`_enclosing_parent_clone(target)` returns the
`_parents/<owner>/<repo>[@<ref>]/` directory by climbing parents until the
parent's name is `_parents`. Returns `None` if not under `_parents` (defensive
— shouldn't happen on a monorepo install, but we won't sweep a random
unrelated directory).

After the lock entry is removed (`lock = remove_entry(lock, slug)`), call:

```python
if parent_clone_to_check is not None and parent_clone_to_check.exists():
    _cleanup_parent_clone_if_orphaned(parent_clone_to_check, lock)
```

This runs **after** `lock = remove_entry(lock, slug)` so the slug we just
removed does not count as its own reference, but **before**
`write_lock(...)` so a sweep failure doesn't leave a stale lock entry
mismatched with disk. Actually — since the sweep does not mutate the lock,
ordering inside the post-remove block is mostly cosmetic; do it after
`write_lock` so the on-disk state is consistent first.

### 3. Add `import os` if missing

Already imported via `os.path` somewhere? Check; add `import os` at module
top if not.

### 4. Regression test

`tests/test_cli/test_skill_remove_monorepo.py`:

```python
def test_remove_monorepo_skill_unlinks_and_cleans_parent(
    tmp_path, monkeypatch, isolated_library,
):
    """skill add (monorepo) → skill remove → symlink and parent clone gone."""
```

Cases:

1. **Single-skill monorepo**: add `mkdocs`, remove `mkdocs`.
   - Assert: `library/skills/mkdocs` does not exist (no symlink, no dir).
   - Assert: parent clone directory does not exist.
   - Assert: lock entry gone.
   - Assert: exit code 0 (no traceback).

2. **Sibling preserved**: add `mkdocs` + `docker` from same parent, remove
   `mkdocs`.
   - Assert: `library/skills/mkdocs` gone, `library/skills/docker` still a
     symlink and resolvable.
   - Assert: parent clone directory still exists.
   - Assert: lock has `docker` but not `mkdocs`.

3. **Last sibling removed**: continuing case 2, remove `docker`.
   - Assert: parent clone directory now gone.

Re-use `_make_parent_repo` and `isolated_library` from
`test_skill_add_monorepo.py` — import them or duplicate the minimal setup.
Imports must remain test-isolated (no fixture sharing across modules unless
exported via `conftest.py`); duplicating the small helper is fine and matches
the existing pattern.

### 5. Existing test sanity

`test_remove_clears_library_and_lock` (non-monorepo path) must still pass —
the `elif library_dir.exists()` branch keeps the original behaviour.

### 6. Pre-flight CI

`uv run pytest -q` from worktree root. Capture log to
`assets/verification/207/preflight-pytest.log`. Non-zero exit → safety stop.

### 7. Verify

CLI-only fix. Verify recipe:

- Build a tiny fake monorepo with two skills in a tmpdir.
- Run `skill add`, `skill remove` against it via the actual installed CLI.
- Assert the bug is gone end-to-end (not just unit-isolated).

Captured to `assets/verification/207/verify.log`.

### 8. Self-review + PR

Standard flow steps 10–13.

## Risks & rollback

- **Wrong target resolution**: if `os.readlink` returns a relative path we
  must resolve it relative to the symlink's parent, not the cwd. The plan
  handles this explicitly.
- **Wrong parent-clone match**: defensive `_enclosing_parent_clone` returns
  `None` if `_parents` is not in the path; sweep is skipped. Worst case: a
  parent clone is left on disk — disk hit only, never data loss.
- **Sibling false-negative**: if a sibling exists outside the lock (e.g. a
  test fixture left in `library_skill_path()`), we'll preserve the parent.
  Acceptable — a no-op `skill add` against the same parent re-uses it.
- **Rollback**: revert the commit; old behaviour returns. No migration, no
  on-disk schema change, no flag.
