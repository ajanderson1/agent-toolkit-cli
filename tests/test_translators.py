"""Unit tests for translator functions in agent_toolkit_cli._translators."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from agent_toolkit_cli._repo_resolution import resolve_toolkit_root
from agent_toolkit_cli._translators import (
    TRANSLATORS,
    _translate_codex_agent,
    _translate_codex_skill,
    _translate_gemini_agent,
    _translate_gemini_command,
    _translate_opencode_agent,
    _translate_opencode_command,
    _translate_opencode_skill,
)
from agent_toolkit_cli.walker import (
    Asset,
    AssetRecord,
    discover_assets,
    load_asset_record,
    strip_frontmatter,
)


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

    assert fm["agent_toolkit_cli"]["apiVersion"] == "agent-toolkit/v1alpha2"
    assert fm["agent_toolkit_cli"]["metadata"]["name"] == "foo"
    assert fm["agent_toolkit_cli"]["spec"]["harnesses"] == ["claude", "opencode"]


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
    assert fm["agent_toolkit_cli"]["metadata"]["name"] == "explain"


def test_translate_opencode_command_round_trip_stable():
    record = _make_command_record("explain", "desc")
    a = _translate_opencode_command(record, "x")
    b = _translate_opencode_command(record, "x")
    assert a == b


def test_translators_dict_has_opencode_command_entry():
    assert ("opencode", "command") in TRANSLATORS
    assert TRANSLATORS[("opencode", "command")] is _translate_opencode_command


def _make_skill_record(slug: str, description: str) -> AssetRecord:
    metadata = {
        "apiVersion": "agent-toolkit/v1alpha2",
        "metadata": {
            "name": slug,
            "description": description,
            "lifecycle": "stable",
        },
        "spec": {"origin": "first-party", "vendored_via": "none", "harnesses": ["codex"]},
    }
    asset = Asset(kind="skill", slug=slug, path=Path(f"/fake/skills/{slug}/SKILL.md"))
    return AssetRecord(asset=asset, metadata=metadata, body_excerpt="", requires={})


def test_translate_codex_skill_emits_top_level_description():
    """Codex's loader requires `description:` at the YAML top level."""
    record = _make_skill_record("demo-skill", "Demo skill — does demo things.")
    out = _translate_codex_skill(record, "# demo-skill\n\nBody.\n")

    assert isinstance(out, bytes)
    text = out.decode("utf-8")
    assert text.startswith("---\n")
    end_idx = text.find("\n---\n", 4)
    assert end_idx != -1
    fm = yaml.safe_load(text[4:end_idx])

    assert fm["description"] == "Demo skill — does demo things."
    assert "mode" not in fm  # skills don't have a mode field


def test_translate_codex_skill_preserves_wrapper_under_agent_toolkit_key():
    record = _make_skill_record("demo-skill", "Desc.")
    out = _translate_codex_skill(record, "")
    text = out.decode("utf-8")
    end_idx = text.find("\n---\n", 4)
    fm = yaml.safe_load(text[4:end_idx])

    assert fm["agent_toolkit_cli"]["apiVersion"] == "agent-toolkit/v1alpha2"
    assert fm["agent_toolkit_cli"]["metadata"]["name"] == "demo-skill"
    assert fm["agent_toolkit_cli"]["spec"]["harnesses"] == ["codex"]


def test_translate_codex_skill_appends_body():
    record = _make_skill_record("demo-skill", "Desc.")
    body = "# Heading\n\nParagraph.\n"
    out = _translate_codex_skill(record, body)
    text = out.decode("utf-8")
    closing_fence_at = text.find("\n---\n", 4)
    after = text[closing_fence_at + len("\n---\n"):]
    assert after == body


def test_translate_codex_skill_round_trip_stable():
    record = _make_skill_record("demo-skill", "Desc.")
    body = "Body.\n"
    a = _translate_codex_skill(record, body)
    b = _translate_codex_skill(record, body)
    assert a == b


def test_translators_dict_has_codex_skill_entry():
    assert ("codex", "skill") in TRANSLATORS
    assert TRANSLATORS[("codex", "skill")] is _translate_codex_skill


