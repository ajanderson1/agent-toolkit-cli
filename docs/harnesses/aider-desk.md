# ![AiderDesk logo](https://github.com/hotovo.png?size=64){ .harness-logo } AiderDesk

`aider-desk` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [❌](#instructions) | no pointer-satisfiable root file |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.aider-desk/skills` |
| [Agents (subagents)](../kinds/agents.md) | [✅](#agents) | config_file+folder |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | — | Pi-only kind |

## Instructions { #instructions }

Not supported (gap) — no default root instruction file a pointer symlink could satisfy.

- **Verdict:** unsupported (gap)
- **Default file:** none (rule files toggled via UI / External Rules extension)
- **Project / global path:** n/a — rule files live under user-chosen folders, enabled per-profile via UI
- **Reads `AGENTS.md` natively:** no
- **Source:** github.com/hotovo/aider-desk — README "Rule Files" / "External Rules extension"; no auto-loaded root file documented in README or main `AGENTS.md`

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.aider-desk/skills`
- **Global dir:** `~/.aider-desk/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection

## Agents (subagents) { #agents }

Supported via the **config_file+folder** mechanism — see the [agents kind](../kinds/agents.md) for what each mechanism means.

- **Mechanism:** config_file+folder
- **User / project path:** `~/.aider-desk/agents/<slug>/config.json` / `.aider-desk/agents/<slug>/config.json`
- **Format:** JSON; required `id`,`name`,`provider`,`model`,`subagent.enabled`,`subagent.systemPrompt`,`subagent.invocationMode`; `subagent.enabled:true` = spawnable
- **Toolkit adapter:** enabled (config_file+folder)
- **Source:** github.com/hotovo/aider-desk .../agent-profile-manager.ts + constants.ts
