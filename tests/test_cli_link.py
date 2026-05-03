"""Pytest port of tests/bats/test_link*.bats. Each test cites the bats file:line it replaces."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit.cli import main


SKILL_FRONTMATTER = """\
---
apiVersion: agent-toolkit/v1alpha1
metadata:
  name: {slug}
  description: {slug} skill.
  lifecycle: stable
spec:
  origin: first-party
  vendored_via: none
  harnesses:
{harness_lines}
---
"""


def _seed_toolkit(tmp: Path) -> Path:
    """Create a minimal valid toolkit repo at `tmp/toolkit`."""
    root = tmp / "toolkit"
    root.mkdir()
    (root / ".agent-toolkit-source").write_text("tool: agent-toolkit-cli\n")
    (root / "schemas").mkdir()
    schema_src = (
        Path(__file__).resolve().parents[1] / "schemas" / "asset-frontmatter.v1alpha1.json"
    )
    (root / "schemas" / "asset-frontmatter.v1alpha1.json").write_text(schema_src.read_text())
    return root


def _seed_skill(toolkit_root: Path, slug: str, harnesses: list[str]) -> Path:
    skill_dir = toolkit_root / "skills" / slug
    skill_dir.mkdir(parents=True, exist_ok=True)
    lines = "\n".join(f"    - {h}" for h in harnesses)
    (skill_dir / "SKILL.md").write_text(
        SKILL_FRONTMATTER.format(slug=slug, harness_lines=lines)
    )
    return skill_dir


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)
    monkeypatch.delenv("AGENT_TOOLKIT_QUIET", raising=False)
    toolkit_root = _seed_toolkit(tmp_path)
    return {"home": home, "toolkit_root": toolkit_root}


# ===========================================================================
# test_link.bats: bare form
# ===========================================================================


def test_link_user_claude_creates_symlink(env):
    """Replaces tests/bats/test_link.bats:41-46."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - alpha\n")
    (home / ".claude").mkdir()
    runner = CliRunner()
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "link", "user", "claude"],
    )
    assert result.exit_code == 0, (result.output, result.stderr)
    link = home / ".claude" / "skills" / "alpha"
    assert link.is_symlink()
    assert os.readlink(str(link)) == str(toolkit / "skills" / "alpha")


def test_link_user_claude_idempotent(env):
    """Replaces tests/bats/test_link.bats:48-53."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - alpha\n")
    runner = CliRunner()
    # First run
    runner.invoke(main, ["--toolkit-repo", str(toolkit), "link", "user", "claude"])
    # Second run
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "link", "user", "claude"],
    )
    assert result.exit_code == 0
    link = home / ".claude" / "skills" / "alpha"
    assert link.is_symlink()


def test_link_user_codex_skips_incompatible(env):
    """Replaces tests/bats/test_link.bats:55-59."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - alpha\n")
    runner = CliRunner()
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "link", "user", "codex"],
    )
    assert result.exit_code == 0
    # alpha is claude-only; nothing should land in .codex
    assert not (home / ".codex" / "skills" / "alpha").exists()


def test_link_removes_stale_when_harness_changes(env):
    """Replaces tests/bats/test_link.bats:61-69."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - alpha\n")
    runner = CliRunner()
    # First run — creates symlink
    runner.invoke(main, ["--toolkit-repo", str(toolkit), "link", "user", "claude"])
    link = home / ".claude" / "skills" / "alpha"
    assert link.is_symlink()
    # Update skill to no longer support claude
    skill_md = toolkit / "skills" / "alpha" / "SKILL.md"
    skill_md.write_text(
        SKILL_FRONTMATTER.format(slug="alpha", harness_lines="    - codex")
    )
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "link", "user", "claude"],
    )
    assert result.exit_code == 0
    assert not link.is_symlink()


def test_link_dry_run_no_symlink_emits_would_link(env):
    """Replaces tests/bats/test_link.bats:71-76."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - alpha\n")
    runner = CliRunner()
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "link", "user", "claude", "--dry-run"],
    )
    assert result.exit_code == 0
    assert not (home / ".claude" / "skills" / "alpha").exists()
    assert "would-link" in result.output


def test_link_emits_linking_header_on_stderr(env):
    """Replaces tests/bats/test_link.bats:78-82."""
    toolkit = env["toolkit_root"]
    home = env["home"]
    _seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - alpha\n")
    runner = CliRunner()
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "link", "user", "claude"],
    )
    assert result.exit_code == 0
    assert "Linking" in result.stderr


