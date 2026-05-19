# Design — doctor crashes on broken TOML under codex (#122)

## Problem

`agent-toolkit-cli doctor` raises an uncaught `tomlkit.exceptions.UnexpectedCharError`
when `~/.codex/config.toml` is malformed. The exception bubbles out of the codex
adapter (`harness_adapters/codex.py::_read`, called by `list_installed` /
`entry_drift`) into the `doctor.mcps` group, aborting the entire `doctor` run.

Doctor's purpose is to *report* problems, not be one. The crash also suppresses
every other group that would otherwise run (since `doctor` exits 1 on the first
unhandled exception).

## Goal

When the codex config file exists but cannot be parsed, the `mcps` group emits a
`FAIL`-status finding citing the file path and the parse error, and the rest of
the doctor run continues normally.

## Scope

- `src/agent_toolkit_cli/doctor/mcps.py`: wrap the adapter calls
  (`list_installed`, `entry_drift`) in a `try / except tomlkit.exceptions.TOMLKitError`.
- Convert the caught error into a `GroupResult(status=FAIL, …)` with one finding
  formatted as `codex config <path>: TOML parse error: <message>`.
- No changes to adapter internals — the adapter contract is "raise on bad input";
  doctor is the layer that converts raises into reports.
- Doctor's `Status.FAIL` plumbing already exists (`result.py`), so the group
  result needs no new infrastructure.

## Non-goals

- We do not "fix" the broken TOML automatically.
- We do not change `link`/`unlink`/`fix` behaviour — only the read-only doctor path.
- We do not silence `TOMLKitError` everywhere; only in the doctor read path.

## Test plan

Unit test in `tests/test_doctor_mcps.py`:

- Seed a toolkit with one allow-listed MCP; write `~/.codex/config.toml` with
  invalid TOML (`"{{{not toml\n"`).
- Run `doctor.mcps.run(harness="codex", scope="user", …)`.
- Assert: `result.status == Status.FAIL`, no exception raised, and the finding
  text contains both the file path and a parse-error marker.

## Acceptance

- `uv run pytest -q` green.
- New test fails on `main`, passes after the fix.
- Manual repro from the issue (`echo "{{{not toml" > ~/.codex/config.toml &&
  agent-toolkit-cli doctor`) no longer prints a traceback; emits a FAIL finding
  and continues to other groups.

Closes #122.
