"""Round-trip parent_url + read_only through v1 and v3 lock formats."""
import json
from pathlib import Path

from agent_toolkit_cli.skill_lock import (
    LockEntry, LockFile, add_entry, read_lock, write_lock,
)


def test_v1_writes_parent_url_and_read_only(tmp_path: Path):
    entry = LockEntry(
        source="vamseeachanta/workspace-hub",
        source_type="github",
        ref="main",
        skill_path="mkdocs",
        parent_url="https://github.com/vamseeachanta/workspace-hub",
        read_only=True,
    )
    lock = add_entry(LockFile(version=1, skills={}), "mkdocs", entry)
    path = tmp_path / "skills-lock.json"
    write_lock(path, lock)
    raw = json.loads(path.read_text())
    assert raw["skills"]["mkdocs"]["parentUrl"] == (
        "https://github.com/vamseeachanta/workspace-hub"
    )
    assert raw["skills"]["mkdocs"]["readOnly"] is True


def test_v1_round_trip_preserves_new_fields(tmp_path: Path):
    entry = LockEntry(
        source="o/r", source_type="github", ref="main",
        skill_path="sub", parent_url="https://github.com/o/r",
        read_only=True,
    )
    lock = add_entry(LockFile(version=1, skills={}), "sub", entry)
    path = tmp_path / "skills-lock.json"
    write_lock(path, lock)
    read = read_lock(path)
    e2 = read.skills["sub"]
    assert e2.parent_url == "https://github.com/o/r"
    assert e2.read_only is True
    assert e2.skill_path == "sub"


def test_v3_round_trip_preserves_new_fields(tmp_path: Path):
    raw = {
        "version": 3,
        "skills": {
            "mkdocs": {
                "source": "o/r",
                "sourceType": "github",
                "sourceUrl": "https://github.com/o/r",
                "skillPath": "mkdocs",
                "parentUrl": "https://github.com/o/r",
                "readOnly": True,
                "installedAt": "2026-05-21T00:00:00Z",
                "updatedAt": "2026-05-21T00:00:00Z",
            }
        },
    }
    path = tmp_path / ".skill-lock.json"
    path.write_text(json.dumps(raw))
    read = read_lock(path)
    assert read.version == 3
    e = read.skills["mkdocs"]
    assert e.parent_url == "https://github.com/o/r"
    assert e.read_only is True
    write_lock(path, read)
    raw2 = json.loads(path.read_text())
    assert raw2["skills"]["mkdocs"]["parentUrl"] == "https://github.com/o/r"
    assert raw2["skills"]["mkdocs"]["readOnly"] is True


def test_read_only_defaults_to_false_when_absent(tmp_path: Path):
    raw = {
        "version": 1,
        "skills": {
            "x": {"source": "o/r", "sourceType": "github", "skillPath": "SKILL.md"}
        },
    }
    path = tmp_path / "skills-lock.json"
    path.write_text(json.dumps(raw))
    read = read_lock(path)
    assert read.skills["x"].read_only is False
    assert read.skills["x"].parent_url is None
