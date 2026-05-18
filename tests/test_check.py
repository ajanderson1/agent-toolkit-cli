from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def test_check_passes_on_valid_asset(tmp_path, monkeypatch):
    repo = tmp_path
    (repo / "schemas").mkdir()
    src_schema = Path(__file__).parent.parent / "schemas" / "asset-frontmatter.v1alpha2.json"
    (repo / "schemas" / "asset-frontmatter.v1alpha2.json").write_text(src_schema.read_text())
    (repo / "skills" / "alpha").mkdir(parents=True)
    (repo / "skills" / "alpha" / "SKILL.md").write_text(
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

    runner = CliRunner()
    result = runner.invoke(main, ["check", "--toolkit-repo", str(repo)])
    assert result.exit_code == 0, result.output


def test_check_exit_code_on_invalid_asset(tmp_path):
    repo = tmp_path
    (repo / "schemas").mkdir()
    src_schema = Path(__file__).parent.parent / "schemas" / "asset-frontmatter.v1alpha2.json"
    (repo / "schemas" / "asset-frontmatter.v1alpha2.json").write_text(src_schema.read_text())
    (repo / "skills" / "alpha").mkdir(parents=True)
    (repo / "skills" / "alpha" / "SKILL.md").write_text(
        "---\nname: alpha\n---\n"   # legacy frontmatter — invalid under v1alpha1
    )

    runner = CliRunner()
    result = runner.invoke(main, ["check", "--toolkit-repo", str(repo), "--exit-code"])
    assert result.exit_code != 0
    assert "schema" in result.output.lower() or "apiVersion" in result.output


def test_check_detects_marker_drift(tmp_path):
    repo = tmp_path
    (repo / "schemas").mkdir()
    src_schema = Path(__file__).parent.parent / "schemas" / "asset-frontmatter.v1alpha2.json"
    (repo / "schemas" / "asset-frontmatter.v1alpha2.json").write_text(src_schema.read_text())
    (repo / "skills" / "alpha").mkdir(parents=True)
    (repo / "skills" / "alpha" / "SKILL.md").write_text(
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
        "---\n"
    )
    (repo / "AGENTS.md").write_text(
        "<!-- BEGIN_AGENT_TOOLKIT:component-table -->\n"
        "STALE\n"
        "<!-- END_AGENT_TOOLKIT:component-table -->\n"
        "<!-- BEGIN_AGENT_TOOLKIT:submodule-table -->\n"
        "STALE\n"
        "<!-- END_AGENT_TOOLKIT:submodule-table -->\n"
    )

    runner = CliRunner()
    result = runner.invoke(main, ["check", "--toolkit-repo", str(repo), "--exit-code"])
    assert result.exit_code != 0
    assert "drift" in result.output.lower() or "STALE" in result.output


def test_check_emits_header_and_summary_on_stderr(tmp_path):
    repo = tmp_path
    (repo / "schemas").mkdir()
    src_schema = Path(__file__).parent.parent / "schemas" / "asset-frontmatter.v1alpha2.json"
    (repo / "schemas" / "asset-frontmatter.v1alpha2.json").write_text(src_schema.read_text())

    runner = CliRunner()
    result = runner.invoke(main, ["check", "--toolkit-repo", str(repo)])
    assert result.exit_code == 0
    # Header and summary are emitted to stderr via _ui module
    # CliRunner's result.output includes both stdout and stderr
    assert "Validating" in result.output
    assert "OK" in result.output
    assert "validated" in result.output or "0 drift" in result.output


def test_check_quiet_env_suppresses_chrome(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_TOOLKIT_QUIET", "1")
    repo = tmp_path
    (repo / "schemas").mkdir()
    src_schema = Path(__file__).parent.parent / "schemas" / "asset-frontmatter.v1alpha2.json"
    (repo / "schemas" / "asset-frontmatter.v1alpha2.json").write_text(src_schema.read_text())

    runner = CliRunner()
    result = runner.invoke(main, ["check", "--toolkit-repo", str(repo)])
    assert result.exit_code == 0
    assert "OK" in result.output
    # With AGENT_TOOLKIT_QUIET=1, header/summary are suppressed
    assert "Validating" not in result.output


def test_check_accepts_v1alpha2_mcp(tmp_path, monkeypatch):
    """Validator accepts a catalog MCP with structured v1alpha2 frontmatter."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)

    toolkit = tmp_path / "toolkit"
    toolkit.mkdir()
    (toolkit / ".agent-toolkit-source").write_text("")
    mcp_dir = toolkit / "mcps" / "context7"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text('{"type":"stdio","command":"npx"}\n')
    (mcp_dir / "README.md").write_text(
        "---\napiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: context7\n  description: c.\n  lifecycle: stable\n"
        "spec:\n  origin: third-party\n  vendored_via: none\n"
        "  upstream: https://example.com\n  harnesses:\n    - claude\n"
        "  mcp:\n    transport: stdio\n    install_method: npx\n---\n"
    )

    runner = CliRunner()
    result = runner.invoke(
        main, ["check", "--exit-code", "--toolkit-repo", str(toolkit)],
    )
    assert result.exit_code == 0, result.output
