import json
from pathlib import Path

from agent_toolkit_cli.skill_lock import (
    LockEntry,
    LockFile,
    add_entry,
    read_lock,
    remove_entry,
    write_lock,
)


def test_read_missing_file_returns_empty(tmp_path: Path):
    lock = read_lock(tmp_path / "nope.json")
    assert lock == LockFile(version=1, skills={})


def test_round_trip(tmp_path: Path):
    p = tmp_path / "skills-lock.json"
    lf = LockFile(
        version=1,
        skills={
            "journal": LockEntry(
                source="ajanderson1/journal",
                source_type="github",
                ref="main",
                skill_path="SKILL.md",
                upstream_sha="abc",
                local_sha="def",
            ),
        },
    )
    write_lock(p, lf)
    raw = json.loads(p.read_text())
    assert raw["version"] == 1
    assert raw["skills"]["journal"]["source"] == "ajanderson1/journal"
    assert raw["skills"]["journal"]["sourceType"] == "github"
    assert raw["skills"]["journal"]["upstreamSha"] == "abc"
    assert raw["skills"]["journal"]["localSha"] == "def"
    assert p.read_text().endswith("\n")
    assert read_lock(p) == lf


def test_keys_sorted_alphabetically(tmp_path: Path):
    p = tmp_path / "skills-lock.json"
    lf = LockFile(version=1, skills={})
    lf = add_entry(lf, "zeta", LockEntry(source="o/zeta", source_type="github"))
    lf = add_entry(lf, "alpha", LockEntry(source="o/alpha", source_type="github"))
    write_lock(p, lf)
    raw = p.read_text()
    assert raw.index('"alpha"') < raw.index('"zeta"')


def test_unknown_fields_in_input_are_preserved_on_round_trip(tmp_path: Path):
    p = tmp_path / "skills-lock.json"
    p.write_text(
        json.dumps(
            {
                "version": 1,
                "skills": {
                    "x": {
                        "source": "o/x",
                        "sourceType": "github",
                        "futureField": "yes",
                    },
                },
            }
        )
    )
    lf = read_lock(p)
    write_lock(p, lf)
    raw = json.loads(p.read_text())
    assert raw["skills"]["x"]["futureField"] == "yes"


def test_remove_entry():
    lf = LockFile(version=1, skills={"a": LockEntry(source="o/a", source_type="github")})
    lf = remove_entry(lf, "a")
    assert lf.skills == {}


def test_remove_unknown_entry_is_noop():
    lf = LockFile(version=1, skills={})
    assert remove_entry(lf, "nope") == lf


def test_bad_version_treated_as_empty(tmp_path: Path):
    p = tmp_path / "skills-lock.json"
    p.write_text('{"version": 999, "skills": {}}')
    lf = read_lock(p)
    assert lf == LockFile(version=1, skills={})


def test_unparseable_file_treated_as_empty(tmp_path: Path):
    p = tmp_path / "skills-lock.json"
    p.write_text("not json")
    lf = read_lock(p)
    assert lf == LockFile(version=1, skills={})
