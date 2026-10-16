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


def test_pi_doctor_repair_confirmed_imports_package_losslessly(tmp_path: Path, monkeypatch):
    """When user confirms repair, local package is recorded in lock, settings.json NOT mutated."""
    fake_home, pi_agent_dir = _setup_env(monkeypatch, tmp_path)
    pkg_dir = tmp_path / "local-pkg"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "package.json").write_text(json.dumps({"name": "my-local-pkg", "version": "1.0.0"}))

    settings_file = pi_agent_dir / "settings.json"
    settings_content = json.dumps({"packages": [str(pkg_dir)], "extensions": []}, indent=2) + "\n"
    settings_file.write_text(settings_content)

    runner = CliRunner()
    r = runner.invoke(main, ["pi-extension", "doctor", "-g", "--repair"], input="y\n")
    assert r.exit_code == 0, r.output
    assert "fixed" in r.output

    # settings.json MUST be byte-for-byte identical — NEVER mutated!
    assert settings_file.read_text() == settings_content

    # Lockfile has the local package entry
    lock = read_lock(lock_file_path(scope="global", home=fake_home))
    assert "my-local-pkg" in lock.skills
    entry = lock.skills["my-local-pkg"]
    assert entry.source_type == "local"

    # Repeat run of doctor: now all clean
    r2 = runner.invoke(main, ["pi-extension", "doctor", "-g"])
    assert r2.exit_code == 0, r2.output
    assert "clean" in r2.output.lower()
