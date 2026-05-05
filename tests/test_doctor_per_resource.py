"""Tests for per-resource doctor (D2 default)."""
from agent_toolkit.doctor.result import Status


def _make_skill(toolkit_root, slug, harnesses=("claude",)):
    skill_dir = toolkit_root / "skills" / slug
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        f"metadata:\n  name: {slug}\n  description: X.\n  lifecycle: stable\n"
        "spec:\n  origin: first-party\n  vendored_via: none\n  harnesses:\n"
        + "".join(f"    - {h}\n" for h in harnesses)
        + "---\n# x\n"
    )


def test_per_resource_unknown_slug_returns_fail(tmp_path):
    from agent_toolkit.doctor.per_resource import diagnose
    (tmp_path / "schemas").mkdir()
    (tmp_path / "schemas" / "asset-frontmatter.v1alpha2.json").write_text("{}")
    result = diagnose(tmp_path, slug="ghost")
    assert result.status == Status.FAIL
    assert "ghost" in result.summary


def test_per_resource_ok_when_linked(tmp_path, monkeypatch):
    from agent_toolkit.doctor.per_resource import diagnose
    (tmp_path / "schemas").mkdir()
    # Use the real schema file from the repo we're running in
    real_schema_path = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "schemas" / "asset-frontmatter.v1alpha2.json"
    )
    (tmp_path / "schemas" / "asset-frontmatter.v1alpha2.json").write_text(
        real_schema_path.read_text()
    )
    _make_skill(tmp_path, "alpha")
    fake_home = tmp_path / "home"
    (fake_home / ".claude" / "skills").mkdir(parents=True)
    (fake_home / ".claude" / "skills" / "alpha").symlink_to(tmp_path / "skills" / "alpha")
    monkeypatch.setenv("HOME", str(fake_home))
    result = diagnose(tmp_path, slug="alpha")
    assert result.status == Status.OK
    # D2 default: linkage check appears
    assert any("linkage" in f for f in result.findings)
