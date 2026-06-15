"""The MCP `standard` projection: the shared project `.mcp.json` slot.

`standard` owns the canonical `mcpServers.<slug>` entry in `<project>/.mcp.json`
— the file the claude-code AND pi MCP adapters already write at project scope
(json_config.py). Promoting it to a named projection collapses that double-write
into one token / one lock row, mirroring the agent kind's standard slot
(agent_adapters/standard.py, #361).

Covered set is HONEST and small. Despite an active proposal
(modelcontextprotocol#2218) to make root `.mcp.json` a universal standard, today
only claude-code reads a bare root `.mcp.json` and pi shares it via our own
adapter — so the covered set is {claude-code, pi}. It grows only as real clients
adopt the convention. There is NO global scope: no client reads `~/.mcp.json`.
"""
from __future__ import annotations

# Harnesses whose project config IS the shared .mcp.json `standard` owns.
# Project-scope only — there is no global standard (no `~/.mcp.json` reader).
STANDARD_MCP_READERS: dict[str, frozenset[str]] = {
    "project": frozenset({"claude-code", "pi"}),
}


def mcp_standard_covered(scope: str) -> frozenset[str]:
    """Covered harness set for a scope. KeyError on a scope with no standard
    (e.g. 'global') — fail loud, mirrors agent_adapters.standard.agents_standard_covered."""
    return STANDARD_MCP_READERS[scope]
