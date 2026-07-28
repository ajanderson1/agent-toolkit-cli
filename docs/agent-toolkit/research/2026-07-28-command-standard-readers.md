# Command Standard Projection — Native Reader Research

**Question.** Which harnesses natively consume Markdown files from
`.claude/commands/` at global and project scope?

**Research date:** 2026-07-28

## Decision

A Commands standard projection is warranted. The evidence establishes more than
one native reader at **both** scopes:

```python
STANDARD_COMMAND_READERS: dict[str, frozenset[str]] = {
    "global": frozenset({"claude-code", "neovate"}),
    "project": frozenset({"claude-code", "neovate", "devin"}),
}
```

This is intentionally a *reader* map, not the command adapter registry.
Neovate and Devin do not yet have individual command adapters; they can still
consume the single standard artifact. Pi, Gemini CLI, and Codex retain their
own projections because they use different paths/formats.

## Verified reader matrix

| Harness | Global `.claude/commands/` | Project `.claude/commands/` | Native behavior | Evidence |
|---|---|---|---|---|
| Claude Code | Yes: `~/.claude/commands/*.md` | Yes: `.claude/commands/*.md` | Markdown single-file prompts invoked with `/name`; Claude's directory reference lists `commands/*.md` as project-and-global. | [Claude Code `.claude` directory](https://code.claude.com/docs/en/claude-directory) — intro defines project `.claude/` versus global `~/.claude/`; file-reference table marks `commands/*.md` as “Project and global.” |
| Neovate | Yes | Yes | Direct Claude-compatible Markdown command directories. Native `.neovate/commands` paths may coexist, but its official docs explicitly state that the Claude paths are supported at each scope. | [Neovate slash commands](https://neovateai.dev/docs/slash-commands), mirrored in [source at 2c54c649](https://github.com/neovateai/neovateai.dev/blob/2c54c6491747f75d4b19b408c2d53809ff6c00c0/content/en/docs/slash-commands.mdx#L44-L70). |
| Devin CLI | No verified user-scope reader | Yes: `.claude/commands/**/*.md` | Automatically imports project Claude commands **as skills** by default. It is a reader of the artifact, but not a byte-for-byte command-menu clone; document that distinction in the standard-column help. | [Devin CLI configuration import](https://docs.devin.ai/cli/reference/configuration/read-config-from) — Claude Code table lists “Commands (as skills) `.claude/commands/**/*.md`”; the page describes project-configuration import and does not list `~/.claude/commands/`. |

### Scope notes

- Claude Code's current documentation calls `commands/*.md` “single-file
  prompts; same mechanism as skills.” It remains a supported compatibility
  location even though skills are preferred for richer assets.
- Neovate documents both compatibility paths explicitly: project at
  `.claude/commands` and global at `~/.claude/commands`.
- Devin's project importer is still a native consumer for projection purposes:
  no adapter-side conversion is required. Its “as skills” semantics mean the
  TUI/info copy must not promise identical command UI behavior.

### Neovate implementation confirmation

The checked upstream implementation at
[`0a24b363`](https://github.com/neovateai/neovate-code/tree/0a24b363ecbe24eb87a0190a88fcb78c80593b4b)
confirms the documentation claim, rather than relying on documentation alone:

- [`SlashCommandManager`](https://github.com/neovateai/neovate-code/blob/0a24b363ecbe24eb87a0190a88fcb78c80593b4b/src/slashCommand.ts#L45-L80)
  loads `~/.claude/commands` before its native global directory and
  `<project>/.claude/commands` before its native project directory.
- [`loadPolishedMarkdownFiles`](https://github.com/neovateai/neovate-code/blob/0a24b363ecbe24eb87a0190a88fcb78c80593b4b/src/outputStyle.ts#L182-L196)
  discovers Markdown recursively with `follow: true`; a toolkit-owned symlink
  is therefore a native reader input, not a copied compatibility artifact.
- [`fileToPromptCommand`](https://github.com/neovateai/neovate-code/blob/0a24b363ecbe24eb87a0190a88fcb78c80593b4b/src/slashCommand.ts#L255-L288)
  only consumes `model` and `progressMessage` from parsed frontmatter. Other
  valid Claude frontmatter is retained by the parser and ignored here, so the
  standard adapter must preserve source bytes rather than strip or translate
  Claude-specific fields.

## In-scope harnesses that do **not** read this slot

| Harness | Native command/prompt locations | Why excluded from the reader map | Evidence |
|---|---|---|---|
| Pi | `~/.pi/agent/prompts/*.md`; `.pi/prompts/*.md` | Pi discovers prompt templates from its own locations, not `.claude/commands`. | [Pi prompt templates](https://pi.dev/docs/latest/prompt-templates) |
| Gemini CLI | `~/.gemini/commands/`; `<project>/.gemini/commands/` (`.toml`) | Different directories and required TOML format. | [Gemini custom commands](https://geminicli.com/docs/cli/custom-commands/) |
| Codex | `~/.codex/prompts/*.md` only (deprecated) | Its deprecated custom prompts are global-only and use a different directory. | [Codex custom prompts](https://developers.openai.com/codex/custom-prompts) |

## Rejected/unproven compatibility claims

These findings prevent a broad reader map from being built on stale or
unmerged claims.

- **OpenCode:** PR [#6990](https://github.com/anomalyco/opencode/pull/6990)
  proposed both Claude paths, but GitHub reports it `closed` and
  `merged: false` (checked 2026-07-28). Current `dev` code search returned no
  `.claude/commands` reference. Do not list OpenCode until a merged upstream
  implementation and current release evidence exist.
- **Kode:** current source includes a user-facing string claiming legacy
  `.claude/commands/*.md` support, but its actual `loadCustomCommands` loader
  enumerates only `.kode/commands` and the Kode user commands directory. A
  source search at commit
  [`4afba64`](https://github.com/shareAI-lab/Kode-CLI/tree/4afba64cec254c2c5096719215c21d77d554f62f)
  found no loader/test for `.claude/commands`. Do not list Kode until upstream
  adds a deterministic loader test or documents the active loader path.
- **Cursor:** this repository already records it as a command-adapter research
  gap. Its current CLI slash-command reference documents built-ins but provides
  no deterministic `.claude/commands` discovery contract. Do not infer support
  from third-party migration guides.

## Implementation consequences for #482

**Implemented by #482.**

1. Install the standard artifact at `~/.claude/commands/<slug>.md` (global) or
   `<project>/.claude/commands/<slug>.md` (project), with existing sentinel and
   foreign-file protections.
2. Use the per-scope reader map above as the SSOT. Unknown scopes must raise
   `KeyError` so composition errors fail loud.
3. Keep Pi, Gemini CLI, and explicit Codex projections separate; the standard
   slot is a convergence path, not a replacement for their native formats.
4. Treat Devin's project entry as **“imported as a skill”** in documentation
   and header info. A standard install must not promise that Devin exposes the
   exact same `/name` UI as Claude Code and Neovate.
5. Tests should pin the two reader sets, assert `standard` is first in the TUI,
   and assert covered harnesses do not gain duplicate per-harness columns at a
   scope where the standard slot covers them.
