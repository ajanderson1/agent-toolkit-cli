import json
from pathlib import Path

import yaml
from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def _setup_pi_home(
    home: Path,
    ext_slugs: list[str],
    packages: list[str],
    node_modules: list[str],
) -> None:
    (home / ".pi/agent/extensions").mkdir(parents=True, exist_ok=True)
    for s in ext_slugs:
        (home / ".pi/agent/extensions" / s).mkdir()
    (home / ".pi/agent").mkdir(parents=True, exist_ok=True)
    (home / ".pi/agent/settings.json").write_text(
        json.dumps({"packages": packages})
    )
    (home / ".pi/agent/npm/node_modules").mkdir(parents=True, exist_ok=True)
    for pkg in node_modules:
        (home / ".pi/agent/npm/node_modules" / pkg).mkdir()


def test_pi_inventory_json_format(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    _setup_pi_home(
        home,
        ext_slugs=["status-bar"],
        packages=["npm:pi-subagents"],
        node_modules=["pi-subagents"],
    )
    monkeypatch.setenv("HOME", str(home))

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--project", str(project), "pi", "inventory", "--format", "json"],
    )
    assert result.exit_code == 0, result.output

    records = json.loads(result.output)
    slugs = {r["slug"] for r in records}
    assert slugs == {"status-bar", "pi-subagents"}

    sb = next(r for r in records if r["slug"] == "status-bar")
    assert sb["origin"] == "first-party"
    assert sb["user_loaded"] is True

    ps = next(r for r in records if r["slug"] == "pi-subagents")
    assert ps["origin"] == "third-party"
    assert ps["user_loaded"] is True


def test_pi_inventory_text_format(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    _setup_pi_home(home, ext_slugs=["status-bar"], packages=[], node_modules=[])
    monkeypatch.setenv("HOME", str(home))

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--project", str(project), "pi", "inventory"],  # default --format text
    )
    assert result.exit_code == 0
    assert "status-bar" in result.output
    assert "first-party" in result.output


def test_pi_inventory_scope_filter(tmp_path: Path, monkeypatch):
    """`--scope user` hides project-only records; `--scope project` shows them."""
    home = tmp_path / "home"
    project = tmp_path / "proj"
    home.mkdir()
    project.mkdir()

    # Project-only third-party: settings.json + node_modules + allowlist.
    (project / ".pi").mkdir()
    (project / ".pi/settings.json").write_text(
        json.dumps({"packages": ["npm:project-only"]})
    )
    (project / ".pi/npm/node_modules/project-only").mkdir(parents=True)
    (project / ".agent-toolkit.yaml").write_text(
        "pi_packages:\n  - npm:project-only\n"
    )

    monkeypatch.setenv("HOME", str(home))
    runner = CliRunner()

    # user scope — nothing should match
    result = runner.invoke(
        main,
        [
            "--project",
            str(project),
            "pi",
            "inventory",
            "--scope",
            "user",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == []

    # project scope — record appears
    result = runner.invoke(
        main,
        [
            "--project",
            str(project),
            "pi",
            "inventory",
            "--scope",
            "project",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0, result.output
    records = json.loads(result.output)
    assert len(records) == 1
    assert records[0]["slug"] == "project-only"
    assert records[0]["toolkit_intent"] == "project"
    assert records[0]["project_loaded"] is True


def test_pi_inventory_malformed_settings_json(tmp_path: Path, monkeypatch):
    """Corrupt settings.json should surface a loud error mentioning the file."""
    home = tmp_path / "home"
    project = tmp_path / "proj"
    (home / ".pi/agent").mkdir(parents=True)
    (home / ".pi/agent/settings.json").write_text("{ not json")
    project.mkdir()
    monkeypatch.setenv("HOME", str(home))

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--project", str(project), "pi", "inventory", "--format", "json"],
    )
    assert result.exit_code != 0
    combined = (result.output or "") + (
        str(result.exception) if result.exception else ""
    )
    assert "settings.json" in combined


def test_pi_inventory_empty(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    home.mkdir()
    project.mkdir()
    monkeypatch.setenv("HOME", str(home))

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--project", str(project), "pi", "inventory", "--format", "json"],
    )
    assert result.exit_code == 0
    assert json.loads(result.output) == []


def test_pi_sync_adds_missing_package(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    (home / ".pi/agent").mkdir(parents=True)
    (home / ".pi/agent/settings.json").write_text(json.dumps({"packages": []}))

    allow = home / ".agent-toolkit.yaml"
    allow.write_text(yaml.safe_dump({"pi_packages": ["npm:pi-subagents"]}))

    monkeypatch.setenv("HOME", str(home))

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--project", str(project), "pi", "sync", "--scope", "user"],
    )
    assert result.exit_code == 0, result.output

    settings = json.loads((home / ".pi/agent/settings.json").read_text())
    assert settings["packages"] == ["npm:pi-subagents"]


def test_pi_sync_removes_orphan_package(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    (home / ".pi/agent").mkdir(parents=True)
    (home / ".pi/agent/settings.json").write_text(
        json.dumps({"packages": ["npm:pi-orphan"]})
    )
    allow = home / ".agent-toolkit.yaml"
    allow.write_text(yaml.safe_dump({"pi_packages": []}))

    monkeypatch.setenv("HOME", str(home))
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--project", str(project), "pi", "sync", "--scope", "user"],
    )
    assert result.exit_code == 0, result.output
    settings = json.loads((home / ".pi/agent/settings.json").read_text())
    assert settings["packages"] == []


def test_pi_sync_idempotent(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    (home / ".pi/agent").mkdir(parents=True)
    (home / ".pi/agent/settings.json").write_text(
        json.dumps({"packages": ["npm:pi-subagents"]})
    )
    allow = home / ".agent-toolkit.yaml"
    allow.write_text(yaml.safe_dump({"pi_packages": ["npm:pi-subagents"]}))

    monkeypatch.setenv("HOME", str(home))
    runner = CliRunner()
    before = (home / ".pi/agent/settings.json").read_text()
    r1 = runner.invoke(
        main, ["--project", str(project), "pi", "sync", "--scope", "user"]
    )
    assert r1.exit_code == 0
    after_first = (home / ".pi/agent/settings.json").read_text()
    r2 = runner.invoke(
        main, ["--project", str(project), "pi", "sync", "--scope", "user"]
    )
    assert r2.exit_code == 0
    after_second = (home / ".pi/agent/settings.json").read_text()
    assert before == after_first == after_second
