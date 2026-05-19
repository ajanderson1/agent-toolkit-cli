# Spec — doctor --strict flag (issue #124)

## Problem

`agent-toolkit-cli doctor --exit-code` exits 0 when the worst status is `WARN`.
Only `FAIL` produces exit 1. The flag name suggests "fail on any problem" but
the contract is "fail only on the most severe class". A CI gate built on
`--exit-code` will silently pass `WARN` states (e.g. fresh sandbox HOME with
many unlinked assets).

Reference: `src/agent_toolkit_cli/commands/doctor.py:~101`:

```python
if use_exit_code and worst == Status.FAIL:
    raise SystemExit(1)
```

## Decision

**Additive, non-breaking.** Keep `--exit-code` semantics unchanged (trip on
`FAIL` only) and add a new `--strict` flag that also trips on `WARN`.
Document both clearly in the help text.

Why additive: any existing CI that relies on `--exit-code` keeps working. The
new `--strict` flag is opt-in for callers who want WARN-as-failure.

Rejected: renaming `--exit-code` or changing its behaviour — breaking and
would silently flip CI semantics for any downstream consumer.

## Behaviour

| Flags                       | Exit on OK | Exit on WARN | Exit on FAIL |
|-----------------------------|------------|--------------|--------------|
| (none)                      | 0          | 0            | 0            |
| `--exit-code`               | 0          | 0            | 1            |
| `--strict`                  | 0          | 1            | 1            |
| `--exit-code --strict`      | 0          | 1            | 1            |

`--strict` implies `--exit-code` — passing only `--strict` is sufficient.
Passing both is harmless; `--strict` dominates.

Applies to:
- Global doctor run (Step 92–102 in `doctor.py`).
- Per-resource diagnosis (slug branch, line ~84).

## Help text

```
--exit-code   Exit 1 if any FAIL (default: tripped by FAIL only).
--strict      Exit 1 if any WARN or FAIL. Implies --exit-code.
```

## Out of scope

- Touching `agent-toolkit-cli check --exit-code` (separate command, separate
  contract).
- Changing the existing `--exit-code` contract.

## Acceptance

1. `doctor --strict` against a tree whose worst is WARN exits 1.
2. `doctor --strict` against a clean tree exits 0.
3. `doctor --exit-code` against a tree whose worst is WARN still exits 0
   (preserves existing contract).
4. `doctor --exit-code` against a tree whose worst is FAIL exits 1
   (unchanged).
5. `doctor --strict` against a tree whose worst is FAIL exits 1.
6. Per-resource (`doctor <slug> --strict`) tripped by WARN.
7. `doctor --help` shows both flags with the table above's contract.

## Tests

Add `tests/test_doctor_strict_flag.py` exercising the table above using
`click.testing.CliRunner`. Reuse fixtures from `tests/test_doctor.py` /
`tests/test_doctor_groups.py` where they yield WARN/FAIL states. If no
WARN fixture exists, monkeypatch a single runner to return a WARN result.
