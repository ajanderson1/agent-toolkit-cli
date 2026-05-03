"""Tests for ingest STAGE."""
from agent_toolkit.ingest.types import Proposal


def _proposal(slug="alpha"):
    return Proposal(
        slug=slug, kind="skill", origin="third-party",
        harnesses=["claude"], lifecycle="experimental",
        target_path=f"skills/{slug}/SKILL.md", vendor_via="copy",
        upstream="https://github.com/x/alpha",
    )


def test_stage_creates_staging_dir(tmp_path):
    from agent_toolkit.ingest.stage import stage_proposal
    snap = tmp_path / "snap"
    snap.mkdir()
    (snap / "SKILL.md").write_text("---\nname: alpha\n---\n# alpha\n")
    out = stage_proposal(toolkit_root=tmp_path, proposal=_proposal(),
                         snapshot_dir=snap)
    assert out.exists()
    assert (out / "STAGE.md").exists()
    assert (out / "SKILL.md").exists()


def test_stage_md_records_metadata(tmp_path):
    from agent_toolkit.ingest.stage import stage_proposal
    snap = tmp_path / "snap"
    snap.mkdir()
    (snap / "SKILL.md").write_text("# x\n")
    out = stage_proposal(toolkit_root=tmp_path, proposal=_proposal(),
                         snapshot_dir=snap)
    body = (out / "STAGE.md").read_text()
    assert "alpha" in body
    assert "claude" in body
    assert "third-party" in body


def test_stage_overwrite_clears_previous(tmp_path):
    from agent_toolkit.ingest.stage import stage_proposal, abort_staging
    snap = tmp_path / "snap"
    snap.mkdir()
    (snap / "SKILL.md").write_text("# x\n")
    stage_proposal(toolkit_root=tmp_path, proposal=_proposal(), snapshot_dir=snap)
    abort_staging(toolkit_root=tmp_path, slug="alpha")
    assert not (tmp_path / ".agent-toolkit" / "staging" / "alpha").exists()
