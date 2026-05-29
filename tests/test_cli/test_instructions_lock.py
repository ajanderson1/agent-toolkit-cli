"""InstructionsLockFile shape + round-trip + add/remove entries."""
from __future__ import annotations

import json

import pytest

from agent_toolkit_cli.instructions_lock import (
    InstructionsLockEntry,
    InstructionsLockFile,
    add_entry,
    read_lock,
    remove_entry,
    write_lock,
)


def test_lockentry_shape():
    """Entry carries scope, source path, and the list of ON harnesses."""
    entry = InstructionsLockEntry(
        scope="project",
        source="AGENTS.md",
        harnesses=["claude-code", "gemini-cli"],
    )
    assert entry.scope == "project"
    assert entry.source == "AGENTS.md"
    assert entry.harnesses == ["claude-code", "gemini-cli"]


def test_lockfile_default_empty():
    lock = InstructionsLockFile(version=1, instructions={})
    assert lock.version == 1
    assert lock.instructions == {}


def test_read_lock_missing_file_returns_empty(tmp_path):
    """A missing lock file is not an error — it's an empty lock."""
    lock = read_lock(tmp_path / "instructions-lock.json")
    assert lock == InstructionsLockFile(version=1, instructions={})


def test_write_then_read_roundtrip(tmp_path):
    lock = InstructionsLockFile(
        version=1,
        instructions={
            "AGENTS.md": InstructionsLockEntry(
                scope="project",
                source="AGENTS.md",
                harnesses=["claude-code"],
            ),
        },
    )
    path = tmp_path / "instructions-lock.json"
    write_lock(path, lock)
    assert read_lock(path) == lock


def test_serialised_shape(tmp_path):
    """The on-disk JSON must match the documented shape exactly."""
    lock = InstructionsLockFile(
        version=1,
        instructions={
            "AGENTS.md": InstructionsLockEntry(
                scope="project",
                source="AGENTS.md",
                harnesses=["claude-code", "gemini-cli"],
            ),
        },
    )
    path = tmp_path / "instructions-lock.json"
    write_lock(path, lock)
    raw = json.loads(path.read_text())
    assert raw == {
        "version": 1,
        "instructions": {
            "AGENTS.md": {
                "scope": "project",
                "source": "AGENTS.md",
                "harnesses": ["claude-code", "gemini-cli"],
            },
        },
    }


def test_add_entry():
    lock = InstructionsLockFile(version=1, instructions={})
    new = add_entry(
        lock,
        "AGENTS.md",
        InstructionsLockEntry(scope="project", source="AGENTS.md", harnesses=["claude-code"]),
    )
    assert "AGENTS.md" in new.instructions
    assert new.instructions["AGENTS.md"].harnesses == ["claude-code"]
    # original unchanged (immutable update pattern)
    assert lock.instructions == {}


def test_remove_entry():
    lock = InstructionsLockFile(
        version=1,
        instructions={
            "AGENTS.md": InstructionsLockEntry(scope="project", source="AGENTS.md", harnesses=["claude-code"]),
        },
    )
    new = remove_entry(lock, "AGENTS.md")
    assert new.instructions == {}


def test_remove_missing_entry_is_noop():
    lock = InstructionsLockFile(version=1, instructions={})
    assert remove_entry(lock, "AGENTS.md") == lock


def test_unknown_version_raises(tmp_path):
    path = tmp_path / "instructions-lock.json"
    path.write_text(json.dumps({"version": 99, "instructions": {}}))
    with pytest.raises(ValueError, match="unsupported instructions-lock version"):
        read_lock(path)
