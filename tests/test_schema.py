import json
from pathlib import Path

import jsonschema
import pytest

SCHEMA_PATH = Path(__file__).parent.parent / "schemas" / "asset-frontmatter.v1alpha1.json"


def test_minimal_valid_frontmatter_passes():
    schema = json.loads(SCHEMA_PATH.read_text())
    data = {
        "apiVersion": "agent-toolkit/v1alpha1",
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
        "apiVersion": "agent-toolkit/v1alpha1",
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


def test_submodule_requires_fork():
    schema = _load_schema()
    data = _base()
    data["spec"]["origin"] = "third-party"
    data["spec"]["upstream"] = "https://example.com/repo"
    data["spec"]["vendored_via"] = "submodule"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(data, schema)
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


def test_apiversion_must_be_v1alpha1():
    schema = _load_schema()
    data = _base()
    data["apiVersion"] = "agent-toolkit/v2"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(data, schema)
