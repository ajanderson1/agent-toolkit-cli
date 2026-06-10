# ![ForgeCode logo](https://www.google.com/s2/favicons?domain=forgecode.dev&sz=64){ .harness-logo } ForgeCode

`forgecode` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.forge/skills` |
| [Agents (subagents)](../kinds/agents.md) | [✅](#agents) | symlink |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | — | Pi-only kind |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions kind](../kinds/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` (recursively: env `base_path` → git root → cwd) / `none (project-only)`
- **Reads `AGENTS.md` natively:** yes
- **Source:** [forgecode.dev/docs/custom-rules-guide/](https://forgecode.dev/docs/custom-rules-guide/)

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.forge/skills`
- **Global dir:** `~/.forge/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Supported via the **symlink** mechanism — see the [agents kind](../kinds/agents.md) for what each mechanism means.

- **Mechanism:** symlink
- **User / project path:** `~/.forge/agents/<slug>.md` (legacy `~/forge/agents/`) / `.forge/agents/<slug>.md`
- **Format:** markdown+frontmatter; `id` auto from filename, all else optional; project overrides global
- **Toolkit adapter:** enabled (symlink)
- **Source:** [antinomyhq/forgecode crates/forge_repo/src/agent.rs](https://github.com/antinomyhq/forgecode/blob/main/crates/forge_repo/src/agent.rs)
