# ![Dexto logo](https://github.com/truffle-ai.png?size=64){ .harness-logo } Dexto

`dexto` · one row of the [compatibility matrix](../matrix.md)

Use the packaged **`atc` CLI** / **`att` TUI**; long executable names remain supported.
[Install and verify](../agent-toolkit/installation.md) ·
[Package updates](../agent-toolkit/updates.md) ·
[Shell completion](../agent-toolkit/shell-completion.md).
These application utilities do not enable assets or expand this harness's supported scopes.

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | research: native; toolkit pointer scopes: none |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.agents/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [✅](#agents) | config_file+folder |
| [Commands](../asset-types/commands.md) | [?](#commands) | unknown — no public evidence found |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Classified as a native `AGENTS.md` reader; no project pointer is created. Check the discovery paths below: some readers are workspace-only or do not load the root canonical at every scope.

- **Project research verdict:** native
- **Global research verdict:** native
- **Installation truth:** actual filesystem pointers, no Instructions lock.
- **Default file:** `AGENTS.md` (priority over `CLAUDE.md`, then `GEMINI.md`)
- **Project / global path:** `<workspaceRoot>/AGENTS.md` / none (global-only AGENTS.md not auto-loaded; only `~/.dexto/commands/` is global)
- **Reads `AGENTS.md` natively:** yes
- **Source:** [github.com/truffle-ai/dexto/blob/main/packages/agent-management/src/config/discover-prompts.ts](https://github.com/truffle-ai/dexto/blob/main/packages/agent-management/src/config/discover-prompts.ts) (`AGENT_INSTRUCTION_FILES = ['agents.md', 'claude.md', 'gemini.md']`, `discoverAgentInstructionFile`)

Research verdicts/paths above are preserved evidence, not enabled mutation targets. The shipped `instructions_install.pointer_slots` contract determines actual scope support (native discovery is separate):

- **Toolkit project pointer:** unavailable — no managed pointer slot at this scope
- **Toolkit global pointer:** unavailable — no managed pointer slot at this scope

## Skills { #skills }

The catalog supplies a skills placement for this harness. The [skills asset type](../asset-types/skills.md) uses the shared Standard slot where covered, otherwise its own projection.

- **Project dir:** `.agents/skills`
- **Global dir:** `~/.agents/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** yes — reads the per-asset-type general directory directly
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Researched support via **config_file+folder**; check the enabled adapter below — see the [agents asset type](../asset-types/agents.md) for what each mechanism means.

- **Mechanism:** config_file+folder
- **User / project path:** `agents/<name>.yml` (project; global unconfirmed) / `agents/<name>.yml`
- **Format:** YAML; req `systemPrompt`,`llm.*`; spawn via `tools[].type: agent-spawner` registry
- **Toolkit adapter:** enabled (config_file+folder)
- **Source:** [docs.dexto.ai/docs/guides/configuring-dexto/agent-yml](https://docs.dexto.ai/docs/guides/configuring-dexto/agent-yml)

## Commands { #commands }

Unknown — bounded search surfaced no public evidence.

- **Support:** ?
- **How:** unknown — no public evidence found
