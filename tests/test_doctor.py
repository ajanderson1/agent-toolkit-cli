from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def test_doctor_runs_and_groups_appear(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["doctor", "--toolkit-repo", str(tmp_path)])
    # Five group labels should appear in output
    for grp in ("environment", "symlink-integrity", "conventions", "submodule-health", "frontmatter"):
        assert grp in result.output, f"missing group {grp!r} in:\n{result.output}"


def test_doctor_exit_code_flag_propagates_failure(tmp_path):
    # Empty tmp_path will fail environment (no schema/AGENTS.md)
    runner = CliRunner()
    result = runner.invoke(main, ["doctor", "--toolkit-repo", str(tmp_path), "--exit-code"])
    assert result.exit_code != 0


def test_doctor_per_resource_unknown_slug(tmp_path):
    (tmp_path / "schemas").mkdir()
    (tmp_path / "schemas" / "asset-frontmatter.v1alpha2.json").write_text("{}")
    runner = CliRunner()
    result = runner.invoke(main, ["doctor", "ghost", "--toolkit-repo", str(tmp_path)])
    assert "ghost" in result.output


def test_doctor_emits_header_and_summary_on_stderr(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["doctor", "--toolkit-repo", str(tmp_path)])
    # Header and summary are emitted to stderr via _ui module.
    # CliRunner combines stdout and stderr in result.output.
    assert "doctor groups" in result.output.lower()
    assert "worst:" in result.output.lower()
