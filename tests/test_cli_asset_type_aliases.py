"""Top-level asset-type command aliases."""
from __future__ import annotations

import re

import click
import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main


ASSET_GROUPS = {
    "skills": "skill",
    "agents": "agent",
    "mcps": "mcp",
    "pi-extensions": "pi-extension",
    "bundles": "bundle",
    "instructions": "instruction",
}

REPRESENTATIVE_SUBCOMMANDS = {
    "skills": "list",
    "agents": "list",
    "mcps": "list",
    "pi-extensions": "list",
    "bundles": "validate",
    "instructions": "list",
}


def _command_row(output: str, name: str) -> re.Match[str] | None:
    return re.search(rf"^\s+{re.escape(name)}\s", output, re.MULTILINE)


def test_root_help_lists_plural_asset_commands_only() -> None:
    result = CliRunner().invoke(main, ["--help"])
    assert result.exit_code == 0, result.output

    for plural, singular in ASSET_GROUPS.items():
        assert _command_row(result.output, plural), result.output
        assert not _command_row(result.output, singular), result.output


def test_root_help_recommends_plural_help_surface() -> None:
    result = CliRunner().invoke(main, ["--help"])
    assert result.exit_code == 0, result.output
    assert "agent-toolkit-cli skills --help" in result.output
    assert "agent-toolkit-cli skill --help" not in result.output


@pytest.mark.parametrize("plural, singular", sorted(ASSET_GROUPS.items()))
def test_singular_alias_resolves_to_canonical_command(plural: str, singular: str) -> None:
    with click.Context(main) as ctx:
        assert main.get_command(ctx, singular) is main.get_command(ctx, plural)


@pytest.mark.parametrize("plural, singular", sorted(ASSET_GROUPS.items()))
def test_singular_and_plural_group_help_both_work(plural: str, singular: str) -> None:
    runner = CliRunner()
    by_plural = runner.invoke(main, [plural, "--help"])
    by_singular = runner.invoke(main, [singular, "--help"])

    assert by_plural.exit_code == 0, by_plural.output
    assert by_singular.exit_code == 0, by_singular.output
    assert REPRESENTATIVE_SUBCOMMANDS[plural] in by_plural.output
    assert REPRESENTATIVE_SUBCOMMANDS[plural] in by_singular.output


@pytest.mark.parametrize("plural, singular", sorted(ASSET_GROUPS.items()))
def test_singular_and_plural_representative_subcommand_help_both_work(
    plural: str, singular: str,
) -> None:
    verb = REPRESENTATIVE_SUBCOMMANDS[plural]
    runner = CliRunner()
    by_plural = runner.invoke(main, [plural, verb, "--help"])
    by_singular = runner.invoke(main, [singular, verb, "--help"])

    assert by_plural.exit_code == 0, by_plural.output
    assert by_singular.exit_code == 0, by_singular.output
