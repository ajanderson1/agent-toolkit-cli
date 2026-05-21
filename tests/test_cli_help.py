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


def test_root_help_does_not_call_doctor_removed():
    """v2.3.0 help string listed 'doctor' as removed; v2.3.x reintroduces it.

    Guard against the stale claim by asserting doctor is not in the removed
    list. (skill doctor itself is registered via `skill.add_command`.)"""
    r = CliRunner().invoke(main, ["--help"])
    assert r.exit_code == 0
    # The "Pre-v2 commands ... were removed" sentence must not mention doctor.
    removed_line = next(
        (line for line in r.output.splitlines() if "were removed" in line),
        "",
    )
    assert "doctor" not in removed_line, removed_line
