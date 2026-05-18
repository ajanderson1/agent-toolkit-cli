"""Pytest port of tests/bats/test_list*.bats. Each test cites the bats file:line it replaces."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main


@pytest.fixture
def multi_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, seed_skill, seed_toolkit):
    """Three skills: alpha (claude), beta (claude+codex), gamma (codex only)."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)
    monkeypatch.delenv("AGENT_TOOLKIT_QUIET", raising=False)
    toolkit_root = seed_toolkit(tmp_path)
    seed_skill(toolkit_root, "alpha", ["claude"])
    seed_skill(toolkit_root, "beta", ["claude", "codex"])
    seed_skill(toolkit_root, "gamma", ["codex"])
    # User scope: alpha installed (in YAML + symlink)
    (home / ".agent-toolkit.yaml").write_text(
        "skills:\n  - alpha\nagents: []\ncommands: []\nhooks: []\nplugins: []\n"
    )
    (home / ".claude" / "skills").mkdir(parents=True)
    (home / ".claude" / "skills" / "alpha").symlink_to(toolkit_root / "skills" / "alpha")
    return {"home": home, "toolkit_root": toolkit_root}


# ===========================================================================
# test_list.bats: basic scenarios
# ===========================================================================


def test_list_shows_user_check(env, seed_skill):
    """Replaces tests/bats/test_list.bats:33-46."""
    home, toolkit = env["home"], env["toolkit_root"]
    seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - alpha\n")
    (home / ".claude" / "skills").mkdir(parents=True)
    (home / ".claude" / "skills" / "alpha").symlink_to(toolkit / "skills" / "alpha")
    runner = CliRunner()
    result = runner.invoke(main, ["--toolkit-repo", str(toolkit), "list"])
    assert result.exit_code == 0, (result.output, result.stderr)
    assert "alpha" in result.output
    assert "user:✓" in result.output


def test_list_header_and_summary_on_stderr(env, seed_skill):
    """Replaces tests/bats/test_list.bats:48-53."""
    toolkit = env["toolkit_root"]
    seed_skill(toolkit, "alpha", ["claude"])
    runner = CliRunner()
    result = runner.invoke(main, ["--toolkit-repo", str(toolkit), "list"])
    assert result.exit_code == 0, (result.output, result.stderr)
    assert "Asset inventory" in result.stderr
    assert "Done" in result.stderr


def test_list_quiet_env_silent(env, monkeypatch, seed_skill):
    """Replaces tests/bats/test_list.bats:55-59."""
    toolkit = env["toolkit_root"]
    seed_skill(toolkit, "alpha", ["claude"])
    monkeypatch.setenv("AGENT_TOOLKIT_QUIET", "1")
    runner = CliRunner()
    result = runner.invoke(main, ["--toolkit-repo", str(toolkit), "list"])
    assert result.exit_code == 0, (result.output, result.stderr)
    assert result.stderr == ""


def test_list_json_valid(env, seed_skill):
    """Replaces tests/bats/test_list.bats:61-73."""
    home, toolkit = env["home"], env["toolkit_root"]
    seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - alpha\n")
    (home / ".claude" / "skills").mkdir(parents=True)
    (home / ".claude" / "skills" / "alpha").symlink_to(toolkit / "skills" / "alpha")
    runner = CliRunner()
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "list", "--format=json"]
    )
    assert result.exit_code == 0, (result.output, result.stderr)
    data = json.loads(result.output)
    assert str(toolkit) in data["toolkit_root"] or data["toolkit_root"].endswith(
        toolkit.name
    )
    assert any(a["slug"] == "alpha" for a in data["assets"])
    cells = [
        c
        for a in data["assets"]
        if a["slug"] == "alpha"
        for c in a["cells"]
    ]
    assert any(
        c["harness"] == "claude" and c["scope"] == "user" and c["status"] == "linked"
        for c in cells
    ), cells


def test_list_json_unsupported_cells(env, seed_skill):
    """Replaces tests/bats/test_list.bats:75-79."""
    toolkit = env["toolkit_root"]
    seed_skill(toolkit, "alpha", ["claude"])
    runner = CliRunner()
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "list", "--format=json"]
    )
    assert result.exit_code == 0, (result.output, result.stderr)
    data = json.loads(result.output)
    cells = [
        c
        for a in data["assets"]
        if a["slug"] == "alpha"
        for c in a["cells"]
    ]
    assert any(
        c["harness"] == "codex" and c["status"] == "unsupported" for c in cells
    ), cells


# ===========================================================================
# test_list_new_grammar.bats
# ===========================================================================


