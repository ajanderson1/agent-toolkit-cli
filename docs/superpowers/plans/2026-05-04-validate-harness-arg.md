# Plan: validate `<harness>` argument in `link` and `unlink`

**Spec:** `docs/superpowers/specs/2026-05-04-validate-harness-arg-design.md`
**Issue:** #9
**Branch:** `feat/9-validate-harness`
**Mode:** TDD per task — write the failing test first, then make it pass.

## Task list

### T1 — Tests for `validate_harness` (red)

**File:** `tests/test_link_lib.py`

Add two tests:
- `test_validate_harness_accepts_known` — calls the helper for each of `claude`, `codex`, `opencode`, `pi` and asserts no exception/exit. Use a `click.Context` constructed with a no-op command.
- `test_validate_harness_rejects_unknown_with_message` — calls the helper with `"banana"` inside `pytest.raises(SystemExit)`; capture stderr and assert it contains `unknown harness 'banana'` and the four valid harness names.

**Run:** `pytest tests/test_link_lib.py -x` — expect 2 failures (helper not yet defined).

### T2 — Implement `validate_harness` (green)

**File:** `src/agent_toolkit/commands/_link_lib.py`

Add at module top (after existing imports):

```python
ALL_HARNESSES: tuple[str, ...] = ("claude", "codex", "opencode", "pi")


def validate_harness(ctx: "click.Context", harness: str) -> None:
    """Exit 2 with a clean error if `harness` is not one of ALL_HARNESSES."""
    if harness not in ALL_HARNESSES:
        click.echo(
            f"unknown harness '{harness}' — expected one of: "
            + " ".join(ALL_HARNESSES),
            err=True,
        )
        ctx.exit(2)
```

Add `import click` to the file if not already present (currently `_link_lib.py` does not import click — verify; if so, add it).

**Run:** `pytest tests/test_link_lib.py -x` — expect green.

### T3 — Consolidate `ALL_HARNESSES` source of truth

**File:** `src/agent_toolkit/commands/_list_json.py`

Replace the local `ALL_HARNESSES = ("claude", "codex", "opencode", "pi")` definition (line ~18) with `from agent_toolkit.commands._link_lib import ALL_HARNESSES`.

Keep the existing `ALL_HARNESSES` symbol in the `_list_json` namespace (re-exported via the import) so other importers (e.g. `list.py`, which does `from agent_toolkit.commands._list_json import ALL_HARNESSES`) keep working unchanged.

**Verify no circular import:** `_link_lib.py` does not import from `_list_json.py`. Confirmed by reading current `_link_lib.py` imports.

**Run:** `pytest tests/test_cli_list.py tests/test_link_lib.py -x` — confirm nothing regressed.

### T4 — Tests for `link` rejecting unknown harness (red)

**File:** `tests/test_cli_link.py`

Add three tests using `CliRunner` with the same fixture pattern the other tests in this file use (look for an existing `runner` / `tmp_repo` fixture and mirror it):

```python
def test_link_unknown_harness_exits_2_with_message(runner, tmp_repo):
    result = runner.invoke(main, ["link", "user", "banana"])
    assert result.exit_code == 2
    assert "unknown harness 'banana'" in result.stderr
    assert "claude codex opencode pi" in result.stderr

def test_link_unknown_harness_does_not_touch_filesystem(runner, tmp_repo, tmp_path):
    # Snapshot any directories link could mutate before invoking.
    before = sorted((tmp_path / "home").rglob("*")) if (tmp_path / "home").exists() else []
    runner.invoke(main, ["link", "user", "banana"], env={"HOME": str(tmp_path / "home")})
    after = sorted((tmp_path / "home").rglob("*")) if (tmp_path / "home").exists() else []
    assert before == after

def test_link_dry_run_unknown_harness_still_validates(runner, tmp_repo):
    result = runner.invoke(main, ["link", "user", "banana", "--dry-run"])
    assert result.exit_code == 2
    assert "unknown harness" in result.stderr
```

**Adapt fixture names to whatever `test_cli_link.py` already uses.** Read the existing tests in that file before writing — pattern-match on style.

