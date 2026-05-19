# Plan — Prune stale projections (#120)

Implements `docs/superpowers/specs/2026-05-19-prune-stale-projections-design.md`.

## Tasks

1. **Add regression tests (failing first).**
   - `tests/test_cli_link.py`:
     - `test_link_bare_prunes_stale_claude_agent_after_yaml_handedit`
     - `test_link_bare_prunes_stale_claude_command_after_yaml_handedit`
     - `test_link_bare_prunes_stale_mcp_codex_after_yaml_handedit`
   - Run `uv run pytest tests/test_cli_link.py -q` — confirm new tests
     fail.

2. **Fix symlink-kind orphan-on-reconcile (`_link_lib.py`).**
   - In `project_from_file`, the `else` branch where the asset is in
     the toolkit but `asset.slug not in allowed_slugs`: switch the
     plain-name fallback to `_slot_filename(asset.slug, kind, harness)`
     before calling `_prune_if_into_repo`. The translated-slot probe
     stays first.

3. **Fix config-file-kind orphan-on-reconcile (`_link_lib.py`).**
   - In the MCP branch: when `previous_allowed is None`, set
     `prev_mcps = set(mcp_allowed_slugs) | adapter.list_installed(scope, project_root)`.
   - In the hook branch: same shape — union the current allowlist
     slugs with `adapter.list_installed(...)`.

4. **Verify regression tests pass + full suite is green.**
   - `uv run ruff check .`
   - `uv run pytest -q`

5. **Audit doc bookkeeping.**
   - No change needed — the spec is the artefact. The audit-rollup
     can be updated in a follow-up after the bug closes.

## Risk / edge cases

- `list_installed()` on a fresh sandbox with no config file returns
  `set()` — union behaviour matches prior fallback.
- For an adapter whose `config_target()` returns `None`
  (project-scope MCP without `.mcp.json`), `list_installed()` returns
  `set()` — same neutral behaviour.
- `_slot_filename` already canonicalises gemini/opencode shapes, so
  the symlink fix won't regress non-claude harnesses.
