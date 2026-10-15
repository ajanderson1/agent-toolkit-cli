Issue: #513

# Pytest User-State Isolation Spec

## Intent

Prevent default pytest runs from reading developer agent configuration or creating, updating, or removing assets in the developer's home directory. Today, tests that exercise global install paths can pass a temporary `HOME` only to subprocesses while Python code resolves its library from the real process environment. Other tests and TUI startup can also resolve real harness settings through `Path.home()`.

## Goals

- Establish a disposable per-test-run user-state root before project test modules import application code.
- Route home-based harness paths, XDG configuration, toolkit library roots, and supported harness-home overrides to that root by default.
- Preserve explicit per-test overrides such as `monkeypatch.setenv("HOME", ...)` and the existing `git_sandbox` environment contract.
- Keep the global Pi projection test exercising the actual global install path while placing its canonical asset, lock, and projection under the disposable root.
- Add an isolation regression test using a synthetic outer home and sentinel data, proving test startup redirects paths and does not change the sentinels.
- Document the boundary in `tests/conftest.py`; preserve existing inherited `GIT_*` scrubbing.
- Keep all test-run state outside the checkout and clean up only the exact temporary root created by the test harness.

## Non-goals

- Do not change production path-resolution semantics or public APIs.
- Do not clean, migrate, or rewrite the developer's existing agent library, lockfiles, or settings.
- Do not prohibit tests from intentionally testing home-path semantics; they must do so against synthetic homes.
- Do not add a new test framework or dependency.
- Do not treat existing untracked pytest artifacts as safe to remove based only on their names.

## Design

Put the default sandbox boundary in `tests/conftest.py`, the earliest project-owned pytest entry point. Initialize a unique temporary home before importing application modules or collecting test modules, because autouse fixtures run too late to protect import-time configuration reads. Save and restore the environment variables changed by this bootstrap. At pytest shutdown, remove only the exact temporary directory created for that run; avoid glob-based cleanup or touching any path derived from the real home.

Set `HOME` and `XDG_CONFIG_HOME` to locations inside the sandbox, and set supported harness-specific home/config overrides (for example `CODEX_HOME`, `CLAUDE_CONFIG_DIR`, and equivalent variables used by the asset catalogs) to sandbox paths. Remove inherited toolkit library-root overrides that could direct assets outside the sandbox, then set the supported toolkit roots to sandbox locations. The implementation must first inventory the repository's supported overrides and use the actual variable names; it must not guess a single cross-kind override exists. Keep platform-specific environment handling explicit and testable.

The sandbox bootstrap must happen before imports with home-derived module constants. If pytest's conftest import order makes that impossible while retaining current top-level imports, move those application imports into fixtures or test functions after environment setup. Do not mask the issue by adding only another fixture to the one known test.

The per-test `git_sandbox` remains a nested Git repository fixture with its own fake `HOME` in the subprocess environment. Tests that call Python APIs directly should either use the default session sandbox or explicitly patch process environment using pytest's reversible monkeypatch facilities. Do not globally force all tests to share the `git_sandbox`'s per-test environment.

## Acceptance Criteria

1. With a synthetic outer `HOME`, invoking ordinary pytest startup before collection redirects `Path.home()` and supported harness/library roots to an isolated temporary location.
2. A regression test seeds a sentinel settings file and sentinel asset under the synthetic outer home, exercises the test bootstrap and a representative global skill install, and verifies the sentinel bytes and directory contents remain unchanged.
3. `test_global_pi_uses_standard_projection` asserts its canonical directory, global lock, and `.agents/skills` projection are all under the test sandbox and still verifies the expected symlink behavior.
4. The test harness does not inherit host-specific toolkit root overrides that escape isolation; intentional test-local overrides continue to work.
5. Existing tests that explicitly patch `HOME` continue to pass, and inherited `GIT_*` variables remain stripped as before.
6. The default test suite's focused isolation checks and full test suite run without reading developer Pi settings or writing into the developer's real agent directories.
7. Shutdown restores the parent process environment and deletes only the harness-created temporary directory; tests do not delete any pre-existing home data.
8. `tests/conftest.py` documents the default isolation guarantee and the safe pattern for tests that need home-specific behavior.

## Risks and Decisions

- **Import timing:** top-level imports in conftest or test modules may evaluate home-dependent defaults before fixtures. Establish the boundary at conftest load time and defer dependent imports as needed.
- **Override inventory:** different asset kinds may have distinct root variables or import-time catalogs. Audit source code and the test suite; do not silently omit one kind or override unrelated variables.
- **Parallel pytest workers:** each worker/run must not share a writable sandbox if parallel execution is supported. Prefer a unique root per pytest process; if xdist is installed/configured, include worker identity or create per-worker homes.
- **Temporary directory cleanup:** cleanup is allowed only for a path allocated by this run and stored directly by the bootstrap; no path expansion, globbing, or fallback to the host home.
- **Tests asserting the host home:** update assertions to use the sandbox path or explicitly pass a synthetic home; do not weaken the isolation boundary for them.

## Authorization Boundary

This issue authorizes prevention and verification of future contamination only. It does not authorize deleting the `pi-global-*` entries or modifying existing user lock/settings files discovered during investigation. Any remediation of existing assets requires separate provenance review and authorization.
