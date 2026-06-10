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
agent-toolkit-cli skill push   [<slug>...] [-g|-p] [--direct]   # PR-branch by default
agent-toolkit-cli skill remove <slug>... [-g|-p] [--force]          # alias: rm
```

`<source>` accepts `owner/repo`, a full HTTPS URL, an SSH URL, or a local path. `-g/--global` and `-p/--project` select scope; default is global. `skill list --json` emits a JSON array (`slug`, `source`, `ref`, `upstream_sha`, `local_sha`, `scope`) for scripting; `-a/--agent <name>` filters to skills currently symlinked into that agent (or the `standard` token).

> **Terminology:** *standard* — formerly "general" (v3), earlier "universal" (pre-v3). The old token spellings still work for one cycle with a deprecation warning and are removed in v4.

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

## skill add

```
Usage: agent-toolkit-cli skill add <source> [--ref <ref>] [--slug <slug>] [--skill <name>]
```

| Flag | Description |
|---|---|
| `<source>` | `owner/repo`, `owner/repo@<ref>`, `owner/repo/<subpath>`, full URL, SSH URL, local path, or `https://www.skills.sh/…` URL. To pin a ref **and** a subpath together, use the URL form `https://github.com/owner/repo/tree/<ref>/<subpath>` or pair the `<owner>/<repo>/<subpath>` shorthand with `--ref`. The combined shorthand `owner/repo@<ref>/<subpath>` is rejected because slash-containing refs make it ambiguous (see #198). |
| `--ref <ref>` | Git ref to pin (branch, tag, or SHA). Shorthand `owner/repo@<ref>` is equivalent for refs without `/`; refs containing `/` (e.g. `feature/branch`) must use this flag. |
| `--slug <slug>` | Override the slug used for the canonical directory and lock-file entry |
| `--skill <name>` | Select one skill by `name:` frontmatter when `<source>` is a monorepo |

### Monorepo skills

These three commands install the same `mkdocs` skill, lock-file equivalent:

```bash
agent-toolkit-cli skill add vamseeachanta/workspace-hub --skill mkdocs
agent-toolkit-cli skill add vamseeachanta/workspace-hub/mkdocs
agent-toolkit-cli skill add https://www.skills.sh/vamseeachanta/workspace-hub/mkdocs
```

The parent repo is cloned once under `$AGENT_TOOLKIT_SKILLS_ROOT/_parents/<owner>/<repo>/` (or `~/.agent-toolkit/skills/_parents/<owner>/<repo>/` by default). The library canonical at `<library>/<slug>/` is a symlink into the parent's subfolder; on platforms where symlinks fail, the CLI falls back to a recursive copy and records `materialised: "copy"` in the lock entry.

`skill update <slug>` for monorepo entries runs `git fetch` + `git merge` against the parent clone, so local commits merge with upstream cleanly. On conflict the command exits 1 and names the parent clone path (`<library>/_parents/<owner>/<repo>/`); resolve there and re-run `skill update`.

`skill push <slug>` for monorepo entries is refused; the message names the parent URL so you can open a PR there instead.

## skill push

By default `skill push <slug>` creates a `skill/self-improvement-<timestamp>` branch in the canonical skill repo, pushes it, and opens a PR against the tracked ref via `gh pr create` (printing the PR URL). When `gh` is not installed or not authenticated the branch is still pushed and the command prints a hint with the branch's web URL so you can open the PR by hand.

`--direct` opts into the pre-#221 behaviour: commit + push straight to the tracked ref and update `local_sha` in the lockfile. Use it for solo first-party skills where opening a PR for every self-improvement would be ceremony. The default path leaves `local_sha` alone — the next `skill update` picks up the merged change normally.

---

## See also

- [`skill-lock.md`](skill-lock.md) — lock-file format and `skill` subcommand reference.
- The 55-agent catalog (`skillsDir == .agents/skills` = standard) lives in `src/agent_toolkit_cli/skill_agents.py`.
- [`schema.md`](schema.md) — asset frontmatter schema (toolkit-repo SSOT, not consumed by this CLI post-v2.3.0).
