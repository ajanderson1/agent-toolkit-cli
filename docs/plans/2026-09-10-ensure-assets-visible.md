Issue: #515
# Ensure Untracked Assets Remain Visible — Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox syntax.

**Goal:** Make local and unmanaged assets visible, auditable, and safely importable without altering user data.
**Architecture:** Extend existing per-kind discovery and row builders; keep lockfiles as managed-state authority and treat filesystem/config observations as untracked rows. Doctor repair is an explicit, confirmed local import, with existing repair patterns and schemas.
**Tech Stack:** Python 3.12+, Click, Textual, pytest.
**Spec:** `docs/superpowers/specs/2026-09-10-ensure-assets-visible.md`

## Global Constraints
- Inventory and `--no-fix` paths are read-only.
- Repair is explicit, confirmed, additive, local when upstream is unknown, and lossless.
- No new dependencies or guessed remote sources.

## Review Focus
- Local Pi package spec can collide with an existing npm or store-owned slug; preserve established precedence and expose package-specific loaded state (test in inventory task).
- Bundle root can itself be a skill and contain nested skills; expose both without duplicate/unstable IDs (test in skill discovery task).
- Filesystem symlinks may escape inventory roots or dangle; discover without following unsafe recursive paths (test in each applicable scanner task).
- Lock write failure during repair must leave source intact and report failure (test in doctor repair task).
- Custom home and default/environment lock paths must agree with canonical path semantics (test in path task).

## File Map
- `src/agent_toolkit_cli/skill_paths.py`, `tests/test_skill_paths.py`: home-aware global lock path.
- `src/agent_toolkit_cli/pi_extension_inventory.py`, related inventory tests and Pi TUI state/grid: local package inventory and badge.
- `src/agent_toolkit_tui/skill_state.py`, `agent_state.py`, `command_state.py`, corresponding TUI tests/widgets: on-disk union and unlisted display.
- `src/agent_toolkit_cli/skill_doctor.py`, `pi_extension_doctor.py`, doctor command modules and tests: audit and import repair.
- Relevant CLI/TUI docs/help: describe origin and repair semantics.

## Tasks

### Task 1: Home-aware skill lock path
- [ ] Add a failing test proving global `lock_file_path(scope="global", home=tmp_path)` uses the sandbox lock path while default/environment behavior remains stable.
- [ ] Run the focused test and verify it fails against current behavior.
- [ ] Implement home-aware resolution in `skill_paths.py`, preserving environment override precedence and canonical filename.
- [ ] Run `uv run pytest tests/test_skill_paths.py -q`.

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
- [ ] Ensure bundle parent and nested skills are represented independently, using stable `bundle:skill` row identifiers where needed.
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
- [ ] Add failing doctor tests for local packages/settings entries and filesystem packages absent from the lock, plus `--no-fix`, decline, import, idempotency, and lock-write failure.
- [ ] Run focused Pi doctor tests and verify orphaned local assets are not imported.
- [ ] Extend diagnosis to union supported on-disk package and settings inventory with lock entries; report source/config path clearly.
- [ ] Add explicit confirmed `--repair` import of supported assets as local lock entries without rewriting unrelated Pi settings; report settings-only assets if they cannot be represented losslessly.
- [ ] Run Pi-extension doctor and inventory tests.

### Task 7: Documentation and full verification
- [ ] Document `unlisted` / local-package badges and doctor `--repair` behavior in the existing CLI/TUI reference.
- [ ] Run focused path, inventory, state/grid, and doctor suites.
- [ ] Run `uv run pytest -q` and record the result.

## Self-review

All acceptance criteria map to Tasks 1–7. The five highest-risk input classes each have a named regression test in the owning task. The implementation retains current per-kind architecture and prioritizes lossless observation over automatic adoption. Before coding, inspect current schemas and root/path helpers; adjust exact file/test anchors to repository state while preserving these requirements.
