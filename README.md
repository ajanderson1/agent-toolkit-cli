# Agent Toolkit CLI

![Tests](https://github.com/ajanderson1/agent-toolkit-cli/actions/workflows/test.yml/badge.svg) ![License](https://img.shields.io/badge/license-MIT%20%2B%20Commons%20Clause-blue) ![Release](https://img.shields.io/github/v/release/ajanderson1/agent-toolkit-cli)

## Overview

Manage AI-agent assets across coding harnesses with **`atc`** (CLI) and **`att`**
(Textual terminal UI). Keep source content in a library, then independently
choose which projects and harnesses can see it.

[Documentation](https://ajanderson1.github.io/agent-toolkit-cli/) ·
[Installation](docs/agent-toolkit/installation.md) ·
[CLI reference](docs/agent-toolkit/cli.md) · [TUI reference](docs/agent-toolkit/tui.md) ·
[Compatibility matrix](docs/matrix.md)

## What's new in 7.1.0

- **Packaged short commands:** `atc` and `att` are real executable entry points,
  not Zsh aliases. Both long names remain supported.
- **Package updates:** CLI/TUI startup notices and explicit `atc update` /
  `att update`, stable releases by default, optional `--main`, and retained
  source-commit/wheel-hash provenance. No automatic package replacement.
- **Dynamic TAB completion:** commands, flags, declared choices and paths for
  all four executable names. Explicit, reversible setup for Zsh, Bash and Fish.

The shared catalogue introduced in 7.0.1 still covers Skills, Agents, Commands
and Git/native npm Pi extensions. Catalogue browsing does not acquire or enable
assets. [Catalogue workflow](docs/agent-toolkit/catalog.md) ·
[Full changelog](CHANGELOG.md) ·
[7.1.0 release assets and receipt](https://github.com/ajanderson1/agent-toolkit-cli/releases/tag/v7.1.0).

## Installation

Requires **Python 3.12+**, [uv](https://docs.astral.sh/uv/) and Git for source
installation/self-updates. This installs both applications in one tool environment:

```bash
uv tool install --from git+https://github.com/ajanderson1/agent-toolkit-cli@v7.1.0 agent-toolkit
atc --version
att --version
```

| Short name | Equivalent long name | Use |
|---|---|---|
| `atc` | `agent-toolkit-cli` | Asset CLI, package updates and completion setup. |
| `att` | `agent-toolkit-tui` | Open the TUI; also run `update` or `completion` from the shell. |

No shell aliases are required. Ensure uv's executable directory is on `PATH`
(`uv tool dir --bin`; `uv tool update-shell` can configure it), then open a new
terminal if needed. There is **no configured PyPI publication**; use this
canonical repository or the official GitHub release assets.

### Upgrade a pre-7.1.0 client

Older clients have neither the short names nor the package updater. Perform a
one-time package-manager upgrade first:

```bash
uv tool install --from git+https://github.com/ajanderson1/agent-toolkit-cli@v7.1.0 agent-toolkit
agent-toolkit-cli --version
agent-toolkit-tui --version
```

Inspect executable collisions and obsolete user-authored aliases rather than
blindly overwriting another tool with `--force`. Restart an already-running TUI.
[PATH, development environments and installation troubleshooting](docs/agent-toolkit/installation.md).

### Verify a release build

Official releases include a wheel, sdist, `SHA256SUMS` and a
`deployment-receipt.json` binding the artifacts to the canonical source commit.
Verify checksums **before** installing a downloaded wheel; keep its durable
source path and receipt. A version string alone is insufficient build identity.

For **7.1.0**, canonical source is
`4c7196db8764ac1ad3b9b7bc50584c28026d7f41` and the official wheel SHA-256 is
`d9d4cd0308e9c36c75b7b90eea9a08b8c6d971308a8343d339efff69b4564aff`.
[Download, verify and install the official wheel](docs/agent-toolkit/installation.md#verify-a-published-wheel).

## Keep Toolkit current

```bash
atc update --check          # Fresh stable-release check, without replacement
atc update                 # Update both applications
att update                 # Same updater; does not open the TUI
atc update --main --check   # Explicit development-commit comparison
atc update --main           # Explicit opt-in to the newest canonical main commit
```

- Automatic checks share a **six-hour** cache. Failures back off for **15 minutes**
  and do not stop normal use. TUI checks run off the UI thread; interactive CLI
  notices go to stderr. Pipes, explicit output formats, help/version and
  completion do not trigger checks.
- Set `AGENT_TOOLKIT_NO_UPDATE_CHECK=1` to disable automatic checks. Explicit
  `update --check` still refreshes; it returns zero for a successful check even
  when a newer release exists, and nonzero on errors.
- Replacement requires a **non-editable `uv tool` installation**. Other environments
  are refused with guidance. The updater builds a pinned canonical commit in a
  temporary checkout and retains its wheel and source/hash receipt. Its local
  wheel is not assumed to have the same hash as a published release wheel.
- Stable mode does not downgrade an equal/newer installed version. `--main`
  compares commits because development builds can share a version number.
- Package updates do **not** refresh asset backing, migrate project data,
  change subscriptions/exposure, or apply TUI edits. They have no automatic
  package-manager rollback. Restart running TUIs after updating.

[Channels, cache/timeout behavior, privacy, provenance and recovery](docs/agent-toolkit/updates.md).

<a id="shell-completion"></a>

## Enable TAB completion

For Zsh:

```bash
atc completion install --shell zsh
source ~/.zshrc
```

Use the configuration path printed by the command for custom dotfiles. Bash
**4.4+** uses `--shell bash` and `~/.bashrc`; Fish uses `--shell fish` and its
`conf.d` directory. Omitting `--shell` detects `$SHELL`.

Setup adds one marked, reversible completion block—not command aliases. It
preserves unrelated text, permissions and symlinked layouts; it does **not**
create an automatic backup. Package installation alone does not edit shell files.

```bash
atc completion init zsh                 # Print integration code; no file changes
atc completion uninstall --shell zsh    # Remove only the managed block
```

TAB queries the installed Click command tree, so new commands become available
after package updates without a static-list rebuild. It does not start the TUI,
check for updates, fetch repositories, or discover asset slugs/catalogue keys.
[All shells, custom paths, implementation and troubleshooting](docs/agent-toolkit/shell-completion.md).

## Quickstart

Run from your consumer project, or supply CLI `--project DIRECTORY`:

```bash
# Acquire one skill into the global library; do not enable it yet.
atc skills add anthropics/skills --skill pdf

# Enable it for the project's Standard readers; install is the shipped verb.
atc skills install pdf --agents standard --scope project
atc skills list -p

# Open the terminal interface in the current directory.
att
```

**Add/remove** means global library membership. **Enable/disable** means harness
exposure; source-backed kinds currently spell those operations
`install`/`uninstall`. Use the shipped tokens in scripts. **MCP is an exception:**
its current `remove` retracts scoped projections but retains library membership.
Native Pi npm has its own installation/selection rules.
[Verb model and exceptions](docs/glossary.md#verb-model).

Choose scope explicitly in automation: a Git repository alone does not choose
project scope, and defaults differ across kinds/verbs. CLI `--project DIRECTORY`
selects a directory, whereas a verb's `-p` selects scope. The TUI uses its launch
directory and its visible scope control. [Scope and target rules](docs/agent-toolkit/cli.md#scope-and-target-selection).

## Usage

### Six asset kinds

| Kind | Model and guide |
|---|---|
| [Skills](docs/asset-types/skills.md) | Real `SKILL.md` folders, standalone/shared Git backing, harness projections. |
| [Agents](docs/asset-types/agents.md) | Subagent definitions; file and supported Pi directory projections. |
| [Commands](docs/asset-types/commands.md) | Reusable prompt definitions, translated where supported. |
| [Instructions](docs/asset-types/instructions.md) | Pointers to user-owned canonical `AGENTS.md`; no installation lock. |
| [Pi extensions](docs/asset-types/pi-extensions.md) | Git library sources, native npm state, and supported local resources. |
| [MCP servers](docs/asset-types/mcp.md) | Authoritative library manifest and per-harness configuration projections. |

Support varies by kind, harness and scope; a catalogue entry is not proof that
an adapter is enabled. [Matrix and per-harness guides](docs/matrix.md).
**Bundles**, catalogue utilities, package updates and completion are not additional
asset kinds. [Bundle schema and limits](docs/agent-toolkit/bundles.md).

### Optional shared catalogue

Replace the sample URL and `KEY` with your publisher's values:

```bash
atc catalog subscribe ssh://git@git.example.org/team/skill-catalog.git --ref main
atc catalog list
atc skills catalog add KEY
atc skills catalog enable KEY --scope project --agents claude-code
```

`catalog add` acquires content only; explicit `catalog enable` can also acquire a
missing selected asset before enabling it. Catalogue refresh fetches the catalogue,
not every advertised source. Failed refreshes hide catalogue-only offers with a
warning; acquired assets remain usable. Delisting/unsubscription does not delete
acquired content or retract existing exposure. [Per-kind behavior and publisher admission](docs/agent-toolkit/catalog.md).

### Update assets, not the application

```bash
atc skills status pdf -g
atc skills check pdf -g
atc skills update pdf -g
atc skills push my-owned-skill -g
```

These are distinct from root `atc update`. Skills update merges upstream rather
than intentionally discarding local edits; owned-source push normally opens a PR.
A clean tree does not prove it is current. Explicit `skills reset SLUG -g --force`
can discard tracked edits/commits across a **whole shared parent checkout**, including
siblings; it is not ordinary update or projection repair and does not run `git clean`.
[Git ownership, pins and recovery](docs/agent-toolkit/skill-lock.md).

## Configuration

- Libraries/global asset locks normally live under `~/.agent-toolkit/`. New project
  Skills/Agents/Commands use central backing; existing private copies remain
  usable. [Storage](docs/agent-toolkit/lock-files.md) ·
  [Explicit backing migration](docs/agent-toolkit/project-backing.md).
- Shared behavior configuration is `~/.agent-toolkit/config.json`;
  `projectBacking` defaults to `"central"`. New isolated projects require both
  `"isolated"` and `allowIsolatedProjects: true`. Catalogue subscription is separate.
- TUI theme/main-harness preferences live in `~/.agent-toolkit/tui-settings.json`.
  They do not select CLI install targets or configure package checks.
  [Preference schema and override](docs/agent-toolkit/tui-settings.md).
- Update metadata uses `${XDG_CACHE_HOME:-~/.cache}/agent-toolkit/update.json`;
  self-built wheels/receipts use `${XDG_STATE_HOME:-~/.local/state}/agent-toolkit/updates/`.
  Neither is an asset lock or library source.
- Instructions content remains user-owned. Native Pi settings and npm metadata
  remain authoritative for npm packages; Toolkit has no npm library registry.

<a id="screenshot"></a>

## Terminal interface

![Toolkit TUI with an expanded skill collection, mixed selections, plural sidebar, repository path and queued edits](assets/agent-toolkit-cli-tui.png)

The real source-asserted screenshot uses disposable local Git/assets, not operator
state. Six grids share cross-kind pending queues: **Space** queues, **Ctrl+S**
applies, **Ctrl+Z** reverts, and **i** shows Info. Apply is not a cross-kind atomic
transaction. Failures stay visible for inspection/retry. Upstream **asset** checks
and updates remain CLI operations; a package-update notification does not run them.
[TUI controls and limits](docs/agent-toolkit/tui.md) ·
[Capture reproduction](docs/assets/screenshots/README.md).

## Contributing

```bash
git clone https://github.com/ajanderson1/agent-toolkit-cli
cd agent-toolkit-cli
uv sync --all-extras
uv run atc --help
uv run att
uv run pytest -q
uv run python scripts/gen_harness_docs.py
make docs-build
```

`uv run` uses this editable checkout, not the global tool; update development
sources through their normal Git workflow and `uv sync`, not package self-update.
`uv build` builds distributions. The mandatory pre-push hook runs the full pytest
suite. [Open an issue](https://github.com/ajanderson1/agent-toolkit-cli/issues) for defects.

### Architecture

This repository is the canonical CLI/TUI source; the separate REGROUND checkout
is historical. `src/agent_toolkit_cli/` owns shared behavior and per-kind facades;
`src/agent_toolkit_tui/` owns Textual presentation. The packaged machine-read
harness matrix and maintained support tables feed `scripts/gen_harness_docs.py`.
Regenerate matrix/harness views; never hand-edit generated outputs. Historical
plans/reviews are not current reference. [Roadmap and non-goals](docs/agent-toolkit/roadmap.md).

## License

[MIT with Commons Clause](LICENSE): use, modify and distribute, but do not sell
the software or products/services whose value derives substantially from it.

## Acknowledgements

The skills catalogue and compatible lock format build on
[vercel-labs/skills](https://github.com/vercel-labs/skills). The terminal interface
uses [Textual](https://textual.textualize.io/).
