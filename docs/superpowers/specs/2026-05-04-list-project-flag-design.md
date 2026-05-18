# Add `--project` to `list` for symmetry with link/unlink/diff

**Issue:** [#7](https://github.com/ajanderson1/agent-toolkit-cli/issues/7)
**Date:** 2026-05-04

## Problem

`link`, `unlink`, and `diff` accept a per-command `--project DIR` flag. `list` does not — it only honours the group-level `--project DIR`. So:

- ✅ `agent-toolkit --project /x list` works
- ✅ `agent-toolkit link --project /x …` works
- ❌ `agent-toolkit list --project /x` errors with `No such option: --project`

A user who reaches for the per-command flag from `link` muscle-memory hits a footgun.

## Decision

Add `--project DIR` to `list_cmd` in `src/agent_toolkit_cli/commands/list.py`. Resolution order matches `link.py` and `unlink.py`:

1. `--project DIR` flag (this PR adds it).
2. Group-level `--project` from `ctx.obj`.
3. `Path.cwd()` fallback.

## Affected files

| File | Change |
|---|---|
| `src/agent_toolkit_cli/commands/list.py` | Add `@click.option("--project", "project_flag", …)` decorator after the existing `--toolkit-repo`. Add `project_flag` parameter. Replace lines 149-150 (the `(ctx.obj).get("project_root")` block) with the four-step resolution from `link.py:108-113`. |
| `tests/test_cli_list.py` | Add a test asserting `list --project /x` is recognised and the project_root resolves to `/x`. Mirror the existing `test_link_project_flag` test pattern from `tests/test_cli_link.py`. |

## Tests

One new test: `test_list_project_flag_resolves_correctly`. It seeds a project dir with a `.agent-toolkit.yaml` containing one slug, points `--project` at it from a different cwd, and asserts the listing reflects the project's allowlist (e.g., a "project:✓" appears).

The existing `multi_env` and `env` fixtures cover all the seeding I need — `--project` just changes which yaml the command reads.

## Non-goals

- Changing the group-level `--project` resolver.
- Adding `--project` to subcommands that don't already use it (e.g., `check`, `doctor`).
- Renaming `project_root` or any internal symbol.

## Risk

Tiny. Pure addition of a flag; the existing fallback chain (group → cwd) stays in place. The only failure mode is a `--project` value that doesn't exist as a directory — Click's `Path(file_okay=False)` validates that before our code runs.
