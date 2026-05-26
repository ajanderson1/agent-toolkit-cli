# `skill import` — sync the global skill library across machines

**Date:** 2026-05-26
**Status:** Design approved, ready for planning

## Problem

The global lock at `~/.agent-toolkit/skills-lock.json` already records every
skill in the library as a list of upstream repos (`slug → {source, sourceType,
ref, skillPath, upstreamSha, ...}`). It *is* a portable description of "what
this machine has." There is currently no way to take that description to a
second machine and reconstruct the library from it.

We want a one-directional restore: point a command at a lock file from another
machine and have it populate the local library from the upstream repos it
names.

## Decisions (from brainstorming)

1. **No `export` command.** The global lock file *is* the export artifact. The
   user syncs `~/.agent-toolkit/skills-lock.json` to the other machine by any
   means (git, Dropbox, scp) — out of our scope.
2. **One new command: `skill import <file>`.** It accepts a lock file path and
   reconstructs the local global library from it.
3. **Global library only.** No project scope. Project-scoped skills are
   explicitly out of scope and never touched.
4. **Additive merge, never replace.** Import only adds slugs that are absent
   locally. The merged lock is `current ∪ (incoming − current)`.
5. **Skip-if-exists is total.** If a slug already exists locally it is left
   byte-for-byte untouched — no overwrite, no update, not even a SHA comparison.
   This guarantees import never silently changes a skill the user already has.
6. **Default pins to the export's `upstreamSha`.** A newly-added skill lands on
   the exact commit recorded in the imported file. The `--latest` flag overrides
   this: clone every new skill at its ref's current HEAD instead. `--latest` is
   all-or-nothing — no per-skill granularity. Either way the *source* is always
   the upstream repo; local commits and dirty state from the source machine are
   never represented in a lock file and so never travel.
7. **Per-skill failures are not fatal.** A repo that won't clone reports `failed`
   and the rest proceed (partial success). The lock is still written for the
   successes.
8. **Full transparency.** Report every stage: a per-skill line as each is
   processed, a summary, then three standing caveat notices (always printed).

## Command surface

```
agent-toolkit-cli skill import <file> [--latest]
```

- `<file>` — path to a lock file. Any supported version parses transparently
  (`read_lock` already accepts v1 and v3).
- `--latest` — clone every newly-added skill at its ref's current HEAD instead
  of the recorded `upstreamSha`.
- No `-p` / `--scope`. Global library only.

Registered in `commands/skill/__init__.py` as a new `import_cmd` (own file
`commands/skill/import_cmd.py`, mirroring `list_cmd` / `status_cmd` structure).

## Algorithm

```
if not Path(<file>).exists():
    raise click.UsageError("import file not found: <path>")

incoming = read_lock(<file>)            # v1 or v3, transparently
current  = read_lock(library_lock_path())

added, skipped, failed = [], [], []

for slug, entry in sorted(incoming.skills.items()):   # stable output order
    if slug in current.skills:
        skipped.append(slug)            # total skip — no source/SHA comparison
        report "skipped  <slug>  (already present)"
        continue

    url       = clone_url_from_entry(entry)   # handles v1/v3, file://, etc.
    ref       = entry.ref
    pin_sha   = None if --latest else entry.upstream_sha
    is_monorepo = bool(entry.skill_path and entry.skill_path != "SKILL.md") \
                  or entry.read_only or entry.parent_url

    try:
        if is_monorepo:
            reconstruct via parent clone + subpath symlink   # mirror _add_monorepo
        else:
            clone into library_skill_path(slug)              # mirror _add_single
            if pin_sha: checkout pin_sha
        landed_sha = head_sha(library_skill_path(slug))
        current = add_entry(current, slug, reconstructed_entry)  # record THIS machine's HEAD
        added.append((slug, landed_sha, used_latest))
        report "added    <slug>  <- <source> @ <landed_sha>"   # "(latest: <sha>)" when --latest
    except Exception as exc:
        failed.append((slug, str(exc)))
        report "failed   <slug>  (<reason>)"
        continue

write_lock(library_lock_path(), current)   # once, at the end
print summary line
print the three caveat notices (always)
exit 1 if failed else 0
```

### Reconstructed entry

For each added skill we record a fresh `LockEntry` reflecting *this* machine's
clone, not a verbatim copy of the imported entry:

