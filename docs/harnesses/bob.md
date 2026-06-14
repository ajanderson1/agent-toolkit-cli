# ![IBM Bob logo](https://www.google.com/s2/favicons?domain=bob.ibm.com&sz=64){ .harness-logo } IBM Bob

`bob` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.bob/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [—](#agents) | no file-drop convention |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions asset type](../asset-types/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` / none (global-only) — global is `~/.bob/rules/*.md` (a *rules* directory, not AGENTS.md)
- **Reads `AGENTS.md` natively:** yes
- **Source:** [bob.ibm.com/docs/ide/configuration/rules](https://bob.ibm.com/docs/ide/configuration/rules) ("`AGENTS.md` file in your workspace root … Automatically loaded by default") and [bob.ibm.com/docs/ide/getting-started/tutorials/start-a-project](https://bob.ibm.com/docs/ide/getting-started/tutorials/start-a-project) ("Bob automatically applies the `AGENTS.md` to new conversations")

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills asset type](../asset-types/skills.md) projects into.

- **Project dir:** `.bob/skills`
- **Global dir:** `~/.bob/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Not supported (gap) — tracked for possible future work.

- **Verdict:** unsupported (gap)
- **Why:** `.bob/rules*/` + modes only; no `agents/` dir; orchestration IBM-internal
- **Source:** [bob.ibm.com/docs/ide/configuration/rules](https://bob.ibm.com/docs/ide/configuration/rules)
