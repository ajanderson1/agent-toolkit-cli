# ![Augment logo](https://www.google.com/s2/favicons?domain=augmentcode.com&sz=64){ .harness-logo } Augment

`augment` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | pointer symlink (`CLAUDE.md` (with `AGENTS.md` as documented fallback) → `AGENTS.md`) |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.augment/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [✅](#agents) | symlink |
| [MCP servers](../asset-types/mcp.md) | — | planned asset type |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Reads a fixed own-name file (`CLAUDE.md` (with `AGENTS.md` as documented fallback)) instead of `AGENTS.md`. The [instructions asset type](../asset-types/instructions.md) creates a same-name pointer symlink → `AGENTS.md`.

- **Verdict:** symlink
- **Default file:** `CLAUDE.md` (with `AGENTS.md` as documented fallback)
- **Project / global path:** `./CLAUDE.md` (workspace root) / `~/.augment/rules/` (directory loader; no fixed root file at user scope)
- **Reads `AGENTS.md` natively:** no (CLAUDE.md takes precedence over AGENTS.md per official rule chain)
- **Source:** [docs.augmentcode.com/cli/rules](https://docs.augmentcode.com/cli/rules)

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills asset type](../asset-types/skills.md) projects into.

- **Project dir:** `.augment/skills`
- **Global dir:** `~/.augment/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Supported via the **symlink** mechanism — see the [agents asset type](../asset-types/agents.md) for what each mechanism means.

- **Mechanism:** symlink
- **User / project path:** `~/.augment/agents/<slug>.md` / `.augment/agents/<slug>.md`
- **Format:** markdown+frontmatter; required `name`; optional `description`,`color`,`model`,`tools`/`disabled_tools` (denylist wins)
- **Toolkit adapter:** enabled (symlink)
- **Source:** [docs.augmentcode.com/cli/subagents](https://docs.augmentcode.com/cli/subagents)
