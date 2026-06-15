# ![Dexto logo](https://github.com/truffle-ai.png?size=64){ .harness-logo } Dexto

`dexto` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.agents/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [✅](#agents) | config_file+folder |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions asset type](../asset-types/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md` (priority over `CLAUDE.md`, then `GEMINI.md`)
- **Project / global path:** `<workspaceRoot>/AGENTS.md` / none (global-only AGENTS.md not auto-loaded; only `~/.dexto/commands/` is global)
- **Reads `AGENTS.md` natively:** yes
- **Source:** [github.com/truffle-ai/dexto/blob/main/packages/agent-management/src/config/discover-prompts.ts](https://github.com/truffle-ai/dexto/blob/main/packages/agent-management/src/config/discover-prompts.ts) (`AGENT_INSTRUCTION_FILES = ['agents.md', 'claude.md', 'gemini.md']`, `discoverAgentInstructionFile`)

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills asset type](../asset-types/skills.md) projects into.

- **Project dir:** `.agents/skills`
- **Global dir:** `~/.agents/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** yes — reads the per-asset-type general directory directly
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Supported via the **config_file+folder** mechanism — see the [agents asset type](../asset-types/agents.md) for what each mechanism means.

- **Mechanism:** config_file+folder
- **User / project path:** `agents/<name>.yml` (project; global unconfirmed) / `agents/<name>.yml`
- **Format:** YAML; req `systemPrompt`,`llm.*`; spawn via `tools[].type: agent-spawner` registry
- **Toolkit adapter:** enabled (config_file+folder)
- **Source:** [docs.dexto.ai/docs/guides/configuring-dexto/agent-yml](https://docs.dexto.ai/docs/guides/configuring-dexto/agent-yml)
