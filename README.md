# Agent Toolkit CLI

Keep AI-agent assets under your control across coding harnesses.

## Overview

Manage **skills, agents, commands, instructions, Pi extensions, and MCP servers** from a Python CLI or Textual terminal interface. Keep source-backed assets in a library, then choose which harnesses can see them at project or global scope. Asset improvements are ordinary Git work in their maintained source repositories.

The toolkit creates symlinks, translates Markdown, or edits named configuration entries as each harness requires. **Support and verbs vary by kind and scope**; catalog membership is not universal support. Instructions uses your canonical `AGENTS.md` and actual filesystem pointers, not a lock. Bundles are an installation utility for skills, agents, and Pi extensions, not a seventh asset kind.

[Documentation](docs/index.md) · [Private Gitea source](ssh://gitlab@broadpeak.tailbf2225.ts.net:2424/ajanderson/agent-toolkit-cli.git) · [Compatibility matrix](docs/matrix.md) · [CLI reference](docs/agent-toolkit/cli.md) · [TUI reference](docs/agent-toolkit/tui.md)

## Installation

Requires **Python 3.12+**, [uv](https://docs.astral.sh/uv/) and Git. Install the **toolkit package** (both binaries):

```bash
# Deployment owner: install the reviewed wheel, not an unreviewed branch.
uv tool install /path/to/reviewed/agent_toolkit-5.11.0-py3-none-any.whl
agent-toolkit-cli --version
```

New source and delivery use private Broadpeak Gitea, not GitHub Releases or PyPI.
Record the source commit and wheel SHA-256: version `5.11.0` alone does not
identify a REGROUND build. Host upgrades are coordinated separately after review.
Legacy GitHub CI/release files remain in history/the checkout; no replacement
Gitea CI/release automation is established by this change.

## Quickstart

```bash
# 1. Add source to the library — does not make it visible to a harness.
# Replace SOURCE_URL and my-skill with your maintained source and entry.
agent-toolkit-cli skills add "$SOURCE_URL" --skill my-skill --ref main

# 2. Install a projection in the current project; the library remains separate.
agent-toolkit-cli skills install my-skill --agents claude-code --scope project
agent-toolkit-cli skills list -p

# 3. Inspect or queue visibility changes in the terminal UI.
agent-toolkit-tui
```

Choose scope explicitly in scripts. Defaults differ across kinds and verbs: a Git repository alone does not select project scope. See [scope rules](docs/agent-toolkit/cli.md#scope-and-target-selection).

## Usage

```bash
# Register one exact Gitea repository directory and project that skill.
agent-toolkit-cli skills add "$SOURCE_URL" --path skills/my-skill --ref main
agent-toolkit-cli skills install my-skill --agents standard --scope project

# Inspect local edits and refresh upstream content.
agent-toolkit-cli skills status my-skill -g
agent-toolkit-cli skills update my-skill -g

# Register/project a complete AGENTS.md directory (or a legacy flat agent).
agent-toolkit-cli agents add "$AGENT_SOURCE_URL" --slug my-agent --ref main
agent-toolkit-cli agents install my-agent -p --harnesses pi

# Share an existing user-authored project AGENTS.md with Claude Code.
agent-toolkit-cli instructions install --scope project --harness claude-code

# Discover each group's actual verbs and flags.
agent-toolkit-cli commands --help
agent-toolkit-cli mcps --help
agent-toolkit-cli bundles --help
```

Canonical groups are `skills`, `agents`, `commands`, `instructions`, `pi-extensions`, `mcps`, and `bundles`; singular aliases still work. `uninstall` removes visibility without forgetting source-backed library content; `remove` can delete that content. **MCP is an exception:** remove retains its library manifest and files. See the [verb model](docs/glossary.md#verb-model), [six asset guides](docs/index.md#asset-types), and [skill ownership workflow](docs/agent-toolkit/skill-lock.md).

## Configuration

- Source-backed libraries and global locks normally live under `~/.agent-toolkit/`; new project skill/agent/command projections share central backing. Existing private installations remain usable. [Configuration and explicit migration](docs/agent-toolkit/project-backing.md).
- Shared behavior config is `~/.agent-toolkit/config.json`: `projectBacking` defaults to `"central"`; new isolation requires both `"isolated"` and `allowIsolatedProjects: true`. Disabled requests are refused by CLI and TUI.
- Instructions canonical content is user-owned: project `AGENTS.md` or `~/.agent-toolkit/AGENTS.md`. Install does not author it. [Instructions safety](docs/asset-types/instructions.md).
- Directory-agent projection preserves memory, nested skills and resources; it does **not** prove native Pi role/memory/skill loading. Non-Pi directory adapters are reported unsupported. [Agent limits](docs/asset-types/agents.md).
- TUI theme and main-harness columns are preferences, not CLI install targets. Use **Ctrl+P → Theme / Main harnesses**. [Settings schema and overrides](docs/agent-toolkit/tui-settings.md).

## Screenshot

![Current TUI with an expanded skill collection, mixed selection, plural sidebar, repository path and queued changes](assets/agent-toolkit-cli-tui.png)

Fresh disposable-fixture capture of this source tree, not operator assets. Collection controls include collapsed and filter-hidden members; **Apply** runs queues across all six kinds, **Revert** clears them, and failures remain visible for retry. Apply is not a cross-kind atomic transaction. [Controls and limits](docs/agent-toolkit/tui.md) · [Reproduce the capture](docs/assets/screenshots/README.md).

## Architecture

- `src/agent_toolkit_cli/`: Click groups, canonical libraries, locks, Git operations and harness adapters.
- `src/agent_toolkit_tui/`: Textual grids over the same inventory and installation facades.
- `docs/agent-toolkit/harness-matrix.md`: packaged compatibility data; `scripts/gen_harness_docs.py` generates matrix/harness views from it and maintained catalog/support tables.

[Storage model](docs/agent-toolkit/lock-files.md) · [Compatibility data](docs/agent-toolkit/harness-matrix.md) · [Unshipped ideas](docs/agent-toolkit/roadmap.md)

## Contributing

```bash
git clone ssh://gitlab@broadpeak.tailbf2225.ts.net:2424/ajanderson/agent-toolkit-cli.git
cd agent-toolkit-cli
uv sync --all-extras
uv run pytest -q
uv run python scripts/gen_harness_docs.py
make docs-build
```

Use temporary HOME/config directories and local Git fixtures, not a live toolkit
installation. `lefthook.yml` currently runs pytest on pre-push; it is not a
release/deployment service. Regenerate harness views rather than hand-editing
outputs. Gitea-owned source changes use ordinary Git; existing provider-specific
PR helpers do not establish a Gitea PR API. Preserve historical reports and
unrelated work.

## License

[MIT with Commons Clause](LICENSE): use, modify and distribute, but do not sell the software or products/services whose value derives substantially from it.

## Acknowledgements

The skills catalog and compatible lock format build on [vercel-labs/skills](https://github.com/vercel-labs/skills). The terminal interface uses [Textual](https://textual.textualize.io/).
