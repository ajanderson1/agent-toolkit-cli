# ![Replit logo](https://www.google.com/s2/favicons?domain=replit.com&sz=64){ .harness-logo } Replit

`replit` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | research: symlink; toolkit pointer scopes: project |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.agents/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [—](#agents) | no file-drop convention |
| [Commands](../asset-types/commands.md) | [?](#commands) | unknown — no public evidence found |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Reads a fixed own-name file (`replit.md`) instead of `AGENTS.md`. This is a research classification, not a scope-support promise. The [instructions asset type](../asset-types/instructions.md) creates pointers only at the enabled toolkit slots listed below.

- **Project research verdict:** symlink
- **Global research verdict:** symlink
- **Installation truth:** actual filesystem pointers, no Instructions lock.
- **Default file:** `replit.md`
- **Project / global path:** `./replit.md` (project root only) / none (project-only)
- **Reads `AGENTS.md` natively:** no
- **Source:** [docs.replit.com/replitai/replit-dot-md](https://docs.replit.com/replitai/replit-dot-md)

Research verdicts/paths above are preserved evidence, not enabled mutation targets. The shipped `instructions_install.pointer_slots` contract determines actual scope support (native discovery is separate):

- **Toolkit project pointer:** `<project>/replit.md`
- **Toolkit global pointer:** unavailable — no managed pointer slot at this scope

## Skills { #skills }

The catalog supplies a skills placement for this harness. The [skills asset type](../asset-types/skills.md) uses the shared Standard slot where covered, otherwise its own projection.

- **Project dir:** `.agents/skills`
- **Global dir:** `~/.config/agents/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** yes — reads the per-asset-type general directory directly
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Not supported (gap) — tracked for possible future work.

- **Verdict:** unsupported (gap)
- **Why:** Agent 3/4 spawns subagents at runtime; no user file-drop convention
- **Source:** [docs.replit.com/replitai/agent](https://docs.replit.com/replitai/agent)

## Commands { #commands }

Unknown — bounded search surfaced no public evidence.

- **Support:** ?
- **How:** unknown — no public evidence found
