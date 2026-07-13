# CLI reference

`agent-toolkit-cli` is a per-asset-type CLI for managing AI-agent assets. The top-level commands are the asset-type groups — `skill` (alias `skills`), `agent`, `command`, `instructions`, `pi-extension`, `mcp` (alias `mcps`) — plus `bundle` for installing several assets together. The frozen pre-v2 surface (`check`, `link`, `doctor`, `fix`, etc.) is pinned at the `v1.0.0` tag — see the [README](../index.md) for the install command.

## Commands

### `skill`

Manage skills via per-skill upstream git repos + a per-scope lock file. The group has the plural alias `skills`; `skill list` aliases to `ls` and `skill remove` to `rm`.

```text
agent-toolkit-cli skill add <source> [--slug <slug>] [--ref <ref>] [--skill <name>] [--owned]
agent-toolkit-cli skill list [-g|-p] [-a/--agent <name>] [--json]   # alias: ls
agent-toolkit-cli skill status [<slug>...] [-g|-p]
agent-toolkit-cli skill update [<slug>...] [-g|-p]      # merge-aware
agent-toolkit-cli skill push   [<slug>...] [-g|-p] [--direct]   # PR-branch by default
agent-toolkit-cli skill remove <slug>... [-g|-p] [--force]          # alias: rm
agent-toolkit-cli skill import <file> [--latest]   # cross-machine sync — see "Moving to a new machine"
agent-toolkit-cli skill doctor [<slug>...] [-g|-p] [--no-fix]
```

`<source>` accepts `owner/repo`, a full HTTPS URL, an SSH URL, or a local path. `-g/--global` and `-p/--project` select scope; default is global. `skill list --json` emits a JSON array (`slug`, `source`, `ref`, `upstream_sha`, `local_sha`, `scope`) for scripting; `-a/--agent <name>` filters to skills currently symlinked into that agent (or the `standard` token).

