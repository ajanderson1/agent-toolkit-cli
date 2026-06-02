# Design: pi-extension doctor false-clean + list/status misreport (Issue #314)

Date: 2026-06-02
Issue: #314
Branch: fix/314-pi-ext-doctor-false-clean

---

## Problem

Two correlated honesty failures when a store-owned pi-extension slug's projection
path is occupied by a **real, non-symlink directory** (a "foreign squatter"):

1. **`pi-extension doctor` reports "all clean"** — the `is_symlink()` gate in
   `_check_slug` (doctor ~line 147) skips the entire symlink check when the slot
   holds a real dir. No finding emitted → user is routed to a no-op.

2. **`pi-extension list`/`status` report `✔ globalLoaded=true`** — `_discover_loose`
   in inventory finds the foreign dir (with `index.ts`), marks it loaded, and the
   lock-backed (store-owned) row inherits `global_loaded=True` — even though our
   symlink was never created and Pi is actually loading the *foreign* directory.

`install` itself already refuses to overwrite the foreign dir (clobber-safety).
The problem is that doctor then finds nothing and inventory reports health — two
lies that contradict `install`'s honest refusal.

---

## Root Cause

### Doctor — `is_symlink()` blind spot

```python
# pi_extension_doctor.py _check_slug (~line 153)
if link.is_symlink():          # only catches symlinks
    target = link.resolve()
    if target != canonical_path.resolve():
        findings.append(Finding(kind="drifted_symlink", ...))
# ← no elif link.exists() arm for the foreign-dir case
```

When `link` is a real non-symlink directory: `link.is_symlink()` is `False` →
entire block skipped → no finding.

### Inventory — no symlink-ownership check in `_discover_loose`

```python
# pi_extension_inventory.py _discover_loose (~line 51)
if entry.is_dir() or (entry.is_symlink() and entry.resolve().is_dir()):
    has_entry = any(...)
    if has_entry:
        out.append((entry.name, True))   # loaded=True regardless of origin
```

A foreign dir that happens to have `index.ts` is treated as loaded. The
lock-backed row then gets `global_loaded=True` from this loose discovery,
misreporting health.

The fix must ensure that for a **store-owned slug**, `global_loaded=True` only
when the projection path is *our* symlink resolving to the canonical store path.

---

## Fix Design

### 1. Doctor: add `squatted_projection` finding kind

In `_check_slug`, after the existing `if link.is_symlink():` block:

```python
elif link.exists():
    findings.append(Finding(
        kind="squatted_projection",
        slug=slug,
        scope=scope,
        path=link,
        detail=(
            f"{link} is occupied by a real {'directory' if link.is_dir() else 'file'} "
            f"(not a symlink owned by the toolkit). "
            f"Expected: our symlink to {canonical_path}. "
            f"The slot is squatted — pi-extension install already refuses to "
            f"overwrite it. Remove or relocate the foreign entry manually."
        ),
        fix_action=None,   # NEVER auto-delete user data
    ))
```

This:
- Emits a finding when expected-our-symlink but found foreign thing.
- `fix_action=None` → report-only, preserving clobber-safety invariant.
- Mirrors how `install` already refuses rather than clobbers.

New `FindingKind` literal: `"squatted_projection"`.

### 2. Inventory: validate symlink ownership before marking loaded

In `_discover_loose`, for directories only count `loaded=True` for a given slug
if the path is **our symlink** pointing to the canonical store path (when such a
canonical can be determined). For untracked/loose slugs the current behaviour is
correct (any dir is loaded). The squatted-projection case affects only slugs that
appear in the lock.

Implementation approach: keep `_discover_loose` return the same `(slug, loaded)`
shape — it's a loose scan and doesn't know about locks. Instead, in
`build_inventory` pass 2 (the loose scan), when updating a *lock-backed
store-owned* row's `global_loaded` flag, validate that the path at the
projection location is actually our symlink to canonical:

```python
# In build_inventory, pass 2 — loose scan
for slug, loaded in _discover_loose(root):
    rec = by_slug.setdefault(
        slug, InventoryRecord(slug=slug, origin="untracked", source="local")
    )
    if scope == "global":
        # For store-owned slugs: only count loaded if the path IS our symlink.
        effective_loaded = loaded and _is_our_symlink(slug, root, scope, home, project, rec)
        rec.global_loaded = rec.global_loaded or effective_loaded
    else:
        effective_loaded = loaded and _is_our_symlink(slug, root, scope, home, project, rec)
        rec.project_loaded = rec.project_loaded or effective_loaded
```

Where `_is_our_symlink` checks:
- If `rec.origin != "store-owned"`: return `True` (untracked/npm rows are unaffected).
- Otherwise: check that the path at `root / slug` (the extension dir) is a symlink
  whose resolved target equals `library_pi_extension_path(slug).resolve()`.

This is a targeted, minimal change: it only gates `loaded=True` for store-owned
rows when the projection path is the correct symlink. Untracked and npm rows are
unchanged.

---

## Acceptance Criteria (from issue)

1. Foreign non-symlink dir at a store-owned slug's projection path:
   - `doctor` emits `squatted_projection` finding (not "all clean").
   - `list`/`status` do NOT show `✔ loaded` for that slug.

2. The fix must NOT delete or modify the foreign dir.

3. Normal cases unchanged:
   - Our symlink present + correct → clean/loaded.
   - Nothing there → not loaded, no finding.
   - Drifted symlink → `drifted_symlink` finding.

4. Tests cover the new case:
   - Seed a foreign non-symlink dir at a store-owned slug's projection path.
   - Assert doctor reports `squatted_projection`.
   - Assert inventory does not set `global_loaded=True`.

---

## Files Changed

- `src/agent_toolkit_cli/pi_extension_doctor.py` — add `"squatted_projection"`
  to `FindingKind`, add `elif link.exists():` arm in `_check_slug`.
- `src/agent_toolkit_cli/pi_extension_inventory.py` — add `_is_our_symlink`
  helper, gate store-owned `global_loaded` on symlink ownership in pass 2.
- `tests/test_cli/test_pi_extension_inventory.py` — new test for squatted projection.
- `tests/test_cli/test_cli_pi_extension_lifecycle.py` — new doctor test for
  squatted projection.
