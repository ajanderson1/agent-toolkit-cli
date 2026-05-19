"""spec.per_harness must accept arbitrary per-harness blocks.

Spec: docs/superpowers/specs/2026-05-20-skill-sidecar-shape-design.md
"""
from __future__ import annotations

import json
from importlib.resources import files

import jsonschema


def _schema():
    text = (files("agent_toolkit_cli") / "_schemas" / "asset-frontmatter.v1alpha2.json").read_text()
    return json.loads(text)


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


def test_per_harness_accepts_pi_argument_hint():
    doc = _base_skill_doc()
    doc["spec"]["per_harness"] = {"pi": {"argument_hint": "<filename>"}}
    jsonschema.validate(doc, _schema())


def test_per_harness_accepts_unknown_harness_block():
    doc = _base_skill_doc()
    doc["spec"]["per_harness"] = {"future_harness": {"any_key": "any_value"}}
    jsonschema.validate(doc, _schema())


def test_per_harness_absent_is_valid():
    doc = _base_skill_doc()
    jsonschema.validate(doc, _schema())
