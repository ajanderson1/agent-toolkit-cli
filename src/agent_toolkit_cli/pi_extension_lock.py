"""Asset-type-aligned re-export of the asset-type-blind lock primitives for the
pi-extension asset type. Behaviourally identical to `skill_lock`; exists so
pi-extension call sites read from a asset-type-named module (mirrors agent_lock)."""
from __future__ import annotations

from agent_toolkit_cli.skill_lock import (
    SUPPORTED_VERSIONS,
    LockEntry,
    LockFile,
    add_entry,
    read_lock,
    remove_entry,
    write_lock,
)

__all__ = [
    "SUPPORTED_VERSIONS",
    "LockEntry",
    "LockFile",
    "add_entry",
    "read_lock",
    "remove_entry",
    "write_lock",
]
