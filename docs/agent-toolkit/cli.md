# agent-toolkit CLI reference

`agent-toolkit-cli` is a single-command CLI for managing AI-agent skills. Post-v2.3.0 the only top-level command is `skill`; the pre-v2 surface (`check`, `link`, `doctor`, `fix`, `ingest`, `inventory`, `migrate-skills`, `new`, `diff`, `list`, `unlink`, `pi`) was removed in [#160](https://github.com/ajanderson1/agent-toolkit-cli/issues/160). The frozen v1 surface is pinned at the `v1.0.0` tag — see the [README](../../README.md) for the install command.

## Commands

### `skill`

Manage skills via per-skill upstream git repos + a per-scope lock file.

```text
agent-toolkit-cli skill add <source> [-g|-p] [--ref <ref>] [--harness <h>]...
agent-toolkit-cli skill list [-g|-p] [-a/--agent <name>] [--json]   # alias: ls
agent-toolkit-cli skill status [<slug>...] [-g|-p]
agent-toolkit-cli skill update [<slug>...] [-g|-p]      # merge-aware
agent-toolkit-cli skill push   [<slug>...] [-g|-p]      # self-improvements upstream
agent-toolkit-cli skill remove <slug>... [-g|-p] [--force]          # alias: rm
```

`<source>` accepts `owner/repo`, a full HTTPS URL, an SSH URL, or a local path. `-g/--global` and `-p/--project` select scope; default is global. `skill list --json` emits a JSON array (`slug`, `source`, `ref`, `upstream_sha`, `local_sha`, `scope`) for scripting; `-a/--agent <name>` filters to skills currently symlinked into that agent (or the `universal` token).

Full reference, lock-file format, and skills.sh interop notes live in [`skill-lock.md`](skill-lock.md).

### `tui` (separate binary)

```text
agent-toolkit-tui                              # interactive skill grid (claude-code + pi)
AGENT_TOOLKIT_TUI_LEGACY=1 agent-toolkit-tui   # restore the legacy multi-tab layout
```

Installed alongside the CLI via the same `uv tool install` command.

## What was removed in v2.3.0

The following pre-v2 commands no longer exist on `main`. They remain available at the `v1.0.0` tag (`uv tool install --from git+https://github.com/ajanderson1/agent-toolkit-cli@v1.0.0 agent-toolkit`):

- `check` — asset-frontmatter validator
- `diff` — preview of `link`
- `doctor` — five-group health check
- `fix` — regenerate AGENTS.md auto-regions
- `ingest` — pull an asset from URL/name/file
- `inventory` — library-scoped asset catalog
- `link` — project assets per allow-list
- `list` — project-scoped install state
- `migrate-skills` — one-shot legacy -> sidecar migration
- `new` — scaffold a new asset
- `pi` — Pi-specific extension load/unload
- `unlink` — inverse of `link`

A tracker issue lists the v2-native rebuild status for each — see the PR body for #160.

## See also

- [`skill-lock.md`](skill-lock.md) — lock-file format and `skill` subcommand reference.
- The 55-agent catalog (`skillsDir == .agents/skills` = universal) lives in `src/agent_toolkit_cli/skill_agents.py`.
- [`schema.md`](schema.md) — asset frontmatter schema (toolkit-repo SSOT, not consumed by this CLI post-v2.3.0).
