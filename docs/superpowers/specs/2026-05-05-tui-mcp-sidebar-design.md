# Spec — TUI: expose MCPs in the kind sidebar (#39)

## Problem

The Textual TUI sidebar (`KindsSidebar`) iterates a hardcoded `KINDS` tuple that omits `"mcp"`. MCP rows are present in `state.rows` (verified via `agent-toolkit list --format json`) but the user cannot select the MCP kind because no row exists in the sidebar.

## Surface area (from scout)

The sidebar render path is fully `KINDS`-driven (`kinds_sidebar.py:11-14, 30-35, 38`). Adding `"mcp"` to `KINDS` and `KIND_LABELS` is the complete sidebar fix. The grid (`asset_grid.py`) is kind-agnostic; columns come from `state.all_harnesses` and rows are filtered by `r.kind == self._kind`. Toggling MCP cells is already a safe no-op via the `status == "unsupported"` guard at `asset_grid.py:100`, which matches today's reality that MCPs project as no-ops in `_link_lib.py:204-223`.

The issue body referenced a `commands/_mcp_dispatch.py` apply path; that module does not exist. The actual apply path is the generic one and already handles MCPs correctly (no-op branch). No CLI-side changes required.

## Out of scope (deferred)

- `generators/list_report.py:12` `_KINDS` tuple also excludes `"mcp"`. Touching it would break `--report` callers and is unrelated to the TUI sidebar.
- Making MCP cells toggleable. That requires a per-harness MCP adapter and a new `CellStatus` value (`"pending"` is hinted at `_list_json.py:162-165`). Out of scope.
- Tests beyond the minimum needed to pin the sidebar+grid behaviour for MCPs.

## Acceptance criteria

1. Launching the TUI with at least one MCP in the inventory shows a row labelled **"MCPs"** in the sidebar with the correct count.
2. Selecting the MCPs row in the sidebar filters `AssetGrid` to MCP rows; the grid does not crash.
3. MCP cells render as the unsupported glyph and are non-toggleable (existing safe no-op behaviour preserved).
4. A unit test asserts `KindsSidebar._count()` returns the right number of MCP rows from a state containing MCPs.
5. A pilot test asserts the grid filters to MCP rows after a `KindChanged(kind="mcp")` message and the row count matches the fixture.
6. `uv run pytest -q` passes.

## Non-goals confirmed

The PR does not change `_list_json.py`, `_link_lib.py`, `asset_grid.py`, `app.py`, or `runner.py`. The user's three-file diff (`kinds_sidebar.py`, `messages.py`, `state.py`) plus tests is the entire change.
