# ![Hermes Agent logo](https://www.google.com/s2/favicons?domain=nousresearch.com&sz=64){ .harness-logo } Hermes Agent

`hermes-agent` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | research: native; toolkit pointer scopes: none |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.hermes/skills` |
| [Agents (subagents)](../asset-types/agents.md) | N/A | no subagent concept |
| [Commands](../asset-types/commands.md) | [?](#commands) | unknown — no public evidence found |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Classified as a native `AGENTS.md` reader; no project pointer is created. Check the discovery paths below: some readers are workspace-only or do not load the root canonical at every scope.

- **Project research verdict:** native
- **Global research verdict:** native
- **Installation truth:** actual filesystem pointers, no Instructions lock.
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` (cwd top-level only; nested injected lazily via tool results) / `none (project-only — global persona uses separate `~/.hermes/SOUL.md`)`
- **Reads `AGENTS.md` natively:** yes
- **Source:** [hermes-agent.nousresearch.com/docs/guides/tips](https://hermes-agent.nousresearch.com/docs/guides/tips)

Research verdicts/paths above are preserved evidence, not enabled mutation targets. The shipped `instructions_install.pointer_slots` contract determines actual scope support (native discovery is separate):

- **Toolkit project pointer:** unavailable — no managed pointer slot at this scope
- **Toolkit global pointer:** unavailable — no managed pointer slot at this scope

## Skills { #skills }

The catalog supplies a skills placement for this harness. The [skills asset type](../asset-types/skills.md) uses the shared Standard slot where covered, otherwise its own projection.

- **Project dir:** `.hermes/skills`
- **Global dir:** `~/.hermes/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Not applicable — no subagent concept; won't be filled.

- **Verdict:** unsupported (by design)
- **Why:** `delegate_task` tool runtime-only; config only `~/.hermes/config.yaml`; no file-drop
- **Source:** [hermes-agent.nousresearch.com/docs/user-guide/features/delegation](https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation)

## Commands { #commands }

Unknown — bounded search surfaced no public evidence.

- **Support:** ?
- **How:** unknown — no public evidence found
