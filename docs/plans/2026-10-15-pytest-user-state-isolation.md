# Pytest User-State Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:executing-plans` or `superpowers:subagent-driven-development` to implement task-by-task.

**Goal:** Make ordinary pytest runs independent of the developer's real home, harness configuration, toolkit libraries, and installed assets.

**Architecture:** Bootstrap a unique temporary home and supported configuration roots at pytest startup, before application imports and test collection. Add regression coverage for both bootstrap routing and a real global install path, while preserving explicit per-test environment overrides and the existing Git environment guard.

**Tech Stack:** Python 3.13, pytest, pytest fixtures, `tempfile`, `pathlib`, existing toolkit path helpers.

**Spec:** `docs/specs/2026-10-15-pytest-user-state-isolation.md` (issue #513)

## Global Constraints

- Do not modify or clean existing developer-home assets or settings.
- Do not change production path APIs or introduce dependencies.
- Default sandbox must be established before home-dependent application imports.
- Cleanup must target only the exact temporary directory allocated by this test process.
- Keep all `GIT_*` variables scrubbed as currently required by #209.
- Inventory supported toolkit and harness path overrides before setting values; no inherited root override may escape the sandbox.

## Review Focus

- Import-time module constants or test collection evaluate real home paths before the sandbox is installed.
- A supported root override is omitted, inherited, or misdirected, allowing a global asset kind to escape.
- The bootstrap clobbers intentional test-local `HOME` overrides or changes explicit path assertions unexpectedly.
- Cleanup deletes a pre-existing path or shared data rather than only the allocated temporary root.
- Parallel test processes share mutable home/library paths.

---

### Task 1: Audit home-derived paths and implement early test sandbox

**Files:**
- Modify: `tests/conftest.py`
- Test: `tests/test_test_home_isolation.py`

**Interfaces:**
- Produces a private startup helper which allocates and configures sandbox paths before application imports.
- Preserves explicit per-test environment changes made later through pytest monkeypatch.

- [x] **Step 1: Write failing startup-isolation test.** In a subprocess with a synthetic outer `HOME`, run pytest against a minimal probe test and a temporary conftest/plugin bootstrap entrypoint. Assert `Path.home()`, toolkit global roots for all supported kinds, and supported harness configuration roots resolve under the newly allocated test sandbox, not the outer home. Seed sentinel settings/library data and assert bytes are unchanged. Avoid directly importing the repository's conftest in the probe because its current top-level CLI import can cache home-derived paths before the helper runs.
- [x] **Step 2: Run the focused test and verify it fails** because startup currently leaves process home and configuration roots unchanged.
- [x] **Step 3: Inventory root variables and home-derived module state.** Search path facades, catalogs, adapters, and config modules for `Path.home()`, `HOME`, XDG, and harness-specific overrides; record exact variables in the helper's tests/docstring. Move `from agent_toolkit_cli.cli import main` and any other home-sensitive imports below sandbox initialization, or lazily import them in fixtures/functions, so no project import precedes the boundary.
- [x] **Step 4: Implement startup sandbox.** Allocate one `tempfile.mkdtemp` root per pytest process; set `HOME`, `XDG_CONFIG_HOME`, supported harness-home overrides, and each supported toolkit root to isolated descendants; remove/replace inherited overrides that escape. Register a pytest shutdown hook to restore the original environment and remove only this root. Do not share writable roots across workers if xdist is supported/configured.
- [x] **Step 5: Run focused tests and verify pass.** Run `uv run pytest -q tests/test_test_home_isolation.py`; verify sentinels unchanged, roots isolated, environment restoration and exact-root cleanup asserted.
- [x] **Step 6: Commit** the sandbox and regression test.

### Task 2: Cover the original global Pi install leak

**Files:**
- Modify: `tests/test_cli/test_skill_install_engine.py`
- Modify: `tests/conftest.py` (only if fixture docs need updating)

**Interfaces:**
- Consumes the default startup sandbox from Task 1.
- Keeps `test_global_pi_uses_standard_projection` behavior and assertion names where practical.

- [x] **Step 1: Strengthen regression assertions.** Assert the global canonical asset directory and global skills lock are under the test sandbox, as is the `.agents/skills` projection, and assert the lock contains only the expected test slug/source.
- [x] **Step 2: Run that test and verify it passes** under isolated roots; additionally run it in a subprocess with a synthetic outer-home sentinel and verify outer state unchanged.
- [x] **Step 3: Remove redundant per-test workaround only if safe.** Keep the explicit projection catalog patch needed by the test, but do not rely on it as library isolation.
- [x] **Step 4: Document default isolation and safe test-local overrides** in conftest docstring/comments.
- [x] **Step 5: Run focused checks.** Run `uv run pytest -q tests/test_test_home_isolation.py tests/test_cli/test_skill_install_engine.py` and inspect test-created outputs for correct roots.
- [x] **Step 6: Commit** the regression assertions and documentation.

### Task 3: Verify whole suite and issue gate

**Files:**
- Modify only additional test files if the audit reveals direct home reads that violate the new boundary.

**Interfaces:**
- Consumes the startup sandbox and global Pi regression test.

- [x] **Step 1: Audit home-sensitive tests** against the new default and update tests that expected the host home to instead assert the sandbox home or use explicit synthetic homes.
- [x] **Step 2: Run focused regression tests** and verify no test-created state appears outside the sandbox.
- [x] **Step 3: Run full suite** with `uv run pytest -q`; verify exit 0 and no tests access real agent settings/assets. If host contamination is observed, stop and report without cleanup.
- [x] **Step 4: Verify preservation.** Compare outer synthetic-home sentinel tree before/after, ensure bootstrap cleanup removes only its own path, and run `git status --short` to check for accidental artifacts.
- [x] **Step 5: Commit any remaining targeted fixes** and report exact verification results.

## Execution Notes

- Use Worktrunk issue branch `fix/513-pytest-real-library-contamination` based on current `origin/main`; worktree path `.worktrees/fix-513-pytest-real-library-contamination`.
- Never run test commands in the source checkout or against the real home. Before every test invocation, confirm cwd is this issue worktree and the pytest bootstrap is present. Initial test-driven red may use only the focused synthetic-home subprocess test.
