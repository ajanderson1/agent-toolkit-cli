# Skill remove: handle monorepo symlinks (issue #207)

## Problem

`agent-toolkit-cli skill remove <slug> --force` raises
`OSError: Cannot call rmtree on a symbolic link` when the slug was installed via
the v2.7.0 monorepo flow (#177). Reported via demo trial of v2.7.0 with the
Anthropic skills monorepo.

Repro:

```bash
agent-toolkit-cli skill add https://github.com/anthropics/skills/tree/main/skills/pdf
agent-toolkit-cli skill remove pdf --force
# OSError: Cannot call rmtree on a symbolic link
```

The library entry for a monorepo skill is a symlink:

```
~/.agent-toolkit/skills/pdf -> ~/.agent-toolkit/skills/_parents/anthropics/skills@main/skills/pdf
```

`shutil.rmtree` refuses to traverse a symlink for safety. Remove fails before
touching the lock entry, leaving the library half-broken.

## Cause

`src/agent_toolkit_cli/commands/skill/__init__.py:586` calls `shutil.rmtree`
unconditionally. It pre-dates monorepo support, where `_add_monorepo`
materialises `library_dir` as a symlink into a shared parent clone at
`<library_root>/_parents/<owner>/<repo>[@<ref>]/`.

## Fix

In `remove_cmd`, branch on `library_dir.is_symlink()`:

- **Symlink** → resolve the target (so we can find the parent clone), `unlink()`
  the symlink, then sweep the parent clone if no other library entry still
  references it.
- **Directory** → keep the existing `shutil.rmtree` path.

### Parent-clone sweep

After unlinking a monorepo symlink:

1. Resolve the symlink's target to find which `_parents/<owner>/<repo>[@<ref>]/`
   directory it pointed into. Use `os.readlink` (not `Path.resolve()`) so a
   missing target still returns a usable path.
2. Walk the remaining lock entries. For each slug whose canonical at
   `library_skill_path(slug)` is a symlink, check whether it points into the
   same parent clone directory.
3. If no sibling references the parent clone → `shutil.rmtree(parent_clone)`.
   Otherwise leave it intact.

This is conservative: we only remove the parent clone when it is provably
unreferenced from the lock. If a stray symlink lives in the library outside the
lock, we play it safe and keep the parent clone (the next `skill add` with the
same parent re-uses it).

### Lock entry

`lock = remove_entry(lock, slug); write_lock(...)` already runs after `rmtree`.
Both branches keep that order: physical cleanup first, lock-write second.

## Acceptance

- [x] `skill remove <monorepo-slug>` succeeds without traceback (the original
      repro).
- [x] After removal: the symlink is gone, the lock entry is gone, the parent
      clone is gone if no other lock entry references it.
- [x] If sibling skills from the same monorepo remain, the parent clone is
      preserved.
- [x] Regression test under `tests/test_cli/` exercises both cases.
- [x] Existing non-monorepo `skill remove` behaviour unchanged.

## Out of scope

- Re-using a `_maybe_cleanup_parent_clone` helper across `update` /
  `reset` flows — those paths are not currently broken; we'll harvest the
  helper later if a second caller appears.
- Removing the `_parents/` directory itself once empty — `_parents/<owner>/`
  may carry other repos; cleaning the leaf `_parents/<owner>/<repo>[@<ref>]/`
  is enough to free the disk space.