**Run:** `pytest tests/test_cli_link.py -x -k unknown_harness` — expect 3 failures.

### T5 — Wire validator into `link` (green)

**File:** `src/agent_toolkit/commands/link.py`

Add to imports:
```python
from agent_toolkit.commands._link_lib import (
    ...,
    validate_harness,
)
```

Inside `link()`, **immediately after the `if quiet:` block** (around line 70-71, before the `# Mode resolution + mutex checks` comment):

```python
    validate_harness(ctx, harness)
```

This runs before any mode/mutex parsing or filesystem interaction.

**Run:** `pytest tests/test_cli_link.py -x` — expect all green, including the new tests.

### T6 — Tests for `unlink` rejecting unknown harness (red)

**File:** `tests/test_cli_unlink.py`

Mirror T4 — three tests, swapping `link` for `unlink` and adapting any unlink-specific fixture detail.

**Run:** `pytest tests/test_cli_unlink.py -x -k unknown_harness` — expect 3 failures.

### T7 — Wire validator into `unlink` (green)

**File:** `src/agent_toolkit/commands/unlink.py`

Same change as T5 but in `unlink.py`. Imports + `validate_harness(ctx, harness)` immediately after the `if quiet:` block.

**Run:** `pytest tests/test_cli_unlink.py -x` — green.

### T8 — Test for `diff` inheritance (red → green in one)

**File:** `tests/test_cli_diff.py`

Add one test:

```python
def test_diff_unknown_harness_exits_2(runner, tmp_repo):
    result = runner.invoke(main, ["diff", "user", "banana"])
    assert result.exit_code == 2
    assert "unknown harness 'banana'" in result.stderr
```

`diff` already forwards to `link.invoke`, so this should pass without any change to `diff.py`. If it does not, that's a signal the inheritance is broken — escalate, do not patch.

**Run:** `pytest tests/test_cli_diff.py -x` — expect green.

### T9 — Full suite + lint

```bash
pytest -q                              # full Python suite
ruff check src tests                   # if ruff is configured
bats tests/bats                        # bash side still passes (we touched none of it)
```

All must be green. If `ruff` or other lints aren't configured in this repo, skip — don't add tooling.

### T10 — Commit and clean

Single commit on the branch (or two if T1-T2 and T3 feel logically separate; agent's call). Conventional commit message:

```
feat(cli): reject unknown harness in link and unlink

Closes #9.

Adds `validate_harness()` to `_link_lib`, called at the top of `link`
and `unlink`. Unknown harnesses now exit 2 with a message naming the
four valid harnesses; previously they silently no-op'd. `diff` inherits
the check via its `ctx.invoke(link, ...)` call.

`list` was already validating its harness filter; no change there.
```

## Acceptance checklist (Verify will run this)

- [ ] `agent-toolkit link user banana` exits 2 with stderr `unknown harness 'banana' — expected one of: claude codex opencode pi`
- [ ] `agent-toolkit unlink user banana` — same
- [ ] `agent-toolkit diff user banana` — same
- [ ] `agent-toolkit link user claude` still works (no behaviour change for valid harnesses)
- [ ] Full `pytest -q` green
- [ ] Full `bats tests/bats` green
- [ ] No new files outside `docs/superpowers/`, no changes to bash, no changes to `_list_json.py` other than the import consolidation in T3.

## Estimated diff size

~25 lines of source (helper + 4 import lines + 2 call sites), ~80 lines of tests. Single commit ~120 LOC including spec/plan if those are committed in the same series.

## Subagent escalation triggers

- Any test that *should* pass per this plan fails for a non-obvious reason → halt, surface with the failing assertion to the user.
- A circular import surfaces during T3 → fall back: keep `ALL_HARNESSES` defined in `_link_lib.py` and have `_list_json.py` keep its own copy with a comment "kept in lockstep with `_link_lib.ALL_HARNESSES`". Mark T3 as deferred.
- The CLI's existing `tests/test_cli_link.py` does not have a `tmp_repo`-style fixture matching the assumption above → halt, ask the user how the existing tests bootstrap their toolkit-root.