def _make_opencode_skill_record(slug: str, name: str, description: str) -> AssetRecord:
    metadata = {
        "apiVersion": "agent-toolkit/v1alpha2",
        "metadata": {
            "name": name,
            "description": description,
            "lifecycle": "stable",
        },
        "spec": {"origin": "first-party", "vendored_via": "none", "harnesses": ["opencode"]},
    }
    asset = Asset(kind="skill", slug=slug, path=Path(f"/fake/skills/{slug}/SKILL.md"))
    return AssetRecord(asset=asset, metadata=metadata, body_excerpt="", requires={})


def test_translate_opencode_skill_emits_top_level_name_and_description():
    """OpenCode silently drops SKILL.md missing top-level `name` or `description`."""
    record = _make_opencode_skill_record("demo-skill", "demo-skill", "Demo skill — does demo things.")
    out = _translate_opencode_skill(record, "# demo-skill\n\nBody.\n")

    text = out.decode("utf-8")
    end_idx = text.find("\n---\n", 4)
    assert end_idx != -1
    fm = yaml.safe_load(text[4:end_idx])

    assert fm["name"] == "demo-skill"
    assert fm["description"] == "Demo skill — does demo things."
    assert "mode" not in fm  # skills don't have a mode field


def test_translate_opencode_skill_preserves_wrapper_under_agent_toolkit_key():
    record = _make_opencode_skill_record("demo-skill", "demo-skill", "Desc.")
    out = _translate_opencode_skill(record, "")
    text = out.decode("utf-8")
    end_idx = text.find("\n---\n", 4)
    fm = yaml.safe_load(text[4:end_idx])

    assert fm["agent_toolkit_cli"]["apiVersion"] == "agent-toolkit/v1alpha2"
    assert fm["agent_toolkit_cli"]["metadata"]["name"] == "demo-skill"
    assert fm["agent_toolkit_cli"]["spec"]["harnesses"] == ["opencode"]


def test_translate_opencode_skill_appends_body():
    record = _make_opencode_skill_record("demo-skill", "demo-skill", "Desc.")
    body = "# Heading\n\nParagraph.\n"
    out = _translate_opencode_skill(record, body)
    text = out.decode("utf-8")
    closing_fence_at = text.find("\n---\n", 4)
    after = text[closing_fence_at + len("\n---\n"):]
    assert after == body


def test_translate_opencode_skill_round_trip_stable():
    record = _make_opencode_skill_record("demo-skill", "demo-skill", "Desc.")
    body = "Body.\n"
    a = _translate_opencode_skill(record, body)
    b = _translate_opencode_skill(record, body)
    assert a == b


def test_translators_dict_has_opencode_skill_entry():
    assert ("opencode", "skill") in TRANSLATORS
    assert TRANSLATORS[("opencode", "skill")] is _translate_opencode_skill


@pytest.mark.parametrize("kind,harness", [
    ("agent", "opencode"),
    ("command", "opencode"),
    ("skill", "codex"),
    ("skill", "opencode"),
])
def test_translator_renders_every_shipping_eligible_asset(kind: str, harness: str):
    """For each (harness, kind) the translator handles, render every shipping
    asset in the toolkit repo whose `spec.harnesses` includes the harness.
    Asserts the output parses as YAML frontmatter + body. Catches
    metadata-shape bugs against real assets. Skips with no error if no
    matching assets exist (expected pre-sweep) OR if the toolkit repo
    isn't resolvable from the current environment (expected in CI)."""
    from agent_toolkit_cli._repo_resolution import RepoNotFoundError
    try:
        toolkit_root = resolve_toolkit_root(explicit=None)
    except RepoNotFoundError:
        pytest.skip("toolkit repo not resolvable from this environment")
    translator = TRANSLATORS[(harness, kind)]

    matching_assets = []
    for asset in discover_assets(toolkit_root):
        if asset.kind != kind:
            continue
        record = load_asset_record(asset)
        harnesses = ((record.metadata.get("spec") or {}).get("harnesses") or [])
        if harness not in harnesses:
            continue
        matching_assets.append((asset, record))

    if not matching_assets:
        pytest.skip(f"no shipping {kind}s declare {harness} yet (pre-sweep)")

    for asset, record in matching_assets:
        text = asset.path.read_text(encoding="utf-8")
        body = strip_frontmatter(text)
        out = translator(record, body)
        out_text = out.decode("utf-8")
        # Frontmatter parses
        end_idx = out_text.find("\n---\n", 4)
        assert end_idx != -1, f"{asset.slug}: missing closing fence"
        fm = yaml.safe_load(out_text[4:end_idx])
        assert isinstance(fm, dict)
        assert "description" in fm


