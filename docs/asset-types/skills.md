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
- **Source pinning:** each entry records repo, `skill_path`, `ref`, and the
  resolved SHA
- **Scope:** all verbs default to global outside a project; `skill add` is
  global-only by construction

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
