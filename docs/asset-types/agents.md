# Agents (subagents)

The optional [shared catalogue](../agent-toolkit/catalog.md) lists agents without
acquiring or enabling them. Use this kind's `catalog list` / `catalog add` /
`catalog enable` commands for Git entries; native Pi npm uses explicit confirmed
`pi-extensions catalog install`, not library registration.


Agents are delegable assistant definitions: canonical Markdown with frontmatter, stored in a source-backed library and projected into supported harness slots. `agents-lock.json` uses the shared `skills` envelope. Source metadata is not proof that the projected file still exists.

## Projection and scope

- **Standard:** `.claude/agents/<slug>.md` (or `~/.claude/agents/<slug>.md`). Shared readers are Claude Code, Kode, Neovate, Cortex and Cursor at both scopes, plus Devin at project scope only. `claude-code` normalizes to `standard`.
- **Symlink:** Claude-compatible Markdown in a harness's own directory.
- **Translate:** generated frontmatter/format in a managed cache, linked into the native slot.
- **Config + folder:** registry entry plus managed artifact where the enabled adapter needs both.
- **Dual symlink:** Pi's agent paths for the external subagent extension; installation does not install that extension or guarantee it is loaded.

Install defaults to Standard plus enabled non-covered adapters at that scope; uninstall is deliberately broader to remove legacy own-directory projections. Catalog/research support is not the same as an enabled adapter: **Codex and Firebender agent adapters remain disabled**. Harness-specific formats and limits live in the [matrix and harness pages](../matrix.md); Standard's per-scope reader sets live in `agent_adapters/standard.py`.

## Complete directories

An agent source may instead contain `AGENTS.md` with `MEMORY.md`, nested skills,
scripts and resources. Registration/import retain the entire directory. Pi
projection links that directory at `.pi/agents/<slug>` (global:
`~/.pi/agent/agents/<slug>`); updates to backing remain visible through the link.
Only the Pi directory projection is currently supported: single-file/translated
adapters are reported skipped rather than flattening away resources. Legacy
`<slug>.md` agents retain their existing adapters. Recorded `agentPath` selection
is authoritative: a maintenance `AGENTS.md` beside a recorded flat entry does
not turn it into a directory agent. New registrations prefer `<slug>.md` when
both files exist. Entry/content symlinks that escape or substitute source paths
are refused on registration and projection, including recorded monorepo paths.

**Projection does not prove native Pi role, memory or skill loading**, install a
subagent extension, or establish an agent runtime. Verify actual loading using
the chosen native Pi setup from the real task location.

New project backing is central by default; existing private installations are
preserved. See [configuration and explicit migration](../agent-toolkit/project-backing.md).

## Use

```bash
agent-toolkit-cli agents add owner/repo/path/to/agent --slug reviewer
agent-toolkit-cli agents install reviewer -p --harnesses standard
agent-toolkit-cli agents list -p --json
agent-toolkit-cli agents doctor -p --no-fix
agent-toolkit-cli agents uninstall reviewer -p --harnesses standard
```

Add/remove/import are global-library operations. Install/uninstall default project; other scope-aware verbs infer from the agent project lock. Update fast-forwards clean, source-matching backing; push opens a PR unless `--direct`; reset requires explicit slugs and can discard local work. [CLI reference](../agent-toolkit/cli.md#agents).

## Ownership and inventory

The TUI unions lock entries with bounded on-disk discovery. Discovered files stay visible as `local`; visibility is not consent to take ownership. Local rows cannot enter single/All/None toggle queues and have no TUI enable/disable or deletion action. Info shows the actual path and manual removal instructions, distinguishing symlink removal from permanent file deletion. `library` rows keep existing controls; disabling retracts the connection, not the central source. Doctor reports Standard drift, orphan/dangling sidecars and Cursor shadows (Cursor's own directory wins conflicts). A divergent sentinel-less Cursor file is report-only, and unmanaged Standard files are never auto-removed. Toolkit-owned generated content uses ownership sidecars; inspect conflict diagnostics instead of replacing foreign files.

[Lock formats](../agent-toolkit/lock-files.md) · [Instructions](instructions.md) · [TUI](../agent-toolkit/tui.md)
