# Spec — skill list (no flag) default scope

Closes #210.

## Problem

`agent-toolkit-cli skill list` (no flag) silently returns `(no skills installed)` when
invoked outside a project directory, even though the user's global library has
skills. `skill add` defaults to **global**, so the mental model is "global by
default"; `list` and `status` violate it.

```
$ cd /tmp
$ agent-toolkit-cli skill list        # → (no skills installed)   ← surprising
$ agent-toolkit-cli skill list -g     # → 5 skills                ← expected
```

Same applies to `skill status <slug>` reporting `(not in lock)` even when the
slug is in the global lock.

## Fix

For the read-only verbs (`list`, `status`), pick the scope to read based on
what actually exists on disk when the user hasn't told us:

| User input | Resolved scope |
|---|---|
| `-g` | global (unchanged) |
| `-p` | project (unchanged — error/no-skills if no project lock) |
| neither, **and** `<cwd>/skills-lock.json` exists | project |
| neither, **and** no project lock | **global** ← the change |

Write-mode commands (`update`, `push`, `reset`, `doctor`) keep the current
behaviour for now. They mutate state; defaulting to a scope the user didn't ask
for is a different conversation and outside #210's scope.

## Messaging

When `-p` is forced and no project lock exists, surface a clear hint instead of
silent emptiness:

- `list -p` outside a project →
  `(no project skills here. Run "skill list -g" for the global library, or "-p" from inside a project)`
- `status -p` with no slugs and no project lock → same hint.

## Out of scope

- Auto-detecting a project root above `cwd` (walking up the tree). Keep it
  literal: a project lock is at `cwd/skills-lock.json`. Anything else is the
  user not standing in the project.
- Changing `--scope` defaults on write commands.
- TUI behaviour (already scope-toggle correct).

## Acceptance

- [x] `skill list` (no flag) outside a project shows global skills.
- [x] `skill list -p` outside a project prints the clear hint.
- [x] `skill status <slug>` (no flag) consults global lock when no project lock.
- [x] Existing project-scope tests still pass (default still resolves to
      project when `cwd/skills-lock.json` exists).
- [x] `skill list -g` and `skill list -p` behaviour unchanged.
