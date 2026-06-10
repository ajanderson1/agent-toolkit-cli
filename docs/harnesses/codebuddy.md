# ![CodeBuddy logo](https://www.google.com/s2/favicons?domain=codebuddy.ai&sz=64){ .harness-logo } CodeBuddy

`codebuddy` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | pointer symlink (`CODEBUDDY.md` → `AGENTS.md`) |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.codebuddy/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [✅](#agents) | symlink |
| [MCP servers](../asset-types/mcp.md) | — | planned asset type |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Reads a fixed own-name file (`CODEBUDDY.md`) instead of `AGENTS.md`. The [instructions asset type](../asset-types/instructions.md) creates a same-name pointer symlink → `AGENTS.md`.

- **Verdict:** symlink
- **Default file:** `CODEBUDDY.md`
- **Project / global path:** `./CODEBUDDY.md` (recursive up from cwd) / `~/.codebuddy/CODEBUDDY.md`
- **Reads `AGENTS.md` natively:** no (own-name preferred; AGENTS.md only as fallback when CODEBUDDY.md absent)
- **Source:** [www.codebuddy.ai/docs/cli/memory](https://www.codebuddy.ai/docs/cli/memory)

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills asset type](../asset-types/skills.md) projects into.

- **Project dir:** `.codebuddy/skills`
- **Global dir:** `~/.codebuddy/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Supported via the **symlink** mechanism — see the [agents asset type](../asset-types/agents.md) for what each mechanism means.

- **Mechanism:** symlink
- **User / project path:** `~/.codebuddy/agents/<slug>.md` / `.codebuddy/agents/<slug>.md`
- **Format:** markdown+frontmatter; required `name`(lc+hyphens),`description`; optional `tools`,`model`,`permissionMode`,`skills`
- **Toolkit adapter:** enabled (symlink)
- **Source:** [www.codebuddy.ai/docs/cli/sub-agents](https://www.codebuddy.ai/docs/cli/sub-agents)
