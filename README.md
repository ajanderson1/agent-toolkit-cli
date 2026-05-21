# agent-toolkit-cli

Python CLI and Textual TUI for managing AI-agent **skills** across Claude Code, Codex, OpenCode, Gemini CLI, and Pi. Lock-file-driven, byte-compatible with [`vercel-labs/skills`](https://github.com/vercel-labs/skills).

> **v2.1.0 — universal-agent install model.** Built on the 55-agent catalog ported from [vercel-labs/skills](https://github.com/vercel-labs/skills/blob/main/src/agents.ts). Universal agents (codex, opencode, gemini-cli, +11 more whose `skillsDir == .agents/skills`) skip per-harness symlinks at global scope; the canonical clone is enough. Non-universal agents (claude-code, pi, windsurf, +37 more) still get their per-harness symlink. Interactive wizard groups by universality; TUI skill grid covers the two we explicitly support (claude-code, pi). v2.0.0's `AGENT_TOOLKIT_TUI_LEGACY=1` escape hatch is preserved.

## Install

```bash
uv tool install --from git+https://github.com/ajanderson1/agent-toolkit-cli agent-toolkit
# SSH form: git+ssh://git@github.com/ajanderson1/agent-toolkit-cli
```

> **Don't `pip install -e .` into a Python that comes earlier on `$PATH` than `~/.local/bin/`** (e.g., pyenv-managed Pythons). The pip shim will shadow `uv tool install`'s shim, and if you later delete the editable source, every invocation will break with `ModuleNotFoundError: agent_toolkit_cli.cli`. If you must install editable for development, either:
>
> - Use a venv that you activate per-session (`python -m venv .venv && source .venv/bin/activate && pip install -e .`), or
> - First `uv tool uninstall agent-toolkit` to make the precedence explicit, and re-install from uv when you're done.
>
> `agent-toolkit-cli doctor` can detect this shadowing symptom (see [#61](https://github.com/ajanderson1/agent-toolkit-cli/issues/61)).

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

### Skills (new in v2.0.0 — lock-file driven)

```text
agent-toolkit-cli skill add <source> [-g|-p] [--ref <ref>] [--harness <h>]...
agent-toolkit-cli skill list [-g|-p]
agent-toolkit-cli skill status [<slug>...] [-g|-p]
agent-toolkit-cli skill update [<slug>...] [-g|-p]      # merge-aware
agent-toolkit-cli skill push   [<slug>...] [-g|-p]      # self-improvements upstream
agent-toolkit-cli skill remove <slug>... [-g|-p] [--force]
```

`<source>` accepts `owner/repo`, full URL, SSH URL, or local path — same scheme as `npx skills add`. See [`docs/agent-toolkit/skill-lock.md`](docs/agent-toolkit/skill-lock.md) for the full reference, lock-file format, and skills.sh interop details.

### Other asset kinds (CLI unchanged; TUI deferred to v3)

```text
agent-toolkit-cli link <user|project> <harness> [<kind>:<slug>] [--all] [-y]
agent-toolkit-cli unlink <user|project> <harness> (--all | <kind>:<slug>)
agent-toolkit-cli list [<kind>] [<harness>]      # install state per scope (bash)
agent-toolkit-cli diff <user|project> <harness>
agent-toolkit-cli check [--exit-code]
agent-toolkit-cli fix
agent-toolkit-cli doctor [<slug>]
agent-toolkit-cli inventory [<kind>|<slug>]      # asset library catalog (python)
agent-toolkit-cli ingest [<url|name|file>]
agent-toolkit-cli new <kind> <slug>
agent-toolkit-cli tui                            # default: skills only
```

`list` vs `inventory`: `list` is project-scoped — shows what's installed for a `<user|project>` scope and harness, with ✓/— install state. `inventory` is library-scoped — browses the SSOT's asset catalog with no notion of install state.

**MCPs** (Claude, Codex, OpenCode, and Gemini shipped via `config_file` adapters; Pi has no MCP concept — see harness-matrix.md).
`link mcp:<name>` writes `[mcp_servers.<name>]` to `~/.codex/config.toml` via a
round-trip parser; sibling sections and comments are preserved. The four-glyph
status `[☑] [≁] [☐] [!]` appears in `list` (and the TUI) for MCPs. Run
`doctor --group mcps --harness codex` to report drift, missing env vars, and
missing prerequisites. Use `fix --mcps-only` to reconcile installed entries to
the canonical allow-list template.

**plugin** (Claude-only) — declarative install via `installed_plugins.json` + `known_marketplaces.json`.

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

The `lefthook.yml` runs lint + tests on pre-commit, including `schema-vendor-check` which keeps the two vendored schema copies (`schemas/` and `src/agent_toolkit_cli/_schemas/`) in lockstep.

## License

MIT © AJ Anderson
