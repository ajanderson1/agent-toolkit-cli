# Junie

`junie` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.junie/skills` |
| [Agents (subagents)](../kinds/agents.md) | [✅](#agents) | symlink |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | — | Pi-only kind |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions kind](../kinds/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md`
- **Project / global path:** `./.junie/AGENTS.md` (preferred) or `./AGENTS.md` (fallback) / `~/.junie/AGENTS.md`
- **Reads `AGENTS.md` natively:** yes
- **Source:** https://junie.jetbrains.com/docs/guidelines-and-memory.html

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.junie/skills`
- **Global dir:** `~/.junie/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection

## Agents (subagents) { #agents }

Supported via the **symlink** mechanism — see the [agents kind](../kinds/agents.md) for what each mechanism means.

- **Mechanism:** symlink
- **User / project path:** `~/.junie/agents/<slug>.md` (also `~/.agents/`) / `.junie/agents/<slug>.md`
- **Format:** markdown+frontmatter; required `description`; Claude-compatible optional fields
- **Toolkit adapter:** enabled (symlink)
- **Source:** https://junie.jetbrains.com/docs/junie-cli-subagents.html
