"""Tests for AliasedGroup help formatting and CLI group alias collapsing."""
from __future__ import annotations

import click
from click.testing import CliRunner

from agent_toolkit_cli._group import AliasedGroup
from agent_toolkit_cli.cli import main


def test_aliased_group_collapses_same_command_object() -> None:
    """Subcommands registered with the exact same Command object collapse into a single row."""
    grp = AliasedGroup(name="demo")

    def dummy_cb() -> None:
        pass

    list_cmd = click.Command("list", callback=dummy_cb, help="List items from store.")
    grp.add_command(list_cmd, name="list")
    grp.add_command(list_cmd, name="ls")

    status_cmd = click.Command("status", callback=dummy_cb, help="Show current status.")
    grp.add_command(status_cmd, name="status")

    runner = CliRunner()
    result = runner.invoke(grp, ["--help"])
    assert result.exit_code == 0
    output = result.output

    # list, ls should appear on a single row
    assert "list, ls" in output
    assert "List items from store." in output
    assert "status" in output
    assert "Show current status." in output

    # There should NOT be a standalone "  ls  " row
    lines = [line.rstrip() for line in output.splitlines()]
    command_lines = [line.strip() for line in lines if "List items from store." in line]
    assert len(command_lines) == 1
    assert command_lines[0].startswith("list, ls")


def test_aliased_group_does_not_collapse_distinct_commands_sharing_callback() -> None:
    """Distinct Command objects sharing a callback function must NOT be collapsed."""
    grp = AliasedGroup(name="demo")

    def shared_cb() -> None:
        pass

    cmd1 = click.Command("alpha", callback=shared_cb, help="Alpha operation.")
    cmd2 = click.Command("beta", callback=shared_cb, help="Beta operation.")

    grp.add_command(cmd1, name="alpha")
    grp.add_command(cmd2, name="beta")

    runner = CliRunner()
    result = runner.invoke(grp, ["--help"])
    assert result.exit_code == 0
    output = result.output

    # Both commands must appear separately, never collapsed
    assert "alpha, beta" not in output
    assert "beta, alpha" not in output

    lines = [line.strip() for line in output.splitlines()]
    alpha_lines = [line for line in lines if "Alpha operation." in line]
    beta_lines = [line for line in lines if "Beta operation." in line]

    assert len(alpha_lines) == 1
    assert alpha_lines[0].startswith("alpha")
    assert len(beta_lines) == 1
    assert beta_lines[0].startswith("beta")


def test_aliased_group_canonical_name_ordering_and_deterministic_fallback() -> None:
    """Canonical name appears first if registered; otherwise falls back deterministically."""
    def dummy_cb() -> None:
        pass

    # Case 1: cmd.name is in registered names
    grp1 = AliasedGroup(name="demo1")
    cmd1 = click.Command("canonical", callback=dummy_cb, help="Canonical help.")
    grp1.add_command(cmd1, name="alias_b")
    grp1.add_command(cmd1, name="canonical")
    grp1.add_command(cmd1, name="alias_a")

    runner = CliRunner()
    res1 = runner.invoke(grp1, ["--help"])
    assert res1.exit_code == 0
    assert "canonical, alias_a, alias_b" in res1.output

    # Case 2: cmd.name is not in registered names -> deterministic first visible fallback
    grp2 = AliasedGroup(name="demo2")
    cmd2 = click.Command("unregistered_name", callback=dummy_cb, help="Unregistered help.")
    grp2.add_command(cmd2, name="zebra")
    grp2.add_command(cmd2, name="apple")

    res2 = runner.invoke(grp2, ["--help"])
    assert res2.exit_code == 0
    # In Click, list_commands is sorted alphabetically: apple is first visible name
    assert "apple, zebra" in res2.output


def test_aliased_group_hidden_commands() -> None:
    """Hidden commands and hidden aliases are excluded from help output."""
    grp = AliasedGroup(name="demo")

    def dummy_cb() -> None:
        pass

    visible_cmd = click.Command("visible", callback=dummy_cb, help="Visible command.")
    hidden_cmd = click.Command("secret", callback=dummy_cb, help="Secret command.", hidden=True)

    grp.add_command(visible_cmd, name="visible")
    grp.add_command(hidden_cmd, name="secret")
    grp.add_command(hidden_cmd, name="sc")

    runner = CliRunner()
    res = runner.invoke(grp, ["--help"])
    assert res.exit_code == 0
    assert "visible" in res.output
    assert "secret" not in res.output
    assert "sc" not in res.output


