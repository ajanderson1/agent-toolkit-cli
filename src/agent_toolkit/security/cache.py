"""24h TTL cache for deterministic security signals."""
from __future__ import annotations

import json
import time
from pathlib import Path

DEFAULT_TTL_SECONDS = 60 * 60 * 24


def cache_path(repo_root: Path, owner: str, repo: str) -> Path:
    return repo_root / ".agent-toolkit" / "cache" / "security" / owner / f"{repo}.json"


def save_cache(repo_root: Path, owner: str, repo: str, payload: dict) -> None:
    target = cache_path(repo_root, owner, repo)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2))


def load_cache(
    repo_root: Path, owner: str, repo: str, *, ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> dict | None:
    target = cache_path(repo_root, owner, repo)
    if not target.exists():
        return None
    age = time.time() - target.stat().st_mtime
    if age > ttl_seconds:
        return None
    return json.loads(target.read_text())
