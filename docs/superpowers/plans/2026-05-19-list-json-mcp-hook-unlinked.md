# Plan — fix `unsupported`→`unlinked` for MCP/hook cells

Linked spec: [`../specs/2026-05-19-list-json-mcp-hook-unlinked-design.md`](../specs/2026-05-19-list-json-mcp-hook-unlinked-design.md).

## Task 1 — Add a failing regression test for MCP

File: `tests/test_list_json.py`.

Add `test_list_json_mcp_codex_unlinked_when_declared_not_allowlisted`:

- Seed toolkit with context7 declaring `codex` (use existing `_seed_mcp_toolkit`).
- `HOME` is fresh; no `.agent-toolkit.yaml`; no installed config.
- Run `list --format=json`.
- Assert the `codex/user` cell on the context7 MCP reports `status == "unlinked"` and `target is None` and `allowlisted is False`.

This should fail against `main` (currently `"unsupported"`).

## Task 2 — Add a failing regression test for hook

File: `tests/test_list_json.py`.

Add `test_list_json_hook_codex_unlinked_when_declared_not_allowlisted`:

- Seed toolkit with demo-hook declaring `codex` (use existing `_seed_hook_toolkit`).
- Fresh `HOME`; no allow-list; no installed entry.
- Run `list --format=json`.
- Assert the `codex/user` cell on demo-hook reports `status == "unlinked"`, `target is None`, `allowlisted is False`.

## Task 3 — Apply the fix

File: `src/agent_toolkit_cli/commands/_list_json.py`.

- Line ~260 (hook branch, `not allowlisted` & `not is_installed` fallthrough): `"unsupported"` → `"unlinked"`.
- Line ~336 (MCP branch, same fallthrough): `"unsupported"` → `"unlinked"`.

Both regression tests should now pass. Existing tests should remain green — in particular, `test_list_json_includes_mcps` (which uses pi, an UnimplementedAdapter) still hits the `"unsupported"` path upstream.

## Task 4 — Verify

- Run `pytest tests/test_list_json.py` — all green.
- Run full test suite — all green.
- (Optional sanity) re-run the issue's repro script and confirm the four `unsupported → unlinked` flips on a real MCP.
