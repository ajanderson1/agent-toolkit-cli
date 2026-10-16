# ![IBM Bob logo](https://www.google.com/s2/favicons?domain=bob.ibm.com&sz=64){ .harness-logo } IBM Bob

`bob` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | research: native; toolkit pointer scopes: none |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.bob/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [—](#agents) | no file-drop convention |
| [Commands](../asset-types/commands.md) | [?](#commands) | unknown — no public evidence found |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Classified as a native `AGENTS.md` reader; no project pointer is created. Check the discovery paths below: some readers are workspace-only or do not load the root canonical at every scope.

- **Project research verdict:** native
- **Global research verdict:** native
- **Installation truth:** actual filesystem pointers, no Instructions lock.
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` / none (global-only) — global is `~/.bob/rules/*.md` (a *rules* directory, not AGENTS.md)
- **Reads `AGENTS.md` natively:** yes
- **Source:** [bob.ibm.com/docs/ide/configuration/rules](https://bob.ibm.com/docs/ide/configuration/rules) ("`AGENTS.md` file in your workspace root … Automatically loaded by default") and [bob.ibm.com/docs/ide/getting-started/tutorials/start-a-project](https://bob.ibm.com/docs/ide/getting-started/tutorials/start-a-project) ("Bob automatically applies the `AGENTS.md` to new conversations")

Research verdicts/paths above are preserved evidence, not enabled mutation targets. The shipped `instructions_install.pointer_slots` contract determines actual scope support (native discovery is separate):

- **Toolkit project pointer:** unavailable — no managed pointer slot at this scope
- **Toolkit global pointer:** unavailable — no managed pointer slot at this scope

## Skills { #skills }

The catalog supplies a skills placement for this harness. The [skills asset type](../asset-types/skills.md) uses the shared Standard slot where covered, otherwise its own projection.

- **Project dir:** `.bob/skills`
- **Global dir:** `~/.bob/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Not supported (gap) — tracked for possible future work.

- **Verdict:** unsupported (gap)
- **Why:** `.bob/rules*/` + modes only; no `agents/` dir; orchestration IBM-internal
- **Source:** [bob.ibm.com/docs/ide/configuration/rules](https://bob.ibm.com/docs/ide/configuration/rules)

## Commands { #commands }

Unknown — bounded search surfaced no public evidence.

- **Support:** ?
- **How:** unknown — no public evidence found
