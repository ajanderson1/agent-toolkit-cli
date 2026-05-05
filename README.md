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

**MCPs** (Codex shipped; Claude / OpenCode / Pi pending follow-up PRs).
`link mcp:<name>` writes `[mcp_servers.<name>]` to `~/.codex/config.toml` via a
round-trip parser; sibling sections and comments are preserved. The four-glyph
status `[☑] [≁] [☐] [!]` appears in `list` (and the TUI) for MCPs. Run
`doctor --group mcps --harness codex` to report drift, missing env vars, and
missing prerequisites. Use `fix --mcps-only` to reconcile installed entries to
the canonical allow-list template.

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

The `lefthook.yml` runs lint + tests on pre-commit, including `schema-vendor-check` which keeps the two vendored schema copies (`schemas/` and `src/agent_toolkit/_schemas/`) in lockstep.

## License

MIT © AJ Anderson
