# Batch 4 — Codex/OpenAI-likes (raw research fragment)

> Raw output. Orchestrator normalizes verdict labels to matrix vocabulary at assembly (Task 4).

| Harness | Verdict | Mechanism | User path / Project path | Format + required/forbidden fields | Citation |
|---|---|---|---|---|---|
| `codex` | `config_file` | `AgentRoleToml.config_file` | `~/.codex/agents/<slug>.toml` (declared via `[agents.<role>]` in `~/.codex/config.toml`) / `.codex/agents/<slug>.toml` | TOML; role decl requires `description`; pointed file requires `developer_instructions`; optional `model`, `sandbox_mode`, `mcp_servers`, `nickname_candidates` | https://developers.openai.com/codex/subagents + `codex-rs/config/src/config_toml.rs:649-691` |
| `kimi-cli` | `unsupported (gap)` | explicit `--agent-file` flag only | n/a / n/a | YAML; required `version: 1`, `name`, `system_prompt_path`, `tools`; subagents nested `subagents.<id>.path` | https://moonshotai.github.io/kimi-cli/en/customization/agents.html |
| `dexto` | `config_file` | `agent-spawner` tool in agents YAML | `~/.dexto/agents/<name>.yml` (unconfirmed) / `agents/<name>.yml` (project) | YAML; required `systemPrompt`, `llm.provider`, `llm.model`, `llm.apiKey`; spawning via `tools[].type: agent-spawner`, `allowedAgents` | https://docs.dexto.ai/docs/guides/configuring-dexto/agent-yml + github.com/truffle-ai/dexto |
| `neovate` | `symlink` | `.md` drop-in, YAML frontmatter | `~/.neovate/agents/<slug>.md` OR `~/.claude/agents/<slug>.md` / `.neovate/agents/<slug>.md` OR `.claude/agents/<slug>.md` | markdown+frontmatter; required `name` (≤64), `description` (≤1024); body=system prompt; optional `tools`, `disallowedTools`, `model`, `forkContext`, `color` | `neovateai/neovate-code:src/agent/agentManager.ts:162-235` |

## What I checked — Batch 4 Codex/OpenAI-likes

- `codex`: Docs (developers.openai.com/codex/subagents) describe `~/.codex/agents/<slug>.toml`; Rust source `codex-rs/config/src/config_toml.rs` shows the real mechanism is `[agents.<role>]` stanzas in `config.toml` with `config_file` pointing to external TOML (NOT auto-scan). `AgentRoleToml` struct at :680-692. Adjusted from v1 `translate` → `config_file` (needs explicit per-role declaration).
- `kimi-cli`: Subagents via YAML + `--agent-file` flag (no auto-scanned dir). Projection would require wrapping CLI invocation. → `unsupported (gap)`.
- `dexto`: `agent-spawner` tool in YAML configs under project `agents/`. No confirmed global user path. → `config_file` (explicit YAML registry).
- `neovate`: Source-confirmed reads `~/.claude/agents/`, `~/.neovate/agents/`, `.claude/agents/`, `.neovate/agents/`. Format identical to Claude Code. → `symlink`.

## Baseline deltas (vs v1 tag v1.0.0)

- **codex:** v1 = `translate → ~/.codex/agents/<slug>.toml` (TOML name/description/developer_instructions, #140). CURRENT source contradicts the pure-translate model: codex requires an `[agents.<role>]` declaration in `config.toml` that POINTS to the TOML file via `config_file=`. So the real mechanism is **config_file** (mutate `config.toml` to register the role) **+folder** (materialize the pointed TOML) — i.e. `config_file+folder` in our vocabulary, NOT translate. This is a material baseline change for Phase B (#140's translate-only adapter is insufficient). FLAGGED.
- **neovate:** NOT in v1 — new supported harness, Claude-compatible markdown → symlink.

## Re-verification 2026-06-10 — `.claude/agents/` readers (#361)

- `neovate`: re-fetched `src/agent/agentManager.ts` (master) — still constructs
  a globalClaude dir (`~/.claude/agents/`) and a projectClaude dir
  (`<project>/.claude/agents/`) alongside the neovate-native dirs, scanned by
  default. HOLDS at both scopes.
- `dexto`: WebSearch — no evidence; agents remain YAML registry entries
  (`agent-spawner`), no `.claude/agents/` read. Negative.
