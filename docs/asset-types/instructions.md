# Instructions

The `instructions` [asset type](../glossary.md#asset-type) shares one user-authored
`AGENTS.md` per [scope](../glossary.md#scope) across coding assistants. It has **no
installation lock**: the actual pointer symlink determines whether it is installed.
Manual links are recognized just like toolkit-created links.

## Canonical content and pointers

- **Project canonical:** `<project>/AGENTS.md`.
- **Global canonical:** `~/.agent-toolkit/AGENTS.md`.
- **Source:** user-owned content; canonical may itself link to a versioned file
  elsewhere. Install/uninstall never author or delete that content.
- **Pointer:** an assistant's expected file (for example `CLAUDE.md`) symlinked
  to canonical. Relative and chained links with the same resolved target count;
  matching text in a regular file does not.

Most assistants read project `AGENTS.md` natively. Compatibility readers get
own-name pointers. Codex, OpenCode and Pi remain native project readers but have
managed **global** pointer slots. See the [scope-aware matrix](../matrix.md).

Install creates only selected pointers (all supported slots by default), without
pruning other existing links. Correct links are idempotent. Real files,
directories and foreign symlinks are never overwritten. Uninstall removes owned
pointers at the selected scope, even when canonical is missing. Requested dependent
pointers are removed before their requested referents so the batch completes
without stranding a requested link. Each link's node identity and raw target are
rechecked before removal. Unrequested links are never removed or rewired; removing
only their intermediate may leave them dangling.

**Source-chain protection:** if canonical routes through a requested pointer —
for example `AGENTS.md → CLAUDE.md → user-source.md` — uninstall refuses the
whole batch before changing anything. The guard compares physical symlink-node
identities (not path spelling or final source identity), covering case/Unicode
aliases, multi-hop chains, directory components and TUI removals. Reorganize the source chain manually before uninstalling; the
toolkit never rewrites it to make removal possible.

Legacy `instructions-lock.json` / `instructions.lock` files are ignored and left
unchanged, even if malformed. No replacement registry is created.

## CLI

```bash
agent-toolkit-cli instructions install --harness claude-code
agent-toolkit-cli instructions install --scope global --harness pi
agent-toolkit-cli instructions list --scope global
agent-toolkit-cli instructions status
agent-toolkit-cli instructions doctor --no-fix
agent-toolkit-cli instructions uninstall --scope project
```

`status` inspects every supported pointer slot: `ok`, `missing` (uninstalled),
`broken` (owned pointer but canonical is unavailable), or `conflict` (foreign,
regular or unresolvable occupant). An absent uninstalled slot is not a doctor
finding, and a correct manual link needs no registration.

Doctor reports broken pointers and conflicts. Its existing **explicitly confirmed**
regular-file adoption can move a file to absent/empty canonical content or back it
up to `.pre-adopt.bak` when canonical already contains text. Content is never
merged; backups are never overwritten. A failed adoption restores the original
file. Foreign symlinks and protected canonical destinations remain report-only.
`--no-fix`, declined prompts and noninteractive invocation do not mutate files.

## Terminal interface

The Instructions grid derives its one row from the selected scope's canonical
file or occupied pointer slots, without reading a lock. The Source cell is the
canonical filename, not provenance or an installation record. Global-shadow
indicators are read-only and cannot populate a project row by themselves.

Save applies only explicit pointer intents. Assistants sharing one physical slot
also share its state; duplicate actions coalesce, opposing actions are refused.
If an I/O error leaves a partially applied batch, the grid reloads actual state
and keeps only unsatisfied edits for retry. Viewing or refreshing inventory never
creates or repairs pointers, source files, directories or installation records.

See also: [CLI reference](../agent-toolkit/cli.md) ·
[TUI reference](../agent-toolkit/tui.md) · [Lock files](../agent-toolkit/lock-files.md)
