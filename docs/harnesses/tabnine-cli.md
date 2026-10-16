# ![Tabnine CLI logo](https://www.google.com/s2/favicons?domain=tabnine.com&sz=64){ .harness-logo } Tabnine CLI

`tabnine-cli` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | pointer symlink (`TABNINE.md` → `AGENTS.md`); global pointer slot |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.tabnine/agent/skills` |
| [Agents (subagents)](../asset-types/agents.md) | N/A | no subagent concept |
| [Commands](../asset-types/commands.md) | [?](#commands) | unknown — no public evidence found |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Reads a fixed own-name file (`TABNINE.md`) instead of `AGENTS.md`. The [instructions asset type](../asset-types/instructions.md) creates a same-name pointer symlink → `AGENTS.md`.

- **Project verdict:** symlink
- **Global verdict:** symlink
- **Installation truth:** actual filesystem pointers, no Instructions lock.
- **Default file:** `TABNINE.md`
- **Project / global path:** `./TABNINE.md` / unclear (no documented global `TABNINE.md` path; `~/.tabnine/guidelines/*.md` is a *directory* of guidelines, not the same file)
- **Reads `AGENTS.md` natively:** no
- **Source:** [docs.tabnine.com/main/getting-started/tabnine-cli/getting-started/quickstart](https://docs.tabnine.com/main/getting-started/tabnine-cli/getting-started/quickstart) ("Add project context with a `TABNINE.md` file in your project root") and [docs.tabnine.com/main/getting-started/tabnine-cli/features/agent-skills](https://docs.tabnine.com/main/getting-started/tabnine-cli/features/agent-skills) ("Unlike `TABNINE.md` project instructions (which load automatically on every session), skills load only when relevant")

A global pointer slot is managed separately from project native reading; install links it to user-authored `~/.agent-toolkit/AGENTS.md`. Only supported/requested slots change; install never authors canonical content.

## Skills { #skills }

The catalog supplies a skills placement for this harness. The [skills asset type](../asset-types/skills.md) uses the shared Standard slot where covered, otherwise its own projection.

- **Project dir:** `.tabnine/agent/skills`
- **Global dir:** `~/.tabnine/agent/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Not applicable — no subagent concept; won't be filled.

- **Verdict:** unsupported (by design)
- **Why:** Enterprise Agent internal mini-agent routing; not user-definable
- **Source:** [docs.tabnine.com/main/getting-started/tabnine-cli](https://docs.tabnine.com/main/getting-started/tabnine-cli)

## Commands { #commands }

Unknown — bounded search surfaced no public evidence.

- **Support:** ?
- **How:** unknown — no public evidence found
