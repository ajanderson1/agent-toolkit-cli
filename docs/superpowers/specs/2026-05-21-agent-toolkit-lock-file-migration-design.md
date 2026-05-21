# Agent Toolkit — Lock-File Migration (Option A) Design

**Status:** Draft, pending user review.
**Date:** 2026-05-21.
**Supersedes:** sidecar-metadata-discovery (2026-05-19), skill-sidecar-shape (2026-05-20) for the skill asset kind; later for all kinds.

## Goal

Re-platform `agent-toolkit-cli` and `agent-toolkit-tui` onto a `skills.sh`-derived model in which **every asset — first-party and third-party — is its own upstream git repository**, addressed and reconciled through a lock file. The `agent-toolkit` monorepo's role as content SSOT dissolves; the lock file becomes the SSOT for "what is installed, where it came from, and how it relates to upstream."

This is **Option A** as scoped during brainstorming, with explicit narrowing during open-question review: **only the skill asset kind migrates in this design.** The other six asset kinds (agent, command, mcp, hook, plugin, pi-extension) remain on the current monorepo + sidecar + walker model. A Phase 2 follow-on design will revisit each of those kinds individually; some (mcp, hook, plugin) have structural shape that does not map cleanly to per-asset repos and may end up staying monorepo-resident permanently.

## Motivation

The current sidecar model fights drift instead of preventing it. Two metadata locations (`SKILL.md` frontmatter + `<slug>.toolkit.yaml`) can disagree; the walker has to infer install state from disk shape; the monorepo cannot version individual skills independently; and there is no mechanism for the self-improvement use case — where an agent edits a skill in-place during a session and the improvement must (a) not be silently overwritten by `update`, and (b) propagate back to upstream so other machines see it.

`skills.sh` solves the install/projection problem cleanly (one canonical clone, per-harness symlinks, lock file as SSOT) but does not solve self-improvement: its `update` overwrites local edits. Adopting its model verbatim and adding a merge-aware update path is the smallest viable design that gets us both robustness and self-improvement.

## Design

### 1. Asset = upstream git repo

Every asset is a standalone git repository under the user's GitHub account (private by default). First-party assets (authored by the user) and third-party assets (forks of upstream) are handled identically. There is no special case.

Per-asset repos live at e.g. `github.com/ajanderson1/<slug>`. The `agent-toolkit` monorepo retains no `skills/`, `agents/`, `commands/`, etc. directories of source-of-truth content. It may continue to exist as a curated catalogue (a list of repos), but is no longer where assets are authored.

### 2. On-disk layout (mimics `skills.sh` verbatim)

```
~/.agents/skills/<slug>/             # canonical: a real `git clone` of upstream
  .git/                              # yes, .git present per asset
  SKILL.md
  ...
~/.agents/.skill-lock.json           # global lock (skills.sh-compatible)

~/.claude/skills/<slug>              # symlink -> ~/.agents/skills/<slug>
~/.codex/skills/<slug>               # symlink -> ~/.agents/skills/<slug>
...

# Per-project mirror when -p / --project is in effect:
./.agents/skills/<slug>/             # canonical for this project
./skills-lock.json                   # project lock, committed to git
```

Per-harness symlinks remain **projections**, not sources of truth. Editing the canonical clone updates every harness simultaneously.

In this design the layout applies **to the skill asset kind only**. The other six kinds retain their current on-disk layout under the monorepo and the existing symlink projection. The Phase 2 design will decide per-kind whether the same layout extends.

### 3. Lock file format

`skills-lock.json` (project) and `.skill-lock.json` (global) follow `skills.sh`'s schema verbatim, with **one additive field**:

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

`upstreamSha` is the last-known upstream commit at the most recent successful sync. `localSha` is our additive field — the working copy's HEAD. `skills.sh` ignores unknown fields, so a lock file written by `agent-toolkit-cli` remains parseable by `npx skills`.

### 4. Merge-aware update (the core differentiator)

Because the canonical clone is a real git checkout, `update <slug>` is a sequence of stock git commands:

