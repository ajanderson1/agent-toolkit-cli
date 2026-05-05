"""Unit tests for translator functions in agent_toolkit._translators."""
from __future__ import annotations

from pathlib import Path

import yaml

from agent_toolkit._translators import (
    TRANSLATORS,
    _translate_opencode_agent,
    _translate_opencode_command,
)
from agent_toolkit.walker import Asset, AssetRecord


def _make_record(slug: str, description: str, harnesses: list[str]) -> AssetRecord:
    """Build an AssetRecord with a minimal valid v1alpha2 metadata dict."""
    metadata = {
        "apiVersion": "agent-toolkit/v1alpha2",
        "metadata": {
            "name": slug,
            "description": description,
            "lifecycle": "stable",
        },
        "spec": {
            "origin": "first-party",
            "vendored_via": "none",
            "harnesses": harnesses,
        },
    }
    asset = Asset(kind="agent", slug=slug, path=Path(f"/fake/agents/{slug}.md"))
    return AssetRecord(asset=asset, metadata=metadata, body_excerpt="", requires={})


def test_translate_opencode_agent_emits_required_native_keys():
    record = _make_record("foo", "Foo agent — does foo things.", ["claude", "opencode"])
    body = "# Foo agent\n\nBody content.\n"

    out = _translate_opencode_agent(record, body)

    assert isinstance(out, bytes)
    text = out.decode("utf-8")
    assert text.startswith("---\n")
    end_idx = text.find("\n---\n", 4)
    assert end_idx != -1, "frontmatter missing closing fence"
    fm = yaml.safe_load(text[4:end_idx])

    assert fm["description"] == "Foo agent — does foo things."
    assert fm["mode"] == "subagent"


def test_translate_opencode_agent_preserves_wrapper_under_agent_toolkit_key():
    record = _make_record("foo", "desc", ["claude", "opencode"])
    out = _translate_opencode_agent(record, "")
    text = out.decode("utf-8")
    end_idx = text.find("\n---\n", 4)
    fm = yaml.safe_load(text[4:end_idx])

    assert fm["agent_toolkit"]["apiVersion"] == "agent-toolkit/v1alpha2"
    assert fm["agent_toolkit"]["metadata"]["name"] == "foo"
    assert fm["agent_toolkit"]["spec"]["harnesses"] == ["claude", "opencode"]


def test_translate_opencode_agent_appends_body():
    record = _make_record("foo", "desc", ["opencode"])
    body = "# Heading\n\nParagraph.\n"
    out = _translate_opencode_agent(record, body)
    text = out.decode("utf-8")
    # Body must appear after the closing fence
    closing_fence_at = text.find("\n---\n", 4)
    after = text[closing_fence_at + len("\n---\n"):]
    assert after == body


def test_translate_opencode_agent_round_trip_stable():
    record = _make_record("foo", "desc", ["opencode"])
    body = "Body.\n"
    a = _translate_opencode_agent(record, body)
    b = _translate_opencode_agent(record, body)
    assert a == b


def test_translators_dict_has_opencode_agent_entry():
    assert ("opencode", "agent") in TRANSLATORS
    assert TRANSLATORS[("opencode", "agent")] is _translate_opencode_agent


def _make_command_record(slug: str, description: str) -> AssetRecord:
    metadata = {
        "apiVersion": "agent-toolkit/v1alpha2",
        "metadata": {
            "name": slug,
            "description": description,
            "lifecycle": "stable",
        },
        "spec": {"origin": "first-party", "vendored_via": "none", "harnesses": ["opencode"]},
    }
    asset = Asset(kind="command", slug=slug, path=Path(f"/fake/commands/{slug}.md"))
    return AssetRecord(asset=asset, metadata=metadata, body_excerpt="", requires={})


def test_translate_opencode_command_has_description_and_no_mode():
    record = _make_command_record("explain", "Explain something.")
    out = _translate_opencode_command(record, "Body.\n")
    text = out.decode("utf-8")
    end_idx = text.find("\n---\n", 4)
    fm = yaml.safe_load(text[4:end_idx])
    assert fm["description"] == "Explain something."
    assert "mode" not in fm
    assert fm["agent_toolkit"]["metadata"]["name"] == "explain"


def test_translate_opencode_command_round_trip_stable():
    record = _make_command_record("explain", "desc")
    a = _translate_opencode_command(record, "x")
    b = _translate_opencode_command(record, "x")
    assert a == b


def test_translators_dict_has_opencode_command_entry():
    assert ("opencode", "command") in TRANSLATORS
    assert TRANSLATORS[("opencode", "command")] is _translate_opencode_command
