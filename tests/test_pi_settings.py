import json
from pathlib import Path

import pytest

from agent_toolkit_cli._pi_settings import read_packages


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
