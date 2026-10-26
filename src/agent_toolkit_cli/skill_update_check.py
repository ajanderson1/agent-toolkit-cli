"""Explicit, read-only upstream revision checks for registered Git-backed skills."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import subprocess
from pathlib import Path

from agent_toolkit_cli.skill_catalog import run_git, write_json
from agent_toolkit_cli.git_revision_check import observe_backing
from agent_toolkit_cli.skill_git import normalise_git_url
from agent_toolkit_cli.skill_lock import clone_url_from_entry, is_sha_pinned, read_lock
from agent_toolkit_cli.skill_paths import canonical_skill_dir, library_lock_path, lock_file_path
from agent_toolkit_cli.skill_source import sanitize_ref


def _state_path(home):
    return library_lock_path(home=home).parent / "skills-update-checks.json"


def _load(home):
    try:
        data = json.loads(_state_path(home).read_text())
        return data if isinstance(data, dict) and data.get("version") == 1 and isinstance(data.get("checks"), dict) else {"version": 1, "checks": {}}
    except (OSError, ValueError):
        return {"version": 1, "checks": {}}


def _entry(slug, scope, home, project):
    entry = read_lock(lock_file_path(scope=scope, home=home, project=project)).skills.get(slug)
    if entry is None and scope == "global":
        entry = read_lock(library_lock_path(home=home)).skills.get(slug)
    return entry


def _identity(entry, canonical):
    return dict(source=clone_url_from_entry(entry), path=entry.skill_path, ref=entry.ref, backing=str(canonical.resolve()))


def _key(slug, scope, project):
    return json.dumps([slug, scope, str(project.resolve()) if project else None])


def check_skills(slugs: tuple[str, ...], *, scope: str, home: Path | None, project: Path | None) -> list[dict]:
    lock = read_lock(lock_file_path(scope=scope, home=home, project=project))
    targets = slugs or tuple(sorted(lock.skills))
    state = _load(home)
    rows = []
    remotes = {}
    for slug in targets:
        entry = _entry(slug, scope, home, project)
        row = dict(slug=slug, checked_at=datetime.now(timezone.utc).isoformat(), status="unknown", local_sha=None, remote_sha=None, local_changes=False, error=None)
        try:
            if entry is None:
                raise ValueError("not a registered skill in this scope")
            canonical = canonical_skill_dir(slug, scope=scope, home=home, project=project)
            row["identity"] = _identity(entry, canonical)
            observe_backing(row, entry, canonical, clone_url_from_entry(entry), remotes, run=run_git)
        except (ValueError, OSError, RuntimeError) as exc:
            row["error"] = str(exc)
        except subprocess.TimeoutExpired:
            row["error"] = "upstream check timed out"
        # A failed probe replaces the old observation: never leave an old green result.
        if entry is not None:
            state["checks"][_key(slug, scope, project)] = row
        rows.append(row)
    if rows and state["checks"]:
        write_json(_state_path(home), state)
    return rows


def read_check(slug: str, *, scope: str, home: Path | None, project: Path | None) -> dict | None:
    row = _load(home)["checks"].get(_key(slug, scope, project))
    if not isinstance(row, dict):
        return None
    row = dict(row)
    entry = _entry(slug, scope, home, project)
    try:
        canonical = canonical_skill_dir(slug, scope=scope, home=home, project=project)
        if entry is None or row.get("identity") != _identity(entry, canonical) or row.get("local_sha") != run_git(["rev-parse", "HEAD"], cwd=canonical):
            row["status"] = "stale"
    except (ValueError, OSError, RuntimeError):
        row["status"] = "stale"
    return row
