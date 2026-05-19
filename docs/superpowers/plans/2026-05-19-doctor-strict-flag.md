# Plan — doctor --strict flag (issue #124)

## Approach

Additive Click flag. Single source-file edit + new test file.

## Tasks

### 1. Add `--strict` flag to `doctor` command

File: `src/agent_toolkit_cli/commands/doctor.py`

- Add `@click.option("--strict", "strict", is_flag=True, help="Exit 1 on WARN or FAIL. Implies --exit-code.")`
- Update help for `--exit-code` to `"Exit 1 on FAIL only. See --strict for WARN-or-FAIL."`
- In the function body, derive the trip threshold:
  - `tripped_on_warn = strict`
  - `should_exit = (use_exit_code or strict)` and the worst-status comparison uses `Status.WARN` if `strict` else `Status.FAIL`.
- Apply same logic to both the per-resource branch (~line 84) and the global branch (~line 101).

Concretely after results computed:

```python
should_exit = use_exit_code or strict
threshold = Status.WARN if strict else Status.FAIL
status_order = {Status.OK: 0, Status.ADVISORY: 0, Status.WARN: 1, Status.FAIL: 2}
if should_exit and status_order[worst] >= status_order[threshold]:
    raise SystemExit(1)
```

(Or simpler: `if should_exit and worst in {Status.FAIL} | ({Status.WARN} if strict else set()): raise SystemExit(1)`.)

### 2. New test file

File: `tests/test_doctor_strict_flag.py`

Use `click.testing.CliRunner` and monkeypatching of `_run_global` to return synthetic `GroupResult` lists. Cover the truth table:

- OK worst + no flag → exit 0
- WARN worst + `--exit-code` → exit 0 (preserves contract)
- WARN worst + `--strict` → exit 1
- FAIL worst + `--exit-code` → exit 1
- FAIL worst + `--strict` → exit 1
- OK worst + `--strict` → exit 0
- Per-resource: monkeypatch `diagnose` to return WARN, `doctor <slug> --strict` → exit 1
- Per-resource: WARN + `--exit-code` only → exit 0

### 3. Verify existing tests still pass

Run `uv run pytest tests/test_doctor.py tests/test_doctor_groups.py` — `--exit-code` semantics unchanged.

### 4. Help-text sanity

`uv run agent-toolkit doctor --help` shows the two flags with the new copy.

## Validation

- `uv run ruff check .` clean
- `uv run pytest` green
- `uv run agent-toolkit doctor --help` output captured to verification artifacts
