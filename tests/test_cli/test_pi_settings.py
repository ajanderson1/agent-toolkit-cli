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


def test_read_packages_accepts_current_pi_source_objects(tmp_path):
    _write(
        tmp_path / ".pi" / "agent" / "settings.json",
        {"packages": [{"source": "npm:foo"}, {"source": "git:github.com/o/r"}]},
    )
    assert ps.read_packages(scope="global", home=tmp_path) == [
        "npm:foo", "git:github.com/o/r",
    ]


@pytest.mark.parametrize(
    "invalid_entry",
    [
        {"source": "npm:foo", "skills": "not-a-list"},
        {"source": "npm:foo", "skills": [123]},
        {"source": "npm:foo", "extensions": "not-a-list"},
        {"source": "npm:foo", "prompts": "not-a-list"},
        {"source": "npm:foo", "themes": "not-a-list"},
        {"source": "npm:foo", "autoload": "not-a-bool"},
    ],
)
def test_read_packages_rejects_invalid_filter_types(tmp_path, invalid_entry):
    _write(tmp_path / ".pi" / "agent" / "settings.json", {"packages": [invalid_entry]})
    with pytest.raises(ps.PiSettingsError):
        ps.read_packages(scope="global", home=tmp_path)


def test_read_packages_accepts_package_objects_with_resource_filters(tmp_path):
    _write(
        tmp_path / ".pi" / "agent" / "settings.json",
        {
            "packages": [
                {"source": "git:github.com/ajanderson1/pi-superpowers", "skills": []},
                {
                    "source": "npm:pi-web-access",
                    "extensions": ["ext.ts"],
                    "autoload": False,
                },
            ]
        },
    )
    assert ps.read_packages(scope="global", home=tmp_path) == [
        "git:github.com/ajanderson1/pi-superpowers",
        "npm:pi-web-access",
    ]


@pytest.mark.parametrize(
    "packages",
    [
        [{"source": 42}],
        [{}],
    ],
)
def test_read_packages_rejects_malformed_objects(tmp_path, packages):
    _write(tmp_path / ".pi" / "agent" / "settings.json", {"packages": packages})
    with pytest.raises(ps.PiSettingsError):
        ps.read_packages(scope="global", home=tmp_path)


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
