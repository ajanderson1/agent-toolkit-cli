# ![AiderDesk logo](https://github.com/hotovo.png?size=64){ .harness-logo } AiderDesk

`aider-desk` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [—](#instructions) | no pointer-satisfiable root file |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.aider-desk/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [✅](#agents) | config_file+folder |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Not supported (gap) — no default root instruction file a pointer symlink could satisfy.

- **Verdict:** unsupported (gap)
- **Default file:** none (rule files toggled via UI / External Rules extension)
- **Project / global path:** n/a — rule files live under user-chosen folders, enabled per-profile via UI
- **Reads `AGENTS.md` natively:** no
- **Source:** [hotovo/aider-desk README](https://github.com/hotovo/aider-desk#readme) — "Rule Files" / "External Rules extension"; no auto-loaded root file documented in README or main `AGENTS.md`

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills asset type](../asset-types/skills.md) projects into.

- **Project dir:** `.aider-desk/skills`
- **Global dir:** `~/.aider-desk/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Supported via the **config_file+folder** mechanism — see the [agents asset type](../asset-types/agents.md) for what each mechanism means.

- **Mechanism:** config_file+folder
- **User / project path:** `~/.aider-desk/agents/<slug>/config.json` / `.aider-desk/agents/<slug>/config.json`
- **Format:** JSON; required `id`,`name`,`provider`,`model`,`subagent.enabled`,`subagent.systemPrompt`,`subagent.invocationMode`; `subagent.enabled:true` = spawnable
- **Toolkit adapter:** enabled (config_file+folder)
- **Source:** [hotovo/aider-desk src/main/agent/agent-profile-manager.ts](https://github.com/hotovo/aider-desk/blob/main/src/main/agent/agent-profile-manager.ts) + constants.ts
