# Spec — skill doctor: flag orphan real-dir strays in ~/.agents/skills (#231)

## Goal
`skill doctor` should flag **real directories** in the universal-bundle root
`~/.agents/skills/<slug>/` whose slug is **not in the global lock**, and offer cleanup
for doctor's own `*.bak-doctor-*` leftovers. Today both are invisible to doctor.

## Confirmed gap (scout)
- `_scan_orphan_canonicals` is **project-scope only** (`if scope != "project": return []`)
  and scans `project_store_root`, never `~/.agents/skills/`.
- `_check_slug` raises `wrong_type_bundle` only for slugs **already in the lock**.
- So a real dir at `~/.agents/skills/<slug>` with slug **not** in the global lock →
  caught by **nothing**. And `*.bak-doctor-*` dirs there are never offered for cleanup.

## Change
Add a new global-only scan `_scan_stray_bundle_dirs` + a new `FindingKind`
`"stray_bundle_dir"`, mirroring `_scan_orphan_canonicals`:

- Target dir: `_universal_bundle_root()` = `~/.agents/skills/`.
- For each entry:
  - `path.is_symlink()` → skip (correct v2.2 global universal install artifact).
  - `name in lock.skills and not is_bak` → skip (real dir that IS in lock is a
    `wrong_type_bundle` case handled by `_check_slug`; don't double-report).
  - `".bak-" in name` → emit a finding with a **hard-delete** fix
    (`_make_rmtree_action`) — already a backup, safe to reap. Matches how
    `_scan_orphan_canonicals` treats `.bak-` dirs.
  - else (genuine stray real dir) → emit `stray_bundle_dir` with a **move-to-bak**
    fix (`_make_backup_dir_action`), consistent with `wrong_type_bundle`'s
    `.bak-doctor-<stamp>` convention. Non-destructive (no hard delete of unknown data).

New helper `_make_backup_dir_action(*, path)`: renames `path` →
`path.name + ".bak-doctor-<stamp>"`, stamping at apply()-time (idempotent on re-run).
Mirrors the backup half of `_make_bundle_repair_action`, minus the relink step (a stray
has no canonical to relink to).

Wire into `diagnose()` in the `slugs is None` full-scan block, next to the other stray
scans. Guard is internal (`if scope != "global": return []`), so no call-site condition.

## Decisions
- **Stray real dir → move-to-bak, not delete.** It may contain real skill files the user
  forgot to lock; preserve them. (Fail-safe over fail-destructive.)
- **`.bak-doctor-*` leftover → hard delete.** Already a backup; reaping is safe and stops
  silent accumulation. Same asymmetry `_scan_orphan_canonicals` already uses.
- **No CLI changes.** `doctor_cmd.py` renders findings generically by `kind/detail/path/
  fix_action`; a new kind + action flows through automatically (incl. exit-code logic).

## Out of scope
- Missing-projection detection (that's #230, separate PR).
- Changing how `.bak-doctor-*` backups are *created* (only their cleanup).

## Definition of done
- Real dir `~/.agents/skills/<ghost>` not in lock → one `stray_bundle_dir` finding.
- Its fix moves it to `<ghost>.bak-doctor-<stamp>` (not a symlink, original gone).
- A planted `*.bak-doctor-*` dir → a finding whose fix removes it.
- A real dir whose slug IS in the lock → NOT reported as `stray_bundle_dir` (no
  double-report with `wrong_type_bundle`).
- Symlinks in the bundle root → never flagged by this scan.
