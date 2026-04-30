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
