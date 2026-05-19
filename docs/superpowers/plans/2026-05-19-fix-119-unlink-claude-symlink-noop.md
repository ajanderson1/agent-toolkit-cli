# Plan — Fix #119 unlink claude per-asset no-op

## Task 1 — Add regression test (TDD red)

- File: `tests/test_cli_unlink.py`
- Add `test_unlink_per_asset_claude_agent_removes_symlink` (uses `seed_agent`).
- Seed an agent, build the YAML with `agents: [demo-agent]`, create the
  `.md` symlink under `~/.claude/agents/`, invoke
  `unlink user claude agent:demo-agent`, assert exit 0, symlink gone, YAML
  entry removed.
- Run: must fail on `assert not link_path.is_symlink()` with current code.

## Task 2 — Apply fix (TDD green)

- File: `src/agent_toolkit_cli/commands/_link_lib.py`
- In `project_from_file`, per-asset prune branch (the `else:` for
  `asset.slug not in allowed_slugs`): when `_prune_translated_slot` returns
  False and `slot_path_translated != slot_path_plain`, additionally call
  `_prune_if_into_repo(slot_path_translated, …)` before falling back to
  `_prune_if_into_repo(slot_path_plain, …)`.

## Task 3 — Verify

- `uv run pytest tests/test_cli_unlink.py` — all 20 pass.
- `uv run pytest` — full suite 863+ pass.
- `uv run ruff check src/agent_toolkit_cli/commands/_link_lib.py
  tests/test_cli_unlink.py` — no new errors beyond pre-existing baseline.

## Risk / blast radius

- Touches a single conditional in one function. The only behaviour change
  is: for harnesses where `_slot_filename` returns a name distinct from the
  bare slug, the prune now also attempts the translated slot path. Safe
  because `_prune_if_into_repo` short-circuits on non-symlinks.

## Done when

- Regression test passes.
- All existing tests pass.
- No new lint errors.
