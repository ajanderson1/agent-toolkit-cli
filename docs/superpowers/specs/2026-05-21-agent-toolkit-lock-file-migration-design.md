# Agent Toolkit — Lock-File Migration (Option A) Design

**Status:** Draft, pending user review.
**Date:** 2026-05-21.
**Supersedes:** sidecar-metadata-discovery (2026-05-19), skill-sidecar-shape (2026-05-20) for the skill asset kind; later for all kinds.

## Goal

Re-platform `agent-toolkit-cli` and `agent-toolkit-tui` onto a `skills.sh`-derived model in which **every asset — first-party and third-party — is its own upstream git repository**, addressed and reconciled through a lock file. The `agent-toolkit` monorepo's role as content SSOT dissolves; the lock file becomes the SSOT for "what is installed, where it came from, and how it relates to upstream."

This is **Option A** as scoped during brainstorming: skills move first, but all seven asset kinds eventually adopt the same model. Non-skill kinds with awkward fit (MCPs, hooks — see "Open questions") get explicit per-kind adapters that translate between the lock-file model and their native install surface, rather than being permanently exempted.

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

The same layout pattern extends to other asset kinds where folder-shaped (`agents/`, `commands/`, `plugins/`, `pi-extensions/`). For kinds that are not folder-shaped (`mcps/`, `hooks/`), see "Open questions" below.

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

The CLI converges on a verb set parallel to `skills.sh`, generalised across asset kinds:

```
agent-toolkit-cli add <source> [-p|--project] [-g|--global] [--ref <ref>]
agent-toolkit-cli update [<slug>...] [-p|--project] [-g|--global]
agent-toolkit-cli push   [<slug>...] [-p|--project] [-g|--global]
agent-toolkit-cli remove <slug>...   [-p|--project] [-g|--global]
agent-toolkit-cli list   [-p|--project] [-g|--global] [--kind <kind>]
agent-toolkit-cli status [<slug>...]      # clean / dirty / behind / conflicted
agent-toolkit-cli doctor                  # consistency check between lock + disk
```

The current `--toolkit-repo` flag is **deprecated and removed** once migration completes — there is no longer a toolkit repo to point at. The `--project` flag remains; its semantics narrow to "which project's lock file." Asset kind is inferred from the asset's own `metadata.kind` (carried in `SKILL.md`-equivalent frontmatter) and from the lock-file entry; no `<kind>:<slug>` syntax is needed at the CLI for the common path.

### 7. Frontmatter / metadata

The `.toolkit.yaml` sidecar is **eliminated** for all asset kinds that adopt the lock-file model. Asset metadata lives in the asset's primary file (`SKILL.md`, `AGENT.md`, command `.md`, etc.) as YAML frontmatter. `skills.sh` requires only `name` + `description`; our additional fields (`apiVersion`, `metadata.lifecycle`, `spec.harnesses`, etc.) are added as extra frontmatter keys. `skills.sh` ignores them; our CLI reads them.

The schema (`asset-frontmatter.v1alpha2.json`) remains, and remains vendored at the same two paths (`schemas/` and `src/agent_toolkit_cli/_schemas/`). Its scope tightens from "validates sidecar OR inline" to "validates inline only." The mutex check disappears with the sidecar.

### 8. TUI

The TUI's data model switches from "walker reads monorepo state" to "reader reads lock file + per-asset working copy git status." Per-kind tabs remain but their contents come from the lock file rather than the walker. New per-row state column: `clean / dirty / behind / ahead / conflicted`, derived from `git status` and `git rev-list` against the working copy.

Actions surfaced in the TUI: update, push, remove, open-in-editor. The TUI is otherwise unchanged in shape — same kinds sidebar, same asset grid.

### 9. Migration (phased, asset-kind by asset-kind)

1. **Skills first.** ~30 skills currently in `~/GitHub/agent-toolkit/skills/`. Each extracted to its own repo via `git filter-repo --path skills/<slug> --path-rename skills/<slug>:` (preserves history). New repos created with `gh repo create ajanderson1/<slug> --private --source=. --push`. Lock file populated by re-running `agent-toolkit-cli add ajanderson1/<slug>` for each.
2. **Agents, commands, plugins, pi-extensions.** Same extraction pattern. Folder-shaped, no transformation needed.
3. **MCPs and hooks.** See "Open questions."
4. **Old code paths removed.** Walker, sidecar discovery, `--toolkit-repo` flag, the monorepo's `skills/` etc. directories, schema's sidecar branch — all deleted once the corresponding kind has finished migrating.

