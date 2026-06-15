"""Best-effort version resolution for `mcp add` / `mcp update`.

Each resolver returns the current version string for a source, or None on ANY
failure (network down, package absent, malformed response, missing tool). A
None is NOT an error at the call site — the entry is stored floating. Wrapping
every subprocess/urllib call in try/except keeps these pure + monkeypatchable
in tests (tests MUST NOT hit the real network).
"""
from __future__ import annotations

import json
import subprocess
import urllib.request
from pathlib import Path

_TIMEOUT = 10  # seconds — short, best-effort.


def resolve_npm_version(pkg: str) -> str | None:
    """Current version of an npm package via `npm view <pkg> version`."""
    try:
        result = subprocess.run(
            ["npm", "view", pkg, "version"],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    version = result.stdout.strip()
    return version or None


def resolve_pypi_version(pkg: str) -> str | None:
    """Current version of a PyPI package via the PyPI JSON API (stdlib only)."""
    url = f"https://pypi.org/pypi/{pkg}/json"
    try:
        with urllib.request.urlopen(url, timeout=_TIMEOUT) as resp:  # noqa: S310 (https only)
            payload = json.loads(resp.read().decode("utf-8"))
    except (OSError, ValueError):
        return None
    version = payload.get("info", {}).get("version")
    return version if isinstance(version, str) and version else None


def resolve_git_head_sha(directory: Path) -> str | None:
    """HEAD SHA of a local git repo, or None if `directory` is not a repo."""
    try:
        result = subprocess.run(
            ["git", "-C", str(directory), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    sha = result.stdout.strip()
    return sha or None
