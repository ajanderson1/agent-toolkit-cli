"""Tests for doctor's Pi advisories (commit 5 of #103).

Three read-only advisories:
1. Hand-authored extension under ~/.pi/agent/extensions/<slug>/
2. Drift between `pi_packages:` and resolved settings.json / node_modules
3. Slug collision between `pi_extensions:` and `pi_packages:`
"""
from __future__ import annotations

import json

from agent_toolkit_cli.doctor.pi_advisories import audit_pi


def test_hand_authored_extension_warns(tmp_path):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    # A real dir under extensions/ that is NOT a symlink.
    (home / ".pi/agent/extensions/handmade").mkdir(parents=True)

    results = audit_pi(home=home, project_root=project)

    assert any(
        "handmade" in r.message and "hand-authored" in r.message.lower() for r in results
    )


def test_drift_warns_when_pi_packages_declares_missing_resolution(tmp_path):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    home.mkdir()
    (home / ".agent-toolkit.yaml").write_text("pi_packages:\n  - npm:phantom\n")
    (home / ".pi/agent").mkdir(parents=True)
    (home / ".pi/agent/settings.json").write_text(json.dumps({"packages": []}))

    results = audit_pi(home=home, project_root=project)

    assert any("phantom" in r.message and "drift" in r.message.lower() for r in results)


def test_slug_collision_warns(tmp_path):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    home.mkdir()
    (home / ".agent-toolkit.yaml").write_text(
        "pi_extensions: [foo]\npi_packages: [npm:foo]\n"
    )

    results = audit_pi(home=home, project_root=project)

    assert any("foo" in r.message and "collision" in r.message.lower() for r in results)


def test_clean_repo_yields_no_warnings(tmp_path):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    home.mkdir()
    project.mkdir()

    results = audit_pi(home=home, project_root=project)
    assert results == []
