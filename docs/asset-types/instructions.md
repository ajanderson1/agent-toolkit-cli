# Instructions

Examples use `atc`, the packaged CLI name; `agent-toolkit-cli` still works.
[Install/verify](../agent-toolkit/installation.md) ·
[Shell completion](../agent-toolkit/shell-completion.md). Root `atc update`
updates the **application**, not this asset; see [package updates](../agent-toolkit/updates.md).

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
  matching text in a regular file does not. Directory-entry aliases are checked
  by actual symlink-node identity, including case/Unicode aliases where the
  filesystem aliases them, rather than by string spelling alone.

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

## Latest host content

`pull` and `restore` explicitly author the **global canonical file** on macOS/Linux.
They are separate from pointer enablement. Older clients such as 7.3.1 need a
Toolkit package update before using these commands.

```bash
# Preview this host's latest instructions on main (the default).
atc instructions pull --source owner/repo --host atlas --dry-run

# Deploy after review; --replace is required if canonical already exists.
atc instructions pull --source owner/repo --host atlas --replace

# Automation must also opt into confirmation with --yes.
# Restore the previous bytes saved by the printed deployment ID.
atc instructions restore deploy-EXAMPLE --replace
```

Source is a repository-root HTTPS/SSH URL, `owner/repo` shorthand or an explicit
local Git repository path. Git authentication uses your existing helper/SSH setup;
do not put tokens in URLs. Local sources read committed objects, never dirty files.
The host is explicitly selected and lowercased, not inferred from the current
machine. Sources may export `AGENTS.<host>.md` at repository root or keep it under
`agents-instructions/` in a full workspace. Exactly one must exist; if both exist,
pull refuses the ambiguity. Only that host file becomes active; no other host
file is deployed. Fetch uses a temporary bare repository with shallow/blob filtering;
servers without filtering may transfer extra Git objects, but no checkout is kept.
Each pull defaults to the latest fetched `main`; no version numbers or tags are
needed. The resolved commit and SHA-256 are printed for traceability, not as a
manual version-selection requirement. For shared rollback, revert a source change
in Git, push, then pull the affected hosts again. Optional `--ref` overrides the
branch or selects a historical revision. Fetch/preview and deployment are explicit;
changing a TUI checkbox does not silently sync content.

`--dry-run` shows source, commit, digest and unified diff without creating global
files or directories. Otherwise confirmation is required (or explicit `--yes`).
Existing canonical content additionally requires `--replace`. Canonical symlinks,
nonregular files and linked deployment directories are refused even with these
flags; reorganizing such a source chain requires separate approval. New source
content must be a regular committed, nonempty UTF-8 file, at most 256 KiB, without
terminal control characters. Existing local content/backups are bounded to 1 MiB.

Before atomic canonical replacement, a unique private directory under
`~/.agent-toolkit/instructions-deployments/deploy-*` saves `AGENTS.md`,
`deployment.json` (source/ref/commit/hash for pulls), and `previous.md` when prior
content existed. Backups are never overwritten or automatically deleted. Restore
uses the selected directory's hash-checked previous content, creates a new backup,
and follows the same preview, replacement and confirmation rules. The first
creation has no previous content to restore. Restore provenance identifies the
prior deployment ID; it does not invent an upstream origin for user-authored bytes.

Receipts describe **prepared attempts**, not an authoritative active-version
registry: a failed final swap can leave a receipt while canonical remains unchanged.
Compare a receipt's `sha256` with canonical before claiming a content match; do not
assume the newest directory is active. Deployment writers serialize with a
filesystem-directory advisory mutex and recheck content since preview; arbitrary
editors do not participate in that mutex. Canonical replacement is atomic, not a
multi-file transaction or a guarantee against concurrent external edits/power loss.

These commands never enable/disable harnesses, change project instructions, or
create an Instructions installation lock. Enable the desired global pointers
separately using `install --scope global --harness NAME`. Existing pointers see the
new canonical bytes without recreation; start fresh agent sessions after changes.

## CLI

```bash
atc instructions install --harness claude-code
atc instructions install --scope global --harness pi
atc instructions list --scope global
atc instructions status
atc instructions doctor --no-fix
atc instructions uninstall --scope project
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
canonical filename, not provenance or an installation record. It does not list
host files or offer revision selection; use `pull` outside the TUI for that. Global-shadow
indicators are read-only and cannot populate a project row by themselves.

Save applies only explicit pointer intents. Assistants sharing one physical slot
also share its state; duplicate actions coalesce, opposing actions are refused.
If an I/O error leaves a partially applied batch, the grid reloads actual state
and keeps only unsatisfied edits for retry. Viewing or refreshing inventory never
creates or repairs pointers, source files, directories or installation records.

See also: [CLI reference](../agent-toolkit/cli.md) ·
[TUI reference](../agent-toolkit/tui.md) · [Lock files](../agent-toolkit/lock-files.md)
