import json

import pytest

from agent_toolkit_cli.command_lock import LockEntry, LockFile, read_lock, write_lock


def test_command_lock_round_trips_command_path(tmp_path):
    path = tmp_path / "commands-lock.json"
    lock = LockFile(version=1, skills={
        "demo": LockEntry(source="owner/repo", source_type="github", ref="main", command_path="COMMAND.md", upstream_sha="abc1234")
    })
    write_lock(path, lock)
    loaded = read_lock(path)
    assert loaded.skills["demo"].command_path == "COMMAND.md"
    assert loaded.skills["demo"].harnesses == ()


@pytest.mark.parametrize("bad", ["../COMMAND.md", "/tmp/COMMAND.md", "sub/../COMMAND.md", "COMMAND.txt"])
def test_command_lock_rejects_unsafe_command_path(tmp_path, bad):
    path = tmp_path / "commands-lock.json"
    path.write_text('{"version":1,"skills":{"demo":{"source":"x","sourceType":"git","commandPath":%r}}}' % bad)
    with pytest.raises(ValueError):
        read_lock(path)


def test_legacy_lock_missing_harnesses_defaults_empty(tmp_path):
    path = tmp_path / "commands-lock.json"
    legacy = {
        "version": 1,
        "skills": {"demo": {"source": "o/r", "sourceType": "github"}},
    }
    path.write_text(json.dumps(legacy))
    assert read_lock(path).skills["demo"].harnesses == ()


def test_harnesses_must_be_list_of_strings(tmp_path):
    path = tmp_path / "commands-lock.json"
    path.write_text(json.dumps({
        "version": 1,
        "skills": {"demo": {"source": "o/r", "sourceType": "github", "harnesses": "standard"}},
    }))
    with pytest.raises(ValueError, match="list"):
        read_lock(path)

    path.write_text(json.dumps({
        "version": 1,
        "skills": {"demo": {"source": "o/r", "sourceType": "github", "harnesses": [1]}},
    }))
    with pytest.raises(ValueError, match="strings"):
        read_lock(path)


def test_write_lock_omits_empty_harnesses_and_dedupes(tmp_path):
    path = tmp_path / "commands-lock.json"
    lock = LockFile(version=1, skills={
        "empty": LockEntry(source="o/r", source_type="github"),
        "demo": LockEntry(
            source="o/r",
            source_type="github",
            harnesses=("standard", "pi", "standard"),
            extras={"note": "keep"},
        ),
    })
    write_lock(path, lock)
    raw = json.loads(path.read_text())
    assert "harnesses" not in raw["skills"]["empty"]
    assert raw["skills"]["demo"]["harnesses"] == ["standard", "pi"]
    assert raw["skills"]["demo"]["note"] == "keep"
    loaded = read_lock(path)
    assert loaded.skills["demo"].harnesses == ("standard", "pi")
    assert loaded.skills["demo"].extras["note"] == "keep"


def test_positional_lock_entry_extras_still_binds():
    """harnesses is after extras so legacy positional extras keep working."""
    entry = LockEntry("o/r", "github", None, None, None, None, None, False, {"k": 1})
    assert entry.extras == {"k": 1}
    assert entry.harnesses == ()
