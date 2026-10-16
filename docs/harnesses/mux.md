# ![Mux logo](https://www.google.com/s2/favicons?domain=coder.com&sz=64){ .harness-logo } Mux

`mux` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | native classification; check discovery paths |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.mux/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [✅](#agents) | translate |
| [Commands](../asset-types/commands.md) | [?](#commands) | unknown — no public evidence found |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Classified as a native `AGENTS.md` reader; no project pointer is created. Check the discovery paths below: some readers are workspace-only or do not load the root canonical at every scope.

- **Project verdict:** native
- **Global verdict:** native
- **Installation truth:** actual filesystem pointers, no Instructions lock.
- **Default file:** `AGENTS.md`
- **Project / global path:** `<workspace>/AGENTS.md` / `~/.mux/AGENTS.md`
- **Reads `AGENTS.md` natively:** yes
- **Source:** [mux.coder.com/agents/instruction-files](https://mux.coder.com/agents/instruction-files) ("Mux picks the first matching base file: 1. AGENTS.md 2. AGENT.md 3. CLAUDE.md"; "Precedence: workspace … then global `~/.mux/AGENTS.md`")

## Skills { #skills }

The catalog supplies a skills placement for this harness. The [skills asset type](../asset-types/skills.md) uses the shared Standard slot where covered, otherwise its own projection.

- **Project dir:** `.mux/skills`
- **Global dir:** `~/.mux/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Researched support via **translate**; check the enabled adapter below — see the [agents asset type](../asset-types/agents.md) for what each mechanism means.

- **Mechanism:** translate
- **User / project path:** `~/.mux/agents/<slug>.md` / `.mux/agents/<slug>.md` (non-recursive)
- **Format:** markdown+frontmatter; required `name`; nested `subagent` block (`runnable`)
- **Toolkit adapter:** enabled (translate)
- **Source:** [mux.coder.com/agents](https://mux.coder.com/agents)

## Commands { #commands }

Unknown — bounded search surfaced no public evidence.

- **Support:** ?
- **How:** unknown — no public evidence found
