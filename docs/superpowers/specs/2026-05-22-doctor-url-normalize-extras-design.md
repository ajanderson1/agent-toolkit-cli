# Design: doctor — cover trailing-slash + `ssh://` URL variants

Closes #208.

## Problem

PR #201 (closed #191) reduced `git@host:path.git` and `https://host/path.git` to `host/path` in `_normalise_git_url`. Self-review on that PR flagged three forms that still slip through and would each produce a false-positive `lock_source_mismatch` finding:

| Input | Currently normalises to | Should equal |
|---|---|---|
| `https://github.com/o/r/` (trailing slash) | `github.com/o/r/` | `github.com/o/r` |
| `ssh://git@github.com/o/r` (`ssh://` form) | falls through to fallback | `github.com/o/r` |
| `git@github.com:o/r.git/` (trailing slash on SSH form) | `github.com/o/r/` | `github.com/o/r` |

None regresses prior behaviour; the #191 reproducer (the canonical SSH ↔ HTTPS pair) still passes. These variants only fire when a user has one of those forms in either the lockfile or the git remote URL, which is uncommon but not unheard of (git CLI accepts the `ssh://` form, and trailing slashes leak in from pasted browser URLs).

## Approach

Two minimal edits to `src/agent_toolkit_cli/skill_doctor.py`:

1. Strip a trailing slash from the normalised output (after the regex group capture or the `.git` fallback strip).
2. Add a third regex for `ssh://[user@]host/path`.

```python
_SSH_GIT_URL_RE = re.compile(r"^git@([^:]+):(.+?)(?:\.git)?/?$")
_HTTPS_GIT_URL_RE = re.compile(r"^https?://([^/]+)/(.+?)(?:\.git)?/?$")
_SSH_URL_RE = re.compile(r"^ssh://(?:[^@]+@)?([^/]+)/(.+?)(?:\.git)?/?$")
```

The trailing `/?$` in each regex absorbs an optional final slash inside the non-greedy capture's exclusion zone, so `o/r/` and `o/r.git/` both collapse to `o/r`. The fallback branch gets an explicit `u.rstrip("/")` for the local-path / unfamiliar-form case (e.g. `/tmp/some-remote.git/`).

Final function:

```python
def _normalise_git_url(url: str) -> str:
    u = url.strip().lower()
    if (m := _SSH_GIT_URL_RE.match(u)):
        return f"{m.group(1)}/{m.group(2)}"
    if (m := _HTTPS_GIT_URL_RE.match(u)):
        return f"{m.group(1)}/{m.group(2)}"
    if (m := _SSH_URL_RE.match(u)):
        return f"{m.group(1)}/{m.group(2)}"
    if u.endswith(".git"):
        u = u[:-4]
    return u.rstrip("/")
```

## Acceptance

- New unit tests cover the three rows above directly (each new variant compared to the canonical `github.com/o/r`).
- `test_normalise_git_url_ssh_https_equivalent`, `test_normalise_git_url_different_repos_differ`, `test_normalise_git_url_fallback_for_unknown_form` still pass (regression).
- `test_diagnose_lock_source_mismatch` still passes — genuinely different remotes (different host or different `owner/repo`) still produce a finding.

## Out of scope

- No new finding kinds, no UI changes, no fix-action for `lock_source_mismatch` (still report-only).
- No change to `clone_url_from_entry` or anywhere else that produces URLs — we normalise at the comparison point only.