def test_list_no_args_all_with_cols(multi_env):
    """Replaces tests/bats/test_list_new_grammar.bats:50-62."""
    toolkit = multi_env["toolkit_root"]
    runner = CliRunner()
    result = runner.invoke(main, ["--toolkit-repo", str(toolkit), "list"])
    assert result.exit_code == 0, (result.output, result.stderr)
    assert "alpha" in result.output
    assert "beta" in result.output
    assert "gamma" in result.output
    # alpha is user-installed
    alpha_line = next(
        line for line in result.output.splitlines() if line.strip().startswith("alpha")
    )
    assert "user:✓" in alpha_line
    # beta and gamma are not installed
    beta_line = next(
        line for line in result.output.splitlines() if line.strip().startswith("beta")
    )
    assert "user:—" in beta_line
    gamma_line = next(
        line for line in result.output.splitlines() if line.strip().startswith("gamma")
    )
    assert "user:—" in gamma_line


def test_list_kind_filter(multi_env):
    """Replaces tests/bats/test_list_new_grammar.bats:64-71."""
    toolkit = multi_env["toolkit_root"]
    runner = CliRunner()
    result = runner.invoke(main, ["--toolkit-repo", str(toolkit), "list", "skill"])
    assert result.exit_code == 0, (result.output, result.stderr)
    assert "SKILLS" in result.output
    assert "AGENTS" not in result.output


def test_list_harness_filter(multi_env):
    """Replaces tests/bats/test_list_new_grammar.bats:73-80."""
    toolkit = multi_env["toolkit_root"]
    runner = CliRunner()
    result = runner.invoke(main, ["--toolkit-repo", str(toolkit), "list", "claude"])
    assert result.exit_code == 0, (result.output, result.stderr)
    assert "alpha" in result.output
    assert "beta" in result.output
    assert "gamma" not in result.output


def test_list_kind_and_harness(multi_env):
    """Replaces tests/bats/test_list_new_grammar.bats:82-89."""
    toolkit = multi_env["toolkit_root"]
    runner = CliRunner()
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "list", "skill", "claude"]
    )
    assert result.exit_code == 0, (result.output, result.stderr)
    assert "alpha" in result.output
    assert "beta" in result.output
    assert "gamma" not in result.output


def test_list_outside_project(multi_env):
    """Replaces tests/bats/test_list_new_grammar.bats:91-96.

    When CWD has no .agent-toolkit.yaml the project column should show '—' for all.
    """
    toolkit = multi_env["toolkit_root"]
    home = multi_env["home"]
    # Use a project dir that has no .agent-toolkit.yaml
    empty_dir = home / "empty_project"
    empty_dir.mkdir()
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--toolkit-repo", str(toolkit), "--project", str(empty_dir), "list"],
    )
    assert result.exit_code == 0, (result.output, result.stderr)
    assert "project:—" in result.output


def test_list_rejects_unknown_positional(multi_env):
    """Replaces tests/bats/test_list_new_grammar.bats:98-103."""
    toolkit = multi_env["toolkit_root"]
    runner = CliRunner()
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "list", "nonsense"]
    )
    assert result.exit_code != 0
    assert "nonsense" in result.output or "nonsense" in (result.stderr or "")


def test_list_project_check(multi_env):
    """Replaces tests/bats/test_list_new_grammar.bats:105-120."""
    toolkit = multi_env["toolkit_root"]
    # Add beta to project scope
    (toolkit / ".agent-toolkit.yaml").write_text(
        "skills:\n  - beta\nagents: []\ncommands: []\nhooks: []\nplugins: []\n"
    )
    (toolkit / ".claude" / "skills").mkdir(parents=True)
    (toolkit / ".claude" / "skills" / "beta").symlink_to(toolkit / "skills" / "beta")
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--toolkit-repo", str(toolkit), "--project", str(toolkit), "list"],
    )
    assert result.exit_code == 0, (result.output, result.stderr)
    beta_line = next(
        line for line in result.output.splitlines() if line.strip().startswith("beta")
    )
    assert "project:✓" in beta_line


def test_list_mcp_filter_succeeds(multi_env):
    """Replaces tests/bats/test_list_new_grammar.bats:122-131.

    The 'mcp' kind filter is accepted by the CLI parser and the command runs
    cleanly. With no MCPs seeded in multi_env the inventory body for MCPs is
    simply empty (no MCPs section emitted), but parsing/dispatch succeed.
    """
    toolkit = multi_env["toolkit_root"]
    runner = CliRunner()
    result = runner.invoke(main, ["--toolkit-repo", str(toolkit), "list", "mcp"])
    assert result.exit_code == 0, result.output
    combined = result.output + (result.stderr or "")
    # Filter parsing must succeed (no "unknown filter" rejection).
    assert "unknown filter" not in combined
    assert "Asset inventory" in combined


