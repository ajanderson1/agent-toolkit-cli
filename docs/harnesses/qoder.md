# ![Qoder logo](https://www.google.com/s2/favicons?domain=qoder.com&sz=64){ .harness-logo } Qoder

`qoder` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.qoder/skills` |
| [Agents (subagents)](../kinds/agents.md) | [✅](#agents) | symlink |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | — | Pi-only kind |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions kind](../kinds/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` (also `.qoder/rules/`) / none (project-only)
- **Reads `AGENTS.md` natively:** yes
- **Source:** [docs.qoder.com/user-guide/rules](https://docs.qoder.com/user-guide/rules)

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.qoder/skills`
- **Global dir:** `~/.qoder/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Supported via the **symlink** mechanism — see the [agents kind](../kinds/agents.md) for what each mechanism means.

- **Mechanism:** symlink
- **User / project path:** `~/.qoder/agents/<name>.md` / `.qoder/agents/<name>.md`
- **Format:** markdown+frontmatter; required `name`,`description`; optional `tools`,`skills`,`mcpServers`
- **Toolkit adapter:** enabled (symlink)
- **Source:** [docs.qoder.com/extensions/subagent](https://docs.qoder.com/extensions/subagent)
