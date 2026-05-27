# Batch 8 — China-market CLIs (raw research fragment)

> Raw output. Orchestrator normalizes verdict labels to matrix vocabulary at assembly (Task 4).
> Markdown drop-ins → `symlink`/`translate`; codestudio unknown.

| Harness | Verdict | Mechanism | User path / Project path | Format + required/forbidden fields | Citation |
|---|---|---|---|---|---|
| `codebuddy` | `config_file+folder` | markdown file-drop, `/agents` discovery | `~/.codebuddy/agents/` / `.codebuddy/agents/` | markdown+frontmatter; required `name` (lc+hyphens), `description`; optional `tools`, `model`, `permissionMode`, `skills`; body=system prompt | https://www.codebuddy.ai/docs/cli/sub-agents |
| `codestudio` | `unknown — no public evidence found` | — | — / — | no product "codestudio" found across Chinese vendors/GitHub/roundups; may be placeholder/unreleased | (exhaustive search, no source) |
| `forgecode` | `config_file+folder` | markdown file-drop, `ForgeAgentRepository` | `~/.forge/agents/*.md` (legacy `~/forge/agents/`) / `.forge/agents/*.md` | markdown+frontmatter; required `id` (auto from filename); optional `title`, `model`, `description`, `system_prompt`, `tools`, `max_turns`, `temperature`, etc. | github.com/antinomyhq/forgecode crates/forge_repo/src/agent.rs |
| `hermes-agent` | `unsupported (by design)` | — | — / — | `delegate_task` tool runtime-only; no file-drop; config only `~/.hermes/config.yaml` | https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation |
| `kiro-cli` | `config_file+folder` | JSON file-drop, name reference + `subagent`/`delegate` tools | `~/.kiro/agents/<name>.json` / `.kiro/agents/<name>.json` | JSON (NOT markdown); no strict required; optional `name`, `description`, `prompt` (inline or `file://`), `model`, `tools`, `mcpServers`, etc.; filename=agent ID | https://kiro.dev/docs/cli/custom-agents/configuration-reference/ |
| `augment` | `config_file+folder` | markdown file-drop, auto-detect + explicit ref | `~/.augment/agents/` / `.augment/agents/` | markdown+frontmatter; required `name`; optional `description`, `color`, `model`, `tools` (allowlist), `disabled_tools` (denylist wins); body=prompt | https://docs.augmentcode.com/cli/subagents |

## What I checked — Batch 8 China-market CLIs

- `codebuddy` (Tencent): dedicated Sub-Agents docs page (CLI + IDE); `~/.codebuddy/agents/` + `.codebuddy/agents/`, markdown+frontmatter. Plugin agents also load from manifest `agents/`. → markdown drop-in.
- `codestudio`: no product with this exact name found anywhere (ByteDance/Trae, Alibaba/Qoder, Baidu/Comate, Tencent/CodeBuddy all checked). → `unknown`.
- `forgecode` (antinomyhq, OSS Rust): source-confirmed `agent.rs` — `~/.forge/agents/` (new) or `~/forge/agents/` (legacy), `.forge/agents/`; markdown+frontmatter; `id` auto-derived; project overrides global. Spawn via `task` tool recursion. → markdown drop-in.
- `hermes-agent` (NousResearch): `delegate_task` tool only, no file-drop, no agents dir. → `unsupported (by design)`.
- `kiro-cli` (AWS Kiro): JSON agents in `~/.kiro/agents/` + `.kiro/agents/` (distinct from `steering/` *.md + specs). `subagent`/`delegate` runtime tools reference by filename. → config_file+folder (JSON, needs translate to JSON).
- `augment` (Augment Code): `~/.augment/agents/` + `.augment/agents/`, markdown+frontmatter, `tools`/`disabled_tools` mutual exclusion. → markdown drop-in.

## Baseline deltas (vs v1 tag v1.0.0)

- None in v1's 5. FOUR newly-supported: **codebuddy, forgecode, augment** (markdown drop-in → symlink/translate), **kiro-cli** (JSON → translate to JSON). hermes = by design; codestudio = unknown.
