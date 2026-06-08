"""Task 1 (#333): npm identity normalization + remove_package_by_identity.

remove_package stays exact-match; the new identity remover catches drift
(missing npm: prefix, version-pinned variants) so global deselect works.
"""
import json

import pytest

from agent_toolkit_cli import _pi_settings as ps


def _seed(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2) + "\n")


def _global(home):
    return home / ".pi" / "agent" / "settings.json"


@pytest.mark.parametrize(
    "spec,identity",
    [
        ("npm:foo", "foo"),
        ("foo", "foo"),
        ("npm:foo@1.2.3", "foo"),
        ("foo@1.2.3", "foo"),
        ("npm:@scope/name", "@scope/name"),
        ("@scope/name", "@scope/name"),
        ("npm:@scope/name@1.2.3", "@scope/name"),
        ("@scope/name@1.2.3", "@scope/name"),
    ],
)
def test_npm_identity_normalizes(spec, identity):
    assert ps._npm_identity(spec) == identity


def test_remove_by_identity_strips_version_pinned_drift(tmp_path):
    p = _global(tmp_path)
    # lock stored npm:foo; settings has a version-pinned, prefix-less variant.
    _seed(p, {"model": "x", "packages": ["foo@1.2.3", "npm:keep"]})
    ps.remove_package_by_identity("npm:foo", scope="global", home=tmp_path)
    body = json.loads(p.read_text())
    assert body["model"] == "x"          # other keys survive
    assert body["packages"] == ["npm:keep"]  # the foo variant is gone


def test_remove_by_identity_removes_all_matching_variants(tmp_path):
    p = _global(tmp_path)
    _seed(p, {"packages": ["npm:foo", "foo@2", "npm:other"]})
    ps.remove_package_by_identity("foo", scope="global", home=tmp_path)
    assert json.loads(p.read_text())["packages"] == ["npm:other"]


def test_remove_by_identity_scoped_name_not_overmatched(tmp_path):
    p = _global(tmp_path)
    _seed(p, {"packages": ["npm:@scope/name", "npm:name"]})
    ps.remove_package_by_identity("@scope/name", scope="global", home=tmp_path)
    # only the scoped one goes; the unscoped "name" stays.
    assert json.loads(p.read_text())["packages"] == ["npm:name"]


def test_remove_by_identity_absent_is_noop(tmp_path):
    p = _global(tmp_path)
    _seed(p, {"packages": ["npm:bar"]})
    ps.remove_package_by_identity("npm:foo", scope="global", home=tmp_path)
    assert json.loads(p.read_text())["packages"] == ["npm:bar"]


def test_remove_by_identity_missing_file_is_noop(tmp_path):
    ps.remove_package_by_identity("npm:foo", scope="global", home=tmp_path)
    assert not _global(tmp_path).exists()


def test_remove_by_identity_malformed_raises(tmp_path):
    p = _global(tmp_path)
    p.parent.mkdir(parents=True)
    p.write_text("{ not json")
    with pytest.raises(ps.PiSettingsError):
        ps.remove_package_by_identity("npm:foo", scope="global", home=tmp_path)
