# ![Kilo Code logo](https://www.google.com/s2/favicons?domain=kilo.ai&sz=64){ .harness-logo } Kilo Code

`kilo` · one row of the [compatibility matrix](../matrix.md)

Use the packaged **`atc` CLI** / **`att` TUI**; long executable names remain supported.
[Install and verify](../agent-toolkit/installation.md) ·
[Package updates](../agent-toolkit/updates.md) ·
[Shell completion](../agent-toolkit/shell-completion.md).
These application utilities do not enable assets or expand this harness's supported scopes.

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | [✅](#instructions) | research: native; toolkit pointer scopes: none |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `.kilocode/skills` |
| [Agents (subagents)](../asset-types/agents.md) | [✅](#agents) | translate |
| [Commands](../asset-types/commands.md) | [?](#commands) | unknown — no public evidence found |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Classified as a native `AGENTS.md` reader; no project pointer is created. Check the discovery paths below: some readers are workspace-only or do not load the root canonical at every scope.

- **Project research verdict:** native
- **Global research verdict:** native
- **Installation truth:** actual filesystem pointers, no Instructions lock.
- **Default file:** `AGENTS.md`
- **Project / global path:** `./AGENTS.md` / none (project-only)
- **Reads `AGENTS.md` natively:** yes
- **Source:** [kilo.ai/docs/agent-behavior/agents-md](https://kilo.ai/docs/agent-behavior/agents-md)

Research verdicts/paths above are preserved evidence, not enabled mutation targets. The shipped `instructions_install.pointer_slots` contract determines actual scope support (native discovery is separate):

- **Toolkit project pointer:** unavailable — no managed pointer slot at this scope
- **Toolkit global pointer:** unavailable — no managed pointer slot at this scope

## Skills { #skills }

The catalog supplies a skills placement for this harness. The [skills asset type](../asset-types/skills.md) uses the shared Standard slot where covered, otherwise its own projection.

- **Project dir:** `.kilocode/skills`
- **Global dir:** `~/.kilocode/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets its own projection
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Researched support via **translate**; check the enabled adapter below — see the [agents asset type](../asset-types/agents.md) for what each mechanism means.

- **Mechanism:** translate
- **User / project path:** `~/.config/kilo/agent/<slug>.md` / `.kilo/agents/<slug>.md`
- **Format:** markdown+frontmatter; required `description`,`mode`(inject `subagent`); optional `model`,`permission`
- **Toolkit adapter:** enabled (translate)
- **Source:** [kilo.ai/docs/agent-behavior/custom-modes](https://kilo.ai/docs/agent-behavior/custom-modes)

## Commands { #commands }

Unknown — bounded search surfaced no public evidence.

- **Support:** ?
- **How:** unknown — no public evidence found
