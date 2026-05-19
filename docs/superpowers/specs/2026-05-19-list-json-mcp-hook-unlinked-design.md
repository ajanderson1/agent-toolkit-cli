# Spec — `list --format=json`: report `unlinked` for supported MCP/hook cells

Issue: [#141](https://github.com/ajanderson1/agent-toolkit-cli/issues/141)

## Problem

`agent-toolkit-cli list --format=json` reports `status: "unsupported"` for `(asset, harness, scope)` cells where:

- the asset *does* declare the harness in its frontmatter, **and**
- the slot is neither allow-listed nor installed.

This collapses two distinct states — *N/A* (asset doesn't declare this harness) and *available* (declared but not yet wired up) — into the same value. The TUI renders both as `──`, so the user can't tell a slot that's truly not applicable from one that's ready to be linked.

The skill/agent/command/plugin branch already gets this right via `_cell_status` (which returns `"unlinked"`). The bug lives only in the **MCP** and **hook** adapter-path branches of `src/agent_toolkit_cli/commands/_list_json.py`.

## Fix

In `_list_json.py`, in the `not-allowlisted, not-installed` fallthrough of both the MCP branch (line ~336) and the hook branch (line ~260), change the emitted status from `"unsupported"` to `"unlinked"`.

The `if h not in declared` guard upstream (line 185) and the `UnimplementedAdapter` guards remain unchanged — they continue to produce the correct `"unsupported"` for true N/A cells. The hook branch's `target_path is None` (scope not supported by the adapter) and `hook_entry is None` (catalog resolution failed) guards also remain `"unsupported"` — those are also true N/A.

## Scope

- Two single-line status-string changes in `src/agent_toolkit_cli/commands/_list_json.py`.
- One existing test asserts `status == "unsupported"` for a context7-on-pi cell (`tests/test_list_json.py:239`). pi has no MCP adapter (UnimplementedAdapter), so that path still hits `"unsupported"` upstream — the assertion stays green.
- New regression tests:
  - MCP + codex adapter, declared but unlinked + unallowlisted → `"unlinked"`.
  - Hook + codex adapter, declared but unlinked + unallowlisted → `"unlinked"`.

## Out of scope

- TUI changes. The TUI glyph table is already correct — once the CLI reports `unlinked`, the TUI renders `☐` automatically.
- Renaming or restructuring the status taxonomy.
- The `installed-not-allowlisted` branch (intentionally distinct) and the `unlinked-allowlisted` branch (allowlisted but not installed).