```
cd ~/.agents/skills/<slug>
git fetch origin
git merge origin/<ref>             # fast-forward when clean; 3-way merge otherwise
```

Outcomes:

- **Clean working copy, upstream advanced**: fast-forward. No prompts.
- **Local commits, no upstream change**: no-op.
- **Local commits, upstream advanced, no overlap**: merge commit created automatically.
- **Local commits, upstream advanced, overlap**: real merge conflict. Surfaced via `git status` and `<<<<<<<` markers in the working copy. CLI exits non-zero with the slug name and the conflict file list.

No bespoke merge code. `git merge-file` and `git merge` carry all the weight. Conflicts are real git conflicts, resolvable with any standard tool.

### 5. Push (self-improvement flow)

```
cd ~/.agents/skills/<slug>
[ "$(git status --porcelain)" = "" ] && exit 0    # nothing to push
git add -A
git commit -m "self-improvement: <timestamp>"
git push origin <ref>
```

Triggered either by explicit `agent-toolkit-cli push <slug>` or by an end-of-session hook (optional, opt-in). Idempotent: clean working copy → no-op.

### 6. CLI surface

A new `skill` subcommand group is added, parallel to but separate from the existing verbs:

```
agent-toolkit-cli skill add <source> [-p|--project] [-g|--global] [--ref <ref>]
agent-toolkit-cli skill update [<slug>...] [-p|--project] [-g|--global]
agent-toolkit-cli skill push   [<slug>...] [-p|--project] [-g|--global]
agent-toolkit-cli skill remove <slug>...   [-p|--project] [-g|--global]
agent-toolkit-cli skill list   [-p|--project] [-g|--global]
agent-toolkit-cli skill status [<slug>...]      # clean / dirty / behind / conflicted
```

The existing verbs (`link`, `unlink`, `list`, `diff`, `check`, `fix`, `doctor`, `inventory`, `ingest`, `new`, `tui`) and the two-flag contract (`--toolkit-repo`, `--project`) remain in place for the six non-migrating asset kinds. They continue to operate against the monorepo SSOT exactly as today.

The legacy `link/unlink/list` paths **stop accepting `skill:<slug>`** once the skill migration completes. Asset-kind boundary is enforced at the CLI: skill operations go through `skill ...`; other kinds go through the legacy verbs.

### 7. Frontmatter / metadata

The `.toolkit.yaml` sidecar is **eliminated for the skill asset kind only**. Skill metadata lives in `SKILL.md` frontmatter. `skills.sh` requires only `name` + `description`; our additional fields (`apiVersion`, `metadata.lifecycle`, `spec.harnesses`, etc.) are added as extra frontmatter keys. `skills.sh` ignores unknown keys; our CLI reads them.

For the six non-migrating kinds, the sidecar model and the inline-vs-sidecar mutex check **remain unchanged**.

The schema (`asset-frontmatter.v1alpha2.json`) remains, vendored at the same two paths (`schemas/` and `src/agent_toolkit_cli/_schemas/`). Its skill branch tightens to "inline only"; its other branches are untouched.

### 8. TUI

The TUI gains a **skill-specific data path**: when the skill tab is active, contents come from the lock file plus `git status`/`git rev-list` against each canonical clone. New per-row state column: `clean / dirty / behind / ahead / conflicted`. New per-row actions: update, push, remove, open-in-editor.

Other tabs (agent, command, mcp, hook, plugin, pi-extension) continue to be driven by the existing walker against the monorepo SSOT. No changes to their shape or data model.

The kinds sidebar and asset grid layout are unchanged.

### 9. Migration (skills only, slug-incremental)

