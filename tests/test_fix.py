from pathlib import Path

from click.testing import CliRunner

from agent_toolkit.cli import main


def _seed_repo(repo: Path) -> None:
    (repo / "schemas").mkdir()
    src_schema = Path(__file__).parent.parent / "schemas" / "asset-frontmatter.v1alpha1.json"
    (repo / "schemas" / "asset-frontmatter.v1alpha1.json").write_text(src_schema.read_text())
    (repo / "skills" / "alpha").mkdir(parents=True)
    (repo / "skills" / "alpha" / "SKILL.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha1\n"
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
        "# Agent Conventions\n"
        "\n"
        "<!-- BEGIN_AGENT_TOOLKIT:component-table -->\n"
        "OLD\n"
        "<!-- END_AGENT_TOOLKIT:component-table -->\n"
        "\n"
        "<!-- BEGIN_AGENT_TOOLKIT:submodule-table -->\n"
        "OLD\n"
        "<!-- END_AGENT_TOOLKIT:submodule-table -->\n"
    )


def test_fix_regenerates_component_table(tmp_path):
    _seed_repo(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["fix", "--toolkit-repo", str(tmp_path)])
    assert result.exit_code == 0, result.output

    text = (tmp_path / "AGENTS.md").read_text()
    assert "OLD" not in text
    assert "Skills" in text  # component table populated
    assert "BEGIN_AGENT_TOOLKIT:component-table" in text


def test_fix_only_filters_generators(tmp_path):
    _seed_repo(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["fix", "--toolkit-repo", str(tmp_path), "--only", "component-table"],
    )
    assert result.exit_code == 0
    text = (tmp_path / "AGENTS.md").read_text()
    # component-table updated; submodule-table still has OLD
    assert "Skills" in text
    submodule_section = text.split("BEGIN_AGENT_TOOLKIT:submodule-table")[1]
    assert "OLD" in submodule_section


def test_fix_to_stdout_does_not_modify_file(tmp_path):
    _seed_repo(tmp_path)
    original = (tmp_path / "AGENTS.md").read_text()
    runner = CliRunner()
    result = runner.invoke(main, ["fix", "--toolkit-repo", str(tmp_path), "--to-stdout"])
    assert result.exit_code == 0
    assert (tmp_path / "AGENTS.md").read_text() == original
    assert "BEGIN_AGENT_TOOLKIT:component-table" in result.output


def test_fix_emits_header_and_summary_on_stderr(tmp_path):
    _seed_repo(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["fix", "--toolkit-repo", str(tmp_path)])
    assert result.exit_code == 0
    # Header and summary are emitted to stderr via _ui module
    # CliRunner's result.output includes both stdout and stderr
    assert "Regenerating" in result.output
    assert "Updated AGENTS.md" in result.output


def test_fix_to_stdout_summary_says_file_unchanged(tmp_path):
    _seed_repo(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["fix", "--toolkit-repo", str(tmp_path), "--to-stdout"])
    assert result.exit_code == 0
    # Summary mentions file unchanged
    assert "file unchanged" in result.output.lower() or "stdout" in result.output.lower()
    # Rendered AGENTS.md content is in output
    assert "BEGIN_AGENT_TOOLKIT:component-table" in result.output
