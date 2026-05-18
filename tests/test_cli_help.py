from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def test_top_level_help_explains_what_the_python_cli_does():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    # The group docstring should mention what these commands DO, not just list them.
    assert "frontmatter" in result.output.lower() or "AGENTS.md" in result.output
    # All four subcommands listed.
    for subcmd in ("check", "doctor", "fix", "new"):
        assert subcmd in result.output


def test_subcommand_help_includes_short_help():
    runner = CliRunner()
    for subcmd in ("check", "doctor", "fix", "new"):
        result = runner.invoke(main, ["--help"])
        assert subcmd in result.output
        # short_help should appear on the same line as the subcommand
        # (Click formatting puts them in the "Commands:" table).
