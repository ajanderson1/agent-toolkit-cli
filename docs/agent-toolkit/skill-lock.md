# `skill` subcommand — lock-file-driven skill management

> For the schema of **all five** lock files at a glance — and how the agent,
> mcp, pi-extension, and instructions locks differ from this one — see
> [Lock files](lock-files.md). This page is the skills-specific deep dive.

## Overview

The `skill` subgroup manages skills using a **per-skill upstream git repo + lock file** model, mirroring the on-disk layout and lock-file schema of [`vercel-labs/skills`](https://github.com/vercel-labs/skills). Lock files written by this CLI are readable by `npx skills`, and skills installed by either tool live in the same canonical directory.

The skill path keeps no metadata in the monorepo: each skill is a standalone git repository and the lock file is the SSOT for installation state. The other first-class asset types — agent, mcp, pi-extension, instructions — each have their own built install machinery and lock file (`agents-lock.json`, `mcps-lock.json`, etc.); see the [CLI reference](cli.md).

The defining behaviour: **`update` is a merge-aware operation.** Local edits to a skill (the "self-improvement" case) survive a pull from upstream when there is no overlap, and surface as real `git` merge conflicts when there is.

## On-disk layout

### Global scope (`-g` / `--global`)

```
~/.agent-toolkit/skills/<slug>/      ← canonical: a real `git clone` of upstream
  .git/
  SKILL.md
  ...
~/.agent-toolkit/skills-lock.json    ← global lock

~/.claude/skills/<slug>              → symlink → ~/.agent-toolkit/skills/<slug>
~/.codex/skills/<slug>               → symlink
~/.config/opencode/skills/<slug>     → symlink
~/.gemini/skills/<slug>              → symlink
~/.pi/skills/<slug>                  → symlink
```

The library root is `~/.agent-toolkit/skills/` by default, overridable via
`$AGENT_TOOLKIT_SKILLS_ROOT`; the global lock sits one level up from the library
root at `<library_root>.parent/skills-lock.json` (`skill_paths.py:6,64-69`,
`_paths_core.py:103-115`).

### Project scope (`-p` / `--project`, default)

The project canonical clone lives **outside** the project tree, in a per-project
store under `~/.agent-toolkit/` (`project_store_root` →
`<library_root>.parent/projects/<id>/skills/<slug>/`, `skill_paths.py:87-93,136-145`),
so removing a skill never touches project files. Only the project lock and the
harness symlinks live inside the project:

```
<project>/skills-lock.json           ← project lock (commit this to git)
<project>/.claude/skills/<slug>      → symlink → the project canonical clone
...
```

The per-harness directories are **projections** — editing the canonical updates every harness instantly.

## Command reference

Most scope-aware `skill` verbs (`list`, `status`, `update`, `push`, `remove`) accept `-g` (global) or `-p` (project); global is the default. `skill add` clones into the library only and takes no scope. `skill install`/`uninstall` select target agents with `--agents <names>` (a comma-separated list, the `standard` token, or `all`), not `--harness`.

| Command | Purpose |
|---|---|
| `skill add <source>` | Clone upstream into the canonical location, create per-harness symlinks, write lock entry. |
| `skill list` | Show installed skills from the lock file. |
| `skill status [<slug>...]` | Per-skill working-tree state: clean / dirty / missing. |
| `skill update [<slug>...]` | `git fetch && git merge` for each skill. Real conflicts surface in the working copy. |
| `skill push [<slug>...]` | Stage, commit, and push any uncommitted local edits. No-op when clean. |
| `skill remove <slug>...` | Tear down: lock entry, symlinks, canonical clone. Refuses dirty trees without `--force`. |

### Source formats

`skill add` accepts the same source formats `npx skills add` does:

```bash
agent-toolkit-cli skill add ajanderson1/journal           # GitHub shorthand
agent-toolkit-cli skill add https://github.com/o/r        # full URL
agent-toolkit-cli skill add https://github.com/o/r/tree/main/skills/foo  # subpath
agent-toolkit-cli skill add git@github.com:o/r.git        # SSH URL
agent-toolkit-cli skill add ./local-skill                 # local path
```

### Example: end-to-end

```bash
# Install
agent-toolkit-cli skill add ajanderson1/journal -g --harness claude
agent-toolkit-cli skill list -g

# Edit in place (the "self-improvement" use case)
$EDITOR ~/.agent-toolkit/skills/journal/SKILL.md
agent-toolkit-cli skill status -g       # → journal  dirty
agent-toolkit-cli skill push journal -g # commits + pushes upstream
agent-toolkit-cli skill status -g       # → journal  clean

# Pull upstream changes
agent-toolkit-cli skill update journal -g
```

### Merge-aware update

`skill update` runs `git fetch origin && git merge --no-edit origin/<ref>` in the canonical clone. Outcomes:

| Working copy | Upstream | Result |
|---|---|---|
| clean | unchanged | no-op |
| clean | advanced | fast-forward, silent success |
| committed local edits | unchanged | no-op |
| committed local edits | advanced, no overlap | automatic merge commit |
| committed local edits | advanced, overlapping lines | **real `git` merge conflict** — `<<<<<<<` markers in the working copy, command exits non-zero with the conflicting file list |

Conflict resolution is whatever your usual git tooling supports (`git mergetool`, an `$EDITOR` pass, etc.).

## Lock-file format

The lock file is JSON, schema-compatible with `vercel-labs/skills`'s `skills-lock.json`. Project lock is at `<project>/skills-lock.json`; global lock is at `~/.agent-toolkit/skills-lock.json`.

```json
{
  "version": 1,
  "skills": {
    "journal": {
      "source": "ajanderson1/journal",
      "sourceType": "github",
      "ref": "main",
      "skillPath": "SKILL.md",
      "upstreamSha": "abc123…",
      "localSha":    "def456…"
    }
  }
}
```

| Field | Meaning |
|---|---|
| `source` | The address we'd use to re-fetch (owner/repo, URL, or local path). |
| `sourceType` | One of `github`, `gitlab`, `git`, `local`. |
| `ref` | Branch/tag we cloned. Defaults to the source's default (typically `main`). |
| `skillPath` | Path within the repo to the skill's `SKILL.md`. Usually `SKILL.md` at root. |
| `upstreamSha` | The remote HEAD at the most recent successful sync. |
| `localSha` | Our additive field — the working copy's HEAD. **Ignored by `npx skills`.** Lets us reason about local-vs-upstream divergence without re-running git. |
| `parentUrl` | Monorepo skills only — the parent repo cloned once into `_parents/<owner>/<repo>/`, with this skill symlinked in from `skillPath`. Absent for standalone (single-repo) skills. |
| `readOnly` | `true` for a monorepo consumed read-only (e.g. `anthropics/skills`); `skill push` refuses it. **Omitted (falsey) for an *owned* monorepo** — see below. |

Skills are sorted alphabetically on write. Unknown fields are preserved on round-trip so the file stays forward-compatible with both upstream additions and our own future fields.

### Owned monorepos (writable)

A monorepo is **owned** when its parent owner is `ajanderson1` (case-insensitive, per `is_owned_owner()`), or when `skill add --owned` is passed. An owned-monorepo entry carries `parentUrl` + `skillPath` but **no** `readOnly` field, so it is writable:

- `skill push <slug>` stages and commits **only the skill's `skillPath` subpath** inside the shared parent clone (a dirty sibling subpath is not swept in) and opens one subpath-scoped PR per push against the parent's base ref.
- `skill status <slug>` reports dirty state scoped to that subpath and marks it `<slug>\t<state> (owned)`.
- `skill update <slug>` merges (never resets), so local owned edits survive.

Read-only consumption of *others'* monorepos is unchanged: those entries keep `readOnly: true` and `skill push` still refuses them.

### Re-homing standalone skills into an owned monorepo

> The dedicated `skill migrate-to-monorepo` command was removed — it only produced
> the flat `skills/<slug>` subpath and never the nested/root shapes the monorepo
> feature actually supports, so it wasn't fit for real consolidations. Re-home by
> hand instead: fold each skill into the monorepo (e.g. `git subtree`), then
> `skill remove <slug>` + `skill add <owner>/<repo>/<skill-subpath> --owned`
> (re-`install -p` per project). The entry rewrites from own-repo shape to
> owned-monorepo-subpath shape:

| | own-repo (before) | owned-monorepo-subpath (after) |
|---|---|---|
| `source` | `ajanderson1/<slug>-skill` | `ajanderson1/<parent-repo>` |
| `skillPath` | `SKILL.md` | `<skill-subpath>` (e.g. `<slug>` at repo root, or `skills/<slug>`) |
| `parentUrl` | absent | set to the parent repo URL |
| `readOnly` | absent | absent (owned → writable) |

After re-adding, the canonical at `~/.agent-toolkit/skills/<slug>/` is a symlink into the shared `_parents/<owner>/<parent-repo>/<skill-subpath>` clone, and harness symlinks are re-projected.

## Interop with `npx skills`

A lock file written by `agent-toolkit-cli skill add` is parseable by `npx skills@latest ls`. We have a smoke test that confirms this (`tests/test_cli/test_skill_interop.py`); it runs whenever `npx` is available on `$PATH`.

The reverse also holds: a skill installed via `npx skills add owner/repo` lands in `~/.agent-toolkit/skills/<slug>/` and `~/.agent-toolkit/skills-lock.json`, where our `skill list` / `skill status` will pick it up.

## What this design intentionally does **not** do

- **Auto-push** of self-improvements. There is no session-end hook that pushes for you. Run `skill push` manually (or wire it into your own workflow). A follow-on design will revisit auto-push once the manual flow is proven.
- **Other asset types in this lock.** This page covers skills only. Agent, mcp, pi-extension, and instructions are first-class built asset types now, each with its own install machinery and lock file (`agents-lock.json`, `mcps-lock.json`, …) — see the [CLI reference](cli.md). They are not recorded in `skills-lock.json`.
- **Submitting to the public skills.sh catalogue.** Your repos can be private; we use the same lock format and addressing scheme without depending on the catalogue.

## Where to look next

- Spec: `docs/superpowers/specs/2026-05-21-agent-toolkit-lock-file-migration-design.md`
- Plan (TDD task breakdown): `docs/superpowers/plans/2026-05-21-skill-lock-file-migration.md`
- Upstream `vercel-labs/skills` source: <https://github.com/vercel-labs/skills>
