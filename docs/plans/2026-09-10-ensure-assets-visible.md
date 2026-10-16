Issue: #515
# Ensure Untracked Assets Remain Visible — Implementation Plan

Document type: plan
Origin: docs/specs/2026-09-10-ensure-assets-visible.md

> **For agentic workers:** Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox syntax.

**Goal:** Make local and unmanaged assets visible, auditable, and safely importable without altering user data.
**Architecture:** Extend existing per-kind discovery and row builders; keep lockfiles as managed-state authority and treat filesystem/config observations as untracked rows. Doctor repair is an explicit, confirmed local import, with existing repair patterns and schemas.
**Tech Stack:** Python 3.12+, Click, Textual, pytest.
**Spec:** `docs/specs/2026-09-10-ensure-assets-visible.md`

## Global Constraints

- Inventory never mutates files, Pi settings, or locks; `--no-fix` reports only.
- Repair requires explicit `--repair` plus confirmation, is additive and repeat-safe, and records unknown sources as local without guessing remotes.
- Preserve source bytes and unrelated Pi configuration; do not adopt or overwrite files or foreign symlinks. Report unsupported/lossy settings-only assets and leave them unmanaged.
- Preserve existing per-kind lockfile formats and unrelated doctor behavior; add no dependency.
- Do not run the full suite until #514 isolation is merged and the tested branch uses it; execute checks with temporary HOME, isolated toolkit/config roots, and sentinel path checks.
- Do not edit `harness-matrix.md` or instructions-only code/docs; avoid shared TUI app/composition primitives and generic test fixtures.

## Critical Review

Build-ready reconciliation: preserve the source specification's observational inventory and local-only unknown-origin rules; apply #513's real-home isolation precedent before any full-suite run; apply #337's explicit doctor confirmation/fix-action precedent; apply #231's filesystem doctor scan context and #360's unlisted row-universe contract. The PR for #514 is a hard prerequisite for ordinary/full pytest commands, because its startup isolation prevents contamination of the real user library. #517 is a separate CWD/status-bar change; reconcile its branch before final integration, but it is not a safety prerequisite to isolated tests after #514.

- **Ownership precedence:** local Pi packages remain distinct from npm/store-owned records; collisions preserve lock ownership and package metadata (Task 2).
- **Discovery boundaries:** bounded scans include supported directories, symlinks, nested `SKILL.md`, and bundle roots; do not follow escaping/dangling symlinks; stable IDs avoid collisions (Task 3).
- **Lossless import:** only supported assets with an existing local lock representation are imported. Settings-only/unsupported values are reported and not imported; never rewrite Pi settings (Tasks 5–6).
- **Repair failure safety:** repair requires explicit `--repair` and confirmation; decline and `--no-fix` do not write; lock-write failure leaves source/settings unchanged; repeat repair is idempotent (Tasks 5–6).
- **Path selection and test isolation:** explicit home, environment override, default path, and #514 isolation are tested before a full suite; full suite runs in temporary HOME/config/toolkit roots and confirms real-home sentinels untouched (Tasks 1 and 7).
- **Visible-state evidence:** automated headless Textual grid tests assert filesystem-only skill/agent/command rows visibly carry untracked state and stable bundle identifiers; local Pi package origin appears in its rendered grid (Tasks 2–4).

These are implementation risks with testable mitigations, not unresolved product choices. Any discovered conflict with an existing schema or source-preservation guarantee must stop the affected repair path rather than weaken the acceptance criteria.

## File Map

- `src/agent_toolkit_cli/skill_paths.py` and `tests/test_skill_paths.py`: home-aware global skill lock path.
- `src/agent_toolkit_cli/pi_extension_inventory.py`, inventory tests, and Pi TUI state/grid: local package inventory and badge.
- `src/agent_toolkit_tui/skill_state.py`, `agent_state.py`, `command_state.py`, corresponding tests/widgets: filesystem union and unlisted display.
- `src/agent_toolkit_cli/skill_doctor.py`, `pi_extension_doctor.py`, doctor command modules and tests: audit and import repair.
- Relevant CLI/TUI reference documentation and help: origin, unlisted, and repair semantics.

## Tasks

### Task 1: Home-aware skill lock path

**Files:** `src/agent_toolkit_cli/skill_paths.py`, `tests/test_skill_paths.py`.

- [ ] Write tests for explicit global `home`, environment override precedence, and unchanged default behavior.
- [ ] Run focused tests under a temporary HOME; verify explicit-home case fails before implementation.
- [ ] Implement resolution in `skill_paths.py` so explicit `home` scopes the default global lock while the documented environment override retains precedence.
- [ ] Run `uv run pytest tests/test_skill_paths.py -q` after verifying #514 isolation has landed; otherwise invoke focused pytest only in an isolated temporary HOME/config/toolkit sandbox.

