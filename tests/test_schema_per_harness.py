"""spec.per_harness must accept arbitrary per-harness blocks.

Spec: docs/superpowers/specs/2026-05-20-skill-sidecar-shape-design.md
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

SCHEMA_PATH = Path(__file__).parent.parent / "src/agent_toolkit_cli/_schemas/asset-frontmatter.v1alpha2.json"


@pytest.fixture
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _base_skill_doc() -> dict:
    return {
        "apiVersion": "agent-toolkit/v1alpha2",
        "metadata": {
            "name": "demo",
            "description": "Concise CLI label.",
            "lifecycle": "experimental",
        },
        "spec": {
            "origin": "first-party",
            "vendored_via": "none",
            "harnesses": ["claude", "pi"],
        },
    }


def test_per_harness_accepts_pi_argument_hint(schema):
    doc = _base_skill_doc()
    doc["spec"]["per_harness"] = {"pi": {"argument_hint": "<filename>"}}
    jsonschema.validate(doc, schema)


def test_per_harness_accepts_unknown_harness_block(schema):
    doc = _base_skill_doc()
    doc["spec"]["per_harness"] = {"future_harness": {"any_key": "any_value"}}
    jsonschema.validate(doc, schema)


def test_per_harness_absent_is_valid(schema):
    doc = _base_skill_doc()
    jsonschema.validate(doc, schema)


def test_per_harness_rejects_non_object_value(schema):
    doc = _base_skill_doc()
    doc["spec"]["per_harness"] = {"pi": "string_not_object"}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(doc, schema)
