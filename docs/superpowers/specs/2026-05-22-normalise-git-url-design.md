# Design: skill doctor — normalise ssh ↔ https URL forms

Closes #191.

## Problem

`_normalise_git_url` in `src/agent_toolkit_cli/skill_doctor.py` only lowercases and strips a trailing `.git`. SSH and HTTPS URLs that point at the same repo therefore compare unequal:

- `https://github.com/foo/bar.git`
- `git@github.com:foo/bar.git`

Result: doctor flags every skill that was cloned over one form but recorded with the other as `lock_source_mismatch` (report-only). Real-world impact: 4 false positives on the dev machine post-#190.

## Approach

Reduce both URL forms to `host/path` before comparison. Keep the existing lowercase + `.git` strip as the fallback for any input the regexes don't match (local paths, file:// URLs, etc.) so we never crash on unexpected formats — `_normalise_git_url` is used inside a comparison, not on a code path with strong typing guarantees.

```python
_SSH_RE = re.compile(r"^git@([^:]+):(.+?)(?:\.git)?$")
_HTTPS_RE = re.compile(r"^https?://([^/]+)/(.+?)(?:\.git)?$")

def _normalise_git_url(url: str) -> str:
    u = url.strip().lower()
    if (m := _SSH_RE.match(u)):
        return f"{m.group(1)}/{m.group(2)}"
    if (m := _HTTPS_RE.match(u)):
        return f"{m.group(1)}/{m.group(2)}"
    if u.endswith(".git"):
        u = u[:-4]
    return u
```

Lowercase happens before regex match because GitHub hostnames and owner/repo are case-insensitive in practice and this matches the function's existing semantics. `\.git` is stripped via the non-greedy capture group rather than a separate slice so we don't double-handle the suffix.

## Acceptance

- `_normalise_git_url("git@github.com:foo/bar.git") == _normalise_git_url("https://github.com/foo/bar.git")`
- The two HTTPS forms `…/bar` and `…/bar.git` still normalise equal (regression).
- `test_diagnose_lock_source_mismatch` still passes — genuinely different remotes (different host or different `owner/repo`) still produce a finding.
- New unit tests cover the equivalence directly so the helper has its own coverage instead of relying on the integration test.

## Out of scope

- No change to `clone_url_from_entry` or anywhere else that produces URLs. We only normalise at the comparison point.
- No new finding kinds, no UI changes.
- No fix_action for `lock_source_mismatch` (still report-only by design).
