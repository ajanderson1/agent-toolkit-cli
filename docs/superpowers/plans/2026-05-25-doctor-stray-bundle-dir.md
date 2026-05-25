# Plan — #231 doctor stray_bundle_dir

## Task 1 — Tests first (TDD red)
**File:** `tests/test_cli/test_skill_doctor.py` (mirror `test_diagnose_wrong_type_bundle_global`
sandbox setup: `fake_home = tmp_path/"home"`, monkeypatch `Path.home`).
- `test_diagnose_stray_bundle_dir_global`: plant real dir `fake_home/.agents/skills/ghost`
  (not in lock) → `diagnose(scope="global", slugs=None)` yields exactly one
  `stray_bundle_dir` finding for `ghost`.
- `test_stray_bundle_dir_fix_moves_to_bak`: apply the fix → original gone, sibling
  `ghost.bak-doctor-*` exists and is a real dir (not symlink).
- `test_stray_bundle_dir_skips_known_slug`: slug in lock + real dir present → NO
  `stray_bundle_dir` finding (it's `wrong_type_bundle`'s job).
- `test_stray_bundle_dir_skips_symlink`: symlink at `~/.agents/skills/<slug>` → not flagged.
- `test_diagnose_bak_doctor_dirs_offered_for_cleanup`: plant
  `~/.agents/skills/ghost.bak-doctor-20250101-120000` → finding whose fix removes it.

## Task 2 — Engine (green)
**File:** `src/agent_toolkit_cli/skill_doctor.py`
1. Add `"stray_bundle_dir"` to the `FindingKind` Literal.
2. Add `_make_backup_dir_action(*, path)` — rename to `.bak-doctor-<stamp>` at apply-time.
3. Add `_scan_stray_bundle_dirs(*, scope, home, project, lock)` per spec (global-only guard,
   skip symlinks, skip in-lock non-bak, `.bak-` → rmtree, else → backup-dir action).
4. Call it from `diagnose()` in the `slugs is None` block.

## Task 3 — Verify
- `uv run pytest tests/test_cli/test_skill_doctor.py tests/test_cli/test_cli_skill_doctor.py`
- Full suite via lefthook on commit.
- Manual: `agent-toolkit-cli skill doctor -g --no-fix` against a sandbox HOME with a planted
  stray, capture to `assets/verification/231/`.

## Risks
- Don't double-report in-lock real dirs (the `name in known and not is_bak` guard).
- Stamp at apply()-time, not closure-creation, for idempotent re-runs.
- `_universal_bundle_root()` calls `Path.home()` directly → tests must monkeypatch it.
- Touches `skill_doctor.py` — #230 will too; sequence merges, resolve any conflict at #230.
