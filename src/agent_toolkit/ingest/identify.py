"""Ingest stage 1 — IDENTIFY: resolve URL / name / file to a credible upstream."""
from __future__ import annotations

import re
from pathlib import Path

from agent_toolkit.ingest.types import IngestTarget, InputForm

_GITHUB_URL = re.compile(r"^https?://github\.com/([^/]+)/([^/?#]+?)(?:\.git)?(?:[/?#].*)?$")
_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def classify_input(value: str) -> IngestTarget:
    candidate_path = Path(value)
    if candidate_path.exists() and candidate_path.is_file():
        return _from_file(candidate_path)
    if _URL_RE.match(value):
        return _from_url(value)
    return _from_name(value)


def _from_file(path: Path) -> IngestTarget:
    kind = _kind_from_filename(path.name)
    slug = path.stem.lower().replace("_", "-")
    return IngestTarget(
        input_value=str(path),
        input_form=InputForm.FILE,
        upstream_url=None,
        kind_guess=kind,
        slug_guess=slug,
        vendor_strategy_guess="copy",
    )


def _from_url(url: str) -> IngestTarget:
    m = _GITHUB_URL.match(url)
    if not m:
        return IngestTarget(
            input_value=url,
            input_form=InputForm.URL,
            upstream_url=url,
            kind_guess="skill",
            slug_guess=url.rsplit("/", 1)[-1].lower(),
            vendor_strategy_guess="copy",
            notes=["non-github URL — vendor strategy may need to be 'copy' or 'clone'"],
        )
    owner, repo = m.group(1), m.group(2)
    kind = _kind_from_repo_name(repo)
    return IngestTarget(
        input_value=url,
        input_form=InputForm.URL,
        upstream_url=f"https://github.com/{owner}/{repo}",
        kind_guess=kind,
        slug_guess=repo.lower(),
        vendor_strategy_guess="submodule",
        owner=owner,
        repo=repo,
    )


def _from_name(name: str) -> IngestTarget:
    return IngestTarget(
        input_value=name,
        input_form=InputForm.NAME,
        upstream_url=None,
        kind_guess=_kind_from_repo_name(name),
        slug_guess=name.lower(),
        vendor_strategy_guess="submodule",
        notes=[
            "name input — RESEARCH stage must resolve to a URL via web search; "
            "always present 2–3 candidates before picking",
        ],
    )


def _kind_from_repo_name(name: str) -> str:
    n = name.lower()
    if "mcp" in n or "mcp-server" in n:
        return "mcp"
    if n.startswith("plugin-") or n.endswith("-plugin"):
        return "plugin"
    if n.startswith("hook-") or n.endswith("-hook"):
        return "hook"
    if n.startswith("agent-") or n.endswith("-agent"):
        return "agent"
    if n.startswith("command-") or n.endswith("-command"):
        return "command"
    return "skill"


def _kind_from_filename(name: str) -> str:
    n = name.lower()
    if n.endswith(".meta.yaml"):
        return "hook"
    if n == "mcp.json":
        return "mcp"
    if n == "marketplace.json":
        return "plugin"
    if n == "skill.md":
        return "skill"
    return "skill"  # default for stray .md