# ===========================================================================
# Wire-through smoke test — invoke the installed Python entry point via
# subprocess to validate the post-install user experience for `list`.
# ===========================================================================


def test_list_subprocess_smoke(env, seed_skill):
    """End-to-end: real subprocess against `agent-toolkit list`."""
    import subprocess

    home, toolkit = env["home"], env["toolkit_root"]
    seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - alpha\n")

    cli = shutil.which("agent-toolkit-cli")
    if not cli:
        pytest.skip("agent-toolkit-cli not on PATH (run `uv sync`)")

    proc = subprocess.run(
        [cli, "--toolkit-repo", str(toolkit), "list"],
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(home)},
        check=False,
    )
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    assert "Asset inventory" in proc.stderr  # header on stderr
    assert "alpha" in proc.stdout  # asset name on stdout


# ===========================================================================
# Issue #7 — --project flag for symmetry with link/unlink/diff
# ===========================================================================


def test_list_project_flag_resolves_correctly(tmp_path, env, seed_skill, monkeypatch):
    """`list --project /x` reads /x/.agent-toolkit.yaml, not CWD's."""
    home, toolkit = env["home"], env["toolkit_root"]
    seed_skill(toolkit, "alpha", ["claude"])

    proj = home / "myproject"
    proj.mkdir()
    (proj / ".agent-toolkit.yaml").write_text(
        "skills:\n  - alpha\nagents: []\ncommands: []\nhooks: []\nplugins: []\n"
    )
    (proj / ".claude" / "skills").mkdir(parents=True)
    (proj / ".claude" / "skills" / "alpha").symlink_to(toolkit / "skills" / "alpha")

    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--toolkit-repo", str(toolkit), "list", "--project", str(proj)],
    )
    assert result.exit_code == 0, (result.output, result.stderr)
    assert "alpha" in result.output
    assert "project:✓" in result.output


# ===========================================================================
# Issue #11 — list --report
# ===========================================================================


def test_list_report_smoke(env, seed_skill):
    home, toolkit = env["home"], env["toolkit_root"]
    seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - alpha\n")
    (home / ".claude" / "skills").mkdir(parents=True)
    (home / ".claude" / "skills" / "alpha").symlink_to(toolkit / "skills" / "alpha")
    runner = CliRunner()
    result = runner.invoke(main, ["--toolkit-repo", str(toolkit), "list", "--report"])
    assert result.exit_code == 0, (result.output, result.stderr)
    assert "Asset inventory report" in result.output
    assert "claude" in result.output
    assert "alpha" in result.output
    assert "linked" in result.output


def test_list_report_rejects_format_json(env):
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--toolkit-repo", str(env["toolkit_root"]), "list", "--report", "--format=json"],
    )
    assert result.exit_code == 2
    assert "cannot combine" in result.stderr


def test_list_text_includes_mcps(tmp_path, monkeypatch):
    """Text-mode list shows an MCPs section with allow-listed MCPs."""
    from click.testing import CliRunner
    from agent_toolkit_cli.cli import main

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)

    toolkit = tmp_path / "toolkit"
    toolkit.mkdir()
    (toolkit / ".agent-toolkit-source").write_text("")
    (toolkit / "schemas").mkdir()
    schema_src = Path(__file__).resolve().parents[1] / "schemas" / "asset-frontmatter.v1alpha2.json"
    (toolkit / "schemas" / "asset-frontmatter.v1alpha2.json").write_text(schema_src.read_text())
    mcp_dir = toolkit / "mcps" / "context7"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text('{"type":"stdio","command":"npx"}\n')
    (mcp_dir / "README.md").write_text(
        "---\napiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: context7\n  description: c.\n  lifecycle: stable\n"
        "spec:\n  origin: third-party\n  vendored_via: none\n"
        "  upstream: https://example.com\n  harnesses:\n    - claude\n---\n"
    )

    project = tmp_path / "project"
    project.mkdir()
    (project / ".agent-toolkit.yaml").write_text("mcps:\n  - context7\n")

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["list", "--toolkit-repo", str(toolkit), "--project", str(project)],
    )
    assert result.exit_code == 0, result.output
    assert "MCPs (1)" in result.output
    assert "context7" in result.output
    # Issue 1 regression guard: bracket must show declared harnesses, not "[]"
    assert "[claude]" in result.output, f"expected bracket containing 'claude', got:\n{result.output}"
    assert "[]" not in result.output, f"bracket was empty — _asset_harnesses not reading README.md frontmatter:\n{result.output}"
