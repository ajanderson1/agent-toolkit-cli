# Agent Toolkit

Use **`atc`** (CLI) and **`att`** (Textual terminal UI) to manage six kinds of
AI-agent assets across coding harnesses. Keep library content separate from
harness exposure, preserve real Git work, and choose scope and targets explicitly.

Both applications ship in the `agent-toolkit` Python package. Short commands are
real package entry points, not shell aliases; `agent-toolkit-cli` and
`agent-toolkit-tui` remain supported.

## Start here

Requires Python **3.12+**, [uv](https://docs.astral.sh/uv/), and Git for source
installation/self-updates:

```bash
uv tool install --from git+https://github.com/ajanderson1/agent-toolkit-cli@v7.1.0 agent-toolkit
atc --version
att --version
```

[Installation and release verification](agent-toolkit/installation.md) covers
PATH setup, official wheel checksums/commit receipts, upgrading an older client,
and development environments. No PyPI publication is configured.

Enable completion in Zsh, if desired:

```bash
atc completion install --shell zsh
source ~/.zshrc
```

Use the path printed by setup for a custom dotfile location. Bash 4.4+ and Fish
are also supported. Completion covers commands, flags, declared choice values
and paths—not asset-name discovery. Setup changes only its marked shell block;
it does not add command aliases. [All shells and troubleshooting](agent-toolkit/shell-completion.md).

## First asset workflow

From your consumer project:

```bash
# Add content to the global library, then enable it for the project.
atc skills add anthropics/skills --skill pdf
atc skills install pdf --scope project --agents standard
atc skills list -p
att
```

**Add/remove** means library membership. **Enable/disable** means harness
exposure; source-backed kinds currently spell those commands
`install`/`uninstall`. Per-kind exceptions and defaults matter: a Git repository
alone does not choose project scope. [Verb model](glossary.md#verb-model) ·
[Scope and target selection](agent-toolkit/cli.md#scope-and-target-selection).

In the TUI, **Space** queues changes, **Ctrl+S** applies, **Ctrl+Z** reverts, and
**i** opens Info. Opening/refreshing inventory does not apply drafts or acquire
advertised catalogue offers. [TUI guide](agent-toolkit/tui.md).

## Keep the application current

```bash
atc update --check
atc update
```

`att update` invokes the same updater without opening the TUI. Stable GitHub
releases are the default; `--main` explicitly selects development commits.
Automatic CLI/TUI notices share a six-hour cache and never replace the package
automatically. Set `AGENT_TOOLKIT_NO_UPDATE_CHECK=1` to opt out of automatic
checks; explicit `--check` still refreshes.

Self-update supports non-editable uv tool installations only. It builds a pinned
canonical commit, retains a wheel/source-hash receipt, and does not update asset
backing, change harness settings, or migrate project state. Restart running TUIs
when finished. [Update behavior, privacy and recovery](agent-toolkit/updates.md).

## Asset types

| Kind | What it manages |
|---|---|
| [Skills](asset-types/skills.md) | `SKILL.md` folders, source-backed libraries and harness projections. |
| [Agents](asset-types/agents.md) | Subagent definitions and supported complete-directory resources. |
| [Commands](asset-types/commands.md) | Reusable prompts projected/translated into supported command slots. |
| [Instructions](asset-types/instructions.md) | Actual pointers to user-owned canonical `AGENTS.md`, without an installation lock. |
| [Pi extensions](asset-types/pi-extensions.md) | Git library sources, native npm packages and supported local resources. |
| [MCP servers](asset-types/mcp.md) | Global authoring manifest and per-scope harness configuration projections. |

Support varies by kind, harness and scope; researched support is not proof an
adapter is enabled. The [compatibility matrix](matrix.md) links to all harness
pages. Bundles, the shared catalogue, package updates and completion are utilities,
not additional asset kinds.

## Reference and workflows

- [CLI reference](agent-toolkit/cli.md) — root utilities, all asset groups, verbs, flags and scope rules.
- [TUI reference](agent-toolkit/tui.md) — six grids, collections, pending edits and failure recovery.
- [Shared asset catalogue](agent-toolkit/catalog.md) — optional subscription, per-kind acquisition/exposure, manifest format and publisher admission.
- [TUI preferences](agent-toolkit/tui-settings.md) — theme/harness-column settings, independent of CLI targets and update-check configuration.
- [Storage and lock files](agent-toolkit/lock-files.md) — library/project records versus package cache/build receipts.
- [Project backing and migration](agent-toolkit/project-backing.md) — central defaults, retained private copies and explicit guarded migration.
- [Skill Git/lock deep dive](agent-toolkit/skill-lock.md) — refs versus observed commits, owned publishing, shared backing and cross-machine import.
- [Bundles](agent-toolkit/bundles.md) — supported local manifests, validation and rollback limits.
- [Glossary](glossary.md) — asset lifecycle, package/build identity and compatibility terms.
- [Roadmap](agent-toolkit/roadmap.md) — shipped features versus unimplemented ideas.
- [Changelog](changelog.md) — canonical release history, including 7.1.0 short commands, package updates and shell completion.

The [repository README](https://github.com/ajanderson1/agent-toolkit-cli#readme)
provides the same entry points for GitHub readers. Historical plans, research and
reviews retain their original context; they are not the current product reference.
