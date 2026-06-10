# ![Firebender logo](https://www.google.com/s2/favicons?domain=firebender.com&sz=64){ .harness-logo } Firebender

`firebender` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.agents/skills` |
| [Agents (subagents)](../kinds/agents.md) | [✅](#agents) | config_file+folder |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | — | Pi-only kind |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions kind](../kinds/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` (also `./.firebender/AGENTS.md`) / `~/.firebender/AGENTS.md`
- **Reads `AGENTS.md` natively:** yes
- **Source:** [docs.firebender.com/api-reference/agents-md.md](https://docs.firebender.com/api-reference/agents-md.md) ("automatically discovered… No configuration in `firebender.json` is required"); changelog v0.15.5 (2026-01-28) [docs.firebender.com/about/changelog](https://docs.firebender.com/about/changelog)

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.agents/skills`
- **Global dir:** `~/.firebender/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** yes — reads the per-kind general directory directly
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Supported via the **config_file+folder** mechanism — see the [agents kind](../kinds/agents.md) for what each mechanism means.

- **Mechanism:** config_file+folder
- **User / project path:** `~/.firebender/firebender.json`→md / `firebender.json`→`.firebender/agents/<slug>.md`
- **Format:** markdown+frontmatter req `name`,`description`,`callable:true` to spawn; registered in `firebender.json` array
- **Toolkit adapter:** currently disabled — would mutate a hot-reloaded IDE registry (firebender.json); pending AJ decision to accept shared-config mutation (PR5a)
- **Source:** [docs.firebender.com/multi-agent/subagents](https://docs.firebender.com/multi-agent/subagents)
