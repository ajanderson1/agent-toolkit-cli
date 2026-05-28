"""Agent-flavoured facade over `skill_lock.py`.

v3.0.0 PR2 — re-exports the kind-blind lock-IO primitives from
`skill_lock`. The agent kind uses the same LockEntry/LockFile structs;
the distinguishing field at write time is `agent_path` (vs `skill_path`)
on the LockEntry, both serialised explicitly per Task 2.

The file's only purpose is to give callers (PR4 CLI verbs, PR5 TUI)
a kind-aligned import path: `from agent_toolkit_cli.agent_lock import …`
instead of reaching into `skill_lock` directly. No behavioural divergence
is introduced; a future PR may add agent-specific helpers here.
"""
from __future__ import annotations

from agent_toolkit_cli.skill_lock import (  # noqa: F401
    SUPPORTED_VERSIONS,
    LockEntry,
    LockFile,
    add_entry,
    clone_url_from_entry,
    read_lock,
    remove_entry,
    write_lock,
)
