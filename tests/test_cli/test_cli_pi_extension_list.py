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
    assert rows["@scope/proj-only"]["projectLoaded"] is False
    assert rows["@scope/proj-only"]["npmProject"]["status"] == "Missing"
    assert rows["@scope/proj-only"]["globalLoaded"] is False


def test_list_and_status_render_user_facing_origin_labels(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    lock = tmp_path / ".agent-toolkit" / "pi-extensions-lock.json"
    lock.parent.mkdir(parents=True)
    lock.write_text(_json.dumps({
        "version": 1,
        "skills": {
            "status-bar": {
                "source": "github.com/o/status-bar",
                "sourceType": "github",
                "piExtensionPath": "status-bar",
            },
            "managed-pkg": {"source": "npm:managed-pkg", "sourceType": "npm"},
        },
    }) + "\n")
    settings = tmp_path / ".pi" / "agent" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(_json.dumps({"packages": ["npm:managed-pkg", "npm:unmanaged-pkg"]}))

    table = CliRunner().invoke(main, ["pi-extension", "list", "-g"], catch_exceptions=False)
    assert table.exit_code == 0
    assert "library" in table.output
    assert "managed-pkg" in table.output and "unmanaged-pkg" in table.output
    assert "npm managed" not in table.output and "npm unmanaged" not in table.output
    assert "store-owned" not in table.output

    status = CliRunner().invoke(main, ["pi-extension", "status", "-g"], catch_exceptions=False)
    assert status.exit_code == 0
    assert "library" in status.output
    assert "managed-pkg" in status.output and "unmanaged-pkg" in status.output
    assert "npm managed" not in status.output and "npm unmanaged" not in status.output
    assert "store-owned" not in status.output


def test_list_json_includes_npm_managed_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    settings = tmp_path / ".pi" / "agent" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text('{"packages": ["npm:pi-title-renamer"]}')

    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(
        main, ["pi-extension", "list", "--json"], catch_exceptions=False
    )
    assert result.exit_code == 0
    # Strip any potential banner
    out = result.output
    if "Operating on project scope" in out:
        out = out.split("\n", 1)[1]
    rows = _json.loads(out)
    row = next(r for r in rows if r["slug"] == "pi-title-renamer")
    assert row["origin"] == "npm"
    assert row["displayOrigin"] == "npm"
    assert row["managed"] is False
    assert row["globalConfigPath"].endswith(".pi/agent/settings.json")
    assert row["globalPackageSpec"] == "npm:pi-title-renamer"


def test_list_json_includes_local_package_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    package = tmp_path / ".pi" / "local-pkg"
    package.mkdir(parents=True)
    (package / "package.json").write_text('{"name": "my-local-tool"}')
    settings = tmp_path / ".pi" / "agent" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text('{"packages": ["../local-pkg"]}')

    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(
        main, ["pi-extension", "list", "--json"], catch_exceptions=False
    )
    assert result.exit_code == 0
    out = result.output
    if "Operating on project scope" in out:
        out = out.split("\n", 1)[1]
    rows = _json.loads(out)
    row = next(r for r in rows if r["slug"] == "../local-pkg")
    assert row["origin"] == "local-package"
    assert row["displayOrigin"] == "local-package untracked"
    assert row["managed"] is False
    assert row["globalConfigPath"].endswith(".pi/agent/settings.json")
    assert row["globalPackageSpec"] == "../local-pkg"
    assert row["globalPackageMetadata"] == {"name": "my-local-tool"}

    status = CliRunner().invoke(main, ["pi-extension", "status", "-g"], catch_exceptions=False)
    assert status.exit_code == 0
    assert "local-package untracked" in status.output
