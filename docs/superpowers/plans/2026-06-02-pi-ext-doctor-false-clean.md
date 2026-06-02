# Plan: pi-extension doctor false-clean + list/status misreport fix (Issue #314)

Date: 2026-06-02
Branch: fix/314-pi-ext-doctor-false-clean

---

## Objective

Fix two correlated honesty failures when a non-symlink foreign directory squats a
store-owned slug's projection path:
1. Doctor reports false-clean → emit `squatted_projection` finding.
2. Inventory misreports `global_loaded=True` → only count loaded when path is our symlink.

---

## Task 1 — Doctor: add `squatted_projection` finding

**File:** `src/agent_toolkit_cli/pi_extension_doctor.py`

### 1a. Extend `FindingKind`

Add `"squatted_projection"` to the `FindingKind` Literal (line ~39-46).

### 1b. Add `elif link.exists():` arm in `_check_slug`

After the existing `if link.is_symlink():` block (line ~153-165), add:

```python
elif link.exists():
    findings.append(Finding(
        kind="squatted_projection",
        slug=slug,
        scope=scope,
        path=link,
        detail=(
            f"{link} is occupied by a real "
            f"{'directory' if link.is_dir() else 'file'} "
            f"(not a symlink owned by the toolkit). "
            f"Expected: our symlink to {canonical_path}. "
            f"The slot is squatted — pi-extension install already refuses to "
            f"overwrite it. Remove or relocate the foreign entry manually."
        ),
        fix_action=None,
    ))
```

Note: `fix_action=None` preserves clobber-safety — the fix is report-only.

**Validation:** The `canonical_path` variable is already assigned above (line ~154
`canonical_path = library_pi_extension_path(slug)`). The `elif` check is after the
`is_symlink()` block which already uses it.

Wait — look at the actual code again. The `canonical_path` is assigned inside the
`if link.is_symlink():` block at line 154. We need to ensure it is also accessible
in the `elif` branch. Two options:
1. Move the `canonical_path` assignment before the `if`/`elif`.
2. Re-assign it in the `elif` block.

**Choose option 1**: hoist `canonical_path = library_pi_extension_path(slug)` to
before the `if link.is_symlink():` check. This is cleaner and makes the code read:
- Get canonical path.
- Check what's at the projection slot.

---

## Task 2 — Inventory: gate store-owned `global_loaded` on symlink ownership

**File:** `src/agent_toolkit_cli/pi_extension_inventory.py`

### 2a. Add `_is_store_owned_symlink` helper

```python
def _is_store_owned_symlink(
    slug: str,
    path: Path,
    rec: InventoryRecord,
) -> bool:
    """Return True iff the path is our symlink to the store canonical for slug.

    For non-store-owned records (untracked/npm), always returns True so existing
    behaviour is unchanged. Only store-owned rows are gated on symlink ownership.
    """
    if rec.origin != "store-owned":
        return True
    if not path.is_symlink():
        return False
    from agent_toolkit_cli.pi_extension_paths import library_pi_extension_path
    try:
        canonical = library_pi_extension_path(slug)
        return path.resolve() == canonical.resolve()
    except Exception:
        return False
```

Import `library_pi_extension_path` from `pi_extension_paths` at the top of the
file (it may already be imported — check and add if needed).

### 2b. Gate `global_loaded` / `project_loaded` in pass 2

In `build_inventory`, in pass 2 (the loose scan), change the `rec.*_loaded` update:

```python
for slug, loaded in _discover_loose(root):
    rec = by_slug.setdefault(
        slug, InventoryRecord(slug=slug, origin="untracked", source="local")
    )
    # The path that _discover_loose found for this slug.
    ext_path = root / slug
    if scope == "global":
        effective_loaded = loaded and _is_store_owned_symlink(slug, ext_path, rec)
        rec.global_loaded = rec.global_loaded or effective_loaded
    else:
        effective_loaded = loaded and _is_store_owned_symlink(slug, ext_path, rec)
        rec.project_loaded = rec.project_loaded or effective_loaded
```

**Validation:** For untracked rows (`rec.origin == "untracked"`), `_is_store_owned_symlink`
returns `True` → behaviour unchanged. For store-owned rows with a correct symlink,
`_is_store_owned_symlink` returns `True` → behaviour unchanged. Only the squatted
case (store-owned row, non-symlink at path) returns `False` → `effective_loaded=False`.

---

## Task 3 — Tests

### 3a. Inventory test: foreign dir squats store-owned projection

**File:** `tests/test_cli/test_pi_extension_inventory.py`

New test `test_store_owned_with_squatted_projection_not_loaded`:
1. Create a lock with a store-owned slug `demo`.
2. Create the projection directory (not a symlink, but a real dir with `index.ts`).
3. Call `build_inventory`.
4. Assert `rec.global_loaded is False`.

### 3b. Doctor test: foreign dir squats store-owned projection

**File:** `tests/test_cli/test_cli_pi_extension_lifecycle.py`

New test `test_doctor_squatted_projection_reported`:
1. Monkeypatch HOME.
2. Add store-owned slug via `pi-extension add`.
3. Create the projection dir path as a real directory (not a symlink) with `index.ts`.
4. Run `pi-extension doctor -g --no-fix`.
5. Assert `squatted_projection` in output.
6. Assert foreign dir was NOT removed/modified.

### 3c. Doctor test: squatted projection fix_action is None (report-only)

Inline in 3b: assert the foreign dir still exists after doctor runs.

---

## Execution Order

1. Task 1a (extend FindingKind)
2. Task 1b (hoist canonical_path + add elif)
3. Task 2a (add _is_store_owned_symlink)
4. Task 2b (gate global_loaded)
5. Task 3a (inventory test)
6. Task 3b (doctor lifecycle test)
7. Run: `uv run pytest tests/test_cli/test_pi_extension_inventory.py tests/test_cli/test_cli_pi_extension_lifecycle.py -q`
8. Run full suite: `uv run pytest -q`

---

## Risk Assessment

**Low risk.** Changes are purely additive:
- `FindingKind` adds a new literal value — no existing code paths broken.
- `elif link.exists()` only fires when `is_symlink()` is False — existing symlink
  cases (clean/drifted/stray) are unaffected.
- `_is_store_owned_symlink` only gates the `global_loaded` update for store-owned
  rows with non-symlink paths — untracked, npm, and correctly-symlinked store-owned
  rows all return `True` from the helper.
- No mutations to the foreign dir anywhere in the fix.
