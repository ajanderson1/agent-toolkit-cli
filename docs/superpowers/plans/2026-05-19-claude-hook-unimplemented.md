# Plan: fix #123 — drop `(claude, hook)` until adapter exists

Tracking issue: #123. Branch: `fix/123-claude-hook-unimplemented`.

## Tasks

### T1 — `_support.py` matrix edit
Remove `("claude", "hook")` rows from `_USER_TARGETS` and `_PROJECT_TARGETS`.
This automatically drops the pair from `SUPPORTED_PAIRS` (derived).

### T2 — `UnimplementedAdapter` kind-aware skip message
Update `harness_adapters/base.py` so `UnimplementedAdapter.__init__` accepts an
optional `kind: str = "mcp"`; `skip_message()` returns
`f"no {self.kind} adapter for harness {self.name} yet — skipping"`.

Update `harness_adapters/__init__.py:get_adapter`: when falling through to the
unimplemented branch, pass `kind` to the constructor.

### T3 — Tests
- `tests/test_support.py`:
  - Update `test_supported_pairs_known_members` to drop the claude/hook assertion.
  - Update `test_supported_kinds_for_claude_returns_full_kind_set` to expect
    `("skill", "agent", "command", "plugin")` (no `"hook"`).
  - Add `test_claude_hook_unsupported_until_adapter_lands` asserting the pair
    is absent from `SUPPORTED_PAIRS` and `is_supported("claude", "hook")` is
    False (regression guard).
- Add or update a test for `UnimplementedAdapter.skip_message()` confirming the
  kind appears in the message (e.g. `"no hook adapter for harness claude yet"`).

### T4 — Doc parity
Update `docs/agent-toolkit/harness-matrix.md` cell for `(claude, hook)`:
change the leading mechanism from `symlink → …` to
`unsupported (gap) — Claude has a hooks API but it lives in ~/.claude/settings.json; no ClaudeHookAdapter has been written yet. Tracked in #123.`

Update the narrative paragraph for `hook` to reflect that Claude is now a
**gap** (not "supported via storage convention").

### T5 — Audit demo
Update `audit/demos/hook-claude.sh` to assert the new behaviour:
- `link user claude hook:demo-hook` exits non-zero with the structured
  "unsupported (harness, kind) pair" message.
- Remove the lifecycle assertions that expected the allowlist to mutate.
- Update narrative comments to say `(claude, hook)` is **unsupported (gap)`,
  not "unimplemented adapter".

### T6 — Verify locally
Run `ruff check`, `pytest`. All must pass.

## Done when

- `pytest` green.
- `ruff check` green.
- Doc matrix cell updated and parity test `tests/test_harness_matrix.py` passes.
- `git diff` shows the minimal set of changes outlined above.
