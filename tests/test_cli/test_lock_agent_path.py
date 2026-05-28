"""LockEntry.agent_path field round-trips through v1 and v3 lockfile formats."""
from __future__ import annotations

import json

from agent_toolkit_cli.skill_lock import (
    LockEntry,
    LockFile,
    add_entry,
    read_lock,
    write_lock,
)


def test_lockentry_has_agent_path_field():
    entry = LockEntry(
        source="ajanderson1/test",
        source_type="github",
        agent_path="my-agent.md",
    )
    assert entry.agent_path == "my-agent.md"


def test_lockentry_agent_path_defaults_none():
    entry = LockEntry(source="ajanderson1/test", source_type="github")
    assert entry.agent_path is None


def test_v1_writer_emits_agent_path(tmp_path):
    lock_path = tmp_path / "agents-lock.json"
    lock = LockFile(version=1, skills={})
    entry = LockEntry(
        source="ajanderson1/test",
        source_type="github",
        ref="main",
        agent_path="agents/foo.md",
    )
    lock = add_entry(lock, "foo", entry)
    write_lock(lock_path, lock)

    body = json.loads(lock_path.read_text())
    assert body["skills"]["foo"]["agentPath"] == "agents/foo.md"


def test_v1_reader_recovers_agent_path(tmp_path):
    lock_path = tmp_path / "agents-lock.json"
    lock_path.write_text(json.dumps({
        "version": 1,
        "skills": {
            "foo": {
                "source": "ajanderson1/test",
                "sourceType": "github",
                "ref": "main",
                "agentPath": "agents/foo.md",
            },
        },
    }))
    lock = read_lock(lock_path)
    assert lock.skills["foo"].agent_path == "agents/foo.md"


def test_v3_writer_emits_agent_path(tmp_path):
    lock_path = tmp_path / "agents-lock.json"
    lock = LockFile(version=3, skills={})
    entry = LockEntry(
        source="ajanderson1/test",
        source_type="github",
        ref="main",
        agent_path="agents/foo.md",
    )
    lock = add_entry(lock, "foo", entry)
    write_lock(lock_path, lock)

    body = json.loads(lock_path.read_text())
    assert body["skills"]["foo"]["agentPath"] == "agents/foo.md"


def test_v3_reader_recovers_agent_path(tmp_path):
    lock_path = tmp_path / "agents-lock.json"
    lock_path.write_text(json.dumps({
        "version": 3,
        "skills": {
            "foo": {
                "source": "ajanderson1/test",
                "sourceType": "github",
                "sourceUrl": "https://github.com/ajanderson1/test.git",
                "ref": "main",
                "agentPath": "agents/foo.md",
                "installedAt": "2026-05-28T20:00:00Z",
                "updatedAt": "2026-05-28T20:00:00Z",
            },
        },
    }))
    lock = read_lock(lock_path)
    assert lock.skills["foo"].agent_path == "agents/foo.md"


def test_agent_path_not_in_extras_on_v3_read(tmp_path):
    """If agentPath is a first-class field, it must NOT leak into extras
    (which would cause it to be written twice)."""
    lock_path = tmp_path / "agents-lock.json"
    lock_path.write_text(json.dumps({
        "version": 3,
        "skills": {
            "foo": {
                "source": "ajanderson1/test",
                "sourceType": "github",
                "sourceUrl": "https://github.com/ajanderson1/test.git",
                "agentPath": "agents/foo.md",
                "installedAt": "2026-05-28T20:00:00Z",
                "updatedAt": "2026-05-28T20:00:00Z",
            },
        },
    }))
    lock = read_lock(lock_path)
    assert "agentPath" not in lock.skills["foo"].extras


def test_skill_path_and_agent_path_coexist(tmp_path):
    """Mixed lock supporting both kinds (forward-compatible): both fields
    preserved separately."""
    lock_path = tmp_path / "mixed-lock.json"
    lock = LockFile(version=3, skills={})
    skill_entry = LockEntry(
        source="ajanderson1/skill", source_type="github", skill_path="SKILL.md",
    )
    agent_entry = LockEntry(
        source="ajanderson1/agent", source_type="github", agent_path="agents/foo.md",
    )
    lock = add_entry(lock, "skill1", skill_entry)
    lock = add_entry(lock, "agent1", agent_entry)
    write_lock(lock_path, lock)

    re = read_lock(lock_path)
    assert re.skills["skill1"].skill_path == "SKILL.md"
    assert re.skills["skill1"].agent_path is None
    assert re.skills["agent1"].skill_path is None
    assert re.skills["agent1"].agent_path == "agents/foo.md"


def test_v1_writer_omits_agent_path_when_none(tmp_path):
    """agentPath key absent from JSON when field is None (matches skillPath behaviour)."""
    lock_path = tmp_path / "agents-lock.json"
    lock = LockFile(version=1, skills={})
    entry = LockEntry(source="ajanderson1/test", source_type="github")
    lock = add_entry(lock, "foo", entry)
    write_lock(lock_path, lock)

    body = json.loads(lock_path.read_text())
    assert "agentPath" not in body["skills"]["foo"]
