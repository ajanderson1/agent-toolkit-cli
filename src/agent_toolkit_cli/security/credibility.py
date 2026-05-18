"""Security review — category 2: author/org credibility."""
from __future__ import annotations

import json
import subprocess

from agent_toolkit_cli.security.types import CategoryResult, Verdict


def collect_signals(owner: str) -> dict:
    import datetime as _dt
    out = subprocess.run(
        ["gh", "api", f"users/{owner}"],
        check=True, capture_output=True, text=True,
    )
    data = json.loads(out.stdout)
    created_at = _dt.datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
    age_days = (_dt.datetime.now(tz=_dt.timezone.utc) - created_at).days
    return {
        "owner_login": data.get("login", owner),
        "owner_type": data.get("type", "User"),
        "public_repos": data.get("public_repos", 0),
        "owner_age_days": age_days,
    }


def render_from_signals(s: dict) -> CategoryResult:
    age = s.get("owner_age_days", 0)
    repos = s.get("public_repos", 0)

    verdict = Verdict.GREEN
    notes: list[str] = []
    if age < 365:
        verdict = Verdict.AMBER
        notes.append(f"owner account is {age}d old (<1yr)")
    if repos < 3:
        verdict = max(verdict, Verdict.AMBER)
        notes.append(f"only {repos} public repos")

    evidence = (
        f"Owner {s.get('owner_login', '<unknown>')} ({s.get('owner_type', 'User')}), "
        f"{repos} public repos, account age {age}d. "
        + ("; ".join(notes) if notes else "No public reputation issues found.")
    )
    return CategoryResult(
        category="2. Author/org credibility",
        verdict=Verdict(verdict),
        evidence=evidence,
        raw_signals=s,
    )
