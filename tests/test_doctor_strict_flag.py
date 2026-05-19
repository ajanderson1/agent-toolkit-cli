"""Tests for `agent-toolkit doctor --strict` flag (issue #124).

Contract:
- `--exit-code`: exit 1 on FAIL only (preserves historical contract).
- `--strict`:    exit 1 on WARN or FAIL. Implies `--exit-code`.
"""
from __future__ import annotations

from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from agent_toolkit_cli.commands import doctor as doctor_mod
from agent_toolkit_cli.doctor.result import GroupResult, Status


def _fake_results(status: Status) -> list[GroupResult]:
    return [GroupResult(name="environment", status=status, summary="fake")]


def _patch_run_global(monkeypatch, status: Status) -> None:
    monkeypatch.setattr(
        doctor_mod,
        "_run_global",
        lambda *a, **kw: _fake_results(status),
    )


def test_no_flag_ok_exit_zero(monkeypatch, tmp_path):
    _patch_run_global(monkeypatch, Status.OK)
    result = CliRunner().invoke(main, ["doctor", "--toolkit-repo", str(tmp_path)])
    assert result.exit_code == 0, result.output


def test_exit_code_warn_returns_zero(monkeypatch, tmp_path):
    """Historical contract: --exit-code does NOT trip on WARN."""
    _patch_run_global(monkeypatch, Status.WARN)
    result = CliRunner().invoke(
        main, ["doctor", "--toolkit-repo", str(tmp_path), "--exit-code"]
    )
    assert result.exit_code == 0, result.output


def test_exit_code_fail_returns_one(monkeypatch, tmp_path):
    _patch_run_global(monkeypatch, Status.FAIL)
    result = CliRunner().invoke(
        main, ["doctor", "--toolkit-repo", str(tmp_path), "--exit-code"]
    )
    assert result.exit_code == 1, result.output


def test_strict_ok_returns_zero(monkeypatch, tmp_path):
    _patch_run_global(monkeypatch, Status.OK)
    result = CliRunner().invoke(
        main, ["doctor", "--toolkit-repo", str(tmp_path), "--strict"]
    )
    assert result.exit_code == 0, result.output


def test_strict_warn_returns_one(monkeypatch, tmp_path):
    """New contract: --strict trips on WARN."""
    _patch_run_global(monkeypatch, Status.WARN)
    result = CliRunner().invoke(
        main, ["doctor", "--toolkit-repo", str(tmp_path), "--strict"]
    )
    assert result.exit_code == 1, result.output


def test_strict_fail_returns_one(monkeypatch, tmp_path):
    _patch_run_global(monkeypatch, Status.FAIL)
    result = CliRunner().invoke(
        main, ["doctor", "--toolkit-repo", str(tmp_path), "--strict"]
    )
    assert result.exit_code == 1, result.output


def test_strict_implies_exit_code(monkeypatch, tmp_path):
    """Passing --strict alone should be sufficient (implies --exit-code)."""
    _patch_run_global(monkeypatch, Status.WARN)
    result = CliRunner().invoke(
        main, ["doctor", "--toolkit-repo", str(tmp_path), "--strict"]
    )
    assert result.exit_code == 1, result.output


def test_both_flags_strict_dominates(monkeypatch, tmp_path):
    _patch_run_global(monkeypatch, Status.WARN)
    result = CliRunner().invoke(
        main,
        ["doctor", "--toolkit-repo", str(tmp_path), "--exit-code", "--strict"],
    )
    assert result.exit_code == 1, result.output


def test_advisory_does_not_trip_strict(monkeypatch, tmp_path):
    _patch_run_global(monkeypatch, Status.ADVISORY)
    result = CliRunner().invoke(
        main, ["doctor", "--toolkit-repo", str(tmp_path), "--strict"]
    )
    assert result.exit_code == 0, result.output


def test_per_resource_strict_trips_on_warn(monkeypatch, tmp_path):
    """Per-resource diagnosis honours --strict."""
    fake = GroupResult(name="ghost", status=Status.WARN, summary="warn-state")
    monkeypatch.setattr(doctor_mod, "diagnose", lambda root, slug, deep: fake)
    result = CliRunner().invoke(
        main,
        ["doctor", "ghost", "--toolkit-repo", str(tmp_path), "--strict"],
    )
    assert result.exit_code == 1, result.output


def test_per_resource_exit_code_only_does_not_trip_on_warn(monkeypatch, tmp_path):
    fake = GroupResult(name="ghost", status=Status.WARN, summary="warn-state")
    monkeypatch.setattr(doctor_mod, "diagnose", lambda root, slug, deep: fake)
    result = CliRunner().invoke(
        main,
        ["doctor", "ghost", "--toolkit-repo", str(tmp_path), "--exit-code"],
    )
    assert result.exit_code == 0, result.output


def test_help_documents_both_flags():
    result = CliRunner().invoke(main, ["doctor", "--help"])
    assert result.exit_code == 0
    assert "--strict" in result.output
    assert "--exit-code" in result.output
    assert "WARN or FAIL" in result.output
