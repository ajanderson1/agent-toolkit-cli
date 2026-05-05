"""Codex MCP adapter — ConfigFileAdapter against ~/.codex/config.toml.

Round-trip via tomlkit. Managed namespace: `[mcp_servers.<name>]` tables.
"""
from __future__ import annotations

# Implementation lands in Task 5. This stub keeps the import path stable.

class CodexAdapter:
    name = "codex"
    strategy = "config_file"

    def __init__(self) -> None:
        raise NotImplementedError(
            "CodexAdapter is implemented in plan task 5; do not instantiate yet"
        )
