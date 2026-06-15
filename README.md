# agent-toolkit-cli

Python CLI and Textual TUI for managing AI-agent **skills** across Claude Code, Codex, OpenCode, Gemini CLI, and Pi. Lock-file-driven, byte-compatible with [`vercel-labs/skills`](https://github.com/vercel-labs/skills).

> The frozen pre-v2 surface lives on at the `v1.0.0` tag: `uv tool install --from git+https://github.com/ajanderson1/agent-toolkit-cli@v1.0.0 agent-toolkit`.

## Install

```bash
uv tool install --from git+https://github.com/ajanderson1/agent-toolkit-cli agent-toolkit
# SSH form: git+ssh://git@github.com/ajanderson1/agent-toolkit-cli
```

> **Don't `pip install -e .` into a Python that comes earlier on `$PATH` than `~/.local/bin/`** (e.g., pyenv-managed Pythons). The pip shim will shadow `uv tool install`'s shim. If you must install editable for development, either:
>
> - Use a venv that you activate per-session (`python -m venv .venv && source .venv/bin/activate && pip install -e .`), or
> - First `uv tool uninstall agent-toolkit` to make the precedence explicit, and re-install from uv when you're done.

## Commands

Two verb axes run through every asset type below: **`add`/`remove`** manage library membership (destructive — `remove` forgets the source), while **`install`/`uninstall`** manage projection into a harness/scope (non-destructive — the library copy survives). The [verb model](https://ajanderson1.github.io/agent-toolkit-cli/glossary/#verb-model) in the glossary is the single source of truth for what each verb means; the sections here describe only the per-asset-type specifics.

### Skills — lock-file driven, agent-aware

```text
agent-toolkit-cli skill add <source> [--ref <ref>] [--slug <slug>] [--skill <name>]
agent-toolkit-cli skill list [-g|-p]
agent-toolkit-cli skill status [<slug>...] [-g|-p]
agent-toolkit-cli skill update [<slug>...] [-g|-p]      # merge-aware
agent-toolkit-cli skill push   [<slug>...] [-g|-p] [--direct]   # PR-branch by default
agent-toolkit-cli skill remove <slug>... [-g|-p] [--force]
```

`<source>` accepts `owner/repo`, full URL, SSH URL, or local path — same scheme as `npx skills add`. See [`docs/agent-toolkit/skill-lock.md`](docs/agent-toolkit/skill-lock.md) for the lock-file format and skills.sh interop details.

The CLI uses the 54-agent catalog ported from [vercel-labs/skills](https://github.com/vercel-labs/skills/blob/main/src/agents.ts). Universal agents (codex, opencode, gemini-cli, +11 more whose `skillsDir == .agents/skills`) skip per-harness symlinks at global scope. Non-universal agents (claude-code, pi, windsurf, +37 more) still get their per-harness symlink. Interactive wizard groups by universality; TUI skill grid covers the two we explicitly support (claude-code, pi). v2.0.0's `AGENT_TOOLKIT_TUI_LEGACY=1` escape hatch is preserved.

**Monorepo skills:** A `<source>` may name a parent repo that contains several skills. Pick one with `--skill <name>` (matches `SKILL.md` frontmatter `name:`), or pass the subpath inline (`owner/repo/<subpath>` or `<repo>/tree/<ref>/<subpath>`). `https://www.skills.sh/<owner>/<repo>/<skill>` URLs also work end-to-end.

The parent clone lives at `<library>/_parents/<owner>/<repo>/` and is yours to edit — local commits are first-class. `skill update` runs `git fetch` + `git merge` on that clone, so your work merges with upstream like any normal git repo. On conflict the clone is left mid-merge; resolve in place and re-run `skill update`. The TUI reports each monorepo skill's `state` as `clean` or `dirty`, same semantics as per-skill repos. `skill push` still refuses monorepo entries — sharing changes back upstream means forking the parent yourself.

### Instructions — link a canonical `AGENTS.md` across harnesses

```text
agent-toolkit-cli instructions install   [--scope project|global] [--harness <name>]...
agent-toolkit-cli instructions uninstall [--scope project|global]
agent-toolkit-cli instructions list      [--format table|json]
agent-toolkit-cli instructions status    [--scope project|global]
agent-toolkit-cli instructions doctor    [--scope project|global]
```

Most harnesses read `AGENTS.md` natively, so the canonical file satisfies them as-is. The seven that read a fixed own-name file instead (`claude-code` → `CLAUDE.md`, `gemini-cli` → `GEMINI.md`, plus `augment`, `codebuddy`, `iflow-cli`, `replit`, `tabnine-cli`) get a same-name pointer symlink → `AGENTS.md`. `install` writes an `instructions-lock.json` and reconciles the pointers; it never clobbers a real file or foreign symlink. Default scope is `project` (pointers are project-rooted); the global canonical lives at `~/.agent-toolkit/AGENTS.md`. Per-harness verdicts come from [`docs/agent-toolkit/harness-matrix.md`](docs/agent-toolkit/harness-matrix.md).

### Pi extensions — read-only inventory (Pi-only)

```text
agent-toolkit-cli pi-extension list   [-g|-p] [--json]
agent-toolkit-cli pi-extension status [<slug>...] [-g|-p]
```

A Pi-only command group for Pi extensions. PR1 ships the read-only verbs `list` (alias `ls`) and `status`, which surface a unified inventory of every extension Pi could load — **store-owned** (owned git repos in the library), **untracked** (loose entries already in `~/.pi/agent/extensions/` or `<project>/.pi/extensions/`), and **npm** (`packages[]` in Pi's `settings.json`). Origin is a column, not a gate. Write verbs (`add`/`install`/`import`/…) and the TUI grid arrive in later releases.

### MCP servers — library-driven, four harnesses (foundations)

```text
agent-toolkit-cli mcp add --npx|--uvx|--docker|--url|--local <source> [--slug <slug>]   # author into the library
agent-toolkit-cli mcp install <slug>   [--harness <name>]... [-g|-p] [--force]
agent-toolkit-cli mcp uninstall <slug> [--harness <name>]... [-g|-p]
agent-toolkit-cli mcp remove <slug>    [-g|-p]
agent-toolkit-cli mcp update <slug>                                              # re-resolve the version + re-project
agent-toolkit-cli mcp list   [-g|-p]
agent-toolkit-cli mcp status [-g|-p]
agent-toolkit-cli mcp doctor [-g|-p]
```

`mcp add` authors a library entry at `~/.agent-toolkit/mcps/<slug>/` from a package, image, URL, or local path, best-effort resolving the current version so projected configs are effectively pinned (transparency, not enforcement; resolution failure stores the entry `floating`). `mcp install` projects it into **Claude Code, Codex, OpenCode, and Pi** by surgically editing each harness's native config **by name** (`mcpServers.<name>` JSON / `[mcp_servers.<name>]` TOML) — never by file ownership, so hand-rolled neighbours and unmanaged entries survive untouched (the latter shown as `[!] unmanaged` in `list`). Writes are loud and atomic; a cross-harness install rolls back on a later-adapter failure; global-scope `~/.claude.json` writes are guarded by a running-`claude` check (`--force` bypasses). `update` is greedy and flagless (re-resolves the version, re-projects the global + current-project locks). Read-only `doctor` reports orphans, structural drift, and missing env vars **by name only**. Drift `fix`, dry-run `diff`, git-clone-and-build sources, cross-machine library sync, and the TUI MCPs section land in follow-ups.

### Bundles — install several assets together

```text
agent-toolkit-cli bundle install  <manifest.json> [--global | --project]   # all-or-nothing
agent-toolkit-cli bundle validate <manifest.json>                          # check resolution, no install
```

A bundle is a JSON manifest that declares a set of assets (skills, agents, pi-extensions) and installs them in one all-or-nothing command, fanning out to each kind's `add` + `install`. If any member fails, the whole run rolls back. `bundle validate` checks the manifest resolves without installing. See [`docs/agent-toolkit/bundles.md`](docs/agent-toolkit/bundles.md) for the manifest schema.

### TUI

```text
agent-toolkit-tui                              # interactive skill grid (claude-code + pi)
AGENT_TOOLKIT_TUI_LEGACY=1 agent-toolkit-tui   # restore the legacy multi-tab layout
```

Full reference: [`docs/agent-toolkit/cli.md`](docs/agent-toolkit/cli.md).

## Development

```bash
git clone https://github.com/ajanderson1/agent-toolkit-cli ~/GitHub/projects/agent-toolkit-cli
cd ~/GitHub/projects/agent-toolkit-cli
uv sync --all-extras
uv run pytest -q
```

The `lefthook.yml` runs pytest on pre-commit.

## License

MIT (c) AJ Anderson
