"""Top-level CLI help should advertise only the `skill` command (post-#160)."""
from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def test_top_level_help_lists_only_skill():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "skill" in result.output
    removed_commands = (
        "check", "diff", "doctor", "fix", "ingest", "inventory",
        "link", "list", "migrate-skills", "new", "pi", "unlink",
    )
    for cmd in removed_commands:
        for line in result.output.splitlines():
            tokens = line.strip().split()
            assert cmd not in tokens, (
                f"Removed command {cmd!r} still appears in --help output: {line!r}"
            )


def test_top_level_help_describes_skill_purpose():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "skill" in result.output.lower()
