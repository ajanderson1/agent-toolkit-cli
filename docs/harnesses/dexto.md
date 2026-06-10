# Dexto

`dexto` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.agents/skills` |
| [Agents (subagents)](../kinds/agents.md) | [✅](#agents) | config_file+folder |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | — | Pi-only kind |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions kind](../kinds/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md` (priority over `CLAUDE.md`, then `GEMINI.md`)
- **Project / global path:** `<workspaceRoot>/AGENTS.md` / none (global-only AGENTS.md not auto-loaded; only `~/.dexto/commands/` is global)
- **Reads `AGENTS.md` natively:** yes
- **Source:** https://github.com/truffle-ai/dexto/blob/main/packages/agent-management/src/config/discover-prompts.ts (`AGENT_INSTRUCTION_FILES = ['agents.md', 'claude.md', 'gemini.md']`, `discoverAgentInstructionFile`)

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.agents/skills`
- **Global dir:** `~/.agents/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** yes — reads the per-kind general directory directly

## Agents (subagents) { #agents }

Supported via the **config_file+folder** mechanism — see the [agents kind](../kinds/agents.md) for what each mechanism means.

- **Mechanism:** config_file+folder
- **User / project path:** `agents/<name>.yml` (project; global unconfirmed) / `agents/<name>.yml`
- **Format:** YAML; req `systemPrompt`,`llm.*`; spawn via `tools[].type: agent-spawner` registry
- **Toolkit adapter:** enabled (config_file+folder)
- **Source:** docs.dexto.ai/docs/guides/configuring-dexto/agent-yml
