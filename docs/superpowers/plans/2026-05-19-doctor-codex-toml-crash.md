# Plan — doctor codex TOML crash (#122)

## Task 1 — Failing test

Add `test_doctor_mcps_fail_on_unparseable_codex_toml` to
`tests/test_doctor_mcps.py`:

- Seed toolkit + allow-list (`context7`).
- Write `~/.codex/config.toml` = `"{{{not toml\n"` (invalid TOML).
- Call `doctor.mcps.run(...)`; assert no exception, `result.status == Status.FAIL`,
  and a finding mentioning the path and "parse" / "TOML".

Expected initial state: test FAILS (current code raises `UnexpectedCharError`).

## Task 2 — Wrap adapter reads in `doctor/mcps.py`

In `src/agent_toolkit_cli/doctor/mcps.py::run`:

1. Import `tomlkit.exceptions` lazily inside the try-block (avoids new top-level
   coupling; tomlkit is already a transitive dep).
2. Wrap the block that calls `adapter.list_installed(...)` and the per-entry
   `adapter.entry_drift(...)` in `try/except tomlkit.exceptions.TOMLKitError as exc`.
3. On catch:
   - Resolve the target path via `getattr(adapter, "config_target", lambda *a: None)(scope, project_root)`
     so non-codex adapters that don't expose `config_target` still degrade
     gracefully (today only codex has the issue, but the doctor layer should
     not assume).
   - Append finding: `f"{harness}: config {target}: TOML parse error: {exc}"`.
   - Return `GroupResult(name="mcps", status=Status.FAIL, summary="config unparseable", findings=findings)`.

## Task 3 — Verify test passes; full suite green

- `uv run pytest -q tests/test_doctor_mcps.py` green.
- `uv run pytest -q` full suite green.

## Task 4 — Manual smoke (optional, recorded in flow.log)

`agent-toolkit-cli doctor --help` to confirm the entry point still imports.
(We will not corrupt the real `~/.codex/config.toml` during pre-flight.)