def _make_gemini_command_record(slug: str, metadata: dict) -> AssetRecord:
    """Build an AssetRecord for a command with the given raw metadata dict."""
    asset = Asset(kind="command", slug=slug, path=Path(f"/fake/commands/{slug}.md"))
    return AssetRecord(asset=asset, metadata=metadata, body_excerpt="", requires={})


def test_translate_gemini_command_minimum():
    """Minimum: description + prompt, no spec block."""
    import tomllib

    record = _make_gemini_command_record(
        "noop",
        {
            "apiVersion": "agent-toolkit/v1alpha2",
            "metadata": {"name": "noop", "description": "Do nothing."},
        },
    )
    body = "Just chill.\n"
    out = _translate_gemini_command(record, body)
    parsed = tomllib.loads(out.decode("utf-8"))
    assert parsed["description"] == "Do nothing."
    assert parsed["prompt"].strip() == "Just chill."
    assert "agent_toolkit_cli" in parsed
    assert parsed["agent_toolkit_cli"]["apiVersion"] == "agent-toolkit/v1alpha2"


def test_translate_gemini_command_round_trips_wrapper():
    """metadata + spec encoded as JSON strings under [agent_toolkit_cli]."""
    import json
    import tomllib

    md = {
        "apiVersion": "agent-toolkit/v1alpha2",
        "metadata": {"name": "n", "description": "d", "tags": ["a", "b"]},
        "spec": {"harnesses": ["gemini"]},
    }
    record = _make_gemini_command_record("n", md)
    out = _translate_gemini_command(record, "body\n")
    parsed = tomllib.loads(out.decode("utf-8"))
    wrapper = parsed["agent_toolkit_cli"]
    assert wrapper["apiVersion"] == "agent-toolkit/v1alpha2"
    assert json.loads(wrapper["metadata"]) == md["metadata"]
    assert json.loads(wrapper["spec"]) == md["spec"]


def test_translate_gemini_command_handles_triple_quoted_body():
    """Bodies containing triple-quotes must round-trip safely."""
    import tomllib

    record = _make_gemini_command_record(
        "q",
        {
            "apiVersion": "agent-toolkit/v1alpha2",
            "metadata": {"name": "q", "description": "d"},
        },
    )
    body = 'before """ in middle """ end\n'
    out = _translate_gemini_command(record, body)
    parsed = tomllib.loads(out.decode("utf-8"))
    assert parsed["prompt"] == body


@pytest.mark.parametrize(
    "trailing",
    ['"', '""'],
    ids=["single-trailing-quote", "double-trailing-quote"],
)
def test_translate_gemini_command_handles_trailing_quotes(trailing):
    """Bodies ending in 1 or 2 `"` butt against the closing `\"\"\"` fence —
    TOML's lexer is greedy about the closing fence and allows up to 2 trailing
    quotes inside, so this MUST round-trip cleanly. Lock-in test to prevent a
    future refactor of `_toml_multiline_string` from regressing this case."""
    import tomllib

    record = _make_gemini_command_record(
        "q",
        {
            "apiVersion": "agent-toolkit/v1alpha2",
            "metadata": {"name": "q", "description": "d"},
        },
    )
    body = f"foo{trailing}"
    out = _translate_gemini_command(record, body)
    parsed = tomllib.loads(out.decode("utf-8"))
    assert parsed["prompt"] == body