def test_link_summary_says_linked_on_first_run(env):
    """Replaces tests/bats/test_link.bats:84-88."""
    toolkit = env["toolkit_root"]
    home = env["home"]
    _seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - alpha\n")
    runner = CliRunner()
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "link", "user", "claude"],
    )
    assert result.exit_code == 0
    assert "Linked" in result.stderr


def test_link_summary_already_in_sync_on_second_run(env):
    """Replaces tests/bats/test_link.bats:90-95."""
    toolkit = env["toolkit_root"]
    home = env["home"]
    _seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - alpha\n")
    runner = CliRunner()
    runner.invoke(main, ["--toolkit-repo", str(toolkit), "link", "user", "claude"])
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "link", "user", "claude"],
    )
    assert result.exit_code == 0
    assert "Already in sync" in result.stderr


def test_link_dry_run_summary_pending_or_nothing(env):
    """Replaces tests/bats/test_link.bats:97-101."""
    toolkit = env["toolkit_root"]
    home = env["home"]
    _seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - alpha\n")
    runner = CliRunner()
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "link", "user", "claude", "--dry-run"],
    )
    assert result.exit_code == 0
    combined = result.output + result.stderr
    assert "pending" in combined or "Nothing to change" in combined


def test_link_quiet_env_suppresses_chrome(env, monkeypatch):
    """Replaces tests/bats/test_link.bats:103-108.

    With AGENT_TOOLKIT_QUIET=1 the header and summary should be suppressed,
    but would-link lines (stdout) should still appear.
    """
    toolkit = env["toolkit_root"]
    home = env["home"]
    _seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - alpha\n")
    monkeypatch.setenv("AGENT_TOOLKIT_QUIET", "1")
    runner = CliRunner()
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "link", "user", "claude", "--dry-run"],
    )
    assert result.exit_code == 0
    assert "Linking" not in result.output
    assert "Linking" not in (result.stderr or "")
    assert "would-link" in result.output


# ===========================================================================
# test_link_per_asset.bats: per-asset form
# ===========================================================================


def test_link_per_asset_creates_yaml_and_symlink(env):
    """Replaces tests/bats/test_link_per_asset.bats:49-55."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--toolkit-repo", str(toolkit), "link", "user", "claude", "skill:alpha"],
    )
    assert result.exit_code == 0, (result.output, result.stderr)
    yaml_path = home / ".agent-toolkit.yaml"
    assert yaml_path.is_file()
    assert "alpha" in yaml_path.read_text()
    assert (home / ".claude" / "skills" / "alpha").is_symlink()


def test_link_per_asset_keeps_both(env):
    """Replaces tests/bats/test_link_per_asset.bats:57-65."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    _seed_skill(toolkit, "beta", ["claude"])
    runner = CliRunner()
    runner.invoke(
        main,
        ["--toolkit-repo", str(toolkit), "link", "user", "claude", "skill:alpha"],
    )
    result = runner.invoke(
        main,
        ["--toolkit-repo", str(toolkit), "link", "user", "claude", "skill:beta"],
    )
    assert result.exit_code == 0
    yaml_text = (home / ".agent-toolkit.yaml").read_text()
    assert "alpha" in yaml_text
    assert "beta" in yaml_text
    assert (home / ".claude" / "skills" / "alpha").is_symlink()
    assert (home / ".claude" / "skills" / "beta").is_symlink()


def test_link_per_asset_idempotent_no_dup(env):
    """Replaces tests/bats/test_link_per_asset.bats:67-75."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    runner = CliRunner()
    runner.invoke(
        main,
        ["--toolkit-repo", str(toolkit), "link", "user", "claude", "skill:alpha"],
    )
    result = runner.invoke(
        main,
        ["--toolkit-repo", str(toolkit), "link", "user", "claude", "skill:alpha"],
    )
    assert result.exit_code == 0
    yaml_text = (home / ".agent-toolkit.yaml").read_text()
    # Slug should appear exactly once
    assert yaml_text.count("alpha") == 1
    assert (home / ".claude" / "skills" / "alpha").is_symlink()


def test_link_per_asset_unknown_slug_errors(env):
    """Replaces tests/bats/test_link_per_asset.bats:77-82."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--toolkit-repo", str(toolkit), "link", "user", "claude", "skill:nonexistent"],
    )
    assert result.exit_code != 0
    combined = result.output + (result.stderr or "")
    assert "no skill named 'nonexistent'" in combined
    assert not (home / ".agent-toolkit.yaml").exists()


