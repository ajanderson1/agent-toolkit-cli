# MCP servers

The `mcp` [asset type](../glossary.md#asset-type) manages MCP (Model Context
Protocol) server registrations — authoring each server once into a local library,
then projecting it into the harnesses that read MCP config.

## How it works

Unlike skills and agents (which project by symlink), MCP uses
**config-injection by name**: each adapter surgically upserts a single named
entry inside the harness's own native config file, preserving every other byte.
Hand-rolled neighbours and unmanaged entries survive untouched. There is no file
ownership — the toolkit manages the `mcpServers.<slug>` / `[mcp_servers.<slug>]`
key, nothing else.

- **Library:** `~/.agent-toolkit/mcps/` — a plain local store (not a git clone).
  Each entry is `<library>/<slug>/config.json` plus a `<library>/<slug>.toolkit.yaml`
  metadata sidecar.
- **Lock file:** `mcps-lock.json` — global `~/.agent-toolkit/mcps-lock.json`,
  project `<project>/mcps-lock.json`. Each slug maps to a list of locked
  per-harness projections.
- **Pinning:** `add` / `update` best-effort resolve the current version and store
  it in the entry's `resolved_version`, so projected configs are effectively
  pinned (transparency, not enforcement). When resolution fails the entry is
  recorded `floating`.

## Supported harnesses

Four harnesses have MCP adapters: **claude-code, codex, opencode, pi**. The
adapters split by config format — `claude-code`, `pi`, and `opencode` write
`mcpServers.<slug>` into a JSON document; `codex` writes `[mcp_servers.<slug>]`
into `~/.codex/config.toml`. No other harness has an MCP adapter.

### The `standard` projection

`standard` is a [projection](../glossary.md#projection), not a harness. It owns
the canonical `mcpServers.<slug>` entry in `<project>/.mcp.json` — the shared
file the claude-code and pi adapters already write at project scope — collapsing
that double-write into one token and one lock row. Its covered set is exactly
**{claude-code, pi}**, and it is **project-scope only**: no client reads
`~/.mcp.json`, so there is no global standard (requesting one fails loud).
Installing `standard` at project scope folds the covered legacy rows into the
single standard row.

## Running-claude guard

A global-scope claude-code write targets `~/.claude.json`, which is live state
while Claude Code is running. That write is refused when a `claude` process is
detected; pass `--force` to override. Project-scope writes are not gated.

## CLI

```bash
agent-toolkit-cli mcp add --npx|--uvx|--docker|--url|--local <source> [--slug <slug>]
agent-toolkit-cli mcp install <slug>   [--harness <name>]... [-g|-p] [--force]
agent-toolkit-cli mcp uninstall <slug> [--harness <name>]... [-g|-p]
agent-toolkit-cli mcp remove <slug>    [-g|-p]   # full undo: every locked harness
agent-toolkit-cli mcp update <slug>             # re-resolve + re-project
agent-toolkit-cli mcp list   [-g|-p]            # alias: ls
agent-toolkit-cli mcp status [<slug>...] [-g|-p]
agent-toolkit-cli mcp doctor [-g|-p]            # read-only drift report
```

See also: [Skills](skills.md) · [Agents](agents.md) ·
[CLI reference](../agent-toolkit/cli.md) · [Glossary](../glossary.md)
