# ![iFlow CLI logo](https://www.google.com/s2/favicons?domain=iflow.cn&sz=64){ .harness-logo } iFlow CLI

`iflow-cli` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [✅](#instructions) | pointer symlink (`IFLOW.md` → `AGENTS.md`) |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.iflow/skills` |
| [Agents (subagents)](../kinds/agents.md) | [—](#agents) | no file-drop convention |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | N/A | Pi-only kind |

## Instructions { #instructions }

Reads a fixed own-name file (`IFLOW.md`) instead of `AGENTS.md`. The [instructions kind](../kinds/instructions.md) creates a same-name pointer symlink → `AGENTS.md`.

- **Verdict:** symlink
- **Default file:** `IFLOW.md`
- **Project / global path:** `./IFLOW.md` / `~/.iflow/IFLOW.md`
- **Reads `AGENTS.md` natively:** no
- **Source:** [`platform.iflow.cn` Memory docs](https://platform.iflow.cn/en/cli/configuration/iflow) — default name `IFLOW.md`, custom names require `contextFileName` setting; confirmed in DeepWiki Command Reference

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.iflow/skills`
- **Global dir:** `~/.iflow/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Not supported (gap) — tracked for possible future work.

- **Verdict:** unsupported (gap)
- **Why:** DEFUNCT (shut 2026-04-17); was `.iflow/agents/<slug>.md` req `agentType`/`systemPrompt`/`whenToUse`
- **Source:** [platform.iflow.cn/en/cli/examples/subagent](https://platform.iflow.cn/en/cli/examples/subagent) (archived)
