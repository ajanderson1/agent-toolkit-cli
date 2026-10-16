# ![CodeArts Agent logo](https://www.google.com/s2/favicons?domain=huaweicloud.com&sz=64){ .harness-logo } CodeArts Agent

`codearts-agent` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [?](#instructions) | no public evidence |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.codeartsdoer/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [?](#agents) | no public evidence |
| [Commands](../asset-types/commands.md) | [?](#commands) | unknown — no public evidence found |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Unknown — bounded search surfaced no public evidence.

- **Project research verdict:** unknown — no public evidence found
- **Global research verdict:** unknown — no public evidence found
- **Installation truth:** actual filesystem pointers, no Instructions lock.
- **Default file:** none
- **Project / global path:** none / none
- **Reads `AGENTS.md` natively:** no
- **Source:** Searched `support.huaweicloud.com` CodeArts docs, JetBrains Marketplace listing, Pandaily/Tiger Brokers public-beta coverage, Baidu-wiki entries — no documented default root instruction-file convention

Research verdicts/paths above are preserved evidence, not enabled mutation targets. The shipped `instructions_install.pointer_slots` contract determines actual scope support (native discovery is separate):

- **Toolkit project pointer:** unavailable — no managed pointer slot at this scope
- **Toolkit global pointer:** unavailable — no managed pointer slot at this scope

## Skills { #skills }

The catalog supplies a skills placement for this harness. The [skills asset type](../asset-types/skills.md) uses the shared Standard slot where covered, otherwise its own projection.

- **Project dir:** `.codeartsdoer/skills`
- **Global dir:** `~/.codeartsdoer/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Unknown — bounded search surfaced no public evidence.

- **Verdict:** unknown — no public evidence found
- **Why:** Huawei CodeArts beta; mentions MCP+Skills, no public subagent file dir
- **Source:** [huaweicloud.com/intl/en-us/product/codearts/ai.html](https://www.huaweicloud.com/intl/en-us/product/codearts/ai.html)

## Commands { #commands }

Unknown — bounded search surfaced no public evidence.

- **Support:** ?
- **How:** unknown — no public evidence found
