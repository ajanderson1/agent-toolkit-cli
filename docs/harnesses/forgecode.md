# ![ForgeCode logo](https://www.google.com/s2/favicons?domain=forgecode.dev&sz=64){ .harness-logo } ForgeCode

`forgecode` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.forge/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [✅](#agents) | symlink |
| [Commands](../asset-types/commands.md) | [?](#commands) | unknown — no public evidence found |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions asset type](../asset-types/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` (recursively: env `base_path` → git root → cwd) / `none (project-only)`
- **Reads `AGENTS.md` natively:** yes
- **Source:** [forgecode.dev/docs/custom-rules-guide/](https://forgecode.dev/docs/custom-rules-guide/)

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills asset type](../asset-types/skills.md) projects into.

- **Project dir:** `.forge/skills`
- **Global dir:** `~/.forge/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Supported via the **symlink** mechanism — see the [agents asset type](../asset-types/agents.md) for what each mechanism means.

- **Mechanism:** symlink
- **User / project path:** `~/.forge/agents/<slug>.md` (legacy `~/forge/agents/`) / `.forge/agents/<slug>.md`
- **Format:** markdown+frontmatter; `id` auto from filename, all else optional; project overrides global
- **Toolkit adapter:** enabled (symlink)
- **Source:** [antinomyhq/forgecode crates/forge_repo/src/agent.rs](https://github.com/antinomyhq/forgecode/blob/main/crates/forge_repo/src/agent.rs)

## Commands { #commands }

Unknown — bounded search surfaced no public evidence.

- **Support:** ?
- **How:** unknown — no public evidence found
