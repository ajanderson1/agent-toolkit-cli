# ![Kode logo](https://github.com/shareAI-lab.png?size=64){ .harness-logo } Kode

`kode` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | research: native; toolkit pointer scopes: none |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.kode/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [✅](#agents) | symlink |
| [Commands](../asset-types/commands.md) | [?](#commands) | unknown — no public evidence found |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Classified as a native `AGENTS.md` reader; no project pointer is created. Check the discovery paths below: some readers are workspace-only or do not load the root canonical at every scope.

- **Project research verdict:** native
- **Global research verdict:** native
- **Installation truth:** actual filesystem pointers, no Instructions lock.
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` (prefers `AGENTS.override.md`) / none (project-only; `~/.kode.json` is JSON config, not an instruction file)
- **Reads `AGENTS.md` natively:** yes
- **Source:** [github.com/shareAI-lab/Kode-cli](https://github.com/shareAI-lab/Kode-cli) README § "AGENTS.md Standard Support" ("Native support for the OpenAI-initiated standard format … prefers `AGENTS.override.md` over `AGENTS.md`")

Research verdicts/paths above are preserved evidence, not enabled mutation targets. The shipped `instructions_install.pointer_slots` contract determines actual scope support (native discovery is separate):

- **Toolkit project pointer:** unavailable — no managed pointer slot at this scope
- **Toolkit global pointer:** unavailable — no managed pointer slot at this scope

## Skills { #skills }

The catalog supplies a skills placement for this harness. The [skills asset type](../asset-types/skills.md) uses the shared Standard slot where covered, otherwise its own projection.

- **Project dir:** `.kode/skills`
- **Global dir:** `~/.kode/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Researched support via **symlink**; check the enabled adapter below — see the [agents asset type](../asset-types/agents.md) for what each mechanism means.

- **Mechanism:** symlink
- **User / project path:** `~/.claude/agents/<slug>.md` (also `~/.kode/agents/`) / `.claude/agents/<slug>.md`
- **Format:** markdown+frontmatter; required `name`,`description`; `model_name` (not `model`)
- **Toolkit adapter:** enabled (symlink)
- **Source:** [github.com/shareAI-lab/Kode-CLI/blob/main/docs/agents-system.md](https://github.com/shareAI-lab/Kode-CLI/blob/main/docs/agents-system.md)

## Commands { #commands }

Unknown — bounded search surfaced no public evidence.

- **Support:** ?
- **How:** unknown — no public evidence found
