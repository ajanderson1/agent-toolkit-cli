# Validate the `<harness>` argument in `link` and `unlink`

**Issue:** [#9](https://github.com/ajanderson1/agent-toolkit-cli/issues/9) — *Decide: should `agent-toolkit link user conventions` error explicitly?*
**Decision recorded on issue:** option (c) — reject any unrecognised harness in all four commands.
**Date:** 2026-05-04

## Problem

`agent-toolkit link user <X>` and `agent-toolkit unlink user <X>` accept any string for `<X>`. When `<X>` is not one of `claude / codex / opencode / pi`, the command silently exits 0 with `Already in sync — 0 assets linked, nothing to change.` because every `(harness, kind)` lookup against `_USER_TARGETS` / `_PROJECT_TARGETS` returns `None`, and the projection loop has nothing to do.

Examples of strings that silently no-op today:

```
agent-toolkit link   user conventions
agent-toolkit link   user banana
agent-toolkit unlink user clude          # typo for claude
agent-toolkit diff   user xyzzy          # diff inherits link's behaviour
```

This is a UX trap. The user thinks the command worked; nothing happened.

`list` is **not** affected — its harness arg is a positional *filter* and unknown values already hit a clean error path (`list.py:124-129`).

## Decision (from issue #9)

Validate `<harness>` against the canonical set `(claude, codex, opencode, pi)` at the top of each command. Anything else exits with a non-zero status and an error message naming the valid harnesses. The validator is **generic** — it knows nothing about `conventions` or any other specific string. Conventions handling is out of scope for this package.

## Goals

1. `link`, `unlink`, `diff` reject unknown harness names with exit code 2 and a message matching the style already used by `list`.
2. The error message lists the four valid harnesses so the user can self-correct without reading docs.
3. Validation lives in **one place** — a single helper invoked by all three commands. No duplicated `if harness not in {...}` blocks across files.
4. `--dry-run` does not bypass validation. The check fires before any side effect.
5. Existing tests for the four commands still pass without modification — the validator is additive.

## Non-goals

- **No conventions handling.** Not even a hint. `conventions` trips the same generic error as any other unknown string.
- No new `--force` / override flag.
- No change to `list`'s existing validation (already correct).
- No change to bash dispatcher (`bin/agent-toolkit`) — PR-2 will retire that side anyway.

## Approach

Add a thin helper to `src/agent_toolkit_cli/commands/_link_lib.py`:

```python
ALL_HARNESSES = ("claude", "codex", "opencode", "pi")

def validate_harness(ctx: click.Context, harness: str) -> None:
    """Exit 2 with a clean error if harness is not recognised."""
    if harness not in ALL_HARNESSES:
        click.echo(
            f"unknown harness '{harness}' — expected one of: "
            + " ".join(ALL_HARNESSES),
            err=True,
        )
        ctx.exit(2)
```

Wire it in:

- `link.py` — first line inside the function body, before any mode/mutex resolution.
- `unlink.py` — same.
- `diff.py` — `diff` already validates `scope` via `Choice` and forwards `harness` to `link.invoke`, so the new validator in `link` will fire there. **No change needed in `diff.py`.**

Both `link.py` and `unlink.py` already use `click.Choice(["user", "project"])` for `scope`, so unknown scope is already rejected at parse time. We only need this for harness.

`ALL_HARNESSES` is already defined as a tuple in `_list_json.py:18`. We should re-export from `_link_lib.py` (or import it there) so there is exactly one source of truth.

## Tests

Add to `tests/test_cli_link.py`:
- `test_link_unknown_harness_exits_2_with_message` — `link user banana` exits 2, stderr contains "unknown harness 'banana'" and "claude codex opencode pi".
- `test_link_unknown_harness_does_not_touch_filesystem` — assert no symlinks created.
- `test_link_dry_run_unknown_harness_still_validates` — `--dry-run` still fires validator.

Add the same shape to `tests/test_cli_unlink.py`.

Add to `tests/test_cli_diff.py`:
- `test_diff_unknown_harness_exits_2` — confirms inheritance through `ctx.invoke(link, ...)`.

Add to `tests/test_link_lib.py`:
- `test_validate_harness_accepts_known` — all four harnesses pass.
- `test_validate_harness_rejects_unknown_with_message` — unit test of the helper.

## Affected files

| File | Change |
|---|---|
| `src/agent_toolkit_cli/commands/_link_lib.py` | Add `ALL_HARNESSES` tuple + `validate_harness` function. |
| `src/agent_toolkit_cli/commands/link.py` | Import + call `validate_harness` first thing in `link()`. |
| `src/agent_toolkit_cli/commands/unlink.py` | Import + call `validate_harness` first thing in `unlink()`. |
| `src/agent_toolkit_cli/commands/_list_json.py` | Re-export `ALL_HARNESSES` from `_link_lib` to keep one source of truth (or leave both and add a comment). Decision made during plan. |
| `tests/test_cli_link.py` | + 3 tests. |
| `tests/test_cli_unlink.py` | + 3 tests. |
| `tests/test_cli_diff.py` | + 1 test. |
| `tests/test_link_lib.py` | + 2 tests. |

No bash files touched. No `conventions` mentioned anywhere.

## Risk

Tiny. The validator is additive — it only changes behaviour for inputs that previously had no useful effect. The only way to break a real workflow would be if someone relied on the silent no-op as a poor man's check, which is unlikely.

The `_list_json.py` `ALL_HARNESSES` consolidation has theoretical risk of a circular import; mitigation is to keep the canonical tuple in `_link_lib.py` (which `_list_json.py` doesn't currently import) and have `_list_json.py` import from there.

## Out-of-scope follow-ups

- PR-2 (already planned) will retire the bash side. After that, the bash `conventions` route in `bin/agent-toolkit:127-141` and `bin/lib/conventions.sh` will be deleted in their entirety.
- A separate package or tool may wish to provide conventions projection — that is not this package's concern.
