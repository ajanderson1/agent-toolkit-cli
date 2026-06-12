from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def _write_manifest(tmp_path: Path, members: list[dict]) -> Path:
    p = tmp_path / "demo.bundle.json"
    p.write_text(json.dumps({
        "schema_version": 1, "name": "demo", "description": "d",
        "members": members,
    }))
    return p


def test_bundle_help_lists_verbs():
    res = CliRunner().invoke(main, ["bundle", "--help"])
    assert res.exit_code == 0
    assert "install" in res.output
    assert "validate" in res.output


def test_install_and_validate_help_exit_zero():
    for verb in ("install", "validate"):
        res = CliRunner().invoke(main, ["bundle", verb, "--help"])
        assert res.exit_code == 0


def test_validate_rejects_mcp_member_with_329(tmp_path):
    p = _write_manifest(tmp_path, [
        {"asset_type": "mcp", "source": "o/r/ctx7", "slug": "context7"},
    ])
    res = CliRunner().invoke(main, ["bundle", "validate", str(p)])
    assert res.exit_code != 0
    assert "#329" in res.output


def test_validate_rejects_instructions_member(tmp_path):
    p = _write_manifest(tmp_path, [{"asset_type": "instructions"}])
    res = CliRunner().invoke(main, ["bundle", "validate", str(p)])
    assert res.exit_code != 0
    assert "not a bundle member type" in res.output


def test_install_missing_manifest_errors(tmp_path):
    res = CliRunner().invoke(
        main, ["bundle", "install", str(tmp_path / "nope.json")]
    )
    assert res.exit_code != 0
    assert "not found" in res.output


def test_install_mcp_member_hard_fails(tmp_path):
    p = _write_manifest(tmp_path, [
        {"asset_type": "mcp", "source": "o/r/ctx7", "slug": "context7"},
    ])
    res = CliRunner().invoke(main, ["bundle", "install", str(p)])
    assert res.exit_code != 0
    assert "#329" in res.output


def test_install_threads_project_root_to_run(tmp_path, monkeypatch):
    import agent_toolkit_cli.commands.bundle.install_cmd as install_cmd_mod

    captured = {}

    def fake_run(manifest, scope, dry_run, project_root=None):
        captured["scope"] = scope
        captured["project_root"] = project_root
        from agent_toolkit_cli.bundle_install import ValidateReport
        return ValidateReport(ok=True)

    monkeypatch.setattr(install_cmd_mod.bundle_install, "run", fake_run)
    p = _write_manifest(tmp_path, [{"asset_type": "skill", "source": "o/r/gw"}])
    res = CliRunner().invoke(
        main, ["bundle", "install", "--project", str(p)], catch_exceptions=False
    )
    assert res.exit_code == 0, res.output
    assert captured["scope"] == "project"
    assert captured["project_root"] is not None


def test_no_flag_scope_uses_default_scope(tmp_path, monkeypatch):
    import agent_toolkit_cli.commands.bundle.install_cmd as install_cmd_mod

    monkeypatch.setattr(install_cmd_mod, "default_scope", lambda cwd: "global")
    captured = {}

    def fake_run(manifest, scope, dry_run, project_root=None):
        captured["scope"] = scope
        from agent_toolkit_cli.bundle_install import ValidateReport
        return ValidateReport(ok=True)

    monkeypatch.setattr(install_cmd_mod.bundle_install, "run", fake_run)
    p = _write_manifest(tmp_path, [{"asset_type": "skill", "source": "o/r/gw"}])
    res = CliRunner().invoke(main, ["bundle", "install", str(p)],
                            catch_exceptions=False)
    assert res.exit_code == 0, res.output
    assert captured["scope"] == "global"
