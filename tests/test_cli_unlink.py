"""Pytest port of tests/bats/test_unlink*.bats. Each test cites the bats file:line it replaces."""
from __future__ import annotations

import re
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
# test_unlink_grammar.bats:41-48 — bare error hint
# ===========================================================================


def test_unlink_bare_errors_with_hint(env):
    """Replaces tests/bats/test_unlink_grammar.bats:41-48."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - alpha\n")
    (home / ".claude" / "skills").mkdir(parents=True)
    link_path = home / ".claude" / "skills" / "alpha"
    link_path.symlink_to(toolkit / "skills" / "alpha")
    runner = CliRunner()
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "unlink", "user", "claude"],
    )
    assert result.exit_code == 2
    assert "unlink requires a target" in result.stderr
    assert "--all" in result.stderr
    assert "<kind>:<slug>" in result.stderr
    assert link_path.is_symlink()  # untouched


# ===========================================================================
# test_unlink.bats:33-37 — --all removes symlinks into repo
# ===========================================================================


def test_unlink_all_removes_into_repo(env):
    """Replaces tests/bats/test_unlink.bats:33-37."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    (home / ".claude" / "skills").mkdir(parents=True)
    link_path = home / ".claude" / "skills" / "alpha"
    link_path.symlink_to(toolkit / "skills" / "alpha")
    runner = CliRunner()
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "unlink", "user", "claude", "--all"],
    )
    assert result.exit_code == 0, (result.output, result.stderr)
    assert not link_path.is_symlink()


# ===========================================================================
# test_unlink.bats:39-44 — --all leaves unrelated symlinks untouched
# ===========================================================================


def test_unlink_all_leaves_unrelated(env):
    """Replaces tests/bats/test_unlink.bats:39-44."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    (home / ".claude" / "skills").mkdir(parents=True)
    link_path = home / ".claude" / "skills" / "alpha"
    link_path.symlink_to(toolkit / "skills" / "alpha")
    unrelated = home / ".claude" / "skills" / "unrelated"
    unrelated.symlink_to("/tmp")
    runner = CliRunner()
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "unlink", "user", "claude", "--all"],
    )
    assert result.exit_code == 0
    assert not link_path.is_symlink()
    assert unrelated.is_symlink()


# ===========================================================================
# test_unlink.bats:46-51 — --all emits header and summary on stderr
# ===========================================================================


def test_unlink_all_header_and_summary(env):
    """Replaces tests/bats/test_unlink.bats:46-51."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    (home / ".claude" / "skills").mkdir(parents=True)
    (home / ".claude" / "skills" / "alpha").symlink_to(toolkit / "skills" / "alpha")
    runner = CliRunner()
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "unlink", "user", "claude", "--all"],
    )
    assert result.exit_code == 0
    assert "Removing" in result.stderr
    assert "Removed" in result.stderr


# ===========================================================================
# test_unlink_grammar.bats:50-56 — --all clears symlinks but preserves YAML
# ===========================================================================


def test_unlink_all_preserves_yaml(env):
    """Replaces tests/bats/test_unlink_grammar.bats:50-56."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    yaml_path = home / ".agent-toolkit.yaml"
    yaml_path.write_text(
        "skills:\n  - alpha\nagents: []\ncommands: []\nhooks: []\nplugins: []\n"
    )
    (home / ".claude" / "skills").mkdir(parents=True)
    link_path = home / ".claude" / "skills" / "alpha"
    link_path.symlink_to(toolkit / "skills" / "alpha")
    runner = CliRunner()
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "unlink", "user", "claude", "--all"],
    )
    assert result.exit_code == 0
    assert not link_path.is_symlink()
    assert yaml_path.is_file()
    assert "alpha" in yaml_path.read_text()


# ===========================================================================
# test_unlink_grammar.bats:58-63 — per-asset removes from file and prunes symlink
# ===========================================================================


def test_unlink_per_asset_removes_yaml_and_symlink(env):
    """Replaces tests/bats/test_unlink_grammar.bats:58-63."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    yaml_path = home / ".agent-toolkit.yaml"
    yaml_path.write_text(
        "skills:\n  - alpha\nagents: []\ncommands: []\nhooks: []\nplugins: []\n"
    )
    (home / ".claude" / "skills").mkdir(parents=True)
    link_path = home / ".claude" / "skills" / "alpha"
    link_path.symlink_to(toolkit / "skills" / "alpha")
    runner = CliRunner()
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "unlink", "user", "claude", "skill:alpha"],
    )
    assert result.exit_code == 0, (result.output, result.stderr)
    assert not link_path.is_symlink()
    yaml_text = yaml_path.read_text()
    # alpha should be removed from the skills list
    assert not re.search(r"^\s*-\s*alpha", yaml_text, re.MULTILINE)


# ===========================================================================
# test_unlink_grammar.bats:65-70 — per-asset idempotent with diagnostic
# ===========================================================================


