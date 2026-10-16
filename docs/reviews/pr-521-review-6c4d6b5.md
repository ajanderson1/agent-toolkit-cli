# PR #521 Review — Issue #499

- Reviewed head: `6c4d6b5ca61ce7ef253834eebd483bf792d93c64`
- Base: `28dc3536eee9346d85b101c3e2eb10085275efbb`
- Review worktree: `review/521-global-instructions-20261016`
- Scope: global instructions pointers and scope-aware verdicts for Codex/OpenCode/Pi; native project-file preservation; unmanaged foreign pointers; TUI instruction state/composition/help/grid consistency.

## Findings

No actionable defects found in the reviewed scope.

## Review notes

- Project matrix rows remain `native` for Codex, OpenCode, and Pi; global rows report `symlink` and identify the corresponding global AGENTS.md slots. Install defaults and TUI actionable columns consume the scope-specific matrix.
- The new global pointer templates cover Codex (`~/.codex/AGENTS.md`), OpenCode (`~/.config/opencode/AGENTS.md`), and Pi (`~/.pi/agent/AGENTS.md`). Project slots for these readers remain absent, so installs do not replace their native project-root `AGENTS.md`.
- Doctor treats the known legacy `~/.conventions/CONVENTIONS.md` global symlink as report-only when its slot is unmanaged; it does not offer an adoption fix or write a lock. Existing foreign symlink and real-file protection in install/uninstall remains intact.
- TUI instruction composition, state building, grid columns, and standard-column help pass the focused checks for scope-aware behavior.

## Verification

- `uv run pytest -q tests/test_instructions_matrix.py tests/test_cli/test_instructions_cli.py tests/test_cli/test_instructions_adapters/test_dispatcher.py tests/test_cli/test_instructions_adapters/test_symlink.py tests/test_tui/test_composition.py tests/test_tui/test_column_info.py tests/test_tui/test_instruction_grid.py tests/test_tui/test_instruction_grid_groups.py tests/test_tui/test_instruction_state.py tests/test_tui/test_instruction_grid_global_indicator.py` — 174 passed.
- `uv build` — source distribution and wheel built successfully.
- `git diff --check BASE...HEAD` — clean.
- Full test suite intentionally not run, as requested by coordinator.

## Boundaries

No real user assets were touched. Verification used temporary test homes. The first focused pytest invocation referenced an incorrect test path and ran no tests; the corrected command above completed successfully. The worktree is clean apart from this review report.
