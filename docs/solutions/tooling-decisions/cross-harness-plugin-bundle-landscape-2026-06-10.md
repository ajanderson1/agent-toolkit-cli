---
title: Cross-harness plugin/bundle landscape (mid-2026) — no shared bundle standard exists
date: 2026-06-10
category: tooling-decisions
module: agent-toolkit-cli
problem_type: tooling_decision
component: tooling
severity: medium
applies_when:
  - Evaluating whether a cross-harness bundle/plugin kind can adopt an existing standard instead of inventing one
  - Adding a new harness adapter and needing to know whether it has a first-class plugin/bundle concept
  - Comparing manifest formats (Claude Code plugins, Copilot CLI shared format, Gemini CLI extensions, Pi packages, Codex plugins, Goose recipes)
  - Deciding how to treat hooks-only (OpenCode) or single-asset-only (Amp, Cursor, Droid) harnesses in a bundle design
tags: [plugins, bundles, harness-matrix, claude-code, gemini-cli, pi, manifest-formats, ecosystem-survey]
related_components: [development_workflow]
---

# Cross-harness plugin/bundle landscape (mid-2026) — no shared bundle standard exists

## Context

agent-toolkit-cli manages four asset kinds (skills, agents, instructions, pi-extensions) across 54 harnesses via clone-and-project. As of mid-2026, most major harnesses have grown a native "bundle" concept — a multi-asset unit shipping skills, agents, MCP servers, hooks, and config together. Before deciding how agent-toolkit-cli should handle bundles (see the companion ADR in `architecture-patterns/`), we surveyed what every harness actually ships, what each manifest looks like, and whether any cross-harness bundle standard exists. This doc is the reference snapshot of that survey, current as of 2026-06-10. It covers the *external* landscape only; the in-repo SSOT for per-harness support of our own kinds is `docs/agent-toolkit/harness-matrix.md`.

## Guidance

### Comparison table

| Harness | Bundle concept | Manifest | Can contain | Distribution | Notes |
|---|---|---|---|---|---|
| Claude Code | Plugin | `.claude-plugin/plugin.json` (only `name` required; components auto-discovered) | skills, agents, hooks (`hooks.json`), MCP servers (`.mcp.json`), LSP servers, commands, themes | `/plugin marketplace add` — GitHub, npm, GitLab, local paths; `marketplace.json` one layer above (one marketplace entry can ship multiple plugins) | Scopes: user/project/local/managed. Plugin-shipped agents CANNOT declare hooks, mcpServers, or permissionMode |
| GitHub Copilot CLI | Plugin | `plugin.json` — explicitly **shared format with Claude Code**, minor documented divergences (e.g. omit the `skills` field for cross-compat) | same family as Claude Code | GitHub repos, marketplace | Microsoft ships dual-target plugins (Power Platform Skills, WinUI) |
| Gemini CLI | Extension | `gemini-extension.json` (`name` required; `mcpServers` map, `contextFileName`, `excludeTools`, `settings[]`, `themes[]`) | MCP servers, TOML commands, hooks, skills, sub-agents, policies, `GEMINI.md` context | `gemini extensions install <github-url\|path>`; gallery at geminicli.com/extensions | |
| Pi (badlogic/pi-mono) | Package | standard `package.json` with a `"pi"` key: `{"pi": {"extensions": [...], "skills": [...], "prompts": [...], "themes": [...]}}`; conventional dir names auto-discovered | extensions, skills, prompts, themes — **NOT MCP** (MCP is not a bundled component) | npm (`pi install npm:@foo/bar`), git URL, local path; `pi-package` keyword for gallery discovery | Global install by default, `-l` for project |
| Codex CLI | Plugin | not fully documented publicly; configured under `[plugins]` in `config.toml` + `/plugins` command | skills, apps, MCP servers | in-app curated catalog | Public manifest schema incomplete |
| Goose | Extension (MCP wrappers only) + Recipe | YAML recipe: goal + required extensions + inputs + steps + subrecipes | recipes bundle workflow, not assets; skills via SKILL.md standard | recipe cookbook + skills marketplace | Moved to Agentic AI Foundation (Linux Foundation) early 2026 |
| OpenCode | "Plugin" = JS/TS hook module | listed in `opencode.json` | custom tools + event hooks only — NOT multi-asset bundles | npm via Bun | |
| Amp | none (SKILL.md skills only) | — | — | — | Legacy toolboxes removed |
| Cursor | none (SKILL.md skills only) | — | — | — | |
| Factory Droid | none | — | individual droid `.md` files only | — | |

