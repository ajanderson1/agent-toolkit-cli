"""Tests for deterministic security signal helpers."""
from agent_toolkit.security.types import Verdict


def test_license_mit_is_green(tmp_path):
    from agent_toolkit.security.license import scan_license
    (tmp_path / "LICENSE").write_text("MIT License\n\nPermission is hereby granted, free of charge…")
    result = scan_license(tmp_path)
    assert result.verdict == Verdict.GREEN
    assert "MIT" in result.evidence


def test_license_missing_is_red(tmp_path):
    from agent_toolkit.security.license import scan_license
    result = scan_license(tmp_path)
    assert result.verdict == Verdict.RED
    assert "no LICENSE" in result.evidence.lower() or "missing" in result.evidence.lower()


def test_license_proprietary_is_amber(tmp_path):
    from agent_toolkit.security.license import scan_license
    (tmp_path / "LICENSE").write_text("All rights reserved. Proprietary software.")
    result = scan_license(tmp_path)
    assert result.verdict == Verdict.AMBER


def test_license_apache_is_green(tmp_path):
    from agent_toolkit.security.license import scan_license
    (tmp_path / "LICENSE").write_text("Apache License\nVersion 2.0, January 2004")
    result = scan_license(tmp_path)
    assert result.verdict == Verdict.GREEN
