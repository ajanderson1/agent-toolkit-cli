---
module: agent_toolkit_tui
problem_type: logic_error
tags: [tui, pending-edits, scope, regression]
---

# Cross-kind pending edits need identity and per-entry scope

PR #530's fresh reviews found two regressions in all-kind Save/Diff/Revert:
merging raw pending dictionaries collapsed identical scope/harness/slug keys
from different grids, and hidden project Command/MCP edits received no project
root when the visible scope was global.

The combined dictionary now appends the grid selector to each key, preserving
scope at index zero for scope counts. Individual grids retain their original
key shapes. Command/MCP apply resolve roots through `_scope_to_roots(scope)`
using each pending group's scope; calls without a scope retain the existing
visible-view behavior. Skills retain their separate Paperclip root handling.

`tests/test_tui/test_cross_asset_review_regressions.py` covers identical names
across all six kinds, mixed-scope Diff/Revert/quit counts, repeated tab switches,
real disposable Command/MCP link and unlink destinations while hidden, all-kind
failure/retry dispatch, and Command handler retry without replaying successes.
MCP per-kind retry semantics and the pre-existing Pi saved count are unchanged.