def _make_gemini_agent_record(slug: str, metadata: dict) -> AssetRecord:
    """Build an AssetRecord for an agent with the given raw metadata dict."""
    from agent_toolkit_cli.walker import Asset, AssetRecord
    asset = Asset(kind="agent", slug=slug, path=Path(f"/fake/agents/{slug}.md"))
    return AssetRecord(asset=asset, metadata=metadata, body_excerpt="", requires={})


def test_translate_gemini_agent_minimum():
    """Minimum: top-level name + description, body preserved, no wrapper."""
    import yaml

    record = _make_gemini_agent_record(
        "demo-agent",
        {
            "apiVersion": "agent-toolkit/v1alpha2",
            "metadata": {"name": "demo-agent", "description": "Verify cross-harness."},
        },
    )
    body = "You are DemoBot.\n"
    out = _translate_gemini_agent(record, body).decode("utf-8")
    assert out.startswith("---\n")
    fm_text, _, body_out = out[4:].partition("\n---\n")
    fm = yaml.safe_load(fm_text)
    assert fm["name"] == "demo-agent"
    assert fm["description"] == "Verify cross-harness."
    assert body_out == body


def test_translate_gemini_agent_omits_wrapper():
    """Gemini's agent loader uses zod `.strict()` and silently drops any
    frontmatter with extra top-level keys (#97). Lock in: the translator
    must NOT emit `agent_toolkit_cli` or any other key beyond name +
    description, even when the source asset has rich metadata + spec.
    """
    import yaml

    md = {
        "apiVersion": "agent-toolkit/v1alpha2",
        "metadata": {"name": "a", "description": "d", "tags": ["x", "y"]},
        "spec": {"harnesses": ["gemini"], "origin": "first-party"},
    }
    record = _make_gemini_agent_record("a", md)
    out = _translate_gemini_agent(record, "body\n").decode("utf-8")
    fm_text, _, _ = out[4:].partition("\n---\n")
    fm = yaml.safe_load(fm_text)
    assert set(fm.keys()) == {"name", "description"}, (
        f"Gemini agent frontmatter must be name+description only; got {sorted(fm.keys())}"
    )


def test_translators_dict_includes_gemini_agent():
    """Regression guard: (gemini, agent) must be in TRANSLATORS."""
    from agent_toolkit_cli._translators import TRANSLATORS

    assert ("gemini", "agent") in TRANSLATORS
    assert TRANSLATORS[("gemini", "agent")] is _translate_gemini_agent


# ===========================================================================
# (codex, agent) translator — #140
# ===========================================================================


def _make_codex_agent_record(slug: str, description: str, spec: dict | None = None) -> AssetRecord:
    """Build an AssetRecord for a codex agent."""
    metadata: dict = {
        "apiVersion": "agent-toolkit/v1alpha2",
        "metadata": {
            "name": slug,
            "description": description,
            "lifecycle": "stable",
        },
        "spec": spec or {
            "origin": "first-party",
            "vendored_via": "none",
            "harnesses": ["codex"],
        },
    }
    asset = Asset(kind="agent", slug=slug, path=Path(f"/fake/agents/{slug}.md"))
    return AssetRecord(asset=asset, metadata=metadata, body_excerpt="", requires={})


def test_translate_codex_agent_produces_valid_toml():
    """tomllib.loads() must succeed on the rendered output."""
    import tomllib

    record = _make_codex_agent_record("my-agent", "Does things.")
    body = "You are MyAgent.\n\nBe helpful.\n"
    out = _translate_codex_agent(record, body)
    assert isinstance(out, bytes)
    parsed = tomllib.loads(out.decode("utf-8"))
    assert isinstance(parsed, dict)


def test_translate_codex_agent_required_fields_present():
    """name, description, developer_instructions must be top-level keys."""
    import tomllib

    record = _make_codex_agent_record("my-agent", "Does things.")
    body = "You are MyAgent.\n"
    parsed = tomllib.loads(_translate_codex_agent(record, body).decode("utf-8"))

    assert parsed["name"] == "my-agent"
    assert parsed["description"] == "Does things."
    assert "developer_instructions" in parsed
    assert parsed["developer_instructions"].strip() == body.strip()


