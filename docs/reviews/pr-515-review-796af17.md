# Code Review: PR #515 (Issue #515)

**Feature:** Surface untracked assets and offer safe repair  
**PR Target:** `main`  
**Current Verified HEAD:** `796af174ebbaee7cc0896c54399ab50c6ef685e4` (`796af17`)  
**Base Commit:** `8ad3e9d8ee8ff219e485615016e4e827f0b06e7d`  
**Initial Reviewed Commit:** `078059fdfc7a4cd176b0a4e53cde954d94028815` (`078059f`)  
**Reviewer:** Independent Read-Only Reviewer  
**Date:** 2026-10-16  
**Final Verdict:** **PASS / APPROVED (NO FINDINGS / READY FOR MERGE)**  

---

## 1. Executive Summary

This review covers the complete change set for Issue #515 across the full commit series through verified current HEAD `796af17`:
- `2b6c0f2`: docs(515): add firmed spec and implementation plan for unmanaged asset visibility
- `2615052`: fix(skill_paths): honor explicit home in global lock_file_path (#515)
- `db80425`: feat(pi-extension): inventory local packages without modifying them (#515)
- `9bfd28b`: docs(skill_paths): update module docstring for home parameter (#515)
- `03b289d`: feat(skill): discover unmanaged filesystem skills and bundles as unlisted (#515)
- `1d81393`: feat(tui): discover unmanaged agents and commands as unlisted rows (#515)
- `078059f`: feat(inventory): import unmanaged assets safely (#515)
- `796af17`: test(skill): assert isolated explicit install home (resolves test runner isolation regression)

The implementation strictly satisfies the approved spec (`docs/specs/2026-09-10-ensure-assets-visible.md`) and plan (`docs/plans/2026-09-10-ensure-assets-visible.md`). All acceptance criteria pass, safety invariants are verified, path sandboxing is airtight, and focused test coverage is exhaustive.

---

## 2. Invariant & Safety Analysis

### 2.1 Confirmed Repair & Zero Mutation Guarantee
- **Doctor Report-Only by Default:**
  Without `--repair`, `diagnose()` supplies `fix_action=None` on unmanaged findings. Unmanaged assets are reported for audit visibility, but neither `skill doctor` nor `pi-extension doctor` prompts or mutates state.
- **Explicit Confirmation Prompt:**
  With `--repair`, Click prompts interactively:
  ```text
  apply? [y/N/q] (default: N)
  ```
  Decline is the safe default (`N`). Only explicit affirmative `y` triggers the fix.
- **`--no-fix` Precedence:**
  `--no-fix` overrides `--repair` and forces all findings to be skipped without prompting.
- **Zero Pi Settings Mutation:**
  Under no circumstance does inventory reading or doctor repair alter `settings.json`. The package import action writes exclusively to `pi-extensions-lock.json`. In `test_pi_extension_doctor_unmanaged.py`, `settings.json` is asserted byte-for-byte identical before and after confirmed repair.
- **Repeat-Repair Idempotence:**
  Both `_make_import_skill_action` and `_make_import_package_action` check `if slug in cur_lock.skills: return`. Successive runs exit cleanly with `✓ all clean`.
- **Atomic / All-or-Nothing Safety:**
  Because the repair action touches only the lockfile via `write_lock()`, any lock-write failure (e.g. disk full or permissions) leaves existing source files, settings, and filesystem structures completely intact.

### 2.2 Collision Handling & Foreign Projections
- **Lock Precedence over Discovery:**
  In `_scan_unmanaged_skills` and `_scan_unmanaged_packages`, any slug that already exists in `lock.skills` is skipped (`if slug in lock.skills: continue`). Discovery will never misclassify an existing managed asset as unmanaged or attempt to re-import it.
- **Foreign Symlink Protection:**
  `_is_inside(child, parent)` ensures child paths resolve strictly inside their parent directory. Symlinks escaping the scanned library or bundle root are ignored and never followed.
- **Dangling Links & Stray Files:**
  Dangling symlinks are safely skipped (`if not target.exists() or not target.is_dir(): continue`). Hidden files (`.*`), `_parents`, and temporary backups (`*.bak-*`) are ignored.
- **Non-Interactive TUI Guard:**
  In `PiGrid._on_data_table_cell_selected()`, rows with `origin in ("untracked", "local-package")` are strictly non-interactive. The user cannot inadvertently trigger toggle mutations from the TUI.

### 2.3 Stable Identifiers & Bundle Preservation
- **Nested Bundle Skills:**
  Nested bundle skills are given stable, collision-free identifiers matching `<bundle>:<subskill>` (e.g., `superpowers:brainstorming`).
- **Relative Skill Path Computation:**
  During import of a bundle subskill, `skill_path` is computed relative to the bundle container root (e.g. `skills/brainstorming`), preserving the bundle layout in the lock entry.

### 2.4 Path Sandboxing & Home Scoping
- `skill_paths.lock_file_path(scope="global", home=home)` now propagates `home` down to `_paths_core.library_lock_path_for_asset_type()` and `library_root_for_asset_type()`, honoring caller-provided home directories while respecting `$AGENT_TOOLKIT_SKILLS_ROOT` override precedence.
- Commit `796af17` corrected `test_global_pi_uses_standard_projection` to pass `home=home` to `library_root` and `library_lock_path`, cleanly aligning test assertions with the home-scoping contract.

---

## 3. Verification & Evidence

### 3.1 Focused Test Suite
Executed the focused suite on HEAD `796af17`:
```text
tests/test_cli/test_skill_doctor_unmanaged.py .......... [100%]
tests/test_cli/test_pi_extension_doctor_unmanaged.py .... [100%]
tests/test_tui/test_inventory_rendered_evidence.py ...... [100%]
Result: 10 passed in 15.61s
```

All 143 tests across the related component suites pass:
```text
tests/test_cli/test_pi_extension_inventory.py
tests/test_cli/test_cli_pi_extension_list.py
tests/test_cli/test_skill_paths.py
tests/test_tui/test_agent_state.py
tests/test_tui/test_command_state.py
tests/test_tui/test_pi_grid.py
tests/test_tui/test_skill_state.py
Result: 143 passed in 24.43s
```

The previously observed failure in `test_global_pi_uses_standard_projection` is resolved:
```bash
uv run pytest tests/test_cli/test_skill_install_engine.py -k "test_global_pi_uses_standard_projection"
Result: 1 passed, 16 deselected in 0.42s
```

Total scoped tests passing: **154 passed, 0 failed**.

### 3.2 Build Verification
`uv build` was executed and completed without error:
```text
Successfully built dist/agent_toolkit-5.9.1.tar.gz
Successfully built dist/agent_toolkit-5.9.1-py3-none-any.whl
```

### 3.3 Visual & Headless Evidence Gate
Headless Textual pilot evidence confirmed under `assets/verification/515/`:
- `inventory.json`: Records rendered table columns, stable keys (`skill:standalone-skill`, `skill:superpowers:brainstorming`, `agent:local-agent`, `command:local-command`, `pi:local-package`), and badge markup (`[yellow]unlisted[/]`, `[yellow]local package · untracked[/]`).
- `inventory.svg`: Terminal screenshot export confirmed intact (>1000 bytes).

---

## 4. Conclusion & Recommendation

The branch `feat/515-inventory-safe-import-p9` at HEAD `796af17` has **no blocking findings**, fulfills all safety constraints, preserves user data losslessly, and has verified test passing status.

**Status for Integrator (p6):**
- Review approval is locked for commit `796af17`.
- When p9 opens the PR at `796af17`, the PR is cleared for immediate integration following p9's full-slot gate.