### Task 2: Pi local package inventory

- [ ] Add failing inventory tests for local file/directory package specs, local origin, and collision precedence with npm/store-owned entries.
- [ ] Run focused inventory tests and verify the local package case fails.
- [ ] Extend the inventory record origin type and settings package pass to classify local specs as `local-package` (untracked, not managed), retaining loaded/config metadata and current precedence.
- [ ] Update Pi row rendering/info to visibly distinguish local-package/untracked origin.
- [ ] Run inventory and Pi TUI tests.

### Task 3: Skill on-disk union and bundles

- [ ] Add failing row tests for unmanaged skill directories, symlinks, a parent bundle, nested `SKILL.md` entries, and duplicate/disambiguated identifiers.
- [ ] Run focused skill-state tests and verify filesystem-only entries are absent.
- [ ] Add bounded filesystem discovery under the skill library root, derive descriptions and cells using existing helpers, and merge discovered entries after lock-backed rows with `unlisted` state and untracked source metadata.
- [ ] Ensure bundle parent and nested skills are represented independently, using stable `bundle:skill` row identifiers where needed; do not recursively follow symlinks outside the scan root.
- [ ] Run skill state/grid tests and check existing locked rows remain unchanged.

### Task 4: Agent and command on-disk union

- [ ] Add failing state tests for on-disk agent files/directories and command `COMMAND.md` directories absent from locks.
- [ ] Run focused tests and verify these rows are absent.
- [ ] Extend the existing agent and command row builders to union lock rows with bounded filesystem discoveries; mark untracked rows `unlisted`, preserve source metadata, and leave actionable harness cells populated from existing adapter probes.
- [ ] Update origin/state legend or badges as needed.
- [ ] Run agent/command state and grid tests.

### Task 5: Skill doctor audit and safe repair

- [ ] Add failing doctor tests for unmanaged library skills, bundle sub-skills, report-only mode, declined prompt, explicit confirmed import, repeat repair, and lock-write failure without source mutation.
- [ ] Run focused doctor tests and verify missing findings/repair behavior.
- [ ] Extend skill doctor findings to report high-visibility unmanaged entries and attach an additive local-import fix action that preserves source content and existing bundle layout.
- [ ] Wire the explicit `--repair` option while retaining interactive confirmation and `--no-fix` precedence.
- [ ] Run skill doctor CLI and unit tests.

### Task 6: Pi-extension doctor audit and safe repair

- [ ] Write tests for on-disk local packages absent from lock, settings-only entries, `--no-fix`, repair without confirmation, decline, confirmed local import, repeat repair, collision, and lock-write failure.
- [ ] Verify each report-only/decline path leaves lock, source, and settings bytes unchanged; failure must not adopt an unrepresentable entry.
- [ ] Extend diagnosis to union supported on-disk local package records with lock entries; identify settings-only values but leave them unmanaged when lossless lock representation is unavailable.
- [ ] Add explicit `--repair` and separate confirmation for supported local imports; do not rewrite Pi settings or external assets.
- [ ] Run focused Pi-extension doctor/inventory tests in isolated runtime roots.

### Task 7: Documentation and full verification

- [ ] Document `unlisted` / local-package badges, discovery boundaries, and doctor report/repair behavior in skill, Pi-extension, CLI, and TUI references without touching instructions sections or `harness-matrix.md`.
- [ ] Run focused paths, inventory, state/grid, and doctor tests in isolated HOME/config/toolkit roots; run formatting/lint/type checks required for touched files.
- [ ] Re-read the issue, spec, plan, and #514 isolation changes. Run full `uv run pytest -q` only after #514 is merged and rebased; set disposable `HOME`, `XDG_CONFIG_HOME`, and agent/toolkit settings roots, seed sentinels inside the sandbox and outside it, then verify real user files unchanged and cleanup removes only allocated temporary roots.
- [ ] Keep automated headless Textual visible-state assertions as the TUI evidence gate (row IDs plus actual rendered unlisted/local-package cells); manual screenshot is unnecessary if the automated pilot proves visible cells.
- [ ] Record observed outputs under `assets/verification/515/`; do not merge or release from this issue PR.

## Self-review

All acceptance criteria map to Tasks 1–7. Each critical review risk above has named implementation and regression-test coverage. The plan preserves the existing per-kind architecture and prioritizes lossless observation over automatic adoption. Before coding, inspect current schemas and root/path helpers; adjust exact file/test anchors to repository state while preserving the specification.
