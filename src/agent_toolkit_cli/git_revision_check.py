"""Read-only Git observation shared by catalogue-associated asset checks."""
from agent_toolkit_cli.skill_catalog import run_git
from agent_toolkit_cli.skill_git import normalise_git_url
from agent_toolkit_cli.skill_lock import is_sha_pinned
from agent_toolkit_cli.skill_source import sanitize_ref


def observe_backing(row, entry, canonical, source_url, remotes, *, run=run_git):
    actual_origin = run(["remote", "get-url", "origin"], cwd=canonical)
    if normalise_git_url(actual_origin) != normalise_git_url(source_url):
        raise ValueError("backing origin does not match recorded source")
    row["local_sha"] = run(["rev-parse", "HEAD"], cwd=canonical)
    row["local_changes"] = bool(run(["--no-optional-locks", "status", "--porcelain"], cwd=canonical))
    if is_sha_pinned(entry):
        row["status"] = "pinned" if row["local_sha"].startswith(entry.ref) else "different"
        row["remote_sha"] = entry.ref
    else:
        ref = sanitize_ref(entry.ref) if entry.ref else None
        cachekey = (actual_origin, ref)
        if cachekey not in remotes:
            patterns = [f"refs/heads/{ref}", f"refs/tags/{ref}", f"refs/tags/{ref}^{{}}"] if ref else ["HEAD"]
            output = run(["ls-remote", "--exit-code", "origin", *patterns], cwd=canonical)
            refs = {parts[1]: parts[0] for line in output.splitlines() if len(parts := line.split()) == 2}
            selected = (refs.get(f"refs/heads/{ref}") or refs.get(f"refs/tags/{ref}^{{}}") or refs.get(f"refs/tags/{ref}")) if ref else refs.get("HEAD")
            if not selected or len(selected) != 40 or any(c not in "0123456789abcdef" for c in selected):
                raise ValueError("upstream ref is missing or ambiguous")
            remotes[cachekey] = selected
        row["remote_sha"] = remotes[cachekey]
        row["status"] = "current" if row["local_sha"] == row["remote_sha"] else "different"
