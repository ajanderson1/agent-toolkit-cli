# Plan — skill push/update/reset/doctor scope-default parity (#220)

**Spec:** [`2026-05-22-skill-scope-defaults-parity-design.md`](../specs/2026-05-22-skill-scope-defaults-parity-design.md)

Small, mechanical change. TDD: red tests first, then the one-line fix per command, then green.

## Task 1 — Add four red regression tests (pre-fix)

Add one test per command file, modelled on `tests/test_cli/test_cli_skill_list.py::test_skill_list_no_flag_outside_project_shows_global` (the #216 pattern).

| File | New test |
|---|---|
| `tests/test_cli/test_cli_skill_push.py` | `test_push_no_flag_outside_project_uses_global` |
| `tests/test_cli/test_cli_skill_update.py` | `test_update_no_flag_outside_project_uses_global` |
| `tests/test_cli/test_cli_skill_reset.py` | `test_reset_no_flag_outside_project_uses_global` |
| `tests/test_cli/test_cli_skill_doctor.py` | `test_doctor_no_flag_outside_project_uses_global` |

Each test:

1. Add a skill at global scope (`skill add`, no `-g` needed — that's global by default).
2. Invoke the verb from a non-project dir via `--project <not-a-project>`, with no `-g` / `-p` flag.
3. Assert the output is **not** the "not in lock" / "no skills" sentinel.
4. Asset positive: a slug-bearing line (e.g. `demo: clean`, `demo: reset to <sha>`, or for doctor `✓ all clean` / a finding mentioning `demo`).

**Run them first** to confirm they fail with the current code (i.e. `<slug>: not in lock`). Capture output to `assets/verification/220/red-tests.log`.

**Acceptance for task 1:** all four new tests fail with `not in lock` or equivalent against unchanged source.

## Task 2 — Apply the four call-site edits

Add `read_only=True` to the `scope_and_roots(...)` call in each command:

| File | Line | Change |
|---|---|---|
| `src/agent_toolkit_cli/commands/skill/push_cmd.py` | 33–37 | append `read_only=True,` |
| `src/agent_toolkit_cli/commands/skill/update_cmd.py` | 38–42 | append `read_only=True,` |
| `src/agent_toolkit_cli/commands/skill/reset_cmd.py` | 44–48 | append `read_only=True,` |
| `src/agent_toolkit_cli/commands/skill/doctor_cmd.py` | 26–29 | append `read_only=True,` |

No other source changes. No helper changes.

**Acceptance for task 2:** edits land cleanly; no other lines moved.

## Task 3 — Run full suite, confirm green

```bash
uv run pytest -q
```

Capture output to `assets/verification/220/preflight-pytest.log`. Existing 339 tests + 4 new tests should all pass (343 passed, 2 skipped).

**Acceptance for task 3:** suite exits 0 with all new tests green and zero regressions.

## Task 4 — Smoke-test the bug repro in a real shell

Reproduce the issue's exact repro using the worktree's installed binary in an isolated tmp dir, capture output to `assets/verification/220/manual-repro.log`. This is the verify-step artifact for the PR body — concrete proof the fix works on the actual user-facing path.

```bash
TMP=$(mktemp -d)
cd "$TMP"
uv --project /path/to/worktree run agent-toolkit-cli skill push find-skills
# expected (before fix): "find-skills: not in lock"
# expected (after fix):  "find-skills: clean — nothing to push" (or "pushed")
```

Same for `update` and one of the four.

**Acceptance for task 4:** none of the four verbs prints `not in lock` for a slug that exists in the global lock.

## Out of scope (don't do)

- Don't rename `read_only` → `infer_scope`. Tracked separately.
- Don't add a "no project skills here" hint to the four affected verbs. Tracked separately.
- Don't touch monorepo / copy-mode logic. Don't touch `_common.py`.
- Don't touch any test file outside `tests/test_cli/test_cli_skill_{push,update,reset,doctor}.py`.

## Commit shape

One commit per task is overkill for a 4-line change. Plan:

- **Commit A:** all four red tests (Task 1). Conventional commit type `test`.
- **Commit B:** the four call-site fixes (Task 2). Conventional commit type `fix`, with `Closes #220` in body.

Two-commit shape lets the PR diff tell the TDD story: tests first, then the minimal fix that turns them green.
