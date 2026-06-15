"""agent_lock.py facade — re-exports asset-type-blind lock primitives from skill_lock.

Per spec correction B, no behavioural divergence in PR2 — LockEntry has
agent_path as a real field (Task 2), and the format is the same.
"""
from __future__ import annotations

from agent_toolkit_cli.agent_lock import __all__ as AGENT_LOCK_PUBLIC


def test_agent_lock_public_surface_preserved():
    """The module's __all__ IS the surface contract; this test pins it
    against the names the rest of PR2 (and PR4/PR5) will rely on."""
    from agent_toolkit_cli import agent_lock
    public = {name for name in dir(agent_lock) if not name.startswith("_")}
    expected = {
        "LockEntry", "LockFile", "SUPPORTED_VERSIONS",
        "read_lock", "write_lock", "add_entry", "remove_entry",
        "clone_url_from_entry",
    }
    for symbol in expected:
        assert symbol in public, f"agent_lock public surface missing: {symbol}"
    # __all__ exists AND matches the expected contract.
    assert set(AGENT_LOCK_PUBLIC) == expected


def test_agent_lock_reexports_match_skill_lock():
    """Same names must resolve to same objects — agent_lock is a thin re-export."""
    from agent_toolkit_cli import agent_lock, skill_lock
    for name in AGENT_LOCK_PUBLIC:
        assert getattr(agent_lock, name) is getattr(skill_lock, name), (
            f"agent_lock.{name} is not the same object as skill_lock.{name}"
        )


def test_agent_lock_round_trip_with_agent_path(tmp_path):
    """End-to-end: write agent entry via agent_lock, read it back, agent_path preserved."""
    from agent_toolkit_cli.agent_lock import (
        LockEntry, LockFile, add_entry, read_lock, write_lock,
    )

    lock_path = tmp_path / "agents-lock.json"
    # `skills` is the asset-type-blind entries-by-slug dict (per PR2 spec Correction B);
    # the same struct holds both skill and agent entries — distinguished by
    # which `*_path` field is populated on each LockEntry.
    lock = LockFile(version=1, skills={})
    entry = LockEntry(
        source="ajanderson1/test",
        source_type="github",
        agent_path="agents/foo.md",
    )
    lock = add_entry(lock, "foo", entry)
    write_lock(lock_path, lock)

    re = read_lock(lock_path)
    assert re.skills["foo"].agent_path == "agents/foo.md"
    assert re.skills["foo"].skill_path is None