def test_aliased_group_narrow_width_formatting() -> None:
    """AliasedGroup formats cleanly under narrow terminal widths."""
    grp = AliasedGroup(name="demo")

    def dummy_cb() -> None:
        pass

    long_cmd = click.Command(
        "verylongcommandname",
        callback=dummy_cb,
        help="A very detailed and long help text that should wrap cleanly under narrow width constraints.",
    )
    grp.add_command(long_cmd, name="verylongcommandname")
    grp.add_command(long_cmd, name="vl")

    runner = CliRunner()
    res = runner.invoke(grp, ["--help"], max_content_width=40)
    assert res.exit_code == 0
    assert "verylongcommandname, vl" in res.output


def test_aliased_group_empty() -> None:
    """Empty AliasedGroup renders options without crashing or printing empty commands block."""
    grp = AliasedGroup(name="demo")
    runner = CliRunner()
    res = runner.invoke(grp, ["--help"])
    assert res.exit_code == 0
    assert "Commands:" not in res.output


def test_cli_help_pi_extension_collapses_list_and_ls() -> None:
    """pi-extension --help and pi-extensions --help collapse list and ls into a single row."""
    runner = CliRunner()
    for name in ("pi-extension", "pi-extensions"):
        res = runner.invoke(main, [name, "--help"])
        assert res.exit_code == 0
        assert "list, ls" in res.output
        lines = [line.strip() for line in res.output.splitlines()]
        ls_rows = [line for line in lines if line.startswith("ls ") or line == "ls"]
        assert ls_rows == [], f"Found standalone ls row in {name} --help"


def test_cli_help_skill_collapses_list_and_remove() -> None:
    """skill --help and skills --help collapse list, ls and remove, rm into single rows."""
    runner = CliRunner()
    for name in ("skill", "skills"):
        res = runner.invoke(main, [name, "--help"])
        assert res.exit_code == 0
        assert "list, ls" in res.output
        assert "remove, rm" in res.output
        lines = [line.strip() for line in res.output.splitlines()]
        ls_rows = [line for line in lines if line.startswith("ls ") or line == "ls"]
        rm_rows = [line for line in lines if line.startswith("rm ") or line == "rm"]
        assert ls_rows == [], f"Found standalone ls row in {name} --help"
        assert rm_rows == [], f"Found standalone rm row in {name} --help"


def test_cli_help_agent_mcp_command_collapse_list_and_ls() -> None:
    """agent, mcp, and command help menus collapse list and ls into a single row."""
    runner = CliRunner()
    for kind, plural in [("agent", "agents"), ("mcp", "mcps"), ("command", "commands")]:
        for name in (kind, plural):
            res = runner.invoke(main, [name, "--help"])
            assert res.exit_code == 0, f"Failed for {name} --help: {res.output}"
            assert "list, ls" in res.output, f"Missing 'list, ls' in {name} --help"
            lines = [line.strip() for line in res.output.splitlines()]
            ls_rows = [line for line in lines if line.startswith("ls ") or line == "ls"]
            assert ls_rows == [], f"Found standalone ls row in {name} --help"


def test_cli_help_unaliased_groups_remain_normal() -> None:
    """Groups without aliases (bundle, instructions) render normal Click help."""
    runner = CliRunner()
    res_b = runner.invoke(main, ["bundle", "--help"])
    assert res_b.exit_code == 0
    assert "install" in res_b.output
    assert "validate" in res_b.output

    res_i = runner.invoke(main, ["instructions", "--help"])
    assert res_i.exit_code == 0
    assert "install" in res_i.output
    assert "list" in res_i.output


def test_cli_top_level_help_unchanged() -> None:
    """Top-level agent-toolkit-cli --help lists canonical plural groups unchanged."""
    runner = CliRunner()
    res = runner.invoke(main, ["--help"])
    assert res.exit_code == 0
    assert "skills" in res.output
    assert "agents" in res.output
    assert "commands" in res.output
    assert "mcps" in res.output
    assert "pi-extensions" in res.output
    assert "bundles" in res.output
    assert "instructions" in res.output


def test_cli_individual_alias_help() -> None:
    """Individual alias help (e.g. pi-extension ls --help) exits 0 and displays help."""
    runner = CliRunner()
    res1 = runner.invoke(main, ["pi-extension", "ls", "--help"])
    assert res1.exit_code == 0
    assert "pi-extension ls [OPTIONS]" in res1.output

    res2 = runner.invoke(main, ["skill", "rm", "--help"])
    assert res2.exit_code == 0
    assert "skill rm [OPTIONS]" in res2.output
