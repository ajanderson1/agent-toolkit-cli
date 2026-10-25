"""Explicit, read-only upstream revision checks for catalog-associated skills."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import subprocess
from pathlib import Path

from agent_toolkit_cli.skill_catalog import run_git, write_json
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
    targets = slugs or tuple(s for s, e in sorted(lock.skills.items()) if isinstance(e.extras.get("catalog"), dict))
    state = _load(home)
    rows = []
    remotes = {}
    for slug in targets:
        entry = _entry(slug, scope, home, project)
        row = dict(slug=slug, checked_at=datetime.now(timezone.utc).isoformat(), status="unknown", local_sha=None, remote_sha=None, local_changes=False, error=None)
        try:
            if entry is None or not isinstance(entry.extras.get("catalog"), dict):
                raise ValueError("not a catalog-associated skill in this scope")
            canonical = canonical_skill_dir(slug, scope=scope, home=home, project=project)
            row["identity"] = _identity(entry, canonical)
            actual_origin = run_git(["remote", "get-url", "origin"], cwd=canonical)
            if normalise_git_url(actual_origin) != normalise_git_url(clone_url_from_entry(entry)):
                raise ValueError("backing origin does not match recorded source")
            row["local_sha"] = run_git(["rev-parse", "HEAD"], cwd=canonical)
            row["local_changes"] = bool(run_git(["--no-optional-locks", "status", "--porcelain"], cwd=canonical))
            if is_sha_pinned(entry):
                row["status"] = "pinned" if row["local_sha"].startswith(entry.ref) else "different"
                row["remote_sha"] = entry.ref
            else:
                ref = sanitize_ref(entry.ref) if entry.ref else None
                cachekey = (actual_origin, ref)
                if cachekey not in remotes:
                    patterns = [f"refs/heads/{ref}", f"refs/tags/{ref}", f"refs/tags/{ref}^{{}}"] if ref else ["HEAD"]
                    output = run_git(["ls-remote", "--exit-code", "origin", *patterns], cwd=canonical)
                    refs = {parts[1]: parts[0] for line in output.splitlines() if len(parts := line.split()) == 2}
                    selected = (refs.get(f"refs/heads/{ref}") or refs.get(f"refs/tags/{ref}^{{}}") or refs.get(f"refs/tags/{ref}")) if ref else refs.get("HEAD")
                    if not selected or len(selected) != 40 or any(c not in "0123456789abcdef" for c in selected):
                        raise ValueError("upstream ref is missing or ambiguous")
                    remotes[cachekey] = selected
                row["remote_sha"] = remotes[cachekey]
                row["status"] = "current" if row["local_sha"] == row["remote_sha"] else "different"
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
