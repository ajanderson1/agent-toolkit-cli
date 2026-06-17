from click.testing import CliRunner
from agent_toolkit_cli.cli import main


def test_command_maintenance_verbs_are_invoked(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    runner = CliRunner()
    import_file = tmp_path / "commands-lock.json"
    import_file.write_text('{"version": 1, "skills": {}}')
    for args in [
        ["command", "list", "-g"],
        ["command", "ls", "-g"],
        ["command", "status", "-g"],
        ["command", "import", str(import_file), "-g"],
        ["command", "doctor", "-g"],
        ["command", "push", "-g"],
        ["command", "reset", "demo", "--force", "-g"],
        ["command", "remove", "demo", "-g"],
        ["command", "uninstall", "demo", "-g"],
        ["command", "update", "-g"],
    ]:
        result = runner.invoke(main, args)
        assert result.exit_code == 0, (args, result.output)
