from pathlib import Path

from agent_toolkit.schema import Validator
from agent_toolkit.walker import Asset


def test_validates_minimal_skill(tmp_path):
    (tmp_path / "skills" / "alpha").mkdir(parents=True)
    (tmp_path / "skills" / "alpha" / "SKILL.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha1\n"
        "metadata:\n"
        "  name: alpha\n"
        "  description: Alpha skill.\n"
        "  lifecycle: stable\n"
        "spec:\n"
        "  origin: first-party\n"
        "  vendored_via: none\n"
        "  harnesses: [claude]\n"
        "---\n"
    )

    validator = Validator(repo_root=Path(__file__).parent.parent)
    asset = Asset(kind="skill", slug="alpha", path=tmp_path / "skills" / "alpha" / "SKILL.md")
    errors = validator.validate(asset)
    assert errors == []


def test_reports_missing_required_metadata(tmp_path):
    (tmp_path / "skills" / "alpha").mkdir(parents=True)
    (tmp_path / "skills" / "alpha" / "SKILL.md").write_text(
        "---\n"
        "name: alpha\n"   # legacy frontmatter only — missing apiVersion, metadata, spec
        "description: Alpha.\n"
        "---\n"
    )

    validator = Validator(repo_root=Path(__file__).parent.parent)
    asset = Asset(kind="skill", slug="alpha", path=tmp_path / "skills" / "alpha" / "SKILL.md")
    errors = validator.validate(asset)
    assert any("apiVersion" in str(e) for e in errors)
    assert any("metadata" in str(e) or "required" in str(e) for e in errors)


def test_reports_slug_mismatch(tmp_path):
    (tmp_path / "skills" / "alpha").mkdir(parents=True)
    (tmp_path / "skills" / "alpha" / "SKILL.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha1\n"
        "metadata:\n"
        "  name: WRONG-NAME\n"  # mismatches dir slug "alpha"
        "  description: Alpha.\n"
        "  lifecycle: stable\n"
        "spec:\n"
        "  origin: first-party\n"
        "  vendored_via: none\n"
        "  harnesses: [claude]\n"
        "---\n"
    )

    validator = Validator(repo_root=Path(__file__).parent.parent)
    asset = Asset(kind="skill", slug="alpha", path=tmp_path / "skills" / "alpha" / "SKILL.md")
    errors = validator.validate(asset)
    # name pattern rejects uppercase, AND we add a slug-match check
    assert any("slug" in str(e).lower() or "name" in str(e).lower() for e in errors)
