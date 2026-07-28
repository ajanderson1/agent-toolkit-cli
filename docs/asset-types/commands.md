# Commands

The `command` asset type manages reusable slash-command prompts. Commands live in the toolkit library as `COMMAND.md` folders and are projected into harness-specific command or prompt-template locations.

- **Lock file:** `commands-lock.json`
- **Canonical entrypoint:** `COMMAND.md`
- **Portable argument recommendation:** `$ARGUMENTS`
- **Default install targets:** `standard`, Pi, Gemini CLI
- **Optional lock field:** `harnesses` — optional projection state written only after a successful mutation; legacy v1 locks without it remain readable (non-mutating reads never backfill)

## Standard slot (#482)

One toolkit-owned Markdown file serves every verified shared-path reader:

| Scope | Path | Readers |
|---|---|---|
| global | `~/.claude/commands/<slug>.md` | Claude Code, Neovate |
| project | `<project>/.claude/commands/<slug>.md` | Claude Code, Neovate, Devin CLI (**as an imported skill**) |

- `standard` is a real install target; `claude-code` normalizes to `standard` because both names resolve to the same destination.
- Only verified readers are included. OpenCode and Kode remain excluded pending merged/deterministic upstream evidence (see the research note).
- Devin imports project commands **as skills** — do not claim an identical slash-command menu.
- Pi and Gemini remain separate native projections; Codex stays explicit/global-only and is never a default or TUI column.

## Harness evidence

| Harness | First-cut support | Projection | Notes |
|---|---:|---|---|
| Standard | ✅ | `.claude/commands/<slug>.md` (shared) | Claude Code + Neovate globally; + Devin (as skill) in projects. |
| Claude Code | ✅ via Standard | same shared slot | Alias of `standard`; no second file. |
| Pi | ✅ | `~/.pi/agent/prompts/<slug>.md`, `<project>/.pi/prompts/<slug>.md` | Uses prompt templates. |
| Gemini CLI | ✅ | `~/.gemini/commands/<slug>.toml`, `<project>/.gemini/commands/<slug>.toml` | `$ARGUMENTS` becomes `{{args}}`; `!{` and `@{` are preserved with a warning. |
| Codex | ✅ explicit only | `~/.codex/prompts/<slug>.md` | Custom prompts are deprecated and global-only, so `codex` is never in the default install fan-out. |
| Cursor | — | researched gap | Forum evidence mentions `.cursor/commands`, but first cut ships no adapter without deterministic validation evidence. |

## Package shape

A command source is a git repo or monorepo subpath containing a regular `COMMAND.md` file:

```text
my-command/
└── COMMAND.md
```

Supporting files may live beside `COMMAND.md` for authorship, but first-cut projections install only the prompt file. Treat supporting files as source-only and non-portable.

## CLI

```text
agent-toolkit-cli command add <source> [--slug <slug>] [--ref <ref>]
agent-toolkit-cli command install <slug> [-g|-p] [--harnesses standard,pi,gemini-cli]
agent-toolkit-cli command uninstall <slug> [-g|-p] [--harnesses <h>[,<h>...]]
agent-toolkit-cli command list [-g|-p] [--json]
agent-toolkit-cli command status|update|push|import|reset|remove|doctor ...
```

- Default install: `standard,pi,gemini-cli`.
- `--harnesses claude-code` normalizes to `standard`.
- No-flag uninstall is maximal (`standard` + all concrete targets) so legacy installs are cleaned.
- `command doctor` is read-only: it reports missing/untracked Standard projections and invents no lock metadata for manual canonicals.
- The Commands TUI shows Standard first (`Standard (2)` globally, `Standard (3)` in projects).

Slugs are path stems, not paths. The CLI rejects traversal, absolute paths, leading dots, and slash/backslash separators before touching the filesystem.

## Safety

- Install refuses unmanaged destination files and foreign symlinks.
- Standard adopts byte-identical legacy Claude files / canonical-resolving symlinks by writing a Standard sidecar without rewriting content.
- Uninstall removes only toolkit-owned files, Standard-owned slots, or sentinel-less byte-identical legacy matches.
- Gemini projections carry `.attk` sidecars with ownership metadata and generated-content hashes.
- `COMMAND.md` must be a regular file, not a symlink.
