# agent-toolkit-cli

Bash + Python CLI and Textual TUI for managing the [`agent-toolkit`](https://github.com/ajanderson1/agent-toolkit) asset library across Claude Code, Codex, OpenCode, and Pi.

## Install

```bash
uv tool install --from git+https://github.com/ajanderson1/agent-toolkit-cli agent-toolkit
# SSH form: git+ssh://git@github.com/ajanderson1/agent-toolkit-cli
```

The TUI extra:

```bash
uv tool install --from git+https://github.com/ajanderson1/agent-toolkit-cli "agent-toolkit[tui]"
```

## Two-flag contract

Every subcommand observes the same two flags:

| Flag | Means | Default |
|---|---|---|
| `--toolkit-repo PATH` | The agent-toolkit SSOT (the library) | four-step order: flag → `AGENT_TOOLKIT_REPO` env → walk-up `.agent-toolkit-source` → `~/GitHub/agent-toolkit/` |
| `--project PATH` | The consumer project being acted on | `.` (CWD) |

Subcommands like `check`, `fix`, `new`, `doctor`, `inventory`, `ingest` only need `--toolkit-repo`. Subcommands like `link`, `unlink`, `list`, `diff` use both — `--toolkit-repo` for asset discovery and `--project` for the consumer-side symlinks.

Clone the toolkit repo to the default path for zero-config usage:

```bash
git clone https://github.com/ajanderson1/agent-toolkit ~/GitHub/agent-toolkit
git -C ~/GitHub/agent-toolkit submodule update --init --recursive
```

## Commands

```text
agent-toolkit link <user|project> <harness> [<kind>:<slug>] [--all] [-y]
agent-toolkit unlink <user|project> <harness> (--all | <kind>:<slug>)
agent-toolkit list [<kind>] [<harness>]      # install state per scope (bash)
agent-toolkit diff <user|project> <harness>
agent-toolkit check [--exit-code]
agent-toolkit fix
agent-toolkit doctor [<slug>]
agent-toolkit inventory [<kind>|<slug>]      # asset library catalog (python)
agent-toolkit ingest [<url|name|file>]
agent-toolkit new <kind> <slug>
agent-toolkit tui                    # requires [tui] extra
```

`list` vs `inventory`: `list` is project-scoped — shows what's installed for a `<user|project>` scope and harness, with ✓/— install state. `inventory` is library-scoped — browses the SSOT's asset catalog with no notion of install state.

**MCPs** are recognised as a first-class kind in the allow-list (`mcps:` section) and surfaced in `list`/`inventory`. Per-harness MCP installation (writing `mcp.json`, etc.) arrives in a follow-up; for now, `link mcp:<name>` updates the allow-list and emits a `not yet implemented` note.

Full reference: [`docs/agent-toolkit/cli.md`](docs/agent-toolkit/cli.md).
Schema reference: [SSOT in the toolkit repo](https://github.com/ajanderson1/agent-toolkit/blob/main/docs/agent-toolkit/schema.md).

## Development

```bash
git clone https://github.com/ajanderson1/agent-toolkit-cli ~/GitHub/projects/agent-toolkit-cli
cd ~/GitHub/projects/agent-toolkit-cli
uv sync --all-extras
uv run pytest -q
bats tests/bats
```

The `lefthook.yml` runs lint + tests on pre-commit. Schema drift vs the toolkit-repo SSOT is checked by `.github/workflows/schema-drift.yml`.

## License

MIT © AJ Anderson
