# ![iFlow CLI logo](https://www.google.com/s2/favicons?domain=iflow.cn&sz=64){ .harness-logo } iFlow CLI

`iflow-cli` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | research: symlink; toolkit pointer scopes: project, global |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.iflow/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [—](#agents) | no file-drop convention |
| [Commands](../asset-types/commands.md) | [?](#commands) | unknown — no public evidence found |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Reads a fixed own-name file (`IFLOW.md`) instead of `AGENTS.md`. This is a research classification, not a scope-support promise. The [instructions asset type](../asset-types/instructions.md) creates pointers only at the enabled toolkit slots listed below.

- **Project research verdict:** symlink
- **Global research verdict:** symlink
- **Installation truth:** actual filesystem pointers, no Instructions lock.
- **Default file:** `IFLOW.md`
- **Project / global path:** `./IFLOW.md` / `~/.iflow/IFLOW.md`
- **Reads `AGENTS.md` natively:** no
- **Source:** [`platform.iflow.cn` Memory docs](https://platform.iflow.cn/en/cli/configuration/iflow) — default name `IFLOW.md`, custom names require `contextFileName` setting; confirmed in DeepWiki Command Reference

Research verdicts/paths above are preserved evidence, not enabled mutation targets. The shipped `instructions_install.pointer_slots` contract determines actual scope support (native discovery is separate):

- **Toolkit project pointer:** `<project>/IFLOW.md`
- **Toolkit global pointer:** `~/.iflow/IFLOW.md`

The enabled global pointer links to user-authored `~/.agent-toolkit/AGENTS.md`. Only requested slots change; install never authors canonical content.

## Skills { #skills }

The catalog supplies a skills placement for this harness. The [skills asset type](../asset-types/skills.md) uses the shared Standard slot where covered, otherwise its own projection.

- **Project dir:** `.iflow/skills`
- **Global dir:** `~/.iflow/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Not supported (gap) — tracked for possible future work.

- **Verdict:** unsupported (gap)
- **Why:** DEFUNCT (shut 2026-04-17); was `.iflow/agents/<slug>.md` req `agentType`/`systemPrompt`/`whenToUse`
- **Source:** [platform.iflow.cn/en/cli/examples/subagent](https://platform.iflow.cn/en/cli/examples/subagent) (archived)

## Commands { #commands }

Unknown — bounded search surfaced no public evidence.

- **Support:** ?
- **How:** unknown — no public evidence found
