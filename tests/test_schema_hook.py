"""Schema validation cases for kind: hook with spec.hook block."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

SCHEMA_PATH = Path(__file__).parent.parent / "src/agent_toolkit_cli/_schemas/asset-frontmatter.v1alpha2.json"


@pytest.fixture
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _base_hook_doc() -> dict:
    return {
        "apiVersion": "agent-toolkit/v1alpha2",
        "metadata": {
            "name": "demo-hook",
            "description": "A demo hook.",
            "kind": "hook",
            "lifecycle": "experimental",
        },
        "spec": {
            "origin": "first-party",
            "vendored_via": "none",
            "harnesses": ["codex"],
            "hook": {
                "events": ["PreToolUse"],
                "command": "check.sh",
            },
        },
    }


def test_kind_hook_with_spec_hook_passes(schema):
    jsonschema.validate(_base_hook_doc(), schema)


def test_kind_hook_without_spec_hook_fails(schema):
    doc = _base_hook_doc()
    del doc["spec"]["hook"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(doc, schema)


def test_kind_hook_unknown_event_fails(schema):
    doc = _base_hook_doc()
    doc["spec"]["hook"]["events"] = ["NotAnEvent"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(doc, schema)


def test_kind_hook_empty_events_fails(schema):
    doc = _base_hook_doc()
    doc["spec"]["hook"]["events"] = []
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(doc, schema)


def test_kind_hook_with_all_optional_fields_passes(schema):
    doc = _base_hook_doc()
    doc["spec"]["hook"].update({
        "matcher": "^Bash$",
        "timeout": 10,
        "async": False,
        "status_message": "checking",
    })
    jsonschema.validate(doc, schema)


def test_non_hook_kind_without_spec_hook_passes(schema):
    """spec.hook is only required when kind == hook."""
    doc = _base_hook_doc()
    doc["metadata"]["kind"] = "skill"
    del doc["spec"]["hook"]
    jsonschema.validate(doc, schema)


def test_kind_skill_with_spec_hook_fails(schema):
    """spec.hook must not appear on non-hook kinds (negative enforcement)."""
    doc = _base_hook_doc()
    doc["metadata"]["kind"] = "skill"
    # Skill doesn't legitimately use spec.hook — schema must reject it.
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(doc, schema)
