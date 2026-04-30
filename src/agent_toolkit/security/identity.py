"""Security review — category 1: repo identity & traction."""
from __future__ import annotations

import json
import subprocess

from agent_toolkit.security.types import CategoryResult, Verdict


def collect_signals(owner: str, repo: str) -> dict:
    """Call `gh api repos/<owner>/<repo>` and shape the response.

    Returns a dict with keys: stars, forks, open_issues, contributors,
    age_days, last_commit_days_ago. Missing keys are filled with 0.
    """
    import datetime as _dt

    out = subprocess.run(
        ["gh", "api", f"repos/{owner}/{repo}"],
        check=True, capture_output=True, text=True,
    )
    repo_data = json.loads(out.stdout)
    contributors_out = subprocess.run(
        ["gh", "api", f"repos/{owner}/{repo}/contributors", "--paginate"],
        check=True, capture_output=True, text=True,
    )
    contributors = json.loads("[" + ",".join(contributors_out.stdout.split("][")) + "]") \
        if contributors_out.stdout.strip().startswith("[") else []

    created_at = _dt.datetime.fromisoformat(repo_data["created_at"].replace("Z", "+00:00"))
    pushed_at = _dt.datetime.fromisoformat(repo_data["pushed_at"].replace("Z", "+00:00"))
    now = _dt.datetime.now(tz=_dt.timezone.utc)
    age_days = (now - created_at).days
    last_commit_days = (now - pushed_at).days

    return {
        "stars": repo_data.get("stargazers_count", 0),
        "forks": repo_data.get("forks_count", 0),
        "open_issues": repo_data.get("open_issues_count", 0),
        "contributors": len(contributors) if isinstance(contributors, list) else 0,
        "age_days": age_days,
        "last_commit_days_ago": last_commit_days,
    }


def render_from_signals(s: dict) -> CategoryResult:
    stars = s.get("stars", 0)
    last_commit = s.get("last_commit_days_ago", 9999)
    contributors = s.get("contributors", 0)

    verdict = Verdict.GREEN
    notes: list[str] = []

    if last_commit > 365:
        verdict = max(verdict, Verdict.AMBER)
        notes.append(f"last commit {last_commit}d ago — possibly stale")
    if stars < 50:
        verdict = max(verdict, Verdict.AMBER)
        notes.append(f"only {stars} stars — low traction")
    if contributors < 2:
        verdict = max(verdict, Verdict.AMBER)
        notes.append(f"{contributors} contributors — low bus factor")
    if last_commit > 1095:
        verdict = Verdict.RED
        notes.append(f"abandoned-looking — last commit {last_commit}d ago")

    base = (
        f"{stars} stars, {s.get('forks', 0)} forks, "
        f"{s.get('open_issues', 0)} open issues, {contributors} contributors, "
        f"age {s.get('age_days', 0)}d, last commit {last_commit}d ago."
    )
    evidence = base + (" " + "; ".join(notes) if notes else "")
    return CategoryResult(
        category="1. Repo identity & traction",
        verdict=Verdict(verdict),
        evidence=evidence,
        raw_signals=s,
    )
