# Batch 9 — Long-tail (raw research fragment)

> Raw output. Orchestrator normalizes verdict labels to matrix vocabulary at assembly (Task 4).

| Harness | Verdict | Mechanism | User path / Project path | Format + required/forbidden fields | Citation |
|---|---|---|---|---|---|
| `mcpjam` | `unsupported (by design)` | — | — / — | MCP inspector/testing tool, not a coding harness; no subagent concept | https://www.mcpjam.com/ ; github.com/MCPJam/inspector |
| `mistral-vibe` | `config_file+folder` | TOML agent file; `agent_type = "subagent"` enables delegation | `~/.vibe/agents/<name>.toml` / `.vibe/agents/<name>.toml` | TOML; required `agent_type="subagent"`, `display_name`, `description`, `safety`, `enabled_tools`; optional `active_model`, `system_prompt_id` | https://docs.mistral.ai/mistral-vibe/agents-skills |
| `openhands` | `unsupported (gap)` | skills/microagents = prompt injection, not spawn | `.openhands/microagents/` (V0 deprecated) / `.openhands/skills/` or `.agents/skills/` (V1) | markdown ± frontmatter; keyword-triggered; injection only, no subagent spawn | https://docs.openhands.dev/overview/skills ; github.com/OpenHands/OpenHands/blob/main/skills/README.md |
| `replit` | `unsupported (gap)` | internal runtime subagent spawn; no user file convention | — / — | no file-based subagent def; spawn is internal Agent 3/4 behavior | https://docs.replit.com/replitai/agent |
| `github-copilot` | `config_file+folder` | `.agent.md` file drop | `~/.copilot/agents/<name>.agent.md` / `.github/agents/<name>.agent.md` | markdown+frontmatter; required `description`; optional `name`, `tools`, `mcp-servers`, `model`, `target`, `user-invocable`; body ≤30k chars | https://docs.github.com/en/copilot/reference/custom-agents-configuration |
| `pochi` | `config_file+folder` | `.md` file drop; `newTask` invokes named agent | `~/.pochi/agents/<name>.md` / `.pochi/agents/<name>.md` | markdown+frontmatter; required `description`; optional `name`, `tools` (allowlist); body=system prompt | https://docs.getpochi.com/custom-agent ; github.com/TabbyML/pochi/issues/391 |
| `adal` | `unknown — no public evidence found` | — | — / — | AdaL CLI main codebase private; public repo docs-only; AGENTS.md+SKILL.md but no public subagent file convention | https://codingagents.md/agents/adal/ ; github.com/SylphAI-Inc/adal-cli |

## What I checked — Batch 9 Long-tail

- `mcpjam`: MCP server testing/debugging platform (JSON-RPC inspector, evals). No coding-harness identity, no subagent concept. → `unsupported (by design)`.
- `mistral-vibe`: official docs confirm TOML agents `~/.vibe/agents/` + `.vibe/agents/`; `agent_type="subagent"` makes it delegatable; built-in `explore` subagent. → TOML drop-in (translate to TOML).
- `openhands`: microagents/skills are context/prompt injection on keyword match — no spawn, no handoff to child process. V0 `.openhands/microagents/` deprecated; V1 `.agents/skills/`. → `unsupported (gap)` (path+format exist but concept is injection not spawn).
- `replit`: Agent 3/4 spawns parallel subagents at runtime (orchestrator-driven) but no user file-drop convention. → `unsupported (gap)`.
- `github-copilot`: RICH finding — two mechanisms: (1) `~/.copilot/agents/` CLI user-level; (2) `.github/agents/` project/org-level; `.agent.md` extension; only `description` required. Works across Copilot CLI + cloud coding agent. → markdown drop-in (`.agent.md` suffix → translate for filename + frontmatter).
- `pochi` (TabbyML): `.md`+frontmatter in `~/.pochi/agents/` + `.pochi/agents/`; spawn other agents via `newTask(<name>)` allowlist; `description` required. → markdown drop-in.
- `adal` (SylphAI): main codebase private; public repo docs-only; AGENTS.md+SKILL.md surfaced but no public subagent file convention. → `unknown`.

## Baseline deltas (vs v1 tag v1.0.0)

- None in v1's 5. THREE newly-supported: **github-copilot** (`.agent.md` → translate), **pochi** (markdown → symlink/translate), **mistral-vibe** (TOML → translate). openhands + replit = gap; mcpjam + adal = by design/unknown.

## Re-verification 2026-06-10 — `.claude/agents/` readers (#361)

- `mistral-vibe`: WebSearch — no evidence; agents are TOML in `~/.vibe/agents/`
  + `.vibe/agents/`. (Blog posts about *delegating from Claude Code to Vibe*
  describe a Claude-side agent file, not Vibe reading `.claude/agents/`.)
  Negative.
- `github-copilot`: WebSearch + docs.github.com custom-agents pages — agents
  are `.github/agents/*.agent.md` (project) + `~/.copilot/agents/` (user); no
  `.claude/agents/` read documented. Negative.
- `pochi`: WebSearch — no evidence; own `.pochi/agents/` dirs only. Negative.
