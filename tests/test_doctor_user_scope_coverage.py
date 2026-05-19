"""doctor user-scope-coverage group: lists (asset, harness) pairs linked at both scopes."""
from __future__ import annotations


def test_user_scope_coverage_lists_both_scope_pairs(env, seed_skill, tmp_path):
    """A skill linked at both user and project scope for one harness shows up
    once in the doctor group's findings, with a single OK-or-INFO status."""
    from agent_toolkit_cli.doctor import user_scope_coverage as g

    toolkit_root = env["toolkit_root"]
    seed_skill(toolkit_root, "alpha", harnesses=["claude"])

    user_yaml = env["home"] / ".agent-toolkit.yaml"
    user_yaml.write_text("skills:\n  - alpha\n")
    project_yaml = tmp_path / ".agent-toolkit.yaml"
    project_yaml.write_text("skills:\n  - alpha\n")

    user_slot = env["home"] / ".claude" / "skills"
    user_slot.mkdir(parents=True, exist_ok=True)
    (user_slot / "alpha").symlink_to(toolkit_root / "skills" / "alpha")
    proj_slot = tmp_path / ".claude" / "skills"
    proj_slot.mkdir(parents=True, exist_ok=True)
    (proj_slot / "alpha").symlink_to(toolkit_root / "skills" / "alpha")

    result = g.run(toolkit_root, project_root=tmp_path)
    from agent_toolkit_cli.doctor.result import Status
    assert result.status == Status.OK
    assert any("alpha" in f and "claude" in f for f in result.findings)


def test_user_scope_coverage_no_findings_when_no_overlap(env, seed_skill, tmp_path):
    """When nothing is linked at both scopes, the group reports OK with no findings."""
    from agent_toolkit_cli.doctor import user_scope_coverage as g
    from agent_toolkit_cli.doctor.result import Status

    toolkit_root = env["toolkit_root"]
    seed_skill(toolkit_root, "alpha", harnesses=["claude"])

    project_yaml = tmp_path / ".agent-toolkit.yaml"
    project_yaml.write_text("skills:\n  - alpha\n")
    proj_slot = tmp_path / ".claude" / "skills"
    proj_slot.mkdir(parents=True, exist_ok=True)
    (proj_slot / "alpha").symlink_to(toolkit_root / "skills" / "alpha")

    result = g.run(toolkit_root, project_root=tmp_path)
    assert result.status == Status.OK
    assert result.findings == []


def test_user_scope_coverage_registered_in_doctor_groups():
    """The new group is wired into the doctor command."""
    from agent_toolkit_cli.commands.doctor import _GROUPS
    assert "user-scope-coverage" in _GROUPS


def test_user_scope_coverage_no_findings_when_user_only(env, seed_skill, tmp_path):
    """User-scope linked but project-scope unlinked → no finding.
    The group fires only on the both-scopes overlap."""
    from agent_toolkit_cli.doctor import user_scope_coverage as g
    from agent_toolkit_cli.doctor.result import Status

    toolkit_root = env["toolkit_root"]
    seed_skill(toolkit_root, "alpha", harnesses=["claude"])

    user_yaml = env["home"] / ".agent-toolkit.yaml"
    user_yaml.write_text("skills:\n  - alpha\n")
    user_slot = env["home"] / ".claude" / "skills"
    user_slot.mkdir(parents=True, exist_ok=True)
    (user_slot / "alpha").symlink_to(toolkit_root / "skills" / "alpha")

    result = g.run(toolkit_root, project_root=tmp_path)
    assert result.status == Status.OK
    assert result.findings == []


def test_user_scope_coverage_reports_per_harness_pair(env, seed_skill, tmp_path):
    """When an asset is linked at both scopes for two harnesses, two findings appear
    (one per (slug, harness)), confirming the granularity of the indicator."""
    from agent_toolkit_cli.doctor import user_scope_coverage as g

    toolkit_root = env["toolkit_root"]
    seed_skill(toolkit_root, "alpha", harnesses=["claude", "codex"])

    # Allowlist + symlinks at both scopes for both harnesses.
    user_yaml = env["home"] / ".agent-toolkit.yaml"
    user_yaml.write_text("skills:\n  - alpha\n")
    project_yaml = tmp_path / ".agent-toolkit.yaml"
    project_yaml.write_text("skills:\n  - alpha\n")

    for slot in (env["home"] / ".claude" / "skills",
                 tmp_path / ".claude" / "skills",
                 env["home"] / ".codex" / "skills",
                 tmp_path / ".codex" / "skills"):
        slot.mkdir(parents=True, exist_ok=True)
        (slot / "alpha").symlink_to(toolkit_root / "skills" / "alpha")

    result = g.run(toolkit_root, project_root=tmp_path)
    # One finding per (slug, harness): claude AND codex.
    assert any("claude" in f for f in result.findings)
    assert any("codex" in f for f in result.findings)
    assert len(result.findings) == 2
