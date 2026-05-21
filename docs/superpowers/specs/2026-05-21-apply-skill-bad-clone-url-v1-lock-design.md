# fix(tui): apply-skill crashes with bad git clone URL for v1 global lock

**Status:** Draft
**Date:** 2026-05-21
**Issue:** #159
**Type:** fix

## Goal

`ensure_project_canonical` should clone the canonical repo successfully for any global lock entry, including v1 locks that don't carry a `sourceUrl`.

## Context

Pressing apply in the TUI to add a skill to a project crashes with:

```
GitError: git ['git', 'clone', 'ajanderson1/journal-skill', '.../journal'] failed (rc=128):
fatal: repository 'ajanderson1/journal-skill' does not exist
```

The call site at `src/agent_toolkit_cli/skill_install.py:365` reads:

```python
source_url = entry.extras.get("sourceUrl") or entry.source
skill_git.clone(str(source_url), project_canonical, ref=entry.ref, env=env)
```

The global lock is v1 (`~/.agent-toolkit/skills-lock.json`):

```json
{ "version": 1, "skills": { "journal": {
    "source": "ajanderson1/journal-skill",
    "sourceType": "github",
    ...
}}}
```

v1 has no `sourceUrl` field, so `extras["sourceUrl"]` is empty and the fallback hands the bare `owner/repo` string to `git clone`. Git rejects it.

`skill_lock.py:131` already synthesises the full URL for the v3 writer:

```python
elif e.source_type == "github" and "/" in e.source:
    out["sourceUrl"] = f"https://github.com/{e.source}.git"
elif e.source_type == "gitlab" and "/" in e.source:
    out["sourceUrl"] = f"https://gitlab.com/{e.source}.git"
else:
    out["sourceUrl"] = e.source
```

That synthesis needs to be available to the read-side too. Best move: extract a shared helper.

## Scope

In:
- New helper `clone_url_from_entry(entry: LockEntry) -> str` (in `skill_lock.py` next to the existing writer logic).
- Replace the inline ladder in `_entry_to_dict_v3` with a call to the helper.
- Replace the `entry.extras.get("sourceUrl") or entry.source` line in `ensure_project_canonical` with a call to the helper.
- Regression test exercising `ensure_project_canonical` against a v1 lock entry (no `sourceUrl`, `sourceType=github`, `source=owner/repo`) — asserts `skill_git.clone` is called with the synthesised URL.

Out:
- Migrating v1 global locks to v3. The read path must keep working for v1 forever.
- SSH vs HTTPS protocol choice. Match the existing writer (HTTPS).
- Other call sites that may also need the helper (none discovered in audit; if any are found during build, they're in scope under the same helper but flagged in the PR body).

## Definition of done

- `clone_url_from_entry` exists and is used by both `_entry_to_dict_v3` and `ensure_project_canonical`.
- New regression test passes; existing tests still pass.
- Manual: TUI apply-skill against the current v1 `~/.agent-toolkit/skills-lock.json` clones successfully (verified out of test sandbox).
- Pre-flight lint + tests green.
