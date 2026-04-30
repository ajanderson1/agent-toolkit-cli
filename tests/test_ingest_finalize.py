"""Tests for ingest FINALISE."""
import subprocess

from agent_toolkit.ingest.types import Proposal


def _init_git_repo(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)


def _proposal(slug="alpha"):
    return Proposal(
        slug=slug, kind="skill", origin="third-party",
        harnesses=["claude"], lifecycle="experimental",
        target_path=f"skills/{slug}/SKILL.md", vendor_via="copy",
        upstream="https://github.com/x/alpha",
        description="Alpha test ingest.",
    )


def _seed_staging(tmp_path, slug="alpha"):
    from agent_toolkit.ingest.stage import stage_proposal
    snap = tmp_path / "snap"
    snap.mkdir()
    (snap / "SKILL.md").write_text("---\nname: alpha\ndescription: Alpha test ingest.\n---\n# alpha\n")
    return stage_proposal(repo_root=tmp_path, proposal=_proposal(slug), snapshot_dir=snap)


def test_finalize_moves_files_to_canonical_path(tmp_path):
    from agent_toolkit.ingest.finalize import finalize
    _init_git_repo(tmp_path)
    # Provide a working schema so check succeeds
    schemas_dir = tmp_path / "schemas"
    schemas_dir.mkdir()
    real_schema_src = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "schemas" / "asset-frontmatter.v1alpha1.json"
    )
    (schemas_dir / "asset-frontmatter.v1alpha1.json").write_text(real_schema_src.read_text())
    (tmp_path / "AGENTS.md").write_text("# AGENTS")
    _seed_staging(tmp_path)

    result = finalize(repo_root=tmp_path, proposal=_proposal(), skip_check=True, skip_commit=True)
    assert result.target_path.exists()
    assert (tmp_path / "skills" / "alpha" / "SKILL.md").exists()


def test_finalize_writes_commit_when_not_skipped(tmp_path):
    from agent_toolkit.ingest.finalize import finalize
    _init_git_repo(tmp_path)
    schemas_dir = tmp_path / "schemas"
    schemas_dir.mkdir()
    real_schema_src = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "schemas" / "asset-frontmatter.v1alpha1.json"
    )
    (schemas_dir / "asset-frontmatter.v1alpha1.json").write_text(real_schema_src.read_text())
    (tmp_path / "AGENTS.md").write_text("# AGENTS")
    # initial commit so there is HEAD
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)
    _seed_staging(tmp_path)

    finalize(repo_root=tmp_path, proposal=_proposal(), skip_check=True)
    log = subprocess.run(["git", "log", "--oneline"], cwd=tmp_path, check=True,
                         capture_output=True, text=True).stdout
    assert "ingest" in log.lower() or "alpha" in log.lower()
