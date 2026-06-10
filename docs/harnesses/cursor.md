# ![Cursor logo](https://www.google.com/s2/favicons?domain=cursor.com&sz=64){ .harness-logo } Cursor

`cursor` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.agents/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [✅](#agents) | symlink |
| [MCP servers](../asset-types/mcp.md) | — | planned asset type |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions asset type](../asset-types/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md` (also `.cursor/rules/*.mdc`)
- **Project / global path:** `./AGENTS.md` / Cursor Settings > Rules (UI, not file)
- **Reads `AGENTS.md` natively:** yes
- **Source:** [cursor.com/docs/rules](https://cursor.com/docs/rules)

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills asset type](../asset-types/skills.md) projects into.

- **Project dir:** `.agents/skills`
- **Global dir:** `~/.cursor/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** yes — reads the per-asset-type general directory directly
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Supported via the **symlink** mechanism — see the [agents asset type](../asset-types/agents.md) for what each mechanism means.

- **Mechanism:** symlink
- **User / project path:** `~/.cursor/agents/<slug>.md` / `.cursor/agents/<slug>.md`
- **Format:** markdown+frontmatter; required `name`,`description`; optional `model`,`readonly`,`is_background`
- **Toolkit adapter:** enabled (symlink)
- **Source:** [cursor.com/docs/subagents](https://cursor.com/docs/subagents)
