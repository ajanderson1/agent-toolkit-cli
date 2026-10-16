# ![Kiro CLI logo](https://www.google.com/s2/favicons?domain=kiro.dev&sz=64){ .harness-logo } Kiro CLI

`kiro-cli` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | native classification; check discovery paths |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.kiro/skills` |
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
- **Project / global path:** `./AGENTS.md` (workspace root) / `~/.kiro/steering/AGENTS.md`
- **Reads `AGENTS.md` natively:** yes
- **Source:** [kiro.dev/docs/cli/steering/](https://kiro.dev/docs/cli/steering/)

## Skills { #skills }

The catalog supplies a skills placement for this harness. The [skills asset type](../asset-types/skills.md) uses the shared Standard slot where covered, otherwise its own projection.

- **Project dir:** `.kiro/skills`
- **Global dir:** `~/.kiro/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Researched support via **translate**; check the enabled adapter below — see the [agents asset type](../asset-types/agents.md) for what each mechanism means.

- **Mechanism:** translate
- **User / project path:** `~/.kiro/agents/<name>.json` / `.kiro/agents/<name>.json`
- **Format:** JSON (not markdown); filename=agent ID; optional `name`,`description`,`prompt`,`model`,`tools`
- **Toolkit adapter:** enabled (translate)
- **Source:** [kiro.dev/docs/cli/custom-agents/configuration-reference/](https://kiro.dev/docs/cli/custom-agents/configuration-reference/)

## Commands { #commands }

Unknown — bounded search surfaced no public evidence.

- **Support:** ?
- **How:** unknown — no public evidence found
