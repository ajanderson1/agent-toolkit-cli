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


_DEPRECATED_TOKENS = (
    "check ", "link ", "doctor ", "fix ", "ingest ",
    "inventory ", "migrate-skills ", "diff ", "unlink ", " pi ",
)


@pytest.mark.parametrize(
    "args",
    [
        ["skill"],
        ["skill", "add"],
        ["skill", "install"],
        ["skill", "uninstall"],
        ["skill", "list"],
        ["skill", "status"],
        ["skill", "update"],
        ["skill", "push"],
        ["skill", "remove"],
    ],
)
def test_examples_block_has_no_deprecated_commands(args: list[str]):
    """Every Examples: block (group + 8 subcommands) must only reference v2 commands."""
    out = _help(args + ["--help"])
    examples = out.split("Examples:", 1)[1]
    for removed in _DEPRECATED_TOKENS:
        assert removed not in examples, (
            f"deprecated token {removed!r} in `{' '.join(args)} --help` Examples block"
        )
    assert "--harness" not in examples, (
        f"--harness is a pre-v2 flag (in `{' '.join(args)} --help`)"
    )
