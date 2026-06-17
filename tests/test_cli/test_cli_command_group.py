from click.testing import CliRunner
from agent_toolkit_cli.cli import main


def test_commands_group_and_singular_alias_exist():
    runner = CliRunner()
    plural = runner.invoke(main, ["commands", "--help"])
    singular = runner.invoke(main, ["command", "--help"])
    assert plural.exit_code == 0, plural.output
    assert singular.exit_code == 0, singular.output
    assert "Manage commands" in plural.output
