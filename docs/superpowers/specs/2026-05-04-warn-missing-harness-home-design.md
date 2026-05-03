# Warn when target harness home directory is missing

**Issue:** [#13](https://github.com/ajanderson1/agent-toolkit-cli/issues/13) — *doctor/link: warn when target harness home directory is missing*
**Date:** 2026-05-04

## Problem

Today, running `agent-toolkit link` against a harness whose home directory doesn't exist (e.g. `~/.codex` on a machine that has never run Codex) either creates symlinks under a path that no harness will read, or fails with a confusing OS-level error. The check is a one-liner — does the harness home directory exist? — but the CLI is silent about it. The old `claude-tui-tools` had implicit feedback via its TUI's "available resources" pane; the new CLI has nothing.

## Decision

Add the harness-home check in two places:

1. **`agent-toolkit doctor`** — gain a per-harness check that the harness home directory exists and is writable. Missing → WARN with a one-line explanation.
2. **`agent-toolkit link <harness>`** — print a one-line warning (not an error) when the harness home is missing, then proceed. `--quiet` suppresses the warning; default behaviour shows it.

The check is **warning, not error** because users may legitimately stage symlinks ahead of installing a harness.

## Harness home table

| Harness | Home dir |
|---|---|
| claude | `~/.claude` |
| codex | `~/.codex` |
| opencode | `~/.opencode` |
| pi | `~/.pi` |

These match the prefixes already in `_USER_TARGETS` (`src/agent_toolkit/commands/_list_json.py:27-37`). New tuple `HARNESS_HOMES` lives next to `ALL_HARNESSES` in `_link_lib.py`.

## Approach

### Helper

Add to `src/agent_toolkit/commands/_link_lib.py`:

```python
HARNESS_HOMES: dict[str, str] = {
    "claude":   ".claude",
    "codex":    ".codex",
    "opencode": ".opencode",
    "pi":       ".pi",
}


def harness_home_path(harness: str, home: Path | None = None) -> Path:
    """Return the absolute path to a harness's home directory under $HOME."""
    h = home if home is not None else Path(os.environ.get("HOME", ""))
    return h / HARNESS_HOMES[harness]
```

### Doctor group

New file `src/agent_toolkit/doctor/harness_homes.py`:

- Iterate `ALL_HARNESSES`. For each, check `harness_home_path(h).exists()` and `is_dir()`.
- A missing home is a WARN finding with `"<harness> home not present at <path> — install the harness or stage the symlinks anyway"`.
- An existing home is an OK finding.
- Returns a `GroupResult` with name `"harness-homes"`, status `WARN` if any missing, else `OK`.

Wire into `commands/doctor.py`: add `("harness-homes", lambda: g_harness_homes.run(...))` to `_run_global`. Add `"harness-homes"` to `_GROUPS` tuple so `--group harness-homes` works.

The doctor check is **harness-agnostic** — it runs once for all four, regardless of the `--harness` flag. (Different from `symlinks` and `conventions` which take the per-run `--harness`.)

### Link warning

In `src/agent_toolkit/commands/link.py`, after `validate_harness(ctx, harness)` (line 73), insert:

```python
quiet_env = os.environ.get("AGENT_TOOLKIT_QUIET") == "1"
home_path = harness_home_path(harness)
if not home_path.is_dir() and not quiet_env:
    click.echo(
        f"warning: {harness} home not present at {home_path} — "
        f"linking anyway, but the symlinks won't be picked up until {harness} is installed",
        err=True,
    )
```

`quiet_env` already gets set above (`if quiet: os.environ["AGENT_TOOLKIT_QUIET"] = "1"`). So the warning is suppressed when the user passes `--quiet`.

## Tests

### `tests/test_doctor_groups.py` (or new `test_doctor_harness_homes.py` if cleaner)

Three tests:

- `test_harness_homes_all_present_returns_ok` — create `~/.claude`, `~/.codex`, `~/.opencode`, `~/.pi`; assert OK.
- `test_harness_homes_one_missing_returns_warn` — create three of four; assert WARN with the missing one named.
- `test_harness_homes_all_missing_returns_warn` — create none; assert WARN listing all four.

### `tests/test_cli_link.py`

Three tests:

- `test_link_warns_when_harness_home_missing` — assert warning on stderr when `~/.codex` doesn't exist; `link user codex` proceeds (no failure exit code).
- `test_link_quiet_suppresses_missing_home_warning` — `link user codex --quiet` produces no warning.
- `test_link_no_warning_when_harness_home_exists` — create `~/.claude`; `link user claude` produces no warning.

## Non-goals

- Auto-installing harnesses or creating their home directories.
- Detecting harness *versions* or capability differences.
- Hard-erroring by default — a warning is enough.
- Refactoring `_USER_TARGETS` to use `HARNESS_HOMES` (cleanup follow-up if motivated; not in this PR).

## Risk

Tiny. Pure addition of a check + a warning print. The link command continues to work even when the home is missing — the warning is informational. The doctor group is new code that adds one entry to `_GROUPS`.

## Edge cases

- `$HOME` unset: `Path("")/".claude"` resolves to `.claude` — the relative-path warning is still useful, and the doctor group will still flag it.
- Home exists but not writable: per the issue, "exists and is writable". I'll use `os.access(path, os.W_OK)` — if exists but not writable, still WARN (rare; out of issue scope to error).
