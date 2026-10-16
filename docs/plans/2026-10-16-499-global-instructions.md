# Scope-Aware Global Instructions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Manage Codex/OpenCode/Pi global instructions without changing native project behavior.

**Architecture:** Add explicit global verdict metadata to the existing instructions matrix and scope selection to its parser. Add global-only symlink adapter cells and reuse existing reconciliation and pointer safety logic. Update instructions CLI and TUI consumers to distinguish scope.

**Tech Stack:** Python, Click, Textual, pytest, uv, Hatch.

**Spec:** docs/specs/2026-10-16-499-global-instructions.md

## Global Constraints

- PR only; no merge. Preserve foreign files and symlinks.
- Unmanaged stale conventions pointers are report-only.
- No test execution against real HOME/config/toolkit paths.
- Shared composition/column-help edits are instructions-only and explicitly approved; #515 confirmed no overlap.

## Review Focus

- Project AGENTS.md must never become a self-link (Task 1/2).
- Correct existing symlinks may traverse canonical symlink chains (Task 2).
- Dangling/indirect conventions targets remain detectable (Task 2).
- Packaged matrix must behave identically to source matrix (Task 3).
- Scope switching must not queue global-only operations at project scope (Task 3).

### Task 1: Scope-aware matrix and adapter contract

**Files:** instructions_matrix.py, instructions_adapters/symlink.py, docs/agent-toolkit/harness-matrix.md; tests/test_instructions_matrix.py and tests/test_cli/test_instructions_adapters/test_dispatcher.py. Paths under src/agent_toolkit_cli unless stated.

**Interfaces:** instructions_matrix_rows(scope: str = "project") -> list[dict[str, str]]; existing _pointer_path and get_adapter retain signatures; CELLS adds global-only codex/opencode/pi.

- [ ] Add tests asserting native project and symlink global verdicts for the three harnesses, exact global paths, and ValueError for project pointer paths.
- [ ] Run focused tests in verified isolation; record expected failure before edits.
- [ ] Add global verdict column to instructions table, parse it with project-compatible default, and add three adapter cells with empty project templates. Validate scope values.
- [ ] Run matrix and adapter tests; expect all pass, including existing real-file/foreign-link safety.
- [ ] Commit with Device trailer.

### Task 2: CLI install/list/status/doctor lifecycle

**Files:** src/agent_toolkit_cli/commands/instructions/{install_cmd,list_cmd,status_cmd,doctor_cmd}.py, instructions_install.py only if necessary; tests/test_cli/test_instructions_cli.py and new tests/test_cli/test_instructions_global_native.py.

**Interfaces:** list adds --scope project|global (default project); install validates scope verdict before lock writes; doctor findings retain fix_action=None for stale unmanaged links.

- [ ] Add parameterized lifecycle tests for three global pointers and project native rejection with unchanged lock/canonical. Add existing-correct chained pointer, real-file, and foreign-symlink preservation tests.
- [ ] Add stale unmanaged direct/indirect/dangling conventions-target tests asserting nonzero report, no prompt, unchanged symlink and lock; managed stale pointers must not produce duplicate findings.
- [ ] Run new tests and record expected failures.
- [ ] Make CLI verdict lookup scope-aware; add --scope list; extend unmanaged global symlink scan to report known-bad target without a fix action. Reuse adapter/reconciliation guards.
- [ ] Run instructions CLI/install/adapter tests; expect pass.
- [ ] Commit with Device trailer.

### Task 3: TUI scope semantics and delivery verification

**Files:** src/agent_toolkit_tui/instruction_state.py, widgets/instruction_grid.py; coordinated instructions-only functions in composition.py and column_info.py; instruction-specific tests plus coordinated instructions cases in test_composition.py/test_column_info.py.

**Interfaces:** instructions_nonstandard_main(selection=None, *, scope="project") returns scope-supported pointers; grid passes its active scope. Matrix consumer for standard coverage receives the current scope.

- [ ] Obtain shared-file authorization before edits.
- [ ] Add global actionable/project-native cell tests, scope-switch tests ensuring no project toggles for global-only adapters, and scope-specific help/coverage assertions.
- [ ] Run new tests, record failures, implement scope propagation without changing unrelated UI behavior, rerun and require pass.
- [ ] Notify #515 matrix/shared-file changes ready for reconciliation.
- [ ] Run isolated focused suite and full suite after safety prerequisite; record command/output and any pre-existing failures separately.
- [ ] Run uv build; inspect wheel packaged matrix and execute parser outside checkout, requiring all three global symlink/project-native verdicts.
- [ ] Commit with Device trailer; open PR with Closes #499, evidence and limitations; report exact head SHA to parent for independent review.

## Self-review

All acceptance criteria map to tasks 1-3. Execution is pre-authorized native inline; shared-file scope expansion is separately pending. No implementation or tests have run at plan creation.
