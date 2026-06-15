"""Status constants for the Textual TUI's asset grid."""
from __future__ import annotations

# Cell statuses that count as "linked at this (scope, harness)" — the union
# of the three states the inventory builder emits when an asset has a real
# slot occupation (symlink, hook entry, or MCP entry). Imported by:
#   - agent_toolkit_tui/widgets/asset_grid.py
USER_LINKED_STATUSES: frozenset[str] = frozenset(
    {"linked", "linked-matches", "linked-drifted"}
)