- `source`, `source_type`, `ref`, `skill_path`, `parent_url`, `read_only` —
  carried from the incoming entry.
- `upstream_sha` / `local_sha` — set from this machine's actual clone HEAD
  (so the new lock is truthful about local state), exactly as `_add_single` /
  `_add_monorepo` already compute them.
- v3-only extras (`installedAt`, etc.) — handled by `write_lock` as today; we do
  not copy the source machine's timestamps.

The merged lock is written in whatever version the *local* library lock already
uses (the `write_lock` preserve-version rule is unchanged).

## Reuse

The clone/checkout/lock mechanics already exist in `_add_single` and
`_add_monorepo` (`commands/skill/__init__.py`). The plan should **extract the
per-skill reconstruction into a shared helper** both `add` and `import` call,
rather than duplicating the monorepo parent-clone + symlink logic. This is the
one targeted refactor in scope — it serves the feature directly (import is "run
add for each absent entry") and avoids a second copy of subtle monorepo code.

## Output

```
importing from ~/sync/skills-lock.json (7 skills)

  added    journal          <- ajanderson1/journal-skill @ a1b2c3d
  added    pocketsmith      <- ajanderson1/pocketsmith-skill @ e4f5g6h
  skipped  skill-builder    (already present)
  added    domain-manager   <- ajanderson1/domain-manager-skill @ 1234abc
  failed   broken-skill     (clone failed: repository not found)
  added    obsidian         <- ajanderson1/obsidian-skill (latest: 9f8e7d6)
  skipped  journal-helper   (already present)

summary: 4 added, 2 skipped, 1 failed

Notes:
  • Imported skills are pinned to upstream commits. Local commits or
    uncommitted changes on the source machine are NOT reflected.
  • Global-library skills only. Project-scoped skills (per-project
    skills-lock.json) must be re-installed manually in each project.
  • Skills were added to the library but not installed for any agent.
    Run `skill install <slug> --agents ...` to make them visible.
```

- SHA after `@` is the commit actually landed on. With `--latest` it is
  annotated `(latest: <sha>)` so the divergence from the export's pin is visible.
- **Exit code 0** when no skill failed; **exit code 1** if any skill failed to
  clone (so scripts/CI notice), even though the lock was written for the
  successes. Matches the "fail loudly" convention.
- The **three notices always print**, regardless of outcome — even if every
  skill was skipped or the file was empty. They are standing facts about what
  import covers, not conditional warnings.

## Edge cases

- **File not found** → `read_lock` would return an empty `LockFile` on
  `FileNotFoundError`, masking a typo as "0 skills." Import does an explicit
  `Path.exists()` check first and raises `click.UsageError`.
- **Empty / zero-skill file** → valid. Reports "0 skills to import", prints the
  notices, exits 0.
- **Importing the live global lock onto itself** → every slug already present →
  all skipped. Harmless, correctly reported.
- **Slug present locally from a different source** → still skipped (skip-if-exists
  is total). Reported under "already present."
- **Monorepo parent already cached** → reuse `parent_clone_path`, fetch like
  `_add_monorepo` does.
- **`--latest` with no resolvable ref** → fall back to `main` (the default
  `_add_single` already uses for `remote_head_sha`).

## Testing

Following the repo's characterization style (Spec 1, git & doctor foundation),
with a temp `AGENT_TOOLKIT_SKILLS_ROOT` and local `file://` sources:

- **Merge logic:** added vs skipped vs failed classification; SHA-pin (default)
  vs `--latest`; additive-merge invariant (every pre-existing entry is
  byte-identical in the lock after import).
- **Partial success:** one failing clone reports `failed`, others added, lock
  still written, exit code 1.
- **Edge cases:** missing file → `UsageError`; empty file → 0 imported + notices
  + exit 0; self-import no-op; monorepo entry reconstruction.
- **Output:** the three notices always print; per-skill lines present; summary
  counts correct.

## Out of scope

- No `export` command (the lock file is the artifact).
- No project-scope import.
- No agent-visibility restore (`skill install` remains a separate, manual step).
- No automatic upstream updates on existing skills (`skill update` remains
  separate and manual).
- No two-way / conflict-resolving sync. Skip-if-exists is the entire conflict
  policy.
