"""Tests for ingest.identify and shared types."""
from agent_toolkit.ingest.types import IngestTarget, Proposal, InputForm


def test_ingest_target_records_input_form():
    t = IngestTarget(
        input_value="https://github.com/owner/repo",
        input_form=InputForm.URL,
        upstream_url="https://github.com/owner/repo",
        kind_guess="skill",
        slug_guess="repo",
        vendor_strategy_guess="submodule",
    )
    assert t.input_form == InputForm.URL
    assert t.upstream_url == "https://github.com/owner/repo"


def test_proposal_serializable_to_dict():
    p = Proposal(
        slug="alpha", kind="skill", origin="third-party",
        harnesses=["claude"], lifecycle="experimental",
        target_path="skills/alpha/SKILL.md",
        vendor_via="submodule",
        upstream="https://github.com/owner/alpha",
        fork=None,
    )
    d = p.to_dict()
    assert d["metadata"]["name"] == "alpha"
    assert d["spec"]["harnesses"] == ["claude"]


def test_identify_github_url():
    from agent_toolkit.ingest.identify import classify_input
    t = classify_input("https://github.com/obra/superpowers")
    assert t.input_form == InputForm.URL
    assert t.owner == "obra"
    assert t.repo == "superpowers"
    assert t.upstream_url == "https://github.com/obra/superpowers"


def test_identify_local_file(tmp_path):
    from agent_toolkit.ingest.identify import classify_input
    skill = tmp_path / "myskill.md"
    skill.write_text("# Skill\n")
    t = classify_input(str(skill))
    assert t.input_form == InputForm.FILE
    assert t.upstream_url is None


def test_identify_treats_bare_token_as_name():
    from agent_toolkit.ingest.identify import classify_input
    t = classify_input("superpowers")
    assert t.input_form == InputForm.NAME
    assert t.upstream_url is None  # name needs research to resolve


def test_identify_kind_guess_for_url_from_path():
    from agent_toolkit.ingest.identify import classify_input
    t = classify_input("https://github.com/owner/some-mcp-server")
    # 'mcp' in name biases the kind guess
    assert t.kind_guess == "mcp"


def test_research_infers_skill_from_skill_md(tmp_path):
    from agent_toolkit.ingest.research import infer_from_snapshot
    (tmp_path / "SKILL.md").write_text("# A skill\n")
    proposal = infer_from_snapshot(
        snapshot_dir=tmp_path,
        slug="alpha",
        upstream="https://github.com/x/alpha",
    )
    assert proposal.kind == "skill"
    assert proposal.harnesses == ["claude", "codex", "opencode", "pi"]


def test_research_narrows_to_pi_when_extension_layout(tmp_path):
    from agent_toolkit.ingest.research import infer_from_snapshot
    (tmp_path / "package.json").write_text('{"keywords": ["pi-extension"]}')
    proposal = infer_from_snapshot(
        snapshot_dir=tmp_path, slug="pi-thing", upstream="https://github.com/x/pi-thing",
    )
    assert "pi" in proposal.harnesses
    # Should narrow when README/package signals are pi-only
    assert proposal.harnesses == ["pi"]


def test_research_marks_third_party_when_upstream_present(tmp_path):
    from agent_toolkit.ingest.research import infer_from_snapshot
    (tmp_path / "SKILL.md").write_text("# x\n")
    proposal = infer_from_snapshot(
        snapshot_dir=tmp_path, slug="x", upstream="https://github.com/owner/x"
    )
    assert proposal.origin == "third-party"


def test_identify_directory_with_skill_md(tmp_path):
    from agent_toolkit.ingest.identify import classify_input
    from agent_toolkit.ingest.types import InputForm
    (tmp_path / "SKILL.md").write_text("# A skill\n")
    t = classify_input(str(tmp_path))
    assert t.input_form == InputForm.DIR
    assert t.kind_guess == "skill"
    assert t.upstream_url is None
    assert not any(n.startswith("dir-no-manifest") for n in t.notes)


def test_identify_directory_with_claude_plugin_manifest(tmp_path):
    from agent_toolkit.ingest.identify import classify_input
    from agent_toolkit.ingest.types import InputForm
    plugin_dir = tmp_path / ".claude-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text('{"name": "companion-html"}\n')
    t = classify_input(str(tmp_path))
    assert t.input_form == InputForm.DIR
    assert t.kind_guess == "plugin"
    assert t.upstream_url is None
    assert t.slug_guess == tmp_path.name.lower().replace("_", "-")


def test_identify_directory_with_mcp_json(tmp_path):
    from agent_toolkit.ingest.identify import classify_input
    from agent_toolkit.ingest.types import InputForm
    (tmp_path / "mcp.json").write_text('{"name": "my-mcp"}\n')
    t = classify_input(str(tmp_path))
    assert t.input_form == InputForm.DIR
    assert t.kind_guess == "mcp"


def test_identify_directory_no_manifest_returns_disambiguation_hint(tmp_path):
    from agent_toolkit.ingest.identify import classify_input
    from agent_toolkit.ingest.types import InputForm
    (tmp_path / "some_random_file.txt").write_text("nothing\n")
    t = classify_input(str(tmp_path))
    assert t.input_form == InputForm.DIR
    assert any(n.startswith("dir-no-manifest:") for n in t.notes)


def test_identify_directory_never_falls_through_to_name(tmp_path):
    from agent_toolkit.ingest.identify import classify_input
    from agent_toolkit.ingest.types import InputForm
    # Even with no manifest, a directory must not be classified as NAME
    t = classify_input(str(tmp_path))
    assert t.input_form != InputForm.NAME


def test_identify_dir_is_snapshot_for_research(tmp_path):
    from agent_toolkit.ingest.identify import classify_input
    from agent_toolkit.ingest.research import infer_from_snapshot
    from agent_toolkit.ingest.types import InputForm
    plugin_dir = tmp_path / ".claude-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text('{"name": "companion-html"}\n')
    (tmp_path / "marketplace.json").write_text('{"name": "companion-html"}\n')
    t = classify_input(str(tmp_path))
    assert t.input_form == InputForm.DIR
    proposal = infer_from_snapshot(
        snapshot_dir=tmp_path,
        slug=t.slug_guess,
        upstream=t.upstream_url,
    )
    assert proposal.kind == "plugin"
    assert proposal.origin == "first-party"  # upstream_url is None → first-party