`skill import <file>` rebuilds the global library from another machine's `skills-lock.json` — an additive, skip-if-exists merge that clones each absent skill at the lock's recorded SHA (or `--latest` for each ref's current HEAD); per-skill clone failures are non-fatal (exit 1 if any failed). See [Moving to a new machine](#moving-to-a-new-machine-cross-machine-sync).

`skill doctor` reports and, with confirmation, repairs library/projection drift. It normally treats a symlink outside `skills-lock.json` as stale. If another system actively owns a global projection, declare that exact link and its permitted resolved target glob in `~/.agent-toolkit/external-skill-projections.json` instead of adding it to the lock:

```json
{
  "version": 1,
  "projections": [{
    "path": ".pi/agent/skills/paperclip",
    "targetGlob": ".npm/_npx/*/node_modules/@paperclipai/server/skills/paperclip",
    "owner": "Paperclip"
  }]
}
```

The `path` and `targetGlob` fields are home-relative. Doctor ignores the link only when both its exact path and its live resolved target match. Missing or changed targets remain repairable stray findings; malformed registry data fails loudly. This registry documents external ownership only — it never makes the external skill part of the agent-toolkit library.

> **Terminology:** *standard* — formerly "general" (v3), earlier "universal" (pre-v3). The old token spellings were removed in v4; they now raise an unknown-token error.

Full reference, lock-file format, and skills.sh interop notes live in [`skill-lock.md`](skill-lock.md).

### `agent`, `command`

Manage subagent definitions (the `agent`, `command` [asset type](../asset-types/agents.md)) — one canonical markdown file per agent, projected per harness.

```text
agent-toolkit-cli agent add <source> [--slug <slug>] [--ref <ref>]
agent-toolkit-cli agent install <slug> [-g|-p] [--harnesses <h>[,<h>...]]
agent-toolkit-cli agent uninstall <slug> [-g|-p] [--harnesses <h>[,<h>...]]   # non-destructive
agent-toolkit-cli agent remove <slug> [--force]                               # destructive
agent-toolkit-cli agent list / status / doctor [-g|-p]
agent-toolkit-cli agent import <file> [--latest]   # cross-machine sync — see "Moving to a new machine"

agent-toolkit-cli agent install my-agent -g --harnesses standard
agent-toolkit-cli agent install my-agent -g                       # covered-aware fan-out
agent-toolkit-cli agent uninstall my-agent -g                     # maximal sweep
```

- `--harnesses standard` (#361) writes the single shared `.claude/agents/<slug>.md` slot (`~/.claude/agents/` at global scope, `<project>/.claude/agents/` at project scope) that every harness in the per-scope covered set reads natively — `agent_adapters/standard.py::STANDARD_AGENT_READERS` is the SSOT for that set (as of 2026-06: claude-code, kode, neovate, cortex, cursor at both scopes, plus devin at project scope only).
- `--harnesses claude-code` is normalized to `standard`: claude-code's destination IS the standard slot, so one file under one token — every scan dedupes by destination and reports it as `standard`.
- `agent install` with no `--harnesses` defaults covered-aware: the standard slot plus every enabled harness the slot does **not** cover at that scope (no redundant own-dir copies for the covered readers). `agent uninstall` with no `--harnesses` deliberately stays **maximal** — the standard slot plus *all* enabled harnesses — so it also cleans own-dir files left by pre-#361 installs.
- Synthetic catalog names (`standard-skill`, `standard-agent`) are rejected with an explicit error telling you to use `standard`, instead of the previous silent no-op.
- `agent import <file>` rebuilds the global library from another machine's `agents-lock.json` (additive, skip-if-exists; `--latest` clones at each ref's current HEAD; per-slug failures non-fatal). See [Moving to a new machine](#moving-to-a-new-machine-cross-machine-sync).

`agent doctor` also checks the standard slot (#361 finding families): `standard-slot-drift` (slot differs from the scope's canonical; fix re-seeds it), `cursor-shadow` (a divergent pre-existing `.cursor/agents/<slug>.md` file — cursor's own dir **wins** name conflicts, so it shadows the slot; when the file carries the tool's `.attk` ownership sidecar the doctor offers to remove it, otherwise it is report-only — a sentinel-less divergent file may equally be hand-authored, and `agent uninstall` refuses exactly that class, so remove it manually if the shadowing is unintended), `standard-slot-orphan` (tool-written slot file with no lock entry), `standard-slot-unmanaged` (hand-authored files in `.claude/agents/` — **never** auto-removed), and `standard-slot-dangling-sidecar` (stale `.attk` ownership sidecar without its slot file). `cursor-shadow` and `standard-slot-unmanaged` are **informational**: they stay visible in the output but never fail the doctor exit code or suppress the clean verdict.

### `command`

Manage reusable slash-command prompts (the [`command` asset type](../asset-types/commands.md)) from canonical `COMMAND.md` folders. The group has plural alias `commands`; `command list` aliases to `ls`.

```text
agent-toolkit-cli command add <source> [--slug <slug>] [--ref <ref>]
agent-toolkit-cli command install <slug> [-g|-p] [--harnesses <h>[,<h>...]]
agent-toolkit-cli command uninstall <slug> [-g|-p] [--harnesses <h>[,<h>...]]
agent-toolkit-cli command list [-g|-p] [--json]
agent-toolkit-cli command status [-g|-p]
agent-toolkit-cli command update [<slug>] [-g|-p]
agent-toolkit-cli command push <slug>
agent-toolkit-cli command import [-g|-p]
agent-toolkit-cli command reset <slug> --force [-g|-p]
agent-toolkit-cli command remove <slug> [-g|-p]
agent-toolkit-cli command doctor [-g|-p]
```

Default install targets are `claude-code,pi,gemini-cli`. `codex` is explicit because Codex custom prompts are deprecated and global-only. Cursor remains a researched gap until deterministic validation evidence exists.

### `mcp`

Manage MCP servers via config-injection adapters + a `mcps-lock.json` lock file. The group has the plural alias `mcps`; `mcp list` aliases to `ls`. See the [MCP asset-type page](../asset-types/mcp.md) for the mechanism, paths, and the `standard` projection.

```text
agent-toolkit-cli mcp add --npx|--uvx|--docker|--url|--local <source> [--slug <slug>]   # author into the library from flags
agent-toolkit-cli mcp install <slug>   [--harness <h>]... [-g|-p] [--force]
agent-toolkit-cli mcp uninstall <slug> [--harness <h>]... [-g|-p] [--force]
agent-toolkit-cli mcp remove <slug>    [-g|-p] [--force]   # full undo: every locked harness
agent-toolkit-cli mcp update <slug>                        # re-resolve + re-project
agent-toolkit-cli mcp list   [-g|-p]                       # alias: ls
agent-toolkit-cli mcp status [<slug>...] [-g|-p]
agent-toolkit-cli mcp doctor [-g|-p]
```

- `mcp add` authors an MCP server into the global library from flags: a source (`--npx`, `--uvx`, `--docker`, `--url`, or `--local` paired with `--command`), plus optional `--command`, `--env` (repeatable), `--description`, and `--slug`.
- `mcp install` projects a library MCP into the chosen scope's harnesses; `--harness` (repeatable) selects from `claude-code`, `codex`, `opencode`, `pi`, or `standard`. `--force` bypasses the running-claude guard for `~/.claude.json` writes.
- `mcp uninstall` removes a MCP's projections from the chosen scope (default: every harness in the lock). `mcp remove` removes them from **every** harness recorded in the lock — full undo, no `--harness`.
- `mcp update` re-resolves a library MCP and re-projects every reachable locked harness. `mcp doctor` diagnoses projection drift read-only — it never writes.
- There is **no `mcp import`** — MCP cross-machine sync is tracked separately ([#429](https://github.com/ajanderson1/agent-toolkit-cli/issues/429)). (The `instructions` asset type likewise has no `import`: it has no per-machine library to reconstruct.)

### `pi-extension`

Manage Pi extensions (the `pi-extension` [asset type](../asset-types/pi-extensions.md)). Its full verb set is documented on the asset-type page; the cross-machine-sync verb is:

```text
agent-toolkit-cli pi-extension import <file> [--latest]   # cross-machine sync — see "Moving to a new machine"
```

`pi-extension import <file>` rebuilds the global library from another machine's `pi-extensions-lock.json` (additive, skip-if-exists; `--latest` clones at each ref's current HEAD; per-slug failures non-fatal). See [Moving to a new machine](#moving-to-a-new-machine-cross-machine-sync).

### `bundle`

Install assets declared together in a bundle manifest. See [`bundles.md`](bundles.md) for the manifest schema and fan-out behaviour.

```text
agent-toolkit-cli bundle install  <manifest> [--global | --project]   # all-or-nothing
agent-toolkit-cli bundle validate <manifest>                          # check resolution, no install
```

- `bundle install` installs every member of a bundle manifest as one all-or-nothing operation.
- `bundle validate` checks a bundle manifest resolves without installing.

### `tui` (separate binary)

```text
agent-toolkit-tui   # interactive cockpit over the same surface
```

Installed alongside the CLI via the same `uv tool install` command. See the
[TUI reference](tui.md) for the layout, key bindings, and edit flow.

## Pre-v2 surface

The pre-v2 commands (`check`, `diff`, `doctor`, `fix`, `ingest`, `inventory`, `link`, `list`, `migrate-skills`, `new`, `pi`, `unlink`) no longer exist on `main`. They remain available at the `v1.0.0` tag:

```text
uv tool install --from git+https://github.com/ajanderson1/agent-toolkit-cli@v1.0.0 agent-toolkit
```

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

## Moving to a new machine (cross-machine sync)

**The lock file is the export artifact** — there is no `export` command. Each asset kind's global library is fully described by its per-scope lock file, so reconstructing your library on a second machine is just: copy the lock file across, then `import` it.

1. On the **source** machine, locate the global lock(s) you want to carry: `skills-lock.json`, `agents-lock.json`, `commands-lock.json`, and/or `pi-extensions-lock.json` (in the toolkit's global config dir).
2. Copy the lock file(s) to the **new** machine (any path — e.g. `~/sync/`).
3. On the new machine, run the matching `import` per kind:

   ```bash
   agent-toolkit-cli skill        import ~/sync/skills-lock.json
   agent-toolkit-cli agent        import ~/sync/agents-lock.json
   agent-toolkit-cli command      import ~/sync/commands-lock.json
   agent-toolkit-cli pi-extension import ~/sync/pi-extensions-lock.json
   ```

**Shared import semantic.** Import is an **additive, skip-if-exists merge**: only slugs absent locally are added, so re-running is safe. By default each new asset is cloned at the **recorded SHA** from the lock — so local commits or uncommitted changes that lived only on the source machine are **NOT** carried across. Pass `--latest` to clone each new asset at its ref's current HEAD instead. Per-slug clone failures are non-fatal (the command still imports the rest and exits 1 if any failed).

**Caveats** (these are what each `import` command prints in its own `Notes:`):

- **Added, not installed.** Imported assets land in the global *library* but are not projected into any harness/agent/scope. Make them visible with the per-kind install command:
  - `skill install <slug> --agents <name>`
  - `agent install <slug> -g`
  - `pi-extension install <slug> -g`
- **Global-library only.** Only the global library is reconstructed. **Project-scoped** assets (recorded in a per-project lock file) must be re-installed by hand in each project.
- **Pinned to upstream.** (skill surfaces this caveat explicitly; it is the recorded-SHA semantic above — true for all three kinds.) Imports take the lock's recorded upstream commit, so anything local-only on the source machine is left behind; use `--latest` if you want current HEADs.

**Why no `export` command (by design).** A separate export step would be redundant: the lock file already *is* a complete, portable description of the library. Copying it and running `import` on the far side is the whole sync. `import`'s skill docstring states this directly — *"The export artifact is just another machine's global skills-lock.json — there is no `export` command."*

`mcp` has no `import` yet (cross-machine sync for MCP servers is tracked: [#429](https://github.com/ajanderson1/agent-toolkit-cli/issues/429)); `instructions` has no per-machine library to sync.

---

## See also

- [`skill-lock.md`](skill-lock.md) — lock-file format and `skill` subcommand reference.
- The 54-agent catalog lives in `src/agent_toolkit_cli/skill_agents.py`; the 14 entries whose `skillsDir == .agents/skills` are the *standard* (universal) agents.
