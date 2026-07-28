# PR #487 data-steward follow-up

**Code under review:** `4ccc573dab60e1169bb6a13220ce105a9e3a71cb`

## Resolved findings

1. Invalid UTF-8 is explicitly decoded and caught in `load()`, returning defaults plus a visible status-bar diagnostic instead of crashing TUI startup.
2. Supported v1 files retain unknown top-level fields. Unsupported schemas carry a write refusal, so theme/harness saves cannot replace a future document. An unavailable stored theme remains in the file during an unrelated harness save.
3. `AGENT_TOOLKIT_TUI_SETTINGS` rejects relative and whitespace-only overrides; startup shows an actionable absolute-path diagnostic and never resolves the override through CWD.

## Fresh verification

| Command | Result |
|---|---|
| Focused new regressions | `11 passed, 18 deselected` |
| `uv run --frozen --no-sync pytest tests/test_tui -q` | `487 passed` |
| `uv run --frozen --no-sync pytest -q` | `2154 passed, 2 skipped` |
| `ruff check` (changed Python) | passed |
| `git diff --exit-code -- uv.lock` | passed |
