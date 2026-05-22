# Plan — TUI `--version` flag (#211)

Spec: `docs/superpowers/specs/2026-05-22-tui-version-flag-design.md`.

## Tasks

1. **Patch `src/agent_toolkit_tui/app.py` `main()`** to intercept `--version` / `-V` as the first argv token. Print `f"agent-toolkit-tui, version {__version__}"` and return 0 without constructing `TUIApp`. Import `sys` at function scope to keep the module-level imports unchanged.

2. **Add `tests/test_tui/test_version_flag.py`** with three cases:
   - `--version` via subprocess → exit 0, stdout matches `^agent-toolkit-tui, version \S+\n$`.
   - `-V` via subprocess → identical.
   - Direct `main()` call with no argv → calls `TUIApp.run` (monkeypatched). Verifies the early-exit path doesn't trigger when no version flag is present.

3. **Run `uv run pytest -q`** — must stay green, including the new tests.

## Risk / non-risk

- No new dependency.
- No change to TUI runtime behaviour for any non-version invocation.
- Version source already proven by `tests/test_tui/test_version.py`.

## Done when

- `uv run agent-toolkit-tui --version` and `-V` both print and exit 0.
- New test file passes.
- Full pytest run green.
