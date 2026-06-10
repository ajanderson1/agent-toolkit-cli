# ![OpenCode logo](https://www.google.com/s2/favicons?domain=opencode.ai&sz=64){ .harness-logo } OpenCode

`opencode` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.agents/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [✅](#agents) | translate |
| [MCP servers](../asset-types/mcp.md) | — | planned asset type |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions asset type](../asset-types/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` / `~/.config/opencode/AGENTS.md`
- **Reads `AGENTS.md` natively:** yes
- **Source:** [opencode.ai/docs/rules/](https://opencode.ai/docs/rules/)

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills asset type](../asset-types/skills.md) projects into.

- **Project dir:** `.agents/skills`
- **Global dir:** `~/.config/opencode/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** yes — reads the per-asset-type general directory directly
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Supported via the **translate** mechanism — see the [agents asset type](../asset-types/agents.md) for what each mechanism means.

- **Mechanism:** translate
- **User / project path:** `~/.config/opencode/{agent,agents}/**/*.md` / `.opencode/{agent,agents}/**/*.md`
- **Format:** markdown+frontmatter; inject `mode: subagent`; name from filename; glob singular+plural
- **Toolkit adapter:** enabled (translate)
- **Source:** [`packages/opencode/src/config/agent.ts`](https://github.com/sst/opencode/blob/dev/packages/opencode/src/config/agent.ts) load(); [`agent/agent.ts:32`](https://github.com/sst/opencode/blob/dev/packages/opencode/src/agent/agent.ts)
