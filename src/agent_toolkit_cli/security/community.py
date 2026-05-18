"""Security review — category 5: community signals."""
from __future__ import annotations

import json
import subprocess

from agent_toolkit_cli.security.types import CategoryResult, Verdict


def collect_signals(owner: str, repo: str) -> dict:
    issues = subprocess.run(
        ["gh", "api", f"repos/{owner}/{repo}/issues",
         "-X", "GET", "-f", "labels=security"],
        check=False, capture_output=True, text=True,
    )
    open_count = 0
    if issues.returncode == 0:
        data = json.loads(issues.stdout) if issues.stdout.strip().startswith("[") else []
        open_count = len([i for i in data if i.get("state") == "open"])

    advisories = subprocess.run(
        ["gh", "api", f"repos/{owner}/{repo}/security-advisories"],
        check=False, capture_output=True, text=True,
    )
    advisory_count = 0
    if advisories.returncode == 0 and advisories.stdout.strip().startswith("["):
        advisory_count = len(json.loads(advisories.stdout))

    return {
        "open_security_issues": open_count,
        "advisory_count": advisory_count,
    }


def render_from_signals(s: dict) -> CategoryResult:
    issues = s.get("open_security_issues", 0)
    advisories = s.get("advisory_count", 0)
    if advisories > 0 or issues > 2:
        verdict = Verdict.RED
        evidence = f"{advisories} CVE advisor(y/ies), {issues} open security-labelled issues."
    elif issues > 0:
        verdict = Verdict.AMBER
        evidence = f"{issues} open security-labelled issue(s); review before ingesting."
    else:
        verdict = Verdict.GREEN
        evidence = "No open security issues, no advisories."
    return CategoryResult(
        category="5. Community signals",
        verdict=verdict,
        evidence=evidence,
        raw_signals=s,
    )
