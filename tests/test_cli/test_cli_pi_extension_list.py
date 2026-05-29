import json as _json
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def test_group_registered():
    result = CliRunner().invoke(main, ["pi-extension", "--help"])
    assert result.exit_code == 0
    assert "list" in result.output
    assert "status" in result.output


def _seed_npm(home: Path):
    s = home / ".pi" / "agent" / "settings.json"
    s.parent.mkdir(parents=True, exist_ok=True)
    s.write_text(_json.dumps({"packages": ["npm:@scope/rpiv-i18n"]}))


def test_list_global_json(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_npm(tmp_path)
    result = CliRunner().invoke(main, ["pi-extension", "list", "-g", "--json"])
    assert result.exit_code == 0
    payload = _json.loads(result.output)
    rows = {r["slug"]: r for r in payload}
    assert rows["@scope/rpiv-i18n"]["origin"] == "npm"


def test_list_global_table(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_npm(tmp_path)
    result = CliRunner().invoke(main, ["pi-extension", "list", "-g"])
    assert result.exit_code == 0
    assert "@scope/rpiv-i18n" in result.output
    assert "npm" in result.output


def test_status_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    result = CliRunner().invoke(main, ["pi-extension", "status", "-g"])
    assert result.exit_code == 0


def test_status_lists_origin(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_npm(tmp_path)
    result = CliRunner().invoke(main, ["pi-extension", "status", "-g"])
    assert result.exit_code == 0
    assert "@scope/rpiv-i18n" in result.output
    assert "npm" in result.output


def _seed_project_npm(project: Path):
    s = project / ".pi" / "settings.json"
    s.parent.mkdir(parents=True, exist_ok=True)
    s.write_text(_json.dumps({"packages": ["npm:@scope/proj-only"]}))


def test_list_project_json(tmp_path, monkeypatch):
    # Separate HOME (so no global rows leak in) makes the project row
    # unambiguous; -p selects project scope, cwd is the project root.
    home = tmp_path / "home"
    project = tmp_path / "proj"
    home.mkdir()
    project.mkdir()
    monkeypatch.setenv("HOME", str(home))
    _seed_project_npm(project)
    monkeypatch.chdir(project)
    result = CliRunner().invoke(main, ["pi-extension", "list", "-p", "--json"])
    assert result.exit_code == 0
    rows = {r["slug"]: r for r in _json.loads(result.output)}
    assert rows["@scope/proj-only"]["origin"] == "npm"
    assert rows["@scope/proj-only"]["projectLoaded"] is True
    assert rows["@scope/proj-only"]["globalLoaded"] is False
