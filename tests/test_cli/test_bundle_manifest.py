from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_toolkit_cli.bundle_manifest import (
    BundleManifest,
    BundleMember,
    ManifestError,
    load,
    parse,
)


def _valid() -> dict:
    return {
        "schema_version": 1,
        "name": "team-review",
        "description": "demo",
        "members": [
            {"asset_type": "agent", "source": "owner/repo/agents/code-reviewer",
             "slug": "code-reviewer", "ref": "v2.1.0"},
            {"asset_type": "skill", "source": "owner/repo/git-worktrees"},
            {"asset_type": "pi-extension", "source": "owner/repo/token-meter",
             "slug": "token-meter"},
        ],
    }


def test_parse_valid_manifest():
    m = parse(_valid())
    assert isinstance(m, BundleManifest)
    assert m.name == "team-review"
    assert len(m.members) == 3
    first = m.members[0]
    assert isinstance(first, BundleMember)
    assert first.asset_type == "agent"
    assert first.source == "owner/repo/agents/code-reviewer"
    assert first.slug == "code-reviewer"
    assert first.ref == "v2.1.0"


def test_member_defaults_optional_fields():
    m = parse(_valid())
    skill = m.members[1]
    assert skill.slug is None
    assert skill.ref is None


def test_unknown_schema_version_rejected():
    data = _valid()
    data["schema_version"] = 2
    with pytest.raises(ManifestError, match="schema_version"):
        parse(data)


def test_missing_schema_version_rejected():
    data = _valid()
    del data["schema_version"]
    with pytest.raises(ManifestError, match="schema_version"):
        parse(data)


def test_missing_name_rejected():
    data = _valid()
    del data["name"]
    with pytest.raises(ManifestError, match="name"):
        parse(data)


def test_empty_members_rejected():
    data = _valid()
    data["members"] = []
    with pytest.raises(ManifestError, match="members"):
        parse(data)


def test_unknown_asset_type_rejected():
    data = _valid()
    data["members"][0]["asset_type"] = "wormhole"
    with pytest.raises(ManifestError, match="asset_type"):
        parse(data)


def test_instructions_member_rejected():
    data = _valid()
    data["members"][0] = {"asset_type": "instructions"}
    with pytest.raises(ManifestError, match="not a bundle member type"):
        parse(data)


def test_installable_member_missing_source_rejected():
    data = _valid()
    del data["members"][1]["source"]  # skill member with no source
    with pytest.raises(ManifestError, match="source"):
        parse(data)


def test_mcp_member_parses_without_error():
    data = _valid()
    data["members"].append({"asset_type": "mcp", "source": "owner/repo/ctx7",
                            "slug": "context7"})
    m = parse(data)
    assert m.members[-1].asset_type == "mcp"


def test_load_reads_json_file(tmp_path: Path):
    p = tmp_path / "b.bundle.json"
    p.write_text(json.dumps(_valid()))
    m = load(p)
    assert m.name == "team-review"


def test_load_bad_json_raises_manifest_error(tmp_path: Path):
    p = tmp_path / "bad.json"
    p.write_text("{not json")
    with pytest.raises(ManifestError, match="JSON"):
        load(p)


def test_load_missing_file_raises_manifest_error(tmp_path: Path):
    with pytest.raises(ManifestError, match="not found"):
        load(tmp_path / "nope.json")


def test_pi_extension_member_with_ref_rejected():
    data = _valid()
    data["members"][2]["ref"] = "v1.2.3"  # the pi-extension member
    with pytest.raises(ManifestError, match="pi-extension does not support ref"):
        parse(data)


def test_non_string_description_rejected():
    data = _valid()
    data["description"] = False
    with pytest.raises(ManifestError, match="description"):
        parse(data)


@pytest.mark.parametrize("field", ["source", "slug", "ref"])
def test_dash_prefixed_field_rejected(field):
    data = _valid()
    data["members"][0][field] = "--force"
    with pytest.raises(ManifestError, match="must not start with '-'"):
        parse(data)