def test_link_per_asset_harness_incompat_errors(env):
    """Replaces tests/bats/test_link_per_asset.bats:84-90."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "codex-only", ["codex"])
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--toolkit-repo", str(toolkit), "link", "user", "claude", "skill:codex-only"],
    )
    assert result.exit_code != 0
    combined = result.output + (result.stderr or "")
    assert "doesn't support harness 'claude'" in combined
    assert "codex" in combined
    assert not (home / ".agent-toolkit.yaml").exists()


def test_link_per_asset_mcp_errors(env):
    """Replaces tests/bats/test_link_per_asset.bats:92-96."""
    toolkit = env["toolkit_root"]
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--toolkit-repo", str(toolkit), "link", "user", "claude", "mcp:foo"],
    )
    assert result.exit_code != 0
    combined = result.output + (result.stderr or "")
    assert "mcps are not yet scope-routed" in combined


def test_link_project_per_asset(env, tmp_path):
    """Replaces tests/bats/test_link_per_asset.bats:98-104."""
    toolkit = env["toolkit_root"]
    project = tmp_path / "project"
    project.mkdir()
    _seed_skill(toolkit, "alpha", ["claude"])
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--toolkit-repo", str(toolkit),
            "link", "project", "claude", "skill:alpha",
            "--project", str(project),
        ],
    )
    assert result.exit_code == 0, (result.output, result.stderr)
    assert (project / ".agent-toolkit.yaml").is_file()
    assert (project / ".claude" / "skills" / "alpha").is_symlink()


def test_link_per_asset_plus_all_rc2(env):
    """Replaces tests/bats/test_link_per_asset.bats:106-110."""
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--toolkit-repo", str(toolkit),
            "link", "user", "claude", "skill:alpha", "--all", "-y",
        ],
    )
    assert result.exit_code == 2
    combined = result.output + (result.stderr or "")
    assert "cannot combine --all with" in combined


def test_link_per_asset_dry_run_no_yaml_write(env):
    """Replaces tests/bats/test_link_per_asset.bats:112-118."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--toolkit-repo", str(toolkit),
            "link", "user", "claude", "skill:alpha", "--dry-run",
        ],
    )
    assert result.exit_code == 0
    combined = result.output + (result.stderr or "")
    assert "would-link" in combined or "pending" in combined
    assert not (home / ".agent-toolkit.yaml").exists()
    assert not (home / ".claude" / "skills" / "alpha").is_symlink()


def test_link_plan_multi_slugs(env):
    """Replaces tests/bats/test_link_per_asset.bats:120-125."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    _seed_skill(toolkit, "beta", ["claude"])
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--toolkit-repo", str(toolkit), "link", "user", "claude", "--plan", "-"],
        input="skill:alpha\nskill:beta\n",
    )
    assert result.exit_code == 0, (result.output, result.stderr)
    assert (home / ".claude" / "skills" / "alpha").is_symlink()
    assert (home / ".claude" / "skills" / "beta").is_symlink()


def test_link_plan_ignores_comments_and_blanks(env):
    """Replaces tests/bats/test_link_per_asset.bats:127-131."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--toolkit-repo", str(toolkit), "link", "user", "claude", "--plan", "-"],
        input="# this is a comment\n\nskill:alpha\n# trailing comment\n",
    )
    assert result.exit_code == 0, (result.output, result.stderr)
    assert (home / ".claude" / "skills" / "alpha").is_symlink()


