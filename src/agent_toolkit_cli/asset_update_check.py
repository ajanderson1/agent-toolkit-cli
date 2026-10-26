"""Timestamped checks of recorded Git selectors, independent of live catalogue access."""
from datetime import datetime, timezone
import json
import subprocess

from agent_toolkit_cli.asset_catalog_ops import backing_modules, clone_url, entry_identity, validate_backing
from agent_toolkit_cli.git_revision_check import observe_backing
from agent_toolkit_cli.skill_catalog import KINDS, run_git, write_json


def _state_path(kind):
    _, paths, _, _ = backing_modules(kind)
    group = next(group for group, value in KINDS.items() if value == kind)
    return paths.library_lock_path().parent / f"{group}-update-checks.json"


def _load(kind):
    try:
        state = json.loads(_state_path(kind).read_text())
        if isinstance(state, dict) and state.get("version") == 1 and isinstance(state.get("checks"), dict):
            return state
    except (OSError, ValueError):
        pass
    return {"version": 1, "checks": {}}


def _key(slug, scope, project):
    return json.dumps([slug, scope, str(project.resolve()) if project else None])


def _identity(kind, slug, entry, canonical):
    return dict(selector=list(entry_identity(kind, slug, entry)), backing=str(canonical.resolve()))


def check_assets(kind, slugs, *, scope, home, project):
    locks, paths, _, canonical_dir = backing_modules(kind)
    entries = locks.read_lock(paths.lock_file_path(scope=scope, home=home, project=project)).skills
    targets = slugs or tuple(sorted(slug for slug, entry in entries.items()
        if entry.source_type != "npm" and isinstance(entry.extras.get("catalog"), dict)))
    state, rows, remotes = _load(kind), [], {}
    for slug in targets:
        entry = entries.get(slug)
        row = dict(slug=slug, checked_at=datetime.now(timezone.utc).isoformat(), status="unknown",
            local_sha=None, remote_sha=None, local_changes=False, error=None)
        try:
            if entry is None or entry.source_type == "npm":
                hint = "; native npm uses Pi package updates, not Git checks" if kind == "pi-extension" else ""
                raise ValueError("not a registered catalogue-associated Git asset in this scope" + hint)
            if not isinstance(entry.extras.get("catalog"), dict):
                raise ValueError("not a catalogue-associated Git asset in this scope")
            canonical = canonical_dir(slug, scope=scope, home=home, project=project)
            row["identity"] = _identity(kind, slug, entry, canonical)
            validate_backing(kind, slug, entry, scope=scope, home=home, project=project)
            observe_backing(row, entry, canonical, clone_url(kind, entry), remotes)
        except (ValueError, OSError, RuntimeError) as exc:
            row["error"] = str(exc)
        except subprocess.TimeoutExpired:
            row["error"] = "upstream check timed out"
        if entry is not None and entry.source_type != "npm":
            state["checks"][_key(slug, scope, project)] = row
        rows.append(row)
    if rows and state["checks"]:
        write_json(_state_path(kind), state)
    return rows


def read_check(kind, slug, *, scope, home, project):
    row = _load(kind)["checks"].get(_key(slug, scope, project))
    if not isinstance(row, dict):
        return None
    row = dict(row)
    locks, paths, _, canonical_dir = backing_modules(kind)
    entry = locks.read_lock(paths.lock_file_path(scope=scope, home=home, project=project)).skills.get(slug)
    try:
        canonical = canonical_dir(slug, scope=scope, home=home, project=project)
        if (entry is None or row.get("identity") != _identity(kind, slug, entry, canonical)
                or row.get("local_sha") != run_git(["rev-parse", "HEAD"], cwd=canonical)):
            row["status"] = "stale"
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError):
        row["status"] = "stale"
    return row
