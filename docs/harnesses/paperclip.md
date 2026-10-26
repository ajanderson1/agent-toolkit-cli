# ![Paperclip logo](https://www.google.com/s2/favicons?domain=paperclip.ing&sz=64){ .harness-logo } Paperclip

`paperclip` · one row of the [compatibility matrix](../matrix.md)

Use the packaged **`atc` CLI** / **`att` TUI**; long executable names remain supported.
[Install and verify](../agent-toolkit/installation.md) ·
[Package updates](../agent-toolkit/updates.md) ·
[Shell completion](../agent-toolkit/shell-completion.md).
These application utilities do not enable assets or expand this harness's supported scopes.

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | N/A | no instruction-file concept |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `<instance-root>/skills/<company-id>` (project scope; company-scoped) |
| [Agents (subagents)](../asset-types/agents.md) | N/A | no subagent concept |
| [Commands](../asset-types/commands.md) | N/A | company Skills integration only; no command concept |
| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |
| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |

## Instructions { #instructions }

Not applicable — no root instruction-file concept at all.

- **Project research verdict:** unsupported (by design)
- **Global research verdict:** unsupported (by design)
- **Installation truth:** actual filesystem pointers, no Instructions lock.
- **Default file:** none
- **Project / global path:** none / none
- **Reads `AGENTS.md` natively:** no
- **Source:** Paperclip company integration in Agent Toolkit is intentionally Skills-only; issue #474

Research verdicts/paths above are preserved evidence, not enabled mutation targets. The shipped `instructions_install.pointer_slots` contract determines actual scope support (native discovery is separate):

- **Toolkit project pointer:** unavailable — no managed pointer slot at this scope
- **Toolkit global pointer:** unavailable — no managed pointer slot at this scope

## Skills { #skills }

Supported at project scope for a detected Paperclip company; global scope is unavailable.

- **Project dir:** `<instance-root>/skills/<company-id>`
- **Global dir:** unavailable — Paperclip skills are company-scoped
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** no — gets a company-library projection
- **Source:** Agent Toolkit issue #474 and its approved design

## Agents (subagents) { #agents }

Not applicable — no subagent concept; won't be filled.

- **Verdict:** unsupported (by design)
- **Why:** company-scoped Skills library only; no Agent asset adapter
- **Source:** issue #474

## Commands { #commands }

Not applicable — no command concept in this integration.

- **Support:** N/A
- **How:** company Skills integration only; no command concept
