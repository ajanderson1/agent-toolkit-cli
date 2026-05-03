from pathlib import Path

from click.testing import CliRunner

from agent_toolkit.cli import main


def test_new_skill_creates_skeleton(tmp_path):
    (tmp_path / "schemas").mkdir()
    src_schema = Path(__file__).parent.parent / "schemas" / "asset-frontmatter.v1alpha1.json"
    (tmp_path / "schemas" / "asset-frontmatter.v1alpha1.json").write_text(src_schema.read_text())
    (tmp_path / "AGENTS.md").write_text(
        "<!-- BEGIN_AGENT_TOOLKIT:component-table -->\n"
        "<!-- END_AGENT_TOOLKIT:component-table -->\n"
        "<!-- BEGIN_AGENT_TOOLKIT:submodule-table -->\n"
        "<!-- END_AGENT_TOOLKIT:submodule-table -->\n"
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["new", "skill", "demo-skill", "--toolkit-repo", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output

    skill_md = tmp_path / "skills" / "demo-skill" / "SKILL.md"
    assert skill_md.exists()
    text = skill_md.read_text()
    assert "apiVersion: agent-toolkit/v1alpha1" in text
    assert "name: demo-skill" in text
    assert "harnesses:" in text


def test_new_skill_validates_against_schema(tmp_path):
    (tmp_path / "schemas").mkdir()
    src_schema = Path(__file__).parent.parent / "schemas" / "asset-frontmatter.v1alpha1.json"
    (tmp_path / "schemas" / "asset-frontmatter.v1alpha1.json").write_text(src_schema.read_text())

    runner = CliRunner()
    runner.invoke(main, ["new", "skill", "demo-skill", "--toolkit-repo", str(tmp_path)])
    result = runner.invoke(main, ["check", "--toolkit-repo", str(tmp_path), "--exit-code"])
    assert result.exit_code == 0, result.output


def test_new_emits_header_and_summary_on_stderr(tmp_path):
    (tmp_path / "schemas").mkdir()
    src_schema = Path(__file__).parent.parent / "schemas" / "asset-frontmatter.v1alpha1.json"
    (tmp_path / "schemas" / "asset-frontmatter.v1alpha1.json").write_text(src_schema.read_text())

    runner = CliRunner()
    result = runner.invoke(main, ["new", "skill", "demo-skill", "--toolkit-repo", str(tmp_path)])
    assert result.exit_code == 0
    assert "Scaffolding" in result.output
    assert "agent-toolkit check" in result.output   # next-step hint
    assert "created" in result.output                # original assertion preserved
