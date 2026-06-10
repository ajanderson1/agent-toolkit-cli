# Mux

`mux` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.mux/skills` |
| [Agents (subagents)](../kinds/agents.md) | [✅](#agents) | translate |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | — | Pi-only kind |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions kind](../kinds/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md`
- **Project / global path:** `<workspace>/AGENTS.md` / `~/.mux/AGENTS.md`
- **Reads `AGENTS.md` natively:** yes
- **Source:** https://mux.coder.com/agents/instruction-files ("Mux picks the first matching base file: 1. AGENTS.md 2. AGENT.md 3. CLAUDE.md"; "Precedence: workspace … then global `~/.mux/AGENTS.md`")

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.mux/skills`
- **Global dir:** `~/.mux/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection

## Agents (subagents) { #agents }

Supported via the **translate** mechanism — see the [agents kind](../kinds/agents.md) for what each mechanism means.

- **Mechanism:** translate
- **User / project path:** `~/.mux/agents/<slug>.md` / `.mux/agents/<slug>.md` (non-recursive)
- **Format:** markdown+frontmatter; required `name`; nested `subagent` block (`runnable`)
- **Toolkit adapter:** enabled (translate)
- **Source:** https://mux.coder.com/agents
