# Plan — TUI: expose MCPs in the kind sidebar (#39)

## Existing state (uncommitted, on `fix/tui-mcp-pi`)

```
src/agent_toolkit_tui/messages.py              | 2 +-   # type-comment doc string
src/agent_toolkit_tui/state.py                 | 2 +-   # type-comment doc string
src/agent_toolkit_tui/widgets/kinds_sidebar.py | 5 +++-- # KINDS + KIND_LABELS now include "mcp"
```

These are correct as-is per scout. No further code changes needed.

## Tasks

### 1. Pin the sidebar count for MCPs

File: `tests/test_tui/test_kinds_sidebar.py` (new file).

- Construct an `InventoryState` whose `rows` contains at least one row with `kind="mcp"` plus a couple of skills/agents for noise.
- Call `KindsSidebar._count(state, "mcp")` and assert it equals the MCP-row count.
- Also assert it equals 0 when the state has no MCPs (regression for empty case).

This is a pure-function test; no Textual pilot needed.

### 2. Pin the grid filter for MCP rows

File: `tests/test_tui/test_app.py` (extend existing).

- Find the local `FakeRunner._doc()` (test_app.py:16) and add an MCP entry whose harness cells are all `status="unsupported"` (matches `_list_json.py:166-178` reality).
- Add a new pilot test `test_kind_change_to_mcp_filters_grid` modelled on the existing `test_kind_change_filters_grid` at test_app.py:253:
  - Start the app.
  - Post `KindChanged(kind="mcp")`.
  - Await idle.
  - Assert `grid._kind == "mcp"` and `len(grid._rows_for_kind()) == <mcp-count>`.

### 3. Run the suite

```
uv run pytest -q tests/test_tui/
uv run pytest -q
```

Both must pass.

### 4. Commit

Single conventional commit:

```
fix(#39): expose MCPs in the TUI kind sidebar

KindsSidebar's KINDS/KIND_LABELS now include "mcp", and the
type-comment strings in messages.py/state.py are aligned. Adds
a unit test for _count() and a pilot test asserting the grid
filters to MCP rows on KindChanged(kind="mcp"). MCP cells render
as unsupported and are non-toggleable, matching the existing
no-op projection behaviour in _link_lib.project_from_file.
```

## Verification

`.claude/testing.md` does not exist (confirmed). No `verify.sh`. Step 9 falls back to the menu — for a pure-Python TUI change with passing tests, the menu choice is "skip" (the test suite is the verification artifact). `flow.log` records preflight CI command outputs; `assets/verification/39/` will hold the preflight logs.

## Risks

- None expected — scout confirmed no snapshot tests, no hardcoded sidebar lists elsewhere, no fixtures that would break.
- If the MCP fixture in `test_app.py` causes an unrelated assertion to drift (e.g. a count assertion that didn't account for the extra row), fix the assertion not the fixture.
