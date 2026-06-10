# CodeBuddy

`codebuddy` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [✅](#instructions) | pointer symlink (`CODEBUDDY.md` → `AGENTS.md`) |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.codebuddy/skills` |
| [Agents (subagents)](../kinds/agents.md) | [✅](#agents) | symlink |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | — | Pi-only kind |

## Instructions { #instructions }

Reads a fixed own-name file (`CODEBUDDY.md`) instead of `AGENTS.md`. The [instructions kind](../kinds/instructions.md) creates a same-name pointer symlink → `AGENTS.md`.

- **Verdict:** symlink
- **Default file:** `CODEBUDDY.md`
- **Project / global path:** `./CODEBUDDY.md` (recursive up from cwd) / `~/.codebuddy/CODEBUDDY.md`
- **Reads `AGENTS.md` natively:** no (own-name preferred; AGENTS.md only as fallback when CODEBUDDY.md absent)
- **Source:** https://www.codebuddy.ai/docs/cli/memory

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.codebuddy/skills`
- **Global dir:** `~/.codebuddy/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection

## Agents (subagents) { #agents }

Supported via the **symlink** mechanism — see the [agents kind](../kinds/agents.md) for what each mechanism means.

- **Mechanism:** symlink
- **User / project path:** `~/.codebuddy/agents/<slug>.md` / `.codebuddy/agents/<slug>.md`
- **Format:** markdown+frontmatter; required `name`(lc+hyphens),`description`; optional `tools`,`model`,`permissionMode`,`skills`
- **Toolkit adapter:** enabled (symlink)
- **Source:** https://www.codebuddy.ai/docs/cli/sub-agents
