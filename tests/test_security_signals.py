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


def test_cache_round_trip(tmp_path):
    from agent_toolkit.security.cache import load_cache, save_cache
    save_cache(tmp_path, "owner", "repo", {"stars": 42})
    loaded = load_cache(tmp_path, "owner", "repo", ttl_seconds=3600)
    assert loaded == {"stars": 42}


def test_cache_expires_past_ttl(tmp_path):
    import os, time
    from agent_toolkit.security.cache import load_cache, save_cache
    save_cache(tmp_path, "owner", "repo", {"stars": 42})
    cache_file = tmp_path / ".agent-toolkit" / "cache" / "security" / "owner" / "repo.json"
    # Backdate the file by 2 days
    old = time.time() - (60 * 60 * 48)
    os.utime(cache_file, (old, old))
    loaded = load_cache(tmp_path, "owner", "repo", ttl_seconds=3600)
    assert loaded is None


def test_identity_renders_from_canned_signals():
    from agent_toolkit.security.identity import render_from_signals
    signals = {
        "stars": 2400, "forks": 87, "open_issues": 12,
        "contributors": 18, "age_days": 700, "last_commit_days_ago": 6,
    }
    result = render_from_signals(signals)
    assert result.verdict == Verdict.GREEN
    assert "2400" in result.evidence or "2.4k" in result.evidence


def test_identity_amber_when_stale():
    from agent_toolkit.security.identity import render_from_signals
    signals = {
        "stars": 12000, "forks": 1000, "open_issues": 200,
        "contributors": 100, "age_days": 2000, "last_commit_days_ago": 1500,
    }
    result = render_from_signals(signals)
    assert result.verdict in (Verdict.AMBER, Verdict.RED)


def test_credibility_renders_from_canned_signals():
    from agent_toolkit.security.credibility import render_from_signals
    signals = {"owner_login": "x", "owner_type": "User", "public_repos": 12, "owner_age_days": 1500}
    result = render_from_signals(signals)
    assert result.verdict in (Verdict.GREEN, Verdict.AMBER)


def test_community_renders_from_canned_signals():
    from agent_toolkit.security.community import render_from_signals
    signals = {"open_security_issues": 0, "advisory_count": 0}
    result = render_from_signals(signals)
    assert result.verdict == Verdict.GREEN

    bad = {"open_security_issues": 3, "advisory_count": 1}
    result = render_from_signals(bad)
    assert result.verdict == Verdict.RED
