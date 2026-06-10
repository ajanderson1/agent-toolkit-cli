# ![Codex logo](https://www.google.com/s2/favicons?domain=openai.com&sz=64){ .harness-logo } Codex

`codex` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | [✅](#instructions) | native `AGENTS.md` reader |
| [Skills](../kinds/skills.md) | [✅](#skills) | `.agents/skills` |
| [Agents (subagents)](../kinds/agents.md) | [✅](#agents) | config_file+folder |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
| [Pi extensions](../kinds/pi-extensions.md) | N/A | Pi-only kind |

## Instructions { #instructions }

Reads the canonical `AGENTS.md` natively — no pointer needed; the [instructions kind](../kinds/instructions.md) is satisfied as-is.

- **Verdict:** native
- **Default file:** `AGENTS.md`
- **Project / global path:** `<git-root>/AGENTS.md` (walks git-root → cwd) / `~/.codex/AGENTS.md` (or `AGENTS.override.md`; honors `$CODEX_HOME`)
- **Reads `AGENTS.md` natively:** yes
- **Source:** [developers.openai.com/codex/guides/agents-md](https://developers.openai.com/codex/guides/agents-md)

## Skills { #skills }

Supported — every harness in the catalog has a skills directory the [skills kind](../kinds/skills.md) projects into.

- **Project dir:** `.agents/skills`
- **Global dir:** `~/.codex/skills`
- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** yes — reads the per-kind general directory directly
- **Source:** [vercel-labs/skills · `src/agents.ts`](https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the upstream per-harness catalog these directories come from (ported as `skill_agents.py`, parity-tested)

## Agents (subagents) { #agents }

Supported via the **config_file+folder** mechanism — see the [agents kind](../kinds/agents.md) for what each mechanism means.

- **Mechanism:** config_file+folder
- **User / project path:** `~/.codex/agents/<slug>.toml` + `[agents.<role>]` in `~/.codex/config.toml` / `.codex/agents/<slug>.toml`
- **Format:** TOML; role decl req `description`; file req `developer_instructions`; registered via `config_file=`
- **Toolkit adapter:** currently disabled — registry-gated shared config.toml — no safe escape hatch; pending AJ decision (PR5a)
- **Source:** [developers.openai.com/codex/subagents](https://developers.openai.com/codex/subagents) + [`codex-rs/config/src/config_toml.rs:649-691`](https://github.com/openai/codex/blob/main/codex-rs/config/src/config_toml.rs)
