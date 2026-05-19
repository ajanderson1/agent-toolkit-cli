from pathlib import Path

from agent_toolkit_cli.schema import Validator
from agent_toolkit_cli.walker import Asset


def test_validates_minimal_skill(tmp_path):
    (tmp_path / "skills" / "alpha").mkdir(parents=True)
    (tmp_path / "skills" / "alpha" / "SKILL.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
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

    validator = Validator(toolkit_root=Path(__file__).parent.parent)
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

    validator = Validator(toolkit_root=Path(__file__).parent.parent)
    asset = Asset(kind="skill", slug="alpha", path=tmp_path / "skills" / "alpha" / "SKILL.md")
    errors = validator.validate(asset)
    assert any("apiVersion" in str(e) for e in errors)
    assert any("metadata" in str(e) or "required" in str(e) for e in errors)


def test_reports_slug_mismatch(tmp_path):
    (tmp_path / "skills" / "alpha").mkdir(parents=True)
    (tmp_path / "skills" / "alpha" / "SKILL.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
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

    validator = Validator(toolkit_root=Path(__file__).parent.parent)
    asset = Asset(kind="skill", slug="alpha", path=tmp_path / "skills" / "alpha" / "SKILL.md")
    errors = validator.validate(asset)
    # name pattern rejects uppercase, AND we add a slug-match check
    assert any("slug" in str(e).lower() or "name" in str(e).lower() for e in errors)


def test_validator_loads_v1alpha2_schema(tmp_path):
    """The bundled schema is v1alpha2."""
    from agent_toolkit_cli.schema import Validator

    v = Validator(toolkit_root=tmp_path)
    assert v.schema["properties"]["apiVersion"]["const"] == "agent-toolkit/v1alpha2"
    assert "mcp" in v.schema["properties"]["spec"]["properties"]


def test_validator_kind_mismatch_is_error(tmp_path):
    """If frontmatter declares metadata.kind, it must match walker-derived kind."""
    from agent_toolkit_cli.schema import Validator
    from agent_toolkit_cli.walker import Asset

    skills = tmp_path / "skills" / "alpha"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n"
        "  name: alpha\n"
        "  description: Alpha.\n"
        "  lifecycle: stable\n"
        "  kind: agent\n"  # mismatch — walker derives 'skill'
        "spec:\n"
        "  origin: first-party\n"
        "  vendored_via: none\n"
        "  harnesses: [claude]\n"
        "---\n"
    )
    asset = Asset(kind="skill", slug="alpha", path=skills / "SKILL.md")
    v = Validator(toolkit_root=tmp_path)
    errors = v.validate(asset)
    assert any("kind" in e and "agent" in e and "skill" in e for e in errors), errors


def test_validator_mcp_requires_spec_mcp(tmp_path):
    """An MCP without spec.mcp fails validation."""
    from agent_toolkit_cli.schema import Validator
    from agent_toolkit_cli.walker import Asset

    mcp_dir = tmp_path / "mcps" / "context7"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text("{}\n")
    (tmp_path / "mcps" / "context7.toolkit.yaml").write_text(
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n"
        "  name: context7\n"
        "  description: c.\n"
        "  lifecycle: stable\n"
        "spec:\n"
        "  origin: third-party\n"
        "  vendored_via: none\n"
        "  upstream: https://example.com\n"
        "  harnesses: [codex]\n"
    )
    asset = Asset(kind="mcp", slug="context7", path=mcp_dir / "config.json")
    v = Validator(toolkit_root=tmp_path)
    errors = v.validate(asset)
    assert any("mcp" in e.lower() for e in errors), errors


def test_validator_mcp_with_spec_mcp_passes(tmp_path):
    """An MCP with valid spec.mcp passes."""
    from agent_toolkit_cli.schema import Validator
    from agent_toolkit_cli.walker import Asset

    mcp_dir = tmp_path / "mcps" / "context7"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text("{}\n")
    (tmp_path / "mcps" / "context7.toolkit.yaml").write_text(
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n"
        "  name: context7\n"
        "  description: c.\n"
        "  lifecycle: stable\n"
        "spec:\n"
        "  origin: third-party\n"
        "  vendored_via: none\n"
        "  upstream: https://example.com\n"
        "  harnesses: [codex]\n"
        "  mcp:\n"
        "    transport: stdio\n"
        "    install_method: npx\n"
    )
    asset = Asset(kind="mcp", slug="context7", path=mcp_dir / "config.json")
    v = Validator(toolkit_root=tmp_path)
    errors = v.validate(asset)
    assert errors == [], errors


def test_validator_skill_with_spec_mcp_is_error(tmp_path):
    """spec.mcp on a non-MCP asset is forbidden."""
    from agent_toolkit_cli.schema import Validator
    from agent_toolkit_cli.walker import Asset

    skills = tmp_path / "skills" / "alpha"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n"
        "  name: alpha\n"
        "  description: Alpha.\n"
        "  lifecycle: stable\n"
        "spec:\n"
        "  origin: first-party\n"
        "  vendored_via: none\n"
        "  harnesses: [claude]\n"
        "  mcp:\n"
        "    transport: stdio\n"
        "    install_method: npx\n"
        "---\n"
    )
    asset = Asset(kind="skill", slug="alpha", path=skills / "SKILL.md")
    v = Validator(toolkit_root=tmp_path)
    errors = v.validate(asset)
    assert errors, "expected error for spec.mcp on a skill"