def test_translate_codex_agent_name_uses_slug_not_metadata_name():
    """name field must equal the asset slug, not metadata.name.

    Codex's filename convention: <name>.toml ↔ TOML name field must match.
    The slug is the canonical source (matches the slot filename stem).
    """
    import tomllib

    # metadata.name has a different value from slug to verify which one wins.
    metadata = {
        "apiVersion": "agent-toolkit/v1alpha2",
        "metadata": {
            "name": "Pretty Name — human display",
            "description": "d",
            "lifecycle": "stable",
        },
        "spec": {"harnesses": ["codex"]},
    }
    asset = Asset(kind="agent", slug="my-slug", path=Path("/fake/agents/my-slug.md"))
    record = AssetRecord(asset=asset, metadata=metadata, body_excerpt="", requires={})
    parsed = tomllib.loads(_translate_codex_agent(record, "body\n").decode("utf-8"))
    # Slot filename is my-slug.toml; TOML name must be my-slug.
    assert parsed["name"] == "my-slug"


def test_translate_codex_agent_body_is_developer_instructions_multiline():
    """developer_instructions is emitted as a TOML multiline basic string."""
    import tomllib

    body = "Line one.\nLine two.\n"
    record = _make_codex_agent_record("agent", "desc")
    parsed = tomllib.loads(_translate_codex_agent(record, body).decode("utf-8"))
    assert parsed["developer_instructions"] == body


def test_translate_codex_agent_body_with_triple_quotes_round_trips():
    """Body containing triple-quotes must survive the multiline string escaping."""
    import tomllib

    body = 'before """ middle """ end\n'
    record = _make_codex_agent_record("agent", "desc")
    parsed = tomllib.loads(_translate_codex_agent(record, body).decode("utf-8"))
    assert parsed["developer_instructions"] == body


def test_translate_codex_agent_toolkit_table_present():
    """[agent_toolkit_cli] table must contain apiVersion + JSON-encoded metadata."""
    import json
    import tomllib

    record = _make_codex_agent_record(
        "agent",
        "desc",
        spec={"harnesses": ["codex"], "origin": "first-party"},
    )
    parsed = tomllib.loads(_translate_codex_agent(record, "body\n").decode("utf-8"))
    wrapper = parsed["agent_toolkit_cli"]
    assert wrapper["apiVersion"] == "agent-toolkit/v1alpha2"
    meta = json.loads(wrapper["metadata"])
    assert meta["description"] == "desc"


def test_translate_codex_agent_toolkit_table_includes_spec_when_present():
    """spec block must be JSON-encoded in [agent_toolkit_cli] when present."""
    import json
    import tomllib

    spec = {"harnesses": ["codex"], "origin": "first-party"}
    record = _make_codex_agent_record("agent", "desc", spec=spec)
    parsed = tomllib.loads(_translate_codex_agent(record, "body\n").decode("utf-8"))
    wrapper = parsed["agent_toolkit_cli"]
    assert "spec" in wrapper
    assert json.loads(wrapper["spec"]) == spec


def test_translate_codex_agent_toolkit_table_omits_spec_when_absent():
    """spec key must be absent from [agent_toolkit_cli] when not in source."""
    import tomllib

    metadata = {
        "apiVersion": "agent-toolkit/v1alpha2",
        "metadata": {"name": "a", "description": "d", "lifecycle": "stable"},
        # No 'spec' key
    }
    asset = Asset(kind="agent", slug="a", path=Path("/fake/agents/a.md"))
    record = AssetRecord(asset=asset, metadata=metadata, body_excerpt="", requires={})
    parsed = tomllib.loads(_translate_codex_agent(record, "body\n").decode("utf-8"))
    assert "spec" not in parsed["agent_toolkit_cli"]


def test_translate_codex_agent_round_trip_stable():
    """Rendering the same input twice yields identical bytes."""
    record = _make_codex_agent_record("agent", "desc")
    body = "Body.\n"
    assert _translate_codex_agent(record, body) == _translate_codex_agent(record, body)


def test_translators_dict_includes_codex_agent():
    """Regression guard: (codex, agent) must be in TRANSLATORS."""
    assert ("codex", "agent") in TRANSLATORS
    assert TRANSLATORS[("codex", "agent")] is _translate_codex_agent
