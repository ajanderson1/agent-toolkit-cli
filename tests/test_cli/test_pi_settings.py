import json

import pytest

from agent_toolkit_cli import _pi_settings as ps


def _write(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj))


def test_global_settings_path(tmp_path):
    assert ps.settings_path(scope="global", home=tmp_path) == (
        tmp_path / ".pi" / "agent" / "settings.json"
    )


def test_project_settings_path(tmp_path):
    proj = tmp_path / "proj"
    assert ps.settings_path(scope="project", project=proj) == (
        proj / ".pi" / "settings.json"
    )


def test_read_packages_global(tmp_path):
    _write(tmp_path / ".pi" / "agent" / "settings.json",
           {"packages": ["npm:foo", "git:github.com/o/r"]})
    assert ps.read_packages(scope="global", home=tmp_path) == [
        "npm:foo", "git:github.com/o/r",
    ]


def test_read_extensions_paths(tmp_path):
    _write(tmp_path / ".pi" / "agent" / "settings.json",
           {"extensions": ["./local-ext", "/abs/ext"]})
    assert ps.read_extension_paths(scope="global", home=tmp_path) == [
        "./local-ext", "/abs/ext",
    ]


def test_missing_file_returns_empty(tmp_path):
    assert ps.read_packages(scope="global", home=tmp_path) == []
    assert ps.read_extension_paths(scope="global", home=tmp_path) == []


def test_malformed_json_raises(tmp_path):
    p = tmp_path / ".pi" / "agent" / "settings.json"
    p.parent.mkdir(parents=True)
    p.write_text("{ not json")
    with pytest.raises(ps.PiSettingsError):
        ps.read_packages(scope="global", home=tmp_path)
