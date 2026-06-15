# agent-toolkit-cli

A Python CLI and Textual TUI for managing AI-agent assets — skills, agents,
instructions, Pi extensions, and MCP servers — across many harnesses. Each asset
type keeps one canonical definition and a lock file, and projects it into every
harness you use by the cheapest mechanism that harness accepts (symlink,
translate, or config-injection).

Install and quickstart live in the [README](https://github.com/ajanderson1/agent-toolkit-cli#readme).
These docs are the reference and the per-asset-type mental models.

## Asset types

- [Skills](asset-types/skills.md) — reusable skill folders, library + lockfile.
- [Agents](asset-types/agents.md) — subagent definitions, projected per harness.
- [Instructions](asset-types/instructions.md) — harness-aware pointers to a canonical `AGENTS.md`.
- [Pi extensions](asset-types/pi-extensions.md) — Pi extension inventory.
- [MCP servers](asset-types/mcp.md) — config-injection of MCP server registrations.

## Reference

- [CLI reference](agent-toolkit/cli.md) — every command group and verb.
- [Compatibility matrix](matrix.md) — which harness supports which asset type.
- [Bundles](agent-toolkit/bundles.md) — install several assets together.
- [Skill lock management](agent-toolkit/skill-lock.md) — skill lock-file format.
- [Glossary](glossary.md) — asset type, library, projection, mechanism, and other terms.
