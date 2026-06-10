# ![Mistral Vibe logo](https://www.google.com/s2/favicons?domain=mistral.ai&sz=64){ .harness-logo } Mistral Vibe

`mistral-vibe` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.vibe/skills` |
| [Agents (subagents)](../kinds/agents.md) | [✅](#agents) | translate |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | N/A | Pi-only kind |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions kind](../kinds/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` (walk up from cwd, trusted dirs only) / `~/.vibe/AGENTS.md` (or `$VIBE_HOME/AGENTS.md`)
- **Reads `AGENTS.md` natively:** yes
- **Source:** [docs.mistral.ai/mistral-vibe/agents-skills](https://docs.mistral.ai/mistral-vibe/agents-skills)

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.vibe/skills`
- **Global dir:** `~/.vibe/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Supported via the **translate** mechanism — see the [agents kind](../kinds/agents.md) for what each mechanism means.

- **Mechanism:** translate
- **User / project path:** `~/.vibe/agents/<name>.toml` / `.vibe/agents/<name>.toml`
- **Format:** TOML; req `agent_type=subagent`,`display_name`,`description`,`safety`,`enabled_tools`
- **Toolkit adapter:** enabled (translate)
- **Source:** [docs.mistral.ai/mistral-vibe/agents-skills](https://docs.mistral.ai/mistral-vibe/agents-skills)
