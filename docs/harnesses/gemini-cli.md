# ![Gemini CLI logo](https://github.com/google-gemini.png?size=64){ .harness-logo } Gemini CLI

`gemini-cli` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [✅](#instructions) | pointer symlink (`GEMINI.md` → `AGENTS.md`) |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.agents/skills` |
| [Agents (subagents)](../kinds/agents.md) | [✅](#agents) | translate |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | N/A | Pi-only kind |

## Instructions { #instructions }

Reads a fixed own-name file (`GEMINI.md`) instead of `AGENTS.md`. The [instructions kind](../kinds/instructions.md) creates a same-name pointer symlink → `AGENTS.md`.

- **Verdict:** symlink
- **Default file:** `GEMINI.md`
- **Project / global path:** `./GEMINI.md` / `~/.gemini/GEMINI.md`
- **Reads `AGENTS.md` natively:** no
- **Source:** [`packages/core/src/tools/memoryTool.ts`](https://github.com/google-gemini/gemini-cli/blob/main/packages/core/src/tools/memoryTool.ts) — `export const DEFAULT_CONTEXT_FILENAME = 'GEMINI.md';` + [`docs/cli/gemini-md.md`](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/gemini-md.md)

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.agents/skills`
- **Global dir:** `~/.gemini/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** yes — reads the per-kind general directory directly
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Supported via the **translate** mechanism — see the [agents kind](../kinds/agents.md) for what each mechanism means.

- **Mechanism:** translate
- **User / project path:** `~/.gemini/agents/<slug>.md` / `.gemini/agents/<slug>.md`
- **Format:** markdown+frontmatter; ONLY `name`+`description` (zod `.strict()` rejects extras)
- **Toolkit adapter:** enabled (translate)
- **Source:** [`packages/core/src/agents/agentLoader.ts`](https://github.com/google-gemini/gemini-cli/blob/main/packages/core/src/agents/agentLoader.ts) localAgentSchema.strict() + `storage.ts:117-118,309-310`
