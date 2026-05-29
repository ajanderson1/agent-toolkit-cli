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
