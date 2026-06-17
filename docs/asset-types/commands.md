# Commands

The `command` asset type manages reusable slash-command prompts. Commands live in the toolkit library as `COMMAND.md` folders and are projected into harness-specific command or prompt-template locations.

- **Lock file:** `commands-lock.json`
- **Canonical entrypoint:** `COMMAND.md`
- **Portable argument recommendation:** `$ARGUMENTS`
- **Initial supported harnesses:** Claude Code, Pi, Gemini CLI, and explicit/deprecated Codex custom prompts

## Harness evidence

| Harness | First-cut support | Projection | Notes |
|---|---:|---|---|
| Claude Code | ✅ | `~/.claude/commands/<slug>.md`, `<project>/.claude/commands/<slug>.md` | Legacy slash commands; Claude skills are still preferred for richer workflows. |
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
agent-toolkit-cli command install <slug> [-g|-p] [--harnesses claude-code,pi,gemini-cli]
agent-toolkit-cli command uninstall <slug> [-g|-p] [--harnesses <h>[,<h>...]]
agent-toolkit-cli command list [-g|-p] [--json]
agent-toolkit-cli command status|update|push|import|reset|remove|doctor ...
```

Slugs are path stems, not paths. The CLI rejects traversal, absolute paths, leading dots, and slash/backslash separators before touching the filesystem.

## Safety

- Install refuses unmanaged destination files and foreign symlinks.
- Uninstall removes only toolkit-owned files or symlinks that point at the canonical `COMMAND.md`.
- Gemini projections carry `.attk` sidecars with ownership metadata and generated-content hashes.
- `COMMAND.md` must be a regular file, not a symlink.
