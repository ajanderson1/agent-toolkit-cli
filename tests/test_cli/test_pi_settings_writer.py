"""Task 1: _pi_settings writer (add_package / remove_package).

Extra-key survival, atomic write, fail-loud on malformed JSON, project scope.
"""
import json

import pytest

from agent_toolkit_cli import _pi_settings as ps


def _seed(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2) + "\n")


def _global(home):
    return home / ".pi" / "agent" / "settings.json"


def test_add_package_preserves_all_other_keys(tmp_path):
    p = _global(tmp_path)
    _seed(p, {
        "model": "claude-opus",
        "mcpServers": {"foo": {"command": "x"}},
        "packages": ["npm:existing"],
        "theme": "dark",
    })
    ps.add_package("npm:@scope/new", scope="global", home=tmp_path)
    body = json.loads(p.read_text())
    # Other keys survive byte-for-value.
    assert body["model"] == "claude-opus"
    assert body["mcpServers"] == {"foo": {"command": "x"}}
    assert body["theme"] == "dark"
    # packages gained the new spec, kept the old, order preserved + appended.
    assert body["packages"] == ["npm:existing", "npm:@scope/new"]


def test_add_package_is_idempotent(tmp_path):
    p = _global(tmp_path)
    _seed(p, {"packages": ["npm:foo"]})
    ps.add_package("npm:foo", scope="global", home=tmp_path)
    body = json.loads(p.read_text())
    assert body["packages"] == ["npm:foo"]  # no duplicate


def test_add_package_creates_minimal_file_when_absent(tmp_path):
    # No settings.json at all -> create exactly {"packages": [spec]}.
    ps.add_package("npm:foo", scope="global", home=tmp_path)
    body = json.loads(_global(tmp_path).read_text())
    assert body == {"packages": ["npm:foo"]}


def test_add_package_creates_packages_key_when_other_keys_exist(tmp_path):
    p = _global(tmp_path)
    _seed(p, {"model": "x"})  # no packages key yet
    ps.add_package("npm:foo", scope="global", home=tmp_path)
    body = json.loads(p.read_text())
    assert body["model"] == "x"
    assert body["packages"] == ["npm:foo"]


def test_remove_package_preserves_other_keys(tmp_path):
    p = _global(tmp_path)
    _seed(p, {"model": "x", "packages": ["npm:foo", "npm:bar"]})
    ps.remove_package("npm:foo", scope="global", home=tmp_path)
    body = json.loads(p.read_text())
    assert body["model"] == "x"
    assert body["packages"] == ["npm:bar"]


def test_remove_package_absent_is_noop(tmp_path):
    p = _global(tmp_path)
    _seed(p, {"packages": ["npm:bar"]})
    ps.remove_package("npm:foo", scope="global", home=tmp_path)
    assert json.loads(p.read_text())["packages"] == ["npm:bar"]


def test_remove_package_on_missing_file_is_noop(tmp_path):
    # Nothing to remove, nothing to create.
    ps.remove_package("npm:foo", scope="global", home=tmp_path)
    assert not _global(tmp_path).exists()


def test_add_package_malformed_existing_raises_and_does_not_clobber(tmp_path):
    p = _global(tmp_path)
    p.parent.mkdir(parents=True)
    original = "{ this is not json"
    p.write_text(original)
    with pytest.raises(ps.PiSettingsError):
        ps.add_package("npm:foo", scope="global", home=tmp_path)
    # The bad file is LEFT UNTOUCHED — we never overwrite config we can't parse.
    assert p.read_text() == original


def test_add_package_non_object_top_level_raises(tmp_path):
    p = _global(tmp_path)
    p.parent.mkdir(parents=True)
    p.write_text("[1, 2, 3]")
    with pytest.raises(ps.PiSettingsError):
        ps.add_package("npm:foo", scope="global", home=tmp_path)


def test_add_package_packages_not_list_raises(tmp_path):
    p = _global(tmp_path)
    _seed(p, {"packages": "not-a-list"})
    with pytest.raises(ps.PiSettingsError):
        ps.add_package("npm:foo", scope="global", home=tmp_path)


def test_project_scope_writes_project_file_only(tmp_path):
    proj = tmp_path / "proj"
    ps.add_package("npm:foo", scope="project", project=proj)
    proj_settings = proj / ".pi" / "settings.json"
    assert json.loads(proj_settings.read_text())["packages"] == ["npm:foo"]
    # global file untouched / absent
    assert not (tmp_path / ".pi" / "agent" / "settings.json").exists()


def test_atomic_write_no_partial_temp_left(tmp_path):
    p = _global(tmp_path)
    _seed(p, {"packages": []})
    ps.add_package("npm:foo", scope="global", home=tmp_path)
    # No stray temp sibling left behind.
    siblings = [x.name for x in p.parent.iterdir()]
    assert siblings == ["settings.json"]