def test_unlink_per_asset_idempotent_diag(env):
    """Replaces tests/bats/test_unlink_grammar.bats:65-70."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    yaml_path = home / ".agent-toolkit.yaml"
    yaml_path.write_text(
        "skills:\n  - alpha\nagents: []\ncommands: []\nhooks: []\nplugins: []\n"
    )
    (home / ".claude" / "skills").mkdir(parents=True)
    link_path = home / ".claude" / "skills" / "alpha"
    link_path.symlink_to(toolkit / "skills" / "alpha")
    runner = CliRunner()
    # First unlink
    runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "unlink", "user", "claude", "skill:alpha"],
    )
    # Second run — idempotent diagnostic
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "unlink", "user", "claude", "skill:alpha"],
    )
    assert result.exit_code == 0
    assert "nothing to remove" in result.stderr


# ===========================================================================
# test_unlink_grammar.bats:72-77 — per-asset when YAML missing errors
# ===========================================================================


def test_unlink_per_asset_no_yaml_errors(env):
    """Replaces tests/bats/test_unlink_grammar.bats:72-77."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    # Do NOT create .agent-toolkit.yaml
    (home / ".claude" / "skills").mkdir(parents=True)
    runner = CliRunner()
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "unlink", "user", "claude", "skill:alpha"],
    )
    assert result.exit_code != 0
    assert "nothing to unlink" in result.stderr


# ===========================================================================
# test_unlink_grammar.bats:79-83 — --all leaves unrelated symlinks alone
# ===========================================================================


def test_unlink_all_unrelated_alone(env):
    """Replaces tests/bats/test_unlink_grammar.bats:79-83."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    yaml_path = home / ".agent-toolkit.yaml"
    yaml_path.write_text(
        "skills:\n  - alpha\nagents: []\ncommands: []\nhooks: []\nplugins: []\n"
    )
    (home / ".claude" / "skills").mkdir(parents=True)
    link_path = home / ".claude" / "skills" / "alpha"
    link_path.symlink_to(toolkit / "skills" / "alpha")
    unrelated = home / ".claude" / "skills" / "unrelated"
    unrelated.symlink_to("/tmp")
    runner = CliRunner()
    runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "unlink", "user", "claude", "--all"],
    )
    assert unrelated.is_symlink()


# ===========================================================================
# test_unlink_grammar.bats:85-120 — --plan - removes multiple slugs
# ===========================================================================


def test_unlink_plan_multi(env):
    """Replaces tests/bats/test_unlink_grammar.bats:85-120."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    _seed_skill(toolkit, "alpha", ["claude"])
    _seed_skill(toolkit, "beta", ["claude"])
    yaml_path = home / ".agent-toolkit.yaml"
    yaml_path.write_text(
        "skills:\n  - alpha\n  - beta\nagents: []\ncommands: []\nhooks: []\nplugins: []\n"
    )
    (home / ".claude" / "skills").mkdir(parents=True)
    link_alpha = home / ".claude" / "skills" / "alpha"
    link_beta = home / ".claude" / "skills" / "beta"
    link_alpha.symlink_to(toolkit / "skills" / "alpha")
    link_beta.symlink_to(toolkit / "skills" / "beta")
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--toolkit-repo", str(toolkit), "unlink", "user", "claude", "--plan", "-"],
        input="skill:alpha\nskill:beta\n",
    )
    assert result.exit_code == 0, (result.output, result.stderr)
    assert not link_alpha.is_symlink()
    assert not link_beta.is_symlink()


# ===========================================================================
# test_unlink_grammar.bats:122-125 — --plan rejects combination with --all
# ===========================================================================


def test_unlink_plan_with_all_rc2(env):
    """Replaces tests/bats/test_unlink_grammar.bats:122-125."""
    toolkit = env["toolkit_root"]
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--toolkit-repo", str(toolkit), "unlink", "user", "claude", "--plan", "-", "--all"],
        input="",
    )
    assert result.exit_code == 2


# ===========================================================================
# test_unlink_grammar.bats:127-131 — --plan with no following arg returns rc=2
# ===========================================================================


def test_unlink_plan_no_arg_rc2(env):
    """Replaces tests/bats/test_unlink_grammar.bats:127-131."""
    toolkit = env["toolkit_root"]
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--toolkit-repo", str(toolkit), "unlink", "user", "claude", "--plan"],
    )
    assert result.exit_code == 2
    combined = result.output + result.stderr
    assert "--plan" in combined


# ===========================================================================
# test_unlink_grammar.bats:133-137 — --plan with non-dash arg returns rc=2
# ===========================================================================


def test_unlink_plan_non_dash_rc2(env):
    """Replaces tests/bats/test_unlink_grammar.bats:133-137."""
    toolkit = env["toolkit_root"]
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--toolkit-repo", str(toolkit), "unlink", "user", "claude", "--plan", "myfile.txt"],
    )
    assert result.exit_code == 2
    combined = result.output + result.stderr
    assert "--plan" in combined


# ===========================================================================
# Issue #9 — reject unknown harness with a clean error
# ===========================================================================


def test_unlink_unknown_harness_exits_2_with_message(env):
    runner = CliRunner()
    result = runner.invoke(
        main, ["--toolkit-repo", str(env["toolkit_root"]), "unlink", "user", "banana", "--all"],
    )
    assert result.exit_code == 2
    assert "unknown harness 'banana'" in result.stderr
    assert "claude codex opencode pi" in result.stderr


def test_unlink_unknown_harness_does_not_touch_filesystem(env):
    home = env["home"]
    (home / ".claude").mkdir()
    before = sorted(p for p in home.rglob("*"))
    runner = CliRunner()
    runner.invoke(
        main, ["--toolkit-repo", str(env["toolkit_root"]), "unlink", "user", "banana", "--all"],
    )
    after = sorted(p for p in home.rglob("*"))
    assert before == after


def test_unlink_dry_run_unknown_harness_still_validates(env):
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--toolkit-repo", str(env["toolkit_root"]),
         "unlink", "user", "banana", "--all", "--dry-run"],
    )
    assert result.exit_code == 2
    assert "unknown harness 'banana'" in result.stderr