Migration is **asset-kind atomic** but **slug-incremental within a kind**: within the skills kind, individual skills migrate one at a time and the CLI tolerates a partially-migrated state (some skills resolved via lock file, others still resolved via the legacy walker against the monorepo). Once the last slug in a kind migrates, the legacy code path for that kind is deleted in a single follow-up commit. No kind ever runs both code paths post-migration.

### 10. Robustness invariants (mirrors `skills.sh` + additions)

1. **Lock file is the single source of truth for installation state.** No filesystem inference.
2. **Operations are idempotent.** `add` twice = `add` once. `update` on a clean, up-to-date install = no-op.
3. **No magic detection.** If a slug is not in the lock file, it is not installed, regardless of what is on disk.
4. **One canonical location per scope.** Global = `~/.agents/`, project = `./.agents/`. Per-harness paths are symlinks only.
5. **Symlinks for projections, content in one place.** Editing the canonical updates every harness.
6. **Failure modes are git failure modes.** Conflicts, auth failures, ref-not-found — all surface as real git errors with stderr passthrough.

## Open questions

These are real design questions that affect the implementation plan. They must be closed before `/writing-plans` is invoked.

1. **MCPs are not folders.** An MCP is a single block in `~/.codex/config.toml` (or equivalent), not a directory with a markdown file. Does an MCP "asset" become its own tiny repo containing just a `mcp.toml` (or similar manifest) + a `README.md`, which the CLI then translates into the target config file? Or do MCPs stay monorepo-resident permanently as a special case, addressed by name only in the lock file (no upstream)?

2. **Hooks are settings.json injections.** Same shape problem as MCPs. A hook is a JSON object inserted into `~/.claude/settings.json`. Becoming its own repo means the repo contains a `hook.json` + `README.md` and the CLI does the injection. Worth confirming this is the intent before specifying.

3. **Plugins (Claude-only).** Currently declarative via `installed_plugins.json` + `known_marketplaces.json`. Likely closer to MCPs/hooks than to skills. Same question.

4. **Per-skill `.git/` directories — disk cost.** ~30 skills × ~100–500 KB per `.git/` = ~3–15 MB per scope, doubled if global + project both populated. Acceptable, but worth naming.

5. **Auto-push policy.** The end-of-session hook that pushes self-improvements: opt-in, opt-out, or unimplemented in this design and deferred to a follow-on?

6. **`agent-toolkit-cli` vs. `npx skills` interop**. Goal stated as bit-compatible lock file. Do we also want `npx skills add ajanderson1/<slug>` to work against our repos? (Mostly automatic given the layout, but worth confirming as a non-goal vs. goal.)

7. **First repo extraction order.** Migration plan calls for skills first, but which skill goes first as the proof-of-concept? `journal` (frequently edited, exercises self-improvement) or `aj-workflow` (simpler, fewer dependencies)?

## Non-goals (in this design)

- Submitting to the public `skills.sh` catalogue. Private repos remain private; we use the addressing scheme and lock format but not the public index.
- Wrapping the `npx skills` CLI. We re-implement in Python so we are not exposed to upstream breakage.
- Migrating MCPs / hooks / plugins concurrently with skills. They land in a follow-on design once the skill path is proven.
- Multi-user / team sync of self-improvements. Self-improvements flow per-user via the user's own forks; team-wide propagation is out of scope.

## Success criteria

- Every skill currently in the monorepo is extracted to its own repo with history preserved.
- `agent-toolkit-cli add ajanderson1/journal -g` followed by `agent-toolkit-cli update journal` and `agent-toolkit-cli push journal` works end-to-end without manual git intervention in the clean case.
- A diverged-edit scenario (machine A edits SKILL.md, machine B independently edits the same lines, both push and pull) surfaces a real git merge conflict in the working copy, resolvable with stock tools.
- The TUI displays per-asset state correctly: clean / dirty / behind / ahead / conflicted.
- `npx skills list` (the upstream `skills.sh` CLI) successfully reads a lock file written by `agent-toolkit-cli`.
- `~/.toolkit-repo` / `--toolkit-repo` no longer appears anywhere in the codebase for migrated kinds.
- The sidecar file format no longer exists for migrated kinds; schema's sidecar branch removed.
