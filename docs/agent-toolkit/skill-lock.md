# `skill` subcommand — lock-file-driven skill management

## Overview

The `skill` subgroup manages skills using a **per-skill upstream git repo + lock file** model, mirroring the on-disk layout and lock-file schema of [`vercel-labs/skills`](https://github.com/vercel-labs/skills). Lock files written by this CLI are readable by `npx skills`, and skills installed by either tool live in the same canonical directory.

Unlike the legacy walker-driven path used for the other six asset kinds (agent, command, mcp, hook, plugin, pi-extension), the skill path keeps no metadata in the monorepo. Each skill is a standalone git repository; the lock file is the SSOT for installation state.

The defining behaviour: **`update` is a merge-aware operation.** Local edits to a skill (the "self-improvement" case) survive a pull from upstream when there is no overlap, and surface as real `git` merge conflicts when there is.

## On-disk layout

### Global scope (`-g` / `--global`)

```
~/.agents/skills/<slug>/             ← canonical: a real `git clone` of upstream
  .git/
  SKILL.md
  ...
~/.agents/.skill-lock.json           ← global lock

~/.claude/skills/<slug>              → symlink → ~/.agents/skills/<slug>
~/.codex/skills/<slug>               → symlink
~/.config/opencode/skills/<slug>     → symlink
~/.gemini/skills/<slug>              → symlink
~/.pi/skills/<slug>                  → symlink
```

### Project scope (`-p` / `--project`, default)

```
<project>/.agents/skills/<slug>/     ← canonical clone
<project>/skills-lock.json           ← project lock (commit this to git)

<project>/.claude/skills/<slug>      → symlink → .agents/skills/<slug>
...
```

The per-harness directories are **projections** — editing the canonical updates every harness instantly.

## Command reference

All `skill` verbs accept `-g` (global) or `-p` (project, default), and `--harness <name>` (repeatable; defaults to all supported).

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
$EDITOR ~/.agents/skills/journal/SKILL.md
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

The lock file is JSON, schema-compatible with `vercel-labs/skills`'s `skills-lock.json`. Project lock is at `<project>/skills-lock.json`; global lock is at `~/.agents/.skill-lock.json`.

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

Skills are sorted alphabetically on write. Unknown fields are preserved on round-trip so the file stays forward-compatible with both upstream additions and our own future fields.

## Interop with `npx skills`

A lock file written by `agent-toolkit-cli skill add` is parseable by `npx skills@latest ls`. We have a smoke test that confirms this (`tests/test_cli/test_skill_interop.py`); it runs whenever `npx` is available on `$PATH`.

The reverse also holds: a skill installed via `npx skills add owner/repo` lands in `~/.agents/skills/<slug>/` and `~/.agents/.skill-lock.json`, where our `skill list` / `skill status` will pick it up.

## What this design intentionally does **not** do

- **Auto-push** of self-improvements. There is no session-end hook that pushes for you. Run `skill push` manually (or wire it into your own workflow). A follow-on design will revisit auto-push once the manual flow is proven.
- **The other six asset kinds.** Agent, command, mcp, hook, plugin, and pi-extension were managed by the pre-v2 CLI commands removed in #160; the frozen surface lives at the `v1.0.0` tag. v2-native replacements (if any) land per-command — see the [#160 tracker issue](https://github.com/ajanderson1/agent-toolkit-cli/issues/163) for status.
- **Submitting to the public skills.sh catalogue.** Your repos can be private; we use the same lock format and addressing scheme without depending on the catalogue.

## Where to look next

- Spec: `docs/superpowers/specs/2026-05-21-agent-toolkit-lock-file-migration-design.md`
- Plan (TDD task breakdown): `docs/superpowers/plans/2026-05-21-skill-lock-file-migration.md`
- Upstream `vercel-labs/skills` source: <https://github.com/vercel-labs/skills>
