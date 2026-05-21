"""Each `skill --help` and `skill <subcmd> --help` ends with an Examples: section."""
import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def _help(args: list[str]) -> str:
    runner = CliRunner()
    result = runner.invoke(main, args)
    assert result.exit_code == 0, result.output
    return result.output


def test_skill_group_help_has_examples_section():
    out = _help(["skill", "--help"])
    assert "Examples:" in out, out


@pytest.mark.parametrize(
    "subcmd",
    ["add", "install", "uninstall", "list", "status", "update", "push", "remove"],
)
def test_skill_subcommand_help_has_examples_section(subcmd: str):
    out = _help(["skill", subcmd, "--help"])
    assert "Examples:" in out, out


def test_skill_help_no_deprecated_commands_in_examples():
    """The Examples block must only reference v2 commands."""
    out = _help(["skill", "--help"])
    examples = out.split("Examples:", 1)[1]
    for removed in ("check ", "link ", "doctor ", "fix ", "ingest ",
                    "inventory ", "migrate-skills ", "diff ", "unlink ", " pi "):
        assert removed not in examples, (
            f"deprecated token {removed!r} appears in Examples block"
        )
    assert "--harness" not in examples, "--harness is a pre-v2 flag"
