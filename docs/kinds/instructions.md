# Instructions

The `instructions` [kind](../glossary.md#kind) manages one canonical
`AGENTS.md` per [scope](../glossary.md#scope) and makes every harness read it —
your root instruction context written once, satisfied everywhere.

## How it works

Most harnesses read `AGENTS.md` natively, so the canonical file satisfies them
with zero work. The handful that read a fixed own-name file instead (e.g.
`CLAUDE.md`, `GEMINI.md`) get a same-name
[pointer symlink](../glossary.md#mechanism) → `AGENTS.md`. There is no
translate step and no config mutation for this kind — pointer symlinks only,
and `install` never clobbers a real file or a foreign symlink.

- **Canonical file:** `./AGENTS.md` (project scope) or
  `~/.agent-toolkit/AGENTS.md` (global scope)
- **Lock file:** `instructions-lock.json` records which pointers exist
- **Doctor:** reconciles pointers, and can adopt an unmanaged `CLAUDE.md`
  (rename → `AGENTS.md`, symlink the old name)

## Support across harnesses

Per the [compatibility matrix](../matrix.md): **39 native** readers ·
**7 pointer-symlink** harnesses (Augment, [Claude Code](../harnesses/claude-code.md),
CodeBuddy, [Gemini CLI](../harnesses/gemini-cli.md), iFlow CLI, Replit,
Tabnine CLI) · 4 gaps · 2 not applicable · 2 unknown. The 39 native readers
are this kind's [general](../glossary.md#general) set — always satisfied, no
toggle.

## CLI

```bash
agent-toolkit-cli instructions install   # canonical + pointers
agent-toolkit-cli instructions list      # per-harness verdicts
agent-toolkit-cli instructions doctor    # reconcile / adopt
```

See also: [Skills](skills.md) · [Agents](agents.md) ·
[Glossary](../glossary.md)