1. **Proof-of-concept first.** A throwaway repo `ajanderson1/test-migration-skill` is created from scratch (not extracted from the monorepo) and used to validate every CLI verb (`add`, `update`, `push`, `remove`, `status`, `list`) end-to-end before any real skill is touched.
2. **Real skills extracted one at a time.** Each skill in `~/GitHub/agent-toolkit/skills/` is extracted to its own repo via `git filter-repo --path skills/<slug> --path-rename skills/<slug>:` (preserves history). New repos created with `gh repo create ajanderson1/<slug> --private --source=. --push`. Lock file populated by re-running `agent-toolkit-cli skill add ajanderson1/<slug>` for each. The CLI tolerates a partially-migrated state: some skills resolved via the lock file, others still resolved via the legacy walker against the monorepo.
3. **Legacy skill code path removed.** Once the last skill migrates, the walker's skill discovery, the skill sidecar mutex check, and any skill-specific monorepo paths are deleted in a single follow-up commit. Other kinds are untouched.
4. **Phase 2 (separate spec).** Each of the six remaining kinds is revisited individually: does it benefit from the lock-file model, or stay monorepo-resident? No commitment in this design.

### 10. Robustness invariants (mirrors `skills.sh` + additions)

1. **Lock file is the single source of truth for installation state.** No filesystem inference.
2. **Operations are idempotent.** `add` twice = `add` once. `update` on a clean, up-to-date install = no-op.
3. **No magic detection.** If a slug is not in the lock file, it is not installed, regardless of what is on disk.
4. **One canonical location per scope.** Global = `~/.agents/`, project = `./.agents/`. Per-harness paths are symlinks only.
5. **Symlinks for projections, content in one place.** Editing the canonical updates every harness.
6. **Failure modes are git failure modes.** Conflicts, auth failures, ref-not-found — all surface as real git errors with stderr passthrough.

## Decisions (closed during review)

1. **Non-skill kinds parked.** Agents, commands, MCPs, hooks, plugins, pi-extensions remain on the current model in this design. A Phase 2 follow-on spec revisits each individually.

2. **Disk cost accepted.** ~3–15 MB per scope for per-skill `.git/` directories is acceptable. Full clones (not shallow) — no `--depth=1` machinery in this design.

3. **Auto-push deferred.** This design ships with manual `agent-toolkit-cli skill push` only. End-of-session auto-push hook is out of scope and will get its own spec once the manual flow is proven.

4. **`skills.sh` interop is a goal.** `npx skills add ajanderson1/<slug>` MUST work against our skill repos. CI includes a smoke test that installs one of our skills via the upstream CLI and verifies the result.

5. **Proof-of-concept is a throwaway repo.** `ajanderson1/test-migration-skill`, created from scratch, validates every CLI verb before any real skill is extracted. The first real extraction is deferred to a separate decision after the POC passes.

## Non-goals (in this design)

- Submitting to the public `skills.sh` catalogue. Private repos remain private; we use the addressing scheme and lock format but not the public index.
- Wrapping the `npx skills` CLI. We re-implement in Python so we are not exposed to upstream breakage.
- Migrating any non-skill asset kind. Phase 2 territory.
- Auto-push of self-improvements. Manual `skill push` only in this design.
- Multi-user / team sync of self-improvements. Self-improvements flow per-user via the user's own forks; team-wide propagation is out of scope.
- Shallow clones / disk-cost optimisation. Full clones; can revisit later if disk becomes a real problem.

## Success criteria

- `agent-toolkit-cli skill add ajanderson1/test-migration-skill -g` followed by `skill update`, `skill push`, and `skill remove` works end-to-end against the throwaway POC repo without manual git intervention in the clean case.
- A diverged-edit scenario on the POC repo (machine A edits `SKILL.md`, machine B independently edits the same lines, both push and pull) surfaces a real `git` merge conflict in the working copy, resolvable with stock tools.
- The TUI's skill tab displays per-asset state correctly: clean / dirty / behind / ahead / conflicted.
- `npx skills list` and `npx skills add ajanderson1/test-migration-skill` (the upstream `skills.sh` CLI) both succeed against a repo and a lock file written by `agent-toolkit-cli`. Verified by a CI smoke test.
- After all real skills are extracted: the monorepo's `skills/` directory is empty (or removed); the walker no longer discovers skills; the sidecar mutex check no longer applies to skills.
- The six non-skill asset kinds continue to operate via their existing code paths with no regressions. Existing test suites for those kinds pass unchanged.