### Cross-harness state

- **SKILL.md standard** (agentskills.io, launched by Anthropic Dec 2025): adopted by 35+ tools — but covers **individual skills only**, not bundles.
- **No cross-harness bundle/plugin manifest standard exists.** The Claude Code ↔ Copilot CLI shared `plugin.json` is the only "write once, run twice" bundle pattern actually shipping.
- Three distinct manifest philosophies: dedicated manifest file (Claude/Copilot `plugin.json`, Gemini `gemini-extension.json`), key-in-existing-manifest (Pi's `"pi"` key in `package.json`), and config-side registration (Codex `config.toml`, OpenCode `opencode.json`).

### Sources

- Claude Code: https://code.claude.com/docs/en/plugins-reference and https://github.com/anthropics/claude-plugins-official
- Copilot CLI: https://docs.github.com/en/copilot/concepts/agents/copilot-cli/about-cli-plugins
- Gemini CLI: https://geminicli.com/docs/extensions/reference/
- Pi: https://badlogic-pi-mono.mintlify.app/coding-agent/pi-packages
- Codex: https://developers.openai.com/codex/plugins
- SKILL.md standard: https://agentskills.io/home

## Why This Matters

Any bundle feature in agent-toolkit-cli has to interoperate with these native systems, not pretend they don't exist. The survey establishes three load-bearing facts: (1) bundle manifests are wildly divergent — four incompatible formats among just the harnesses that have one — so pairwise translation doesn't scale; (2) the only convergence shipping is Claude/Copilot's shared `plugin.json`, making it the strongest candidate for an input format we'd parse; (3) several harnesses' "bundles" aren't asset bundles at all (OpenCode hook modules, Goose recipes), so a per-harness verdict model — like the existing 54-harness matrix in `docs/agent-toolkit/harness-matrix.md` — is required, not optional.

## When to Apply

- Designing or reviewing the bundle/composite kind for agent-toolkit-cli (see the companion ADR).
- Evaluating whether a new harness's "plugin" concept maps to our kinds — check this table first for the closest analogue.
- Deciding which manifest format to accept as bundle input.
- Re-survey trigger: this is a point-in-time snapshot (2026-06-10). Re-verify before relying on it after ~Q4 2026, especially Codex (schema undocumented) and any cross-harness standardisation effort following SKILL.md's trajectory.

## Examples

**Same logical bundle, three manifests.** A bundle with one skill, one agent, one MCP server:

- Claude Code: `.claude-plugin/plugin.json` with `{"name": "foo"}` — skill/agent/MCP auto-discovered from `skills/`, `agents/`, `.mcp.json`.
- Gemini CLI: `gemini-extension.json` with `{"name": "foo", "mcpServers": {...}}` — skill and sub-agent in conventional dirs.
- Pi: `package.json` with `{"pi": {"skills": ["skills/"], "extensions": [...]}}` — and **no way to ship the MCP server at all**.

**The one portability win that exists.** Microsoft's Power Platform Skills plugin ships a single `plugin.json` consumed by both Claude Code and Copilot CLI, with the documented caveat of omitting the `skills` field for cross-compat.

**A "plugin" that isn't a bundle.** OpenCode plugins are JS modules registering event hooks — installing a multi-asset bundle "into OpenCode" has no native target; only its constituent skills (SKILL.md) land anywhere.

## Related

- Companion ADR: `docs/solutions/architecture-patterns/clone-and-project-substrate-for-bundle-plugin-capability-2026-06-10.md`
- In-repo per-harness SSOT: `docs/agent-toolkit/harness-matrix.md`
- Prior plugin-kind work: issue #149 (closed — declarative wrapper around native Claude plugin install), issues #64/#72 (closed — walker/ingest handling of `.claude-plugin/plugin.json`)
