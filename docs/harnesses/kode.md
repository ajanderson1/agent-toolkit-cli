# ![Kode logo](https://github.com/shareAI-lab.png?size=64){ .harness-logo } Kode

`kode` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.kode/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [✅](#agents) | symlink |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions asset type](../asset-types/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` (prefers `AGENTS.override.md`) / none (project-only; `~/.kode.json` is JSON config, not an instruction file)
- **Reads `AGENTS.md` natively:** yes
- **Source:** [github.com/shareAI-lab/Kode-cli](https://github.com/shareAI-lab/Kode-cli) README § "AGENTS.md Standard Support" ("Native support for the OpenAI-initiated standard format … prefers `AGENTS.override.md` over `AGENTS.md`")

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills asset type](../asset-types/skills.md) projects into.

- **Project dir:** `.kode/skills`
- **Global dir:** `~/.kode/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Supported via the **symlink** mechanism — see the [agents asset type](../asset-types/agents.md) for what each mechanism means.

- **Mechanism:** symlink
- **User / project path:** `~/.claude/agents/<slug>.md` (also `~/.kode/agents/`) / `.claude/agents/<slug>.md`
- **Format:** markdown+frontmatter; required `name`,`description`; `model_name` (not `model`)
- **Toolkit adapter:** enabled (symlink)
- **Source:** [github.com/shareAI-lab/Kode-CLI/blob/main/docs/agents-system.md](https://github.com/shareAI-lab/Kode-CLI/blob/main/docs/agents-system.md)