def test_link_plan_partial_failure_rc1(env):
    """Replaces tests/bats/test_link_per_asset.bats:133-138."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--toolkit-repo", str(toolkit), "link", "user", "claude", "--plan", "-"],
        input="skill:alpha\nskill:does-not-exist\n",
    )
    assert result.exit_code == 1
    assert (home / ".claude" / "skills" / "alpha").is_symlink()
    combined = result.output + (result.stderr or "")
    assert "does-not-exist" in combined


def test_link_plan_with_all_rc2(env):
    """Replaces tests/bats/test_link_per_asset.bats:140-143."""
    toolkit = env["toolkit_root"]
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--toolkit-repo", str(toolkit), "link", "user", "claude", "--plan", "-", "--all"],
        input="",
    )
    assert result.exit_code == 2


def test_link_plan_with_per_asset_rc2(env):
    """Replaces tests/bats/test_link_per_asset.bats:145-148."""
    toolkit = env["toolkit_root"]
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--toolkit-repo", str(toolkit),
            "link", "user", "claude", "--plan", "-", "skill:alpha",
        ],
        input="",
    )
    assert result.exit_code == 2


def test_link_all_with_plan_rc2(env):
    """Replaces tests/bats/test_link_per_asset.bats:150-153."""
    toolkit = env["toolkit_root"]
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--toolkit-repo", str(toolkit), "link", "user", "claude", "--all", "--plan", "-"],
        input="",
    )
    assert result.exit_code == 2


def test_link_plan_no_arg_rc2(env):
    """Replaces tests/bats/test_link_per_asset.bats:155-159.

    --plan with no following argument returns rc=2 and mentions --plan.
    """
    toolkit = env["toolkit_root"]
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--toolkit-repo", str(toolkit), "link", "user", "claude", "--plan"],
    )
    assert result.exit_code == 2
    combined = result.output + (result.stderr or "")
    assert "--plan" in combined


def test_link_plan_non_dash_rc2(env):
    """Replaces tests/bats/test_link_per_asset.bats:161-165.

    --plan with a non-dash arg returns rc=2 and mentions --plan.
    """
    toolkit = env["toolkit_root"]
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--toolkit-repo", str(toolkit), "link", "user", "claude", "--plan", "myfile.txt"],
    )
    assert result.exit_code == 2
    combined = result.output + (result.stderr or "")
    assert "--plan" in combined


# ===========================================================================
# test_link_all_prompt.bats: --all form
# ===========================================================================


def test_link_all_yes_creates_yaml_with_slugs(env):
    """Replaces tests/bats/test_link_all_prompt.bats:33-41."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    _seed_skill(toolkit, "beta", ["claude"])
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--toolkit-repo", str(toolkit), "link", "user", "claude", "--all", "--yes"],
    )
    assert result.exit_code == 0, (result.output, result.stderr)
    yaml_path = home / ".agent-toolkit.yaml"
    assert yaml_path.is_file()
    yaml_text = yaml_path.read_text()
    assert "alpha" in yaml_text
    assert "beta" in yaml_text
    assert (home / ".claude" / "skills" / "alpha").is_symlink()
    assert (home / ".claude" / "skills" / "beta").is_symlink()


def test_link_all_yes_overwrites(env):
    """Replaces tests/bats/test_link_all_prompt.bats:43-56."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text(
        "skills:\n  - oldslug\nagents: []\ncommands: []\nhooks: []\nplugins: []\n"
    )
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--toolkit-repo", str(toolkit), "link", "user", "claude", "--all", "-y"],
    )
    assert result.exit_code == 0
    yaml_text = (home / ".agent-toolkit.yaml").read_text()
    assert "oldslug" not in yaml_text
    assert "alpha" in yaml_text


def test_link_all_non_tty_no_yes_refuses(env, monkeypatch):
    """Replaces tests/bats/test_link_all_prompt.bats:58-71.

    Non-TTY without -y should refuse. We simulate no-TTY by using CliRunner
    with input="" (no TTY) and NOT passing --yes.
    """
    home = env["home"]
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text(
        "skills:\n  - oldslug\nagents: []\ncommands: []\nhooks: []\nplugins: []\n"
    )
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--toolkit-repo", str(toolkit), "link", "user", "claude", "--all"],
        input="",
    )
    assert result.exit_code != 0
    combined = result.output + (result.stderr or "")
    assert "no TTY" in combined
    # Existing file should be unchanged
    assert "oldslug" in (home / ".agent-toolkit.yaml").read_text()


def test_link_all_empty_file_no_prompt(env):
    """Replaces tests/bats/test_link_all_prompt.bats:73-78."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text("")
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--toolkit-repo", str(toolkit), "link", "user", "claude", "--all"],
        input="",  # no-TTY but file is empty so no prompt needed
    )
    assert result.exit_code == 0, (result.output, result.stderr)
    assert "alpha" in (home / ".agent-toolkit.yaml").read_text()


def test_link_all_dry_run_no_write(env):
    """Replaces tests/bats/test_link_all_prompt.bats:80-96."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    _seed_skill(toolkit, "beta", ["claude"])
    (home / ".agent-toolkit.yaml").write_text(
        "skills:\n  - oldslug\nagents: []\ncommands: []\nhooks: []\nplugins: []\n"
    )
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--toolkit-repo", str(toolkit), "link", "user", "claude", "--all", "-y", "--dry-run"],
    )
    assert result.exit_code == 0
    combined = result.output + (result.stderr or "")
    # Should mention actual slugs (alpha/beta) or pending changes
    assert "alpha" in combined or "pending" in combined
    # Actual file should NOT have been written
    yaml_text = (home / ".agent-toolkit.yaml").read_text()
    assert "oldslug" in yaml_text
    assert "alpha" not in yaml_text


# ===========================================================================
# test_link_user_optin.bats: bare form with opt-in file
# ===========================================================================


def test_link_bare_no_yaml_hints_with_all_and_kind_slug(env):
    """Replaces tests/bats/test_link_user_optin.bats:31-38."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    runner = CliRunner()
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "link", "user", "claude"],
    )
    assert result.exit_code == 2
    combined = result.output + (result.stderr or "")
    assert f"no {home / '.agent-toolkit.yaml'}" in combined
    assert "--all" in combined
    assert "<kind>:<slug>" in combined
    assert not (home / ".claude" / "skills" / "alpha").is_symlink()


