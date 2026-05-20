"""_translate_pi_skill emits top-level name + description + optional argument-hint.

Spec: docs/superpowers/specs/2026-05-20-skill-sidecar-shape-design.md
"""
from __future__ import annotations

import yaml

from agent_toolkit_cli._translators import (
    _translate_codex_skill,
    _translate_opencode_skill,
    _translate_pi_skill,
)
from agent_toolkit_cli.walker import Asset, AssetRecord


def _record(*, harness_description: str, per_harness: dict | None = None) -> AssetRecord:
    metadata = {
        "apiVersion": "agent-toolkit/v1alpha2",
        "metadata": {
            "name": "demo",
            "description": "Concise CLI label.",
            "lifecycle": "experimental",
        },
        "spec": {
            "origin": "first-party",
            "vendored_via": "none",
            "harnesses": ["pi"],
            **({"per_harness": per_harness} if per_harness else {}),
        },
    }
    return AssetRecord(
        asset=Asset(kind="skill", slug="demo", path=None),  # path unused by translators
        metadata=metadata,
        body_excerpt="",
        requires={},
        harness_description=harness_description,
        cli_description="Concise CLI label.",
    )


def _parse_frontmatter(out: bytes) -> dict:
    text = out.decode("utf-8")
    assert text.startswith("---\n")
    end = text.find("\n---\n", 4)
    return yaml.safe_load(text[4:end])


def test_emits_top_level_name_and_description():
    record = _record(harness_description="Long harness description.")
    out = _translate_pi_skill(record, body="body\n")
    fm = _parse_frontmatter(out)
    assert fm["name"] == "demo"
    assert fm["description"] == "Long harness description."


def test_lifts_argument_hint_from_per_harness_pi():
    record = _record(
        harness_description="Long harness description.",
        per_harness={"pi": {"argument_hint": "<filename>"}},
    )
    out = _translate_pi_skill(record, body="body\n")
    fm = _parse_frontmatter(out)
    assert fm["argument-hint"] == "<filename>"


def test_omits_argument_hint_when_absent():
    record = _record(harness_description="Long harness description.")
    out = _translate_pi_skill(record, body="body\n")
    fm = _parse_frontmatter(out)
    assert "argument-hint" not in fm


def test_includes_agent_toolkit_cli_wrapper_for_traceability():
    record = _record(harness_description="Long harness description.")
    out = _translate_pi_skill(record, body="body\n")
    fm = _parse_frontmatter(out)
    assert "agent_toolkit_cli" in fm
    assert fm["agent_toolkit_cli"]["apiVersion"] == "agent-toolkit/v1alpha2"


def _legacy_inline_record() -> AssetRecord:
    """Mimic what the walker produces for a legacy inline-shape skill.

    Legacy skills have no sidecar, so the walker passes the v1alpha2
    wrapper as `metadata` and leaves harness_description/cli_description
    as None. Translators must fall back to the wrapper's metadata.description.
    """
    metadata = {
        "apiVersion": "agent-toolkit/v1alpha2",
        "metadata": {
            "name": "demo",
            "description": "Legacy combined description.",
            "lifecycle": "experimental",
        },
        "spec": {"origin": "first-party", "vendored_via": "none", "harnesses": ["pi"]},
    }
    return AssetRecord(
        asset=Asset(kind="skill", slug="demo", path=None),
        metadata=metadata,
        body_excerpt="",
        requires={},
        harness_description=None,
        cli_description=None,
    )


def test_legacy_fallback_pi():
    fm = _parse_frontmatter(_translate_pi_skill(_legacy_inline_record(), body=""))
    assert fm["description"] == "Legacy combined description."


def test_legacy_fallback_codex():
    fm = _parse_frontmatter(_translate_codex_skill(_legacy_inline_record(), body=""))
    assert fm["description"] == "Legacy combined description."


def test_legacy_fallback_opencode():
    fm = _parse_frontmatter(_translate_opencode_skill(_legacy_inline_record(), body=""))
    assert fm["description"] == "Legacy combined description."
    assert fm["name"] == "demo"
