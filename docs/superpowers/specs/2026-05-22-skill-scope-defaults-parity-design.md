# Design — skill push/update/reset/doctor scope-default parity (#220)

**Status:** draft for `--auto` flow
**Issue:** [#220](https://github.com/ajanderson1/agent-toolkit-cli/issues/220)
**Type:** `type:fix` · `priority:med`
**Predecessor:** [PR #216](https://github.com/ajanderson1/agent-toolkit-cli/pull/216) (closes #210) — same fix shape applied to `list` and `status`.

## Problem

`commands/skill/_common.py:scope_and_roots()` learned a `read_only=True` kwarg in PR #216 that means "fall back to global scope when no `<cwd>/skills-lock.json` exists." Only `list_cmd.py` and `status_cmd.py` pass it.

Outside a project directory (cwd has no `skills-lock.json`), `push`, `update`, `reset`, and `doctor` still default to project scope, then read an empty lock and return `<slug>: not in lock` (or no-op) — even though the skill is in the global lock at `~/.agent-toolkit/skills-lock.json`.

This is a parity bug: a skill installed with `skill add` (defaults to global) cannot be operated on by these verbs without `-g`. The mental model `add` sets up — "no flag = act on whichever lock matches my cwd" — breaks for everything that mutates.

## Goals

1. `skill push <slug>` outside a project dir reads the global lock when no project lock exists.
2. Same for `skill update`, `skill reset`, `skill doctor`.
3. `-p` continues to force project scope and prints the existing `no project skills here` hint when no project lock exists.
4. A regression test for each command mirrors the test pattern landed by #216.
5. Tests that already pass (push monorepo, update monorepo, reset, doctor) stay green.

## Non-goals

- **Renaming `read_only` → `infer_scope`.** Tempting (the issue suggests it) but out of scope. The parameter name is internal; renaming touches more sites and isn't required to fix the bug. Track separately if desired.
- **Improving the `not in lock` error message.** Mentioned as an alternative in the issue. The real fix removes the case for installed-but-wrong-scope skills, so the message is fine as-is for the legitimately-not-in-lock case.
- **Auto-merge UX, monorepo behaviour, or any other `skill` subcommand semantics.** Strictly a scope-default fix.

## Approach

Four-line behavioural change. In each command's `scope_and_roots()` call, add `read_only=True`:

```python
# push_cmd.py:33, update_cmd.py:38, reset_cmd.py:44, doctor_cmd.py:26
scope, home, project_root = scope_and_roots(
    global_,
    project_flag,
    ctx.obj.get("project_root") if ctx.obj else None,
    read_only=True,                # <-- new
)
```

The helper already implements the fallback correctly (#216). No changes to `_common.py`. No new tests for the helper itself — it's covered transitively.

### Why this is safe

- `read_only=True` only changes behaviour when **both** `-g` and `-p` are unset AND no `<cwd>/skills-lock.json` exists. In every other situation it returns the same scope as before.
- Inside a project dir (the normal case), there's a `skills-lock.json` at the project root, so all four commands behave exactly as today.
- `-g` and `-p` explicit forms are untouched.
- The flag's misleading name (`read_only`) does **not** imply read-only behaviour at runtime. It is only a signal to `scope_and_roots()`. Inside `_common.py`, the docstring already calls this out; the spec acknowledges the misnomer and explicitly declines to rename in this PR.

### Error-message surface

`-p` outside a project dir already prints `(no project skills here. Run "skill list -g" for the global library, or "-p" from inside a project)` via `list_cmd._emit_table`. The other four commands do not currently emit that hint — they emit `<slug>: not in lock` from the loop.

**Decision: do not add a parallel hint** in this PR. Rationale:

- `list` emits a single "is this empty?" message; the others iterate per-slug. A "no project skills here" header before each slug's `not in lock` would be noisy.
- The fix removes the **silent fallback to empty project scope** for the common case (no flag). Users who explicitly pass `-p` to a non-project dir get the existing `not in lock` per slug, which is at least factually correct.
- A nicer hint is a follow-up improvement, not a regression in this PR.

## Out-of-scope but acknowledged

- **Issue #221** (`skill push` writes straight to main with no PR branch) is unrelated and tracked separately.
- The `read_only` → `infer_scope` rename would clarify intent. File as a follow-up chore if desired; do not block this PR on it.

## Acceptance

Mirrors the issue's acceptance criteria:

- [x] `skill push <slug>` outside a project dir resolves the global lock when no project lock exists.
- [x] Same for `skill update`, `skill reset`, `skill doctor`.
- [x] `-p` continues to force project scope (and still prints the `no project skills here` hint via `list`, where present).
- [x] Regression test per command, modelled on the #216 test pattern (`test_skill_list_no_flag_outside_project_shows_global`).
- [x] Existing test suite stays green (`uv run pytest -q`).

## Test plan

Four new tests, one per file, in the existing `tests/test_cli/test_cli_skill_<name>.py` modules:

| File | Test name | Shape |
|---|---|---|
| `test_cli_skill_push.py` | `test_push_no_flag_outside_project_uses_global` | add at global → push from non-project dir → expect `<slug>: clean` or `pushed`, **not** `not in lock` |
| `test_cli_skill_update.py` | `test_update_no_flag_outside_project_uses_global` | add at global → update from non-project dir → expect `<slug>: updated` (or `(no skills)` if nothing changed), **not** `not in lock` |
| `test_cli_skill_reset.py` | `test_reset_no_flag_outside_project_uses_global` | add at global → reset from non-project dir → expect `<slug>: reset to <sha>`, **not** `not in lock` |
| `test_cli_skill_doctor.py` | `test_doctor_no_flag_outside_project_uses_global` | add at global → doctor from non-project dir → expect `✓ all clean` or a global-scoped finding, **not** `(no skills)` |

Each test uses the same fixtures as the existing tests in the file: `git_sandbox`, `tmp_path`, `monkeypatch` with `AGENT_TOOLKIT_SKILLS_ROOT`. Invocation uses `--project <not-a-project-dir>` to simulate "running from outside a project." Pattern stolen verbatim from `tests/test_cli/test_cli_skill_list.py::test_skill_list_no_flag_outside_project_shows_global`.

## Risk

Near-zero. The behavioural change is gated by an existing helper flag that already has the right semantics. The four call sites are mechanical edits.
