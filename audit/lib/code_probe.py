"""code_probe.py — emit (kind, harness, supported) TSV from CLI internals.

This is the code-derived probe in the audit's three-source support matrix.
Schema and empirical probes live in audit/discover-matrix.sh.

Run as: uv run python audit/lib/code_probe.py

Supported is determined by:
- Non-MCP kinds: membership in _support.SUPPORTED_PAIRS (keyed from _USER_TARGETS).
- MCP kind: get_adapter(harness, "mcp") returns a real adapter (not UnimplementedAdapter).
"""
from __future__ import annotations

import sys

from agent_toolkit_cli._support import ALL_HARNESSES, ALL_KINDS, SUPPORTED_PAIRS
from agent_toolkit_cli.harness_adapters import UnimplementedAdapter, get_adapter

KINDS = list(ALL_KINDS)
HARNESSES = list(ALL_HARNESSES)


def _supported(kind: str, harness: str) -> bool:
    if kind == "mcp":
        return not isinstance(get_adapter(harness, "mcp"), UnimplementedAdapter)
    return (harness, kind) in SUPPORTED_PAIRS


def main() -> int:
    print("kind\tharness\tsupported")
    for kind in KINDS:
        for harness in HARNESSES:
            ok = "true" if _supported(kind, harness) else "false"
            print(f"{kind}\t{harness}\t{ok}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
