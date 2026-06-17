# Skills

The `skill` [asset type](../glossary.md#asset-type) manages reusable skill folders (a
`SKILL.md` plus supporting files) and projects them into every harness you
use. The lock file and layout are byte-compatible with
[`vercel-labs/skills`](https://github.com/vercel-labs/skills).

## How it works

Skills live once in the [library](../glossary.md#library)
(`~/.agent-toolkit/skills/<slug>`, a git clone of the skill's source repo) and
are [projected](../glossary.md#projection) by symlink into each harness's
skills directory — `.claude/skills/`, `.gemini/skills/`, and so on. Harnesses
that read the [general](../glossary.md#general) directory (`.agents/skills`)
need no per-harness symlink at all.

- **Lock file:** `skills-lock.json` (project) / `~/.agent-toolkit/skills-lock.json` (global)
- **Source pinning:** each entry records repo, `skillPath`, `ref`, and the
  resolved SHA
- **Scope:** all verbs default to global outside a project; `skill add` is
  global-only by construction

### Monorepo skills

A source can name *one skill inside a larger repo* rather than a repo whose
root is the skill — see [monorepo skill](../glossary.md#monorepo-skill). You
reach one three ways:

```bash
agent-toolkit-cli skill add owner/repo/path/to/skill   # explicit subpath
agent-toolkit-cli skill add owner/repo --skill <name>  # match SKILL.md name:
```

These take a different path from a single-repo add:

- **Shared parent clone.** The parent repo is cloned **shallow** (only one
  subpath's tree is used, so its full history is waste) into the
  [`_parents/` cache](../glossary.md#parents-cache) —
  `~/.agent-toolkit/_parents/<owner>/<repo>[@<ref>]/`. Every skill from the
  same parent reuses that one clone.
- **Symlinked canonical.** The library canonical
  `~/.agent-toolkit/skills/<slug>` is a **symlink** into `parent/<subpath>`,
  not its own clone (it falls back to a copy only if symlinking fails).
- **Pinned to parent HEAD.** The lock entry records `parentUrl`, the
  `skillPath` subpath, and the parent's HEAD as `upstreamSha`; a SHA pin is
  ignored for monorepo adds.
- **Project scope re-clones the parent** into a project-local `_parents/`
  cache so removing a project skill never touches the global cache or the
  project tree.

**Ownership decides whether `skill push` works.** The parent is
[*owned*](../glossary.md#owned) (writable) when its owner is a known owned
owner or you pass `--owned`; otherwise the lock entry is marked `readOnly`.
`skill push` opens a PR against the parent for an owned skill — committing only
that skill's subpath, so a dirty sibling in the shared clone is left alone —
and **refuses** for a read-only one.

## Support across harnesses

Universal — every harness in the catalog has a skills directory, so the
[compatibility matrix](../matrix.md) shows a full ✅ column. 14 harnesses read
the general `.agents/skills` directory directly (including
[Codex](../harnesses/codex.md), [Cursor](../harnesses/cursor.md),
[Gemini CLI](../harnesses/gemini-cli.md), [OpenCode](../harnesses/opencode.md)).

## CLI

```bash
agent-toolkit-cli skill add <source>     # clone into the library + lock
agent-toolkit-cli skill install          # project into harnesses
agent-toolkit-cli skill update           # fetch + fast-forward
agent-toolkit-cli skill push             # publish local edits upstream
agent-toolkit-cli skill doctor           # reconcile projections
```

See also: [Instructions](instructions.md) · [Agents](agents.md) ·
[Glossary](../glossary.md)


## Commands relationship

Use [commands](commands.md) for lightweight slash-command prompts. Use skills when the workflow needs richer instructions, references, or tool code.
