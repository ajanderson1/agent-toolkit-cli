# ![Droid logo](https://www.google.com/s2/favicons?domain=factory.ai&sz=64){ .harness-logo } Droid

`droid` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | native classification; check discovery paths |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.factory/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [✅](#agents) | symlink |
| [Commands](../asset-types/commands.md) | [?](#commands) | unknown — no public evidence found |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Classified as a native `AGENTS.md` reader; no project pointer is created. Check the discovery paths below: some readers are workspace-only or do not load the root canonical at every scope.

- **Project verdict:** native
- **Global verdict:** native
- **Installation truth:** actual filesystem pointers, no Instructions lock.
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` / `~/.factory/AGENTS.md`
- **Reads `AGENTS.md` natively:** yes
- **Source:** [docs.factory.ai/cli/configuration/agents-md](https://docs.factory.ai/cli/configuration/agents-md) ("Agents look for AGENTS.md in this order (first match wins): 1. `./AGENTS.md` in the current working directory … 4. Personal override: `~/.factory/AGENTS.md`. Agents read it automatically; no extra flags required.")

## Skills { #skills }

The catalog supplies a skills placement for this harness. The [skills asset type](../asset-types/skills.md) uses the shared Standard slot where covered, otherwise its own projection.

- **Project dir:** `.factory/skills`
- **Global dir:** `~/.factory/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Researched support via **symlink**; check the enabled adapter below — see the [agents asset type](../asset-types/agents.md) for what each mechanism means.

- **Mechanism:** symlink
- **User / project path:** `~/.factory/droids/<slug>.md` / `.factory/droids/<slug>.md`
- **Format:** markdown+frontmatter; required `name`(lc/digits/-/_)+non-empty body; optional `description`(≤500),`model`,`tools`
- **Toolkit adapter:** enabled (symlink)
- **Source:** [docs.factory.ai/cli/configuration/custom-droids](https://docs.factory.ai/cli/configuration/custom-droids)

## Commands { #commands }

Unknown — bounded search surfaced no public evidence.

- **Support:** ?
- **How:** unknown — no public evidence found
