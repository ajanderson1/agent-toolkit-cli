# ![Antigravity logo](https://www.google.com/s2/favicons?domain=antigravity.google&sz=64){ .harness-logo } Antigravity

`antigravity` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.agents/skills` |
| [Agents (subagents)](../kinds/agents.md) | [❓](#agents) | no public evidence |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | — | Pi-only kind |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions kind](../kinds/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md` + `GEMINI.md`
- **Project / global path:** `./AGENTS.md` (workspace root) / `~/.gemini/AGENTS.md`
- **Reads `AGENTS.md` natively:** yes
- **Source:** [Antigravity 1.20.3 changelog (2026-03-05)](https://discuss.ai.google.dev/t/antigravity-update-1-20-3-2026-3-5/129320): "Added support for reading rules from AGENTS.md in addition to GEMINI.md."

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.agents/skills`
- **Global dir:** `~/.gemini/antigravity/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** yes — reads the per-kind general directory directly
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Unknown — bounded search surfaced no public evidence.

- **Verdict:** unknown — no public evidence found
- **Why:** dynamic orchestrator-spawned only; closed-source Go binary; community `agent.json` unconfirmed
- **Source:** [google-gemini/gemini-cli discussion #27305](https://github.com/google-gemini/gemini-cli/discussions/27305)
