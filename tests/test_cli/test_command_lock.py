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


@pytest.mark.parametrize("bad", ["../COMMAND.md", "/tmp/COMMAND.md", "sub/../COMMAND.md", "COMMAND.txt"])
def test_command_lock_rejects_unsafe_command_path(tmp_path, bad):
    path = tmp_path / "commands-lock.json"
    path.write_text('{"version":1,"skills":{"demo":{"source":"x","sourceType":"git","commandPath":%r}}}' % bad)
    with pytest.raises(ValueError):
        read_lock(path)
