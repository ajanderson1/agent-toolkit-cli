import json

from agent_toolkit_cli.skill_lock import (
    LockEntry,
    LockFile,
    read_lock,
    write_lock,
)


def _entry(**kw) -> LockEntry:
    return LockEntry(source="github.com/o/r", source_type="github", **kw)


def test_field_exists_defaults_none():
    assert _entry().pi_extension_path is None


def test_v1_round_trip_pi_extension_path(tmp_path):
    p = tmp_path / "pi-extensions-lock.json"
    lf = LockFile(version=1, skills={"ext": _entry(pi_extension_path="ext")})
    write_lock(p, lf)
    body = json.loads(p.read_text())
    assert body["skills"]["ext"]["piExtensionPath"] == "ext"
    assert read_lock(p) == lf


def test_v3_round_trip_pi_extension_path(tmp_path):
    p = tmp_path / "pi-extensions-lock.json"
    lf = LockFile(version=3, skills={"ext": _entry(pi_extension_path="ext")})
    write_lock(p, lf)
    body = json.loads(p.read_text())
    assert body["skills"]["ext"]["piExtensionPath"] == "ext"
    # v3 injects installedAt/updatedAt/sourceUrl on write (timestamps land in
    # extras on read), so the codebase verifies v3 round-trips by asserting the
    # field survives, not by full-object equality. See test_skill_lock.py.
    assert read_lock(p).skills["ext"].pi_extension_path == "ext"


def test_not_swept_into_extras(tmp_path):
    p = tmp_path / "pi-extensions-lock.json"
    p.write_text(json.dumps({
        "version": 1,
        "skills": {"ext": {"source": "x", "sourceType": "github",
                           "piExtensionPath": "ext"}},
    }) + "\n")
    e = read_lock(p).skills["ext"]
    assert e.pi_extension_path == "ext"
    assert "piExtensionPath" not in e.extras
