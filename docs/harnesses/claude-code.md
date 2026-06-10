# Claude Code

`claude-code` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [✅](#instructions) | pointer symlink (`CLAUDE.md` → `AGENTS.md`) |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.claude/skills` |
| [Agents (subagents)](../kinds/agents.md) | [✅](#agents) | symlink |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | — | Pi-only kind |

## Instructions { #instructions }

Reads a fixed own-name file (`CLAUDE.md`) instead of `AGENTS.md`. The [instructions kind](../kinds/instructions.md) creates a same-name pointer symlink → `AGENTS.md`.

- **Verdict:** symlink
- **Default file:** `CLAUDE.md`
- **Project / global path:** `./CLAUDE.md` or `./.claude/CLAUDE.md` / `~/.claude/CLAUDE.md`
- **Reads `AGENTS.md` natively:** no
- **Source:** https://code.claude.com/docs/en/memory § "AGENTS.md" ("Claude Code reads `CLAUDE.md`, not `AGENTS.md`")

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.claude/skills`
- **Global dir:** `~/.claude/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection

## Agents (subagents) { #agents }

Supported via the **symlink** mechanism — see the [agents kind](../kinds/agents.md) for what each mechanism means.

- **Mechanism:** symlink
- **User / project path:** `~/.claude/agents/<slug>.md` / `.claude/agents/<slug>.md` (recursive)
- **Format:** markdown+frontmatter; required `name`,`description`; extra keys ignored; 15 optional fields
- **Toolkit adapter:** enabled (symlink)
- **Source:** https://code.claude.com/docs/en/sub-agents
