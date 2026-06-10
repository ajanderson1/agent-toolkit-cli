# Droid

`droid` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.factory/skills` |
| [Agents (subagents)](../kinds/agents.md) | [✅](#agents) | symlink |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | — | Pi-only kind |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions kind](../kinds/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` / `~/.factory/AGENTS.md`
- **Reads `AGENTS.md` natively:** yes
- **Source:** https://docs.factory.ai/cli/configuration/agents-md ("Agents look for AGENTS.md in this order (first match wins): 1. `./AGENTS.md` in the current working directory … 4. Personal override: `~/.factory/AGENTS.md`. Agents read it automatically; no extra flags required.")

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.factory/skills`
- **Global dir:** `~/.factory/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection

## Agents (subagents) { #agents }

Supported via the **symlink** mechanism — see the [agents kind](../kinds/agents.md) for what each mechanism means.

- **Mechanism:** symlink
- **User / project path:** `~/.factory/droids/<slug>.md` / `.factory/droids/<slug>.md`
- **Format:** markdown+frontmatter; required `name`(lc/digits/-/_)+non-empty body; optional `description`(≤500),`model`,`tools`
- **Toolkit adapter:** enabled (symlink)
- **Source:** https://docs.factory.ai/cli/configuration/custom-droids
