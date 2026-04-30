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
