# ![Qoder logo](https://www.google.com/s2/favicons?domain=qoder.com&sz=64){ .harness-logo } Qoder

`qoder` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.qoder/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [✅](#agents) | symlink |
| [MCP servers](../asset-types/mcp.md) | — | planned asset type |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions asset type](../asset-types/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` (also `.qoder/rules/`) / none (project-only)
- **Reads `AGENTS.md` natively:** yes
- **Source:** [docs.qoder.com/user-guide/rules](https://docs.qoder.com/user-guide/rules)

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills asset type](../asset-types/skills.md) projects into.

- **Project dir:** `.qoder/skills`
- **Global dir:** `~/.qoder/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Supported via the **symlink** mechanism — see the [agents asset type](../asset-types/agents.md) for what each mechanism means.

- **Mechanism:** symlink
- **User / project path:** `~/.qoder/agents/<name>.md` / `.qoder/agents/<name>.md`
- **Format:** markdown+frontmatter; required `name`,`description`; optional `tools`,`skills`,`mcpServers`
- **Toolkit adapter:** enabled (symlink)
- **Source:** [docs.qoder.com/extensions/subagent](https://docs.qoder.com/extensions/subagent)
