# Spec: Remove `(claude, hook)` from `_USER_TARGETS` until adapter exists

Issue #123. The combo `(claude, hook)` is registered in the support matrix but no
`ClaudeHookAdapter` exists. `link user claude hook:<slug>` reports success and
edits `~/.agent-toolkit.yaml` under `hooks:`, but:

- No script is materialised under `~/.claude/hooks/`.
- `~/.claude/settings.json` is never written.
- The CLI prints `"no MCP adapter for harness claude yet — skipping"` — confusing
  because the hook adapter is not an MCP adapter.

## Decision: option (b)

Per `~/.conventions/conventions/coding-agent.md` and the "prefer simple defaults"
principle, we take the smaller, safer change: **stop advertising
`(claude, hook)` as supported until the adapter lands**, and fix the misleading
log message.

## Changes

1. Remove `("claude", "hook")` from `_USER_TARGETS` and `_PROJECT_TARGETS` in
   `src/agent_toolkit_cli/_support.py`.

2. Make `UnimplementedAdapter.skip_message()` kind-aware so the printed text
   says `"no <kind> adapter for harness <name> yet — skipping"`. Constructor
   gains an optional `kind` parameter (defaults to `"mcp"` for back-compat with
   existing callers). `get_adapter(harness, kind)` passes `kind` when returning
   the unimplemented sentinel.

3. Update `docs/agent-toolkit/harness-matrix.md`: change the `(claude, hook)`
   cell from `symlink → …` to `unsupported (gap) — …` with a short rationale.

4. Update `tests/test_support.py`:
   - Remove `assert ("claude", "hook") in SUPPORTED_PAIRS`.
   - Add a regression assert: `("claude", "hook") not in SUPPORTED_PAIRS` and
     `is_supported("claude", "hook") is False`.
   - Update `supported_kinds_for("claude")` expectation: drop `"hook"`.

5. Update `audit/demos/hook-claude.sh`:
   - Replace the existing assertions that link/unlink succeed with the new
     expected behaviour: `link user claude hook:demo-hook` now exits non-zero
     (unsupported pair). Adjust narrative comments accordingly.
   - The cell now documents "(claude, hook) is unsupported until a ClaudeHookAdapter
     lands" as the structural finding.

## Non-goals

- Implementing `ClaudeHookAdapter`. Tracked separately; this PR only stops the
  silent no-op.
- Touching codex hooks, MCP adapters, or other harness/kind cells.

## Risk

Low. The only externally-observable behaviour change is that
`link user claude hook:<slug>` now fails with the structured "unsupported pair"
error (exit 2), which is exactly what users expect when the feature isn't there.
The allowlist file is no longer mutated for the unsupported combo, so no
on-disk state is mis-managed.

## Verification

- `pytest` — all support/matrix tests pass after the doc + test updates.
- `ruff check` — clean.
- The audit demo `audit/demos/hook-claude.sh` is updated to assert the new
  behaviour. The PR does not run the tmux audit demo end-to-end; that's
  manual ops.
