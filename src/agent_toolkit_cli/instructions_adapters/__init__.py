"""Adapter dispatcher for the instructions kind.

Only one mechanism exists (`symlink`), so the dispatcher is trivially thin —
get_adapter(harness) just delegates to symlink.adapter_for(harness).
Kept as a layer for symmetry with the agent kind's mechanism-dispatcher
(which has 3 mechanisms) and to give a clean import boundary for the CLI.
"""
from __future__ import annotations

from agent_toolkit_cli.instructions_adapters import symlink

SUPPORTED_HARNESSES: frozenset[str] = frozenset(symlink.CELLS)


def get_adapter(harness: str) -> symlink.Adapter:
    """Return the symlink adapter bound to `harness`. Raises UnknownHarnessError."""
    return symlink.adapter_for(harness)
