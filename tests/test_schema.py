import json
from pathlib import Path

import jsonschema
import pytest

SCHEMA_PATH = Path(__file__).parent.parent / "schemas" / "asset-frontmatter.v1alpha2.json"


def test_minimal_valid_frontmatter_passes():
    schema = json.loads(SCHEMA_PATH.read_text())
    data = {
        "apiVersion": "agent-toolkit/v1alpha2",
        "metadata": {
            "name": "example",
            "description": "An example asset.",
            "lifecycle": "stable",
        },
        "spec": {
            "origin": "first-party",
            "vendored_via": "none",
            "harnesses": ["claude"],
        },
    }
    jsonschema.validate(data, schema)


def _load_schema():
    return json.loads(SCHEMA_PATH.read_text())


def _base():
    return {
        "apiVersion": "agent-toolkit/v1alpha2",
        "metadata": {
            "name": "example",
            "description": "An example asset.",
            "lifecycle": "stable",
        },
        "spec": {
            "origin": "first-party",
            "vendored_via": "none",
            "harnesses": ["claude"],
        },
    }


def test_third_party_requires_upstream():
    schema = _load_schema()
    data = _base()
    data["spec"]["origin"] = "third-party"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(data, schema)
    data["spec"]["upstream"] = "https://example.com/repo"
    jsonschema.validate(data, schema)


def test_submodule_fork_is_optional():
    """spec.fork is optional under vendored_via=submodule (unpatched upstreams need no fork)."""
    schema = _load_schema()
    data = _base()
    data["spec"]["origin"] = "third-party"
    data["spec"]["upstream"] = "https://example.com/repo"
    data["spec"]["vendored_via"] = "submodule"
    # submodule without fork must now be valid
    jsonschema.validate(data, schema)
    # submodule with fork must also remain valid
    data["spec"]["fork"] = "https://github.com/ajanderson1/repo"
    jsonschema.validate(data, schema)


def test_description_must_end_with_period():
    schema = _load_schema()
    data = _base()
    data["metadata"]["description"] = "no period"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(data, schema)


def test_name_pattern_rejects_uppercase():
    schema = _load_schema()
    data = _base()
    data["metadata"]["name"] = "BadName"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(data, schema)


def test_harnesses_must_be_unique():
    schema = _load_schema()
    data = _base()
    data["spec"]["harnesses"] = ["claude", "claude"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(data, schema)


def test_harnesses_minimum_one():
    schema = _load_schema()
    data = _base()
    data["spec"]["harnesses"] = []
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(data, schema)


def test_harnesses_closed_enum():
    schema = _load_schema()
    data = _base()
    data["spec"]["harnesses"] = ["claude", "novel-harness"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(data, schema)


def test_harnesses_enum_matches_all_harnesses():
    """Schema enum must include every entry in ALL_HARNESSES — otherwise a
    user declaring a newly-supported harness in `spec.harnesses` would fail
    frontmatter validation even though the registry says the pair is
    supported. Regression guard for #53 (gemini was added to ALL_HARNESSES
    but the schema enum was a separate literal that drifted)."""
    from agent_toolkit_cli._support import ALL_HARNESSES

    schema = _load_schema()
    enum = set(schema["properties"]["spec"]["properties"]["harnesses"]["items"]["enum"])
    assert set(ALL_HARNESSES) == enum, (
        f"schema enum {enum} drifted from ALL_HARNESSES {set(ALL_HARNESSES)}"
    )

    # Smoke: each ALL_HARNESSES member individually passes schema validation.
    for h in ALL_HARNESSES:
        data = _base()
        data["spec"]["harnesses"] = [h]
        jsonschema.validate(data, schema)


def test_metadata_no_extra_keys():
    schema = _load_schema()
    data = _base()
    data["metadata"]["unrecognised"] = "x"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(data, schema)


def test_spec_no_extra_keys():
    schema = _load_schema()
    data = _base()
    data["spec"]["unrecognised"] = "x"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(data, schema)


def test_apiversion_must_be_v1alpha2():
    schema = _load_schema()
    data = _base()
    data["apiVersion"] = "agent-toolkit/v2"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(data, schema)