def test_link_bare_empty_yaml_links_nothing(env):
    """Replaces tests/bats/test_link_user_optin.bats:40-45."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text("")
    runner = CliRunner()
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "link", "user", "claude"],
    )
    assert result.exit_code == 0
    assert not (home / ".claude" / "skills" / "alpha").is_symlink()


def test_link_bare_allowlisted_links(env):
    """Replaces tests/bats/test_link_user_optin.bats:47-59."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text(
        "skills:\n  - alpha\nagents: []\ncommands: []\nhooks: []\nplugins: []\n"
    )
    runner = CliRunner()
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "link", "user", "claude"],
    )
    assert result.exit_code == 0
    assert (home / ".claude" / "skills" / "alpha").is_symlink()


def test_link_bare_skips_unlisted(env):
    """Replaces tests/bats/test_link_user_optin.bats:61-72."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text(
        "skills: []\nagents: []\ncommands: []\nhooks: []\nplugins: []\n"
    )
    runner = CliRunner()
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "link", "user", "claude"],
    )
    assert result.exit_code == 0
    assert not (home / ".claude" / "skills" / "alpha").is_symlink()


def test_link_bare_prunes_when_removed(env):
    """Replaces tests/bats/test_link_user_optin.bats:74-95."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text(
        "skills:\n  - alpha\nagents: []\ncommands: []\nhooks: []\nplugins: []\n"
    )
    runner = CliRunner()
    runner.invoke(main, ["--toolkit-repo", str(toolkit), "link", "user", "claude"])
    link = home / ".claude" / "skills" / "alpha"
    assert link.is_symlink()
    # Remove alpha from allow-list
    (home / ".agent-toolkit.yaml").write_text(
        "skills: []\nagents: []\ncommands: []\nhooks: []\nplugins: []\n"
    )
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "link", "user", "claude"],
    )
    assert result.exit_code == 0
    assert not link.is_symlink()


def test_link_bare_prunes_orphan(env):
    """Replaces tests/bats/test_link_user_optin.bats:97-131."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text(
        "skills:\n  - alpha\nagents: []\ncommands: []\nhooks: []\nplugins: []\n"
    )
    runner = CliRunner()
    runner.invoke(main, ["--toolkit-repo", str(toolkit), "link", "user", "claude"])
    link_alpha = home / ".claude" / "skills" / "alpha"
    assert link_alpha.is_symlink()

    # Simulate orphan: create a skill, link it manually, then delete it from repo
    _seed_skill(toolkit, "orphan", ["claude"])
    orphan_link = home / ".claude" / "skills" / "orphan"
    orphan_link.symlink_to(toolkit / "skills" / "orphan")
    # Remove from repo
    shutil.rmtree(toolkit / "skills" / "orphan")
    assert orphan_link.is_symlink()  # dangling symlink remains

    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "link", "user", "claude"],
    )
    assert result.exit_code == 0
    assert not orphan_link.is_symlink()  # orphan pruned
    assert link_alpha.is_symlink()  # alpha still there


# ===========================================================================
# Wire-through smoke test — invoke the installed Python entry point via
# subprocess to validate the post-install user experience (stderr/stdout
# split, real symlink creation). Verifies the bug at the heart of issue #1
# is fixed: `agent-toolkit link …` works through the [project.scripts]
# entry, not just CliRunner.
# ===========================================================================


def test_link_subprocess_smoke(env):
    """End-to-end: real subprocess against `agent-toolkit` on PATH."""
    import subprocess

    home, toolkit = env["home"], env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - alpha\n")
    (home / ".claude").mkdir()

    cli = shutil.which("agent-toolkit")
    if not cli:
        pytest.skip("agent-toolkit not on PATH (run `uv sync --extra tui`)")

    proc = subprocess.run(
        [cli, "--toolkit-repo", str(toolkit), "link", "user", "claude"],
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(home)},
        check=False,
    )
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    assert "Linking" in proc.stderr  # header on stderr
    assert (home / ".claude" / "skills" / "alpha").is_symlink()
