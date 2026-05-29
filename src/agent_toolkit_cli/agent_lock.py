"""Agent-flavoured facade over `skill_lock.py`.

v3.0.0 PR2 — re-exports the kind-blind lock-IO primitives from
`skill_lock`. The agent kind uses the same LockEntry/LockFile structs;
the distinguishing field at write time is `agent_path` (vs `skill_path`)
on the LockEntry, both serialised explicitly per Task 2.

The file's only purpose is to give callers (PR4 CLI verbs, PR5 TUI)
a kind-aligned import path: `from agent_toolkit_cli.agent_lock import …`
instead of reaching into `skill_lock` directly. No behavioural divergence.
"""
from __future__ import annotations

from agent_toolkit_cli.skill_lock import (
    SUPPORTED_VERSIONS,
    LockEntry,
    LockFile,
    add_entry,
    clone_url_from_entry,
    read_lock,
    remove_entry,
    write_lock,
)

# Machine-checked re-export contract: any caller doing `from agent_lock
# import *` gets exactly these names; ruff/pyflakes treat membership as
# usage so `# noqa: F401` is unnecessary.
__all__ = [
    "SUPPORTED_VERSIONS",
    "LockEntry",
    "LockFile",
    "add_entry",
    "clone_url_from_entry",
    "read_lock",
    "remove_entry",
    "write_lock",
]
