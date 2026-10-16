# ![Goose logo](https://github.com/block.png?size=64){ .harness-logo } Goose

`goose` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | native classification; check discovery paths |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.goose/skills` |
| [Agents (subagents)](../asset-types/agents.md) | N/A | no subagent concept |
| [Commands](../asset-types/commands.md) | [?](#commands) | unknown — no public evidence found |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Classified as a native `AGENTS.md` reader; no project pointer is created. Check the discovery paths below: some readers are workspace-only or do not load the root canonical at every scope.

- **Project verdict:** native
- **Global verdict:** native
- **Installation truth:** actual filesystem pointers, no Instructions lock.
- **Default file:** `.goosehints` (and `AGENTS.md`)
- **Project / global path:** `./.goosehints` and `./AGENTS.md` / `~/.config/goose/.goosehints` and `~/.config/goose/AGENTS.md` (XDG; on macOS `~/Library/Application Support/Block/goose/`)
- **Reads `AGENTS.md` natively:** yes
- **Source:** [block/goose `crates/goose/src/hints/load_hints.rs`](https://github.com/block/goose/blob/main/crates/goose/src/hints/load_hints.rs) — `get_context_filenames()` defaults to `[".goosehints", "AGENTS.md"]`; `load_hints_from_directory` reads both project-cwd and `Paths::in_config_dir(...)`

## Skills { #skills }

The catalog supplies a skills placement for this harness. The [skills asset type](../asset-types/skills.md) uses the shared Standard slot where covered, otherwise its own projection.

- **Project dir:** `.goose/skills`
- **Global dir:** `~/.config/goose/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Not applicable — no subagent concept; won't be filled.

- **Verdict:** unsupported (by design)
- **Why:** subagents transient (no def file); subrecipes are session presets, not spawnable assistants
- **Source:** [goose blog 2025-09-26: subagents vs subrecipes](https://goose-docs.ai/blog/2025/09/26/subagents-vs-subrecipes/)

## Commands { #commands }

Unknown — bounded search surfaced no public evidence.

- **Support:** ?
- **How:** unknown — no public evidence found
