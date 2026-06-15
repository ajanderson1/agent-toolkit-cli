"""Tests for mcp_lock.py — the mcps-lock.json reader/writer."""
from __future__ import annotations

from agent_toolkit_cli.mcp_lock import (
    McpLockEntry,
    lock_path_for_scope,
    read_lock,
    upsert_entry,
    remove_entry,
    write_lock,
)


def test_lock_path_user_scope(tmp_path):
    assert lock_path_for_scope("global", home=tmp_path, project=None) == (
        tmp_path / ".agent-toolkit" / "mcps-lock.json"
    )


def test_lock_path_project_scope(tmp_path):
    assert lock_path_for_scope("project", home=tmp_path, project=tmp_path / "p") == (
        tmp_path / "p" / "mcps-lock.json"
    )


def test_round_trip_empty(tmp_path):
    p = tmp_path / "mcps-lock.json"
    write_lock(p, {})
    assert read_lock(p) == {}


def test_upsert_and_remove(tmp_path):
    p = tmp_path / "mcps-lock.json"
    lock = read_lock(p)
    lock = upsert_entry(lock, McpLockEntry(slug="context7", harness="claude-code", source="ajanderson1/mcps"))
    write_lock(p, lock)
    reloaded = read_lock(p)
    assert "context7" in reloaded
    assert reloaded["context7"][0].harness == "claude-code"
    reloaded = remove_entry(reloaded, slug="context7", harness="claude-code")
    assert "context7" not in reloaded


def test_upsert_two_harnesses_same_slug(tmp_path):
    lock = upsert_entry({}, McpLockEntry(slug="context7", harness="claude-code", source="s"))
    lock = upsert_entry(lock, McpLockEntry(slug="context7", harness="codex", source="s"))
    harnesses = sorted(e.harness for e in lock["context7"])
    assert harnesses == ["claude-code", "codex"]
    lock = remove_entry(lock, slug="context7", harness="claude-code")
    assert [e.harness for e in lock["context7"]] == ["codex"]
