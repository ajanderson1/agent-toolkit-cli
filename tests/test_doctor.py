from click.testing import CliRunner

from agent_toolkit.cli import main


def test_doctor_runs_and_reports(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["doctor", "--repo-root", str(tmp_path)])
    # exits 0 even if some checks fail — doctor reports, doesn't gate
    assert result.exit_code == 0
    assert "schema" in result.output.lower() or "AGENTS.md" in result.output


def test_doctor_reports_missing_schema(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["doctor", "--repo-root", str(tmp_path)])
    assert "schema" in result.output.lower()
    # schemas/asset-frontmatter.v1alpha1.json is missing in tmp_path
    assert "missing" in result.output.lower() or "not found" in result.output.lower()
