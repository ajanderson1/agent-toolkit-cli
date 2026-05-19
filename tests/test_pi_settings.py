import json
from pathlib import Path

import pytest

from agent_toolkit_cli._pi_settings import (
    add_package,
    read_extensions_overrides,
    read_packages,
    remove_package,
    write_packages,
)


def test_read_packages_missing_file(tmp_path: Path):
    assert read_packages(tmp_path / "nope.json") == []


def test_read_packages_empty_file(tmp_path: Path):
    p = tmp_path / "settings.json"
    p.write_text("")
    assert read_packages(p) == []


def test_read_packages_with_entries(tmp_path: Path):
    p = tmp_path / "settings.json"
    p.write_text(
        json.dumps(
            {
                "packages": ["npm:pi-subagents", "git:github.com/u/r@v1"],
                "unrelated": "ignored",
            }
        )
    )
    assert read_packages(p) == ["npm:pi-subagents", "git:github.com/u/r@v1"]


def test_read_packages_packages_missing(tmp_path: Path):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"other": "key"}))
    assert read_packages(p) == []


def test_read_packages_malformed_json_raises(tmp_path: Path):
    p = tmp_path / "settings.json"
    p.write_text("{ not json")
    with pytest.raises(ValueError) as exc:
        read_packages(p)
    assert "settings.json" in str(exc.value).lower()


def test_write_packages_preserves_unknown_keys(tmp_path: Path):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"packages": [], "other": {"keep": 1}}))
    write_packages(p, ["npm:foo"])
    parsed = json.loads(p.read_text())
    assert parsed["packages"] == ["npm:foo"]
    assert parsed["other"] == {"keep": 1}


def test_write_packages_creates_missing_file(tmp_path: Path):
    p = tmp_path / "missing" / "settings.json"
    write_packages(p, ["npm:foo"])
    parsed = json.loads(p.read_text())
    assert parsed == {"packages": ["npm:foo"]}


def test_add_package_idempotent(tmp_path: Path):
    p = tmp_path / "settings.json"
    add_package(p, "npm:foo")
    add_package(p, "npm:foo")
    parsed = json.loads(p.read_text())
    assert parsed["packages"] == ["npm:foo"]


def test_remove_package_idempotent(tmp_path: Path):
    p = tmp_path / "settings.json"
    add_package(p, "npm:foo")
    remove_package(p, "npm:foo")
    remove_package(p, "npm:foo")
    parsed = json.loads(p.read_text())
    assert parsed["packages"] == []


def test_read_extensions_overrides_missing_file(tmp_path: Path):
    assert read_extensions_overrides(tmp_path / "nope.json") == []


def test_read_extensions_overrides_missing_key(tmp_path: Path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"packages": ["npm:foo"]}), encoding="utf-8")
    assert read_extensions_overrides(p) == []


def test_read_extensions_overrides_returns_list(tmp_path: Path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"extensions": ["!foo", "+bar"]}), encoding="utf-8")
    assert read_extensions_overrides(p) == ["!foo", "+bar"]


def test_read_extensions_overrides_non_list_returns_empty(tmp_path: Path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"extensions": "huh"}), encoding="utf-8")
    assert read_extensions_overrides(p) == []


def test_read_extensions_overrides_malformed_raises(tmp_path: Path):
    p = tmp_path / "s.json"
    p.write_text("{not-json", encoding="utf-8")
    try:
        read_extensions_overrides(p)
    except ValueError as exc:
        assert "malformed settings.json" in str(exc)
    else:
        raise AssertionError("expected ValueError")
