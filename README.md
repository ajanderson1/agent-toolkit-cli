# Agent Toolkit CLI

![Tests](https://github.com/ajanderson1/agent-toolkit-cli/actions/workflows/test.yml/badge.svg) ![License](https://img.shields.io/badge/license-MIT%20%2B%20Commons%20Clause-blue) ![Release](https://img.shields.io/github/v/release/ajanderson1/agent-toolkit-cli)

Keep AI-agent assets under your control across coding harnesses.

## Overview

Manage **skills, agents, commands, instructions, Pi extensions, and MCP servers** from a Python CLI or Textual terminal interface. Keep source-backed assets in a library, then choose which harnesses can see them at project or global scope. Local skill improvements are real Git work: update by merging upstream and publish through a pull request.

The toolkit creates symlinks, translates Markdown, or edits named configuration entries as each harness requires. **Support and verbs vary by kind and scope**; catalog membership is not universal support. Instructions uses your canonical `AGENTS.md` and actual filesystem pointers, not a lock. Bundles are an installation utility for skills, agents, and Pi extensions, not a seventh asset kind.

[Documentation](https://ajanderson1.github.io/agent-toolkit-cli/) · [Compatibility matrix](docs/matrix.md) · [CLI reference](docs/agent-toolkit/cli.md) · [TUI reference](docs/agent-toolkit/tui.md)

## What's new in 7.0.1 and 7.0

- **Shared asset catalogue (7.0.1):** one optional subscription now covers Skills, Agents, Commands and Git/native npm Pi extensions. New or changed publisher entries require revision-bound inspection evidence; browsing never acquires or enables assets.
- **Guarded catalogue actions (7.0.1):** explicit per-kind acquisition, selector-only pending validation, non-advancing Git reuse and regular Pi entrypoint checks preserve local work. Native npm installation remains explicit and confirmed, without a Toolkit npm registry.
- **Expandable skill collections:** advertised and acquired children of the same Git repository/ref appear together. Browsing does not download skill content; explicit enablement acquires only selected missing children.
- **Safer queued changes:** collection selections retain their original identities across refreshes, filters and collapse. Apply isolates failures by collection and scope, retaining safely acquired library content for retry.
- **Precise Git state:** child clean/dirty badges inspect their own directories; parent badges describe the whole checkout. Explicit `skills check` works for registered Git-backed skills without requiring a catalogue subscription.
- **Pinned reset support:** force reset restores the configured commit pin, tag or latest fetched branch tip—not an invented `origin/<SHA>` branch.

The catalogue remains optional. Version 7.0.1 extends its original skills-only
format to **Skills, Agents, Commands and Pi extensions**, with explicit acquisition
and revision-bound publishing checks. [Shared catalogue](docs/agent-toolkit/catalog.md). Existing command spellings remain supported: **add/remove** describe library membership; **enable/disable** describe harness exposure, currently spelled `install`/`uninstall` for source-backed kinds. Version 7.0 does not introduce that proposed CLI rename.

[Full changelog](CHANGELOG.md) · [Release assets and receipts](https://github.com/ajanderson1/agent-toolkit-cli/releases/tag/v7.0.1)

## Installation

Requires **Python 3.12+**, [uv](https://docs.astral.sh/uv/) and Git. Install the **toolkit package** (both binaries):

```bash
uv tool install --from git+https://github.com/ajanderson1/agent-toolkit-cli@v7.0.1 agent-toolkit
agent-toolkit-cli --version
```

This selects the tagged release rather than a moving development branch. To upgrade an existing installation to this release:

```bash
uv tool install --force --from git+https://github.com/ajanderson1/agent-toolkit-cli@v7.0.1 agent-toolkit
agent-toolkit-cli --version
agent-toolkit-tui --version
```

Restart an already-running TUI after upgrading. For development builds, omit `@v7.0.1` to use the repository's default branch.

Verified wheel/sdist assets, `SHA256SUMS` and a source-commit/artifact receipt are available on [GitHub Releases](https://github.com/ajanderson1/agent-toolkit-cli/releases). Verify the checksums before installing a downloaded wheel; identify builds by commit and wheel SHA-256, not version alone. No PyPI publication is configured. The incompatible pre-v2 commands remain frozen at `v1.0.0`; see [legacy installation](docs/agent-toolkit/cli.md#pre-v2-surface).

## Quickstart

```bash
# 1. Add source to the library — does not make it visible to a harness.
agent-toolkit-cli skills add anthropics/skills --skill pdf

# 2. Enable it in the current project (the shipped command is install).
agent-toolkit-cli skills install pdf --agents claude-code --scope project
agent-toolkit-cli skills list -p

# 3. Inspect or queue visibility changes in the terminal UI.
agent-toolkit-tui
```

Choose scope explicitly in scripts. Defaults differ across kinds and verbs: a Git repository alone does not select project scope. See [scope rules](docs/agent-toolkit/cli.md#scope-and-target-selection).

## Usage

```bash
# Register a repository's real skills; install its registered children together.
agent-toolkit-cli skills add --source owner/repo --ref main
agent-toolkit-cli skills install --source owner/repo --agents standard --scope global

# Inspect local edits and explicitly check upstream, then merge updates.
agent-toolkit-cli skills status pdf -g
agent-toolkit-cli skills check pdf -g
agent-toolkit-cli skills update pdf -g

# Publish an owned skill through a PR; third-party read-only sources refuse push.
agent-toolkit-cli skills push my-owned-skill -g

# Share an existing user-authored project AGENTS.md with Claude Code.
agent-toolkit-cli instructions install --scope project --harness claude-code

# Discover each group's actual verbs and flags.
agent-toolkit-cli commands --help
agent-toolkit-cli mcps --help
agent-toolkit-cli bundles --help
```

### Optional shared asset catalogue

Subscribe to a publisher's Git catalogue, replacing the example URL and `KEY` with its values:

```bash
agent-toolkit-cli catalog subscribe ssh://git@git.example.org/team/skill-catalog.git --ref main
agent-toolkit-cli catalog list
agent-toolkit-cli skills catalog add KEY
agent-toolkit-cli skills catalog enable KEY --scope project --agents claude-code
```

`add` acquires library content without enabling it. Explicit catalogue `enable` can also acquire a missing selected skill before creating its harness exposure. The TUI provides the same workflow: expand a collection, press **Space** to queue changes, **Ctrl+S** to Apply, **Ctrl+Z** to Revert, and **i** for Info. Upstream checks and updates remain CLI-only.

Listing refreshes fetch the catalogue, not its advertised asset repositories. A failed refresh hides catalogue-only offers with a warning rather than showing stale listings; acquired skills remain usable. Disabling, publisher delisting or `skills catalog unsubscribe` does not delete acquired content. Unsubscribing does not retract existing exposure. [Catalogue format, per-kind actions and admission](docs/agent-toolkit/catalog.md).

### Discarding local Git work

Use this only when you intend to discard local commits and tracked edits:

```bash
agent-toolkit-cli skills reset SLUG -g --force
```

**For a shared monorepo, this resets the entire parent checkout, including sibling skills.** A commit pin stays at that exact commit; a branch uses its latest fetched tip. Reset does not run `git clean` or purge unrelated untracked files. Normal `update` merges instead of intentionally discarding edits. A clean working tree does not mean it is the latest upstream revision.

Canonical groups are `skills`, `agents`, `commands`, `instructions`, `pi-extensions`, `mcps`, and `bundles`; singular aliases still work. For source-backed kinds, `uninstall` disables harness exposure without forgetting library content; `remove` can delete that content. **MCP is an exception:** remove retains its library manifest and files. See the [verb model](docs/glossary.md#verb-model), [six asset guides](docs/index.md#asset-types), and [skill ownership workflow](docs/agent-toolkit/skill-lock.md).

## Configuration

- Source-backed libraries and global locks normally live under `~/.agent-toolkit/`; new project skill/agent/command installations share central backing. Existing private installations remain usable. [Storage reference](docs/agent-toolkit/lock-files.md) · [Backing configuration and explicit migration](docs/agent-toolkit/project-backing.md).
- Shared CLI/TUI behavior config is `~/.agent-toolkit/config.json`: `projectBacking` defaults to `"central"`; creating isolated projects requires both `"isolated"` and `allowIsolatedProjects: true`.
- Pi directory-agent installation preserves `AGENTS.md`, memory, nested skills and resources; non-Pi directory adapters remain unsupported. This does not by itself activate native Pi roles or memory. [Agent support](docs/asset-types/agents.md).
- Instructions canonical content is user-owned: project `AGENTS.md` or `~/.agent-toolkit/AGENTS.md`. Install does not author it. [Instructions safety](docs/asset-types/instructions.md).
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
git clone https://github.com/ajanderson1/agent-toolkit-cli
cd agent-toolkit-cli
uv sync --all-extras
uv run pytest -q
uv run python scripts/gen_harness_docs.py
make docs-build
```

This repository is the canonical CLI/TUI source; the separate REGROUND checkout is historical. Identify installed builds by canonical commit and wheel SHA-256, not version alone.

`lefthook.yml` runs the full pytest suite on **pre-push**. Update affected docs with behavior changes; regenerate harness pages rather than editing generated output. [Open an issue](https://github.com/ajanderson1/agent-toolkit-cli/issues) for defects or compatibility gaps.

## License

[MIT with Commons Clause](LICENSE): use, modify and distribute, but do not sell the software or products/services whose value derives substantially from it.

## Acknowledgements

The skills catalog and compatible lock format build on [vercel-labs/skills](https://github.com/vercel-labs/skills). The terminal interface uses [Textual](https://textual.textualize.io/).
