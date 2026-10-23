"""Tests for pi-extension doctor unmanaged package discovery and safe confirmed repair."""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from agent_toolkit_cli.pi_extension_lock import read_lock
from agent_toolkit_cli.pi_extension_paths import lock_file_path


def _setup_env(monkeypatch, tmp_path: Path):
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    pi_agent_dir = fake_home / ".pi" / "agent"
    pi_agent_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
    return fake_home, pi_agent_dir


def test_pi_doctor_discovers_unmanaged_local_package_report_only(tmp_path: Path, monkeypatch):
    """Doctor without --repair reports unmanaged local package but does not prompt or mutate."""
    fake_home, pi_agent_dir = _setup_env(monkeypatch, tmp_path)
    pkg_dir = tmp_path / "local-pkg"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "package.json").write_text(json.dumps({"name": "my-local-pkg", "version": "1.0.0"}))

    settings_file = pi_agent_dir / "settings.json"
    settings_content = json.dumps({"packages": [str(pkg_dir)], "extensions": []}, indent=2) + "\n"
    settings_file.write_text(settings_content)

    runner = CliRunner()
    r = runner.invoke(main, ["pi-extension", "doctor", "-g"])
    assert r.exit_code != 0
    assert "my-local-pkg" in r.output
    assert "unmanaged" in r.output

    # Settings and lock must not be changed
    assert settings_file.read_text() == settings_content
    lock = read_lock(lock_file_path(scope="global", home=fake_home))
    assert "my-local-pkg" not in lock.skills


def test_pi_doctor_no_fix_overrides_repair(tmp_path: Path, monkeypatch):
    """--no-fix keeps doctor in report-only mode even when --repair is passed."""
    fake_home, pi_agent_dir = _setup_env(monkeypatch, tmp_path)
    pkg_dir = tmp_path / "local-pkg"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "package.json").write_text(json.dumps({"name": "my-local-pkg", "version": "1.0.0"}))

    settings_file = pi_agent_dir / "settings.json"
    settings_content = json.dumps({"packages": [str(pkg_dir)], "extensions": []}, indent=2) + "\n"
    settings_file.write_text(settings_content)

    runner = CliRunner()
    r = runner.invoke(main, ["pi-extension", "doctor", "-g", "--repair", "--no-fix"])
    assert r.exit_code != 0
    assert "my-local-pkg" in r.output

    assert settings_file.read_text() == settings_content
    lock = read_lock(lock_file_path(scope="global", home=fake_home))
    assert "my-local-pkg" not in lock.skills


def test_pi_doctor_repair_declined_leaves_settings_and_lock_untouched(tmp_path: Path, monkeypatch):
    """When user declines confirmation, nothing is modified."""
    fake_home, pi_agent_dir = _setup_env(monkeypatch, tmp_path)
    pkg_dir = tmp_path / "local-pkg"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "package.json").write_text(json.dumps({"name": "my-local-pkg", "version": "1.0.0"}))

    settings_file = pi_agent_dir / "settings.json"
    settings_content = json.dumps({"packages": [str(pkg_dir)], "extensions": []}, indent=2) + "\n"
    settings_file.write_text(settings_content)

    runner = CliRunner()
    r = runner.invoke(main, ["pi-extension", "doctor", "-g", "--repair"], input="N\n")
    assert r.exit_code != 0
    assert "my-local-pkg" in r.output

    assert settings_file.read_text() == settings_content
    lock = read_lock(lock_file_path(scope="global", home=fake_home))
    assert "my-local-pkg" not in lock.skills


def test_pi_doctor_repair_never_imports_local_package(tmp_path: Path, monkeypatch):
    fake_home, pi_agent_dir = _setup_env(monkeypatch, tmp_path)
    pkg_dir = tmp_path / "local-pkg"
    pkg_dir.mkdir()
    manifest = '{"name": "my-local-pkg", "version": "1.0.0"}'
    (pkg_dir / "package.json").write_text(manifest)
    settings = pi_agent_dir / "settings.json"
    content = json.dumps({"packages": [str(pkg_dir)], "extensions": []}) + "\n"
    settings.write_text(content)

    result = CliRunner().invoke(main, ["pi-extension", "doctor", "-g", "--repair"], input="y\n")
    assert result.exit_code != 0, result.output
    assert "my-local-pkg" in result.output
    assert "Import unmanaged" not in result.output
    assert settings.read_text() == content
    assert "my-local-pkg" not in read_lock(lock_file_path(scope="global", home=fake_home)).skills
    assert (pkg_dir / "package.json").read_text() == manifest


def test_local_package_findings_have_no_repair_in_either_scope(tmp_path, monkeypatch):
    from agent_toolkit_cli.pi_extension_doctor import diagnose

    home, pi_dir = _setup_env(monkeypatch, tmp_path)
    project = tmp_path / "project"
    package = tmp_path / "local-package"
    package.mkdir()
    (package / "package.json").write_text('{"name": "local-package"}')
    for scope, settings in (("global", pi_dir / "settings.json"),
                            ("project", project / ".pi/settings.json")):
        settings.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps({"packages": [{"source": str(package), "extensions": ["index.ts"]}]})
        settings.write_text(content)
        findings = diagnose(slugs=("local-package",), scope=scope, home=home,
                            project=project if scope == "project" else None, repair=True)
        local = [f for f in findings if f.finding_type == "unmanaged"]
        assert len(local) == 1
        assert local[0].path == package
        assert local[0].fix_action is None
        assert settings.read_text() == content
