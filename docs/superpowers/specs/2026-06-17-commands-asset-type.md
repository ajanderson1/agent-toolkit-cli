# Commands Asset Type Spec

## Summary

Reintroduce `commands` as a first-class agent-toolkit asset type. A command is a reusable user-invoked slash-command prompt, stored in the toolkit library, tracked by `commands-lock.json`, and projected into harness-specific command/prompt locations. The first implementation must be a complete one-shot feature, not a hidden stub: CLI, lock/path/install machinery, adapters, tests, TUI visibility, docs, harness matrix updates, and a package version bump all ship together.

## Background and research

Current agent-toolkit v4 manages `skill`, `agent`, `instructions`, `mcp`, `pi-extension`, and `bundle`. `commands` existed as a pre-v2 concept but is absent from the v3 per-kind surface. The repo now favors one module family per kind (`*_paths.py`, `*_lock.py`, `*_install.py`, `commands/<kind>/`) and explicit TUI state/grid support. The new kind must follow that architecture instead of reintroducing a generic `asset_type=` discriminator.

Harness command conventions are not uniform:

- Claude Code: custom commands are legacy-compatible markdown files under `.claude/commands/<name>.md`, but official docs now say commands have been merged into skills and `.claude/skills/<name>/SKILL.md` is recommended. Existing `.claude/commands/` still works, uses filename as command name, and supports the same frontmatter/argument substitution as skills. Source: https://code.claude.com/docs/en/skills and https://code.claude.com/docs/en/slash-commands.md.
- Gemini CLI: custom commands are TOML files under `~/.gemini/commands/` or `<project>/.gemini/commands/`; project overrides user; subdirectories namespace as `/git:commit`; required field is `prompt`, optional `description`; args use `{{args}}`; shell injection uses `!{...}`; file injection uses `@{...}`. Source: https://github.com/google-gemini/gemini-cli/blob/HEAD/docs/cli/custom-commands.md.
- Codex: current official direction is that custom prompts are deprecated in favor of skills, but existing custom prompts live as top-level markdown files in `~/.codex/prompts/*.md`, with YAML frontmatter `description` and `argument-hint`, positional `$1..$9`, `$ARGUMENTS`, and named `$KEY=value` arguments. They are explicit slash invocations, usually as `/prompts:<name>`. Source: https://developers.openai.com/codex/custom-prompts and https://developers.openai.com/codex/cli/slash-commands.
- Pi: prompt templates are markdown files in `~/.pi/agent/prompts/*.md` or `.pi/prompts/*.md`, non-recursive by default; filename becomes `/name`; optional YAML frontmatter `description` and `argument-hint`; arguments support `$1`, `$2`, `$@`, `$ARGUMENTS`, defaults, and slices. Extensions can also register runtime commands, but prompt templates are the file-backed command-like asset. Source: local Pi docs `/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/docs/prompt-templates.md` and `docs/usage.md`.
- Cursor: public documentation centers on rules, while Cursor forum guidance reports custom slash commands in `.cursor/commands` project-level and `~/.cursor/commands` global. Evidence is weaker than Claude/Gemini/Codex/Pi, so Cursor is **not** included in the first supported set unless a worker records deterministic validation evidence. Source: https://forum.cursor.com/t/how-to-use-slash-commands-w-cursor-cli/149995.

## Problem statement

agent-toolkit users need one way to register, install, update, and sync slash-command prompts across harnesses. Today they must manually maintain command files in each harness-specific folder and format. That creates drift, especially because Gemini uses TOML, Pi/Codex/Claude use Markdown-like formats with different argument variables, and some harnesses have deprecated old command formats in favor of skills.

## Goals

1. Add a `commands` top-level CLI group with singular alias `command`.
2. Store global command libraries under `~/.agent-toolkit/commands/<slug>/` and project canonicals in the existing external project store pattern.
3. Track commands in `commands-lock.json` without changing existing lock files or existing asset behavior.
4. Support git-sourced single-repo and monorepo/category-repo commands using the same mental model as skills.
5. Project command assets into researched harness command locations with adapter-specific translation where required.
6. Expose commands in the TUI sidebar and grids with global/project scope behavior matching other git-backed kinds.
7. Update all human docs and generated harness docs so commands are no longer invisible.
8. Bump package version when implementation completes.
9. Preserve backwards compatibility for all existing commands and lock files.

## Non-goals

- Do not migrate existing harness-local command files automatically.
- Do not remove or deprecate `skill` support.
- Do not force users to use commands instead of skills for Claude or Codex.
- Do not mutate shared config files for harnesses that lack file-drop command support.
- Do not implement runtime Pi extension `registerCommand()` packaging as part of this asset type; Pi command projection uses prompt templates.
- Do not promise support for every harness in the 54-harness catalog in the first cut.
- Do not add commands to bundle manifests in the first cut; document bundle support as out of scope unless the implementation explicitly extends bundle tests and docs.

## Canonical command format

A command library entry is a directory with `COMMAND.md` at its root:

```text
my-command/
├── COMMAND.md
└── references/              # optional supporting files, kept with source
```

`COMMAND.md` uses YAML frontmatter plus Markdown body:

```markdown
---
description: Review staged changes and suggest a commit message.
argument-hint: "[focus]"
---
Review staged changes with `git diff --staged`.
Focus on: $ARGUMENTS
```

Required/recognized fields:

- `description`: optional but recommended; shown in CLI/TUI/docs and translated where a harness supports it.
- `argument-hint`: optional; translated where a harness supports it.
- `name`: optional display-only metadata; command invocation name remains slug/path-derived to avoid harness disagreements.

The body remains Markdown. Supporting files are kept in the source/canonical directory for authorship and git history, but first-cut projections install only the `COMMAND.md` prompt into harness command slots. Docs must call supporting files source-only/non-portable until a harness-specific package projection exists.

Adapters may translate placeholders only when a target harness uses a different syntax:

| Canonical | Claude | Pi | Codex | Gemini |
|---|---|---|---|---|
| `$ARGUMENTS` | `$ARGUMENTS` | `$ARGUMENTS` | `$ARGUMENTS` | `{{args}}` |
| `$1..$9` | `$0..$8` mismatch risk; leave unchanged in first cut unless tests prove safe | `$1..$9` | `$1..$9` | no positional equivalent; leave literal and document |
| frontmatter | passthrough | passthrough | passthrough | TOML fields |

First cut should strongly recommend `$ARGUMENTS` for portable commands. Positional and harness-specific syntax may be preserved, but the docs must warn users they are not portable.

Slugs are path stems, not paths. Validate slugs before any filesystem operation: reject empty strings, `.`, `..`, absolute paths, any `/` or `\\`, control characters, leading dots, and characters outside `[A-Za-z0-9][A-Za-z0-9._-]*`. Namespace subdirectories are a future feature, not implicit slash handling.

`COMMAND.md` must resolve to a regular file inside the canonical command directory or monorepo subpath. Refuse symlinked `COMMAND.md`, absolute/escaping `commandPath` values, and lock/import entries whose normalized path leaves the clone root or does not end at `COMMAND.md`.

## Initial harness support

Implement only file-drop targets with clear conventions:

| Harness token | Scope | Projection | Mechanism | Notes |
|---|---|---|---|---|
| `claude-code` | global/project | `~/.claude/commands/<slug>.md`, `<project>/.claude/commands/<slug>.md` | symlink or managed file | Legacy but still supported; skill precedence documented. |
| `pi` | global/project | `~/.pi/agent/prompts/<slug>.md`, `<project>/.pi/prompts/<slug>.md` | symlink or managed file | Non-recursive prompt templates; slug must be file stem. |
| `codex` | global only initially | `~/.codex/prompts/<slug>.md` | symlink or managed file | Deprecated custom prompts; no project path. Include deprecation warning in docs. |
| `gemini-cli` | global/project | `~/.gemini/commands/<slug>.toml`, `<project>/.gemini/commands/<slug>.toml` | translate | TOML file with `description` and `prompt`. |
| `cursor` | gap unless worker records validation evidence | `~/.cursor/commands/<slug>.md`, `<project>/.cursor/commands/<slug>.md` | not first-cut default | Evidence weaker; mark as gap with research note unless deterministic validation is added. |

No `standard` command token in the first cut. Command directories are too format-specific; `.agents/commands` is not yet a broadly accepted standard and Codex support for it is only an issue/request, not shipped behavior.

## CLI behavior

Top-level:

```text
agent-toolkit-cli commands ...
agent-toolkit-cli command ...      # singular alias
```

Verb surface, matching skills where applicable:

```text
agent-toolkit-cli command add <source> [--slug <slug>] [--ref <ref>]
agent-toolkit-cli command install <slug> [-g|-p] [--harnesses <h>[,<h>...]]
agent-toolkit-cli command uninstall <slug> [-g|-p] [--harnesses <h>[,<h>...]]
agent-toolkit-cli command list [-g|-p] [--json]
agent-toolkit-cli command status [<slug>...] [-g|-p]
agent-toolkit-cli command update [<slug>...] [-g|-p]
agent-toolkit-cli command push [<slug>...] [-g|-p] [--direct]
agent-toolkit-cli command import <commands-lock.json> [--latest]
agent-toolkit-cli command reset <slug> [-g|-p]
agent-toolkit-cli command remove <slug> [-g|-p] [--force]
agent-toolkit-cli command doctor [-g|-p]
```

Default install target should be conservative: supported command harnesses that can be installed without mutating shared config, with clear output for deprecated targets. First-cut default target is `claude-code,pi,gemini-cli`; Codex is supported but must be explicit (`--harnesses codex`) or emit a deprecation warning if included in a future default. `--harnesses` should accept comma-separated tokens and reject unknown/synthetic names loudly.

## Architecture requirements

New modules mirror existing per-kind architecture:

- `src/agent_toolkit_cli/command_paths.py`
- `src/agent_toolkit_cli/command_lock.py`
- `src/agent_toolkit_cli/command_install.py`
- `src/agent_toolkit_cli/command_adapters/`
- `src/agent_toolkit_cli/commands/command/`
- `src/agent_toolkit_tui/command_state.py`
- `src/agent_toolkit_tui/widgets/command_grid.py`

Shared seams may be reused:

- `_paths_core.AssetTypeBinding` gains `COMMAND_BINDING`.
- `skill_source.py` parsing can be reused for git sources and monorepos.
- `_install_core` can be reused only through command-specific facade injection.
- `skill_git.py` can be reused for clone/update/push logic.
- Lock reader/writer code may be copied/adapted but should not add `commandPath` handling to existing skill/agent/pi-extension files unless tests prove no breaking behavior.

Architecture guard tests must be updated to assert five per-kind modules exist and no install entrypoint accepts `kind=` or `asset_type=`.

## Documentation requirements

Update:

- `README.md`
- `docs/index.md`
- `docs/agent-toolkit/cli.md`
- `docs/asset-types/commands.md` (new)
- `docs/asset-types/skills.md` cross-link, noting Claude/Codex command-vs-skill overlap
- `docs/agent-toolkit/harness-matrix.md`
- generated `docs/matrix.md` and affected `docs/harnesses/*.md`
- `docs/glossary.md`
- `docs/agent-toolkit/lock-files.md` or `skill-lock.md` equivalent references
- `docs/asset-types/skills.md` cross-link
- `mkdocs.yml` navigation
- TUI docs if commands tab is exposed

Docs must cite the harness evidence above and clearly mark deprecated/weak-evidence targets.

## Acceptance criteria

1. `agent-toolkit-cli command --help` and `agent-toolkit-cli commands --help` both work.
2. `command add` clones a single-repo source with root `COMMAND.md`, writes `~/.agent-toolkit/commands-lock.json`, and refuses sources missing `COMMAND.md` without leaving an orphan clone.
3. `command add` supports monorepo subpaths and records `commandPath` plus parent metadata with `commandPath` defined as the relative content-file path ending in `COMMAND.md`.
4. `command install` projects to Claude, Pi, and Gemini by default using researched paths/formats; Codex works only when explicitly requested or emits a deprecation warning; Cursor is documented as a gap unless validated.
5. `command uninstall` removes only toolkit-owned projections and never deletes hand-authored files.
6. `command list/status/update/push/import/reset/remove/doctor` match skill behavior where applicable.
7. Existing `skill`, `agent`, `instructions`, `mcp`, `pi-extension`, `bundle`, and TUI behavior remains unchanged.
8. TUI shows a Commands asset type with global/project rows and install cells.
9. Docs and harness matrix include Commands as a sixth asset type.
10. Package version is bumped from `4.3.0` to the next feature version.
11. Tests cover CLI aliases, lock/path behavior, adapter projections, doctor drift/orphan detection, TUI state/grid, docs matrix generation/parity, and backwards compatibility.
12. Full test suite passes with `uv run pytest -q`.
13. `uv run mkdocs build --strict` passes.
14. `uv.lock` is updated if the version bump changes package metadata.

## Test surface

Minimum tests:

- `tests/test_cli/test_command_paths.py`
- `tests/test_cli/test_command_lock.py`
- `tests/test_cli/test_command_add.py`
- `tests/test_cli/test_command_add_monorepo.py`
- `tests/test_cli/test_command_install.py`
- `tests/test_cli/test_command_adapters/test_claude.py`
- `tests/test_cli/test_command_adapters/test_pi.py`
- `tests/test_cli/test_command_adapters/test_codex.py`
- `tests/test_cli/test_command_adapters/test_gemini.py`
- `tests/test_cli/test_cli_command_group.py`
- `tests/test_cli/test_command_import.py`
- `tests/test_cli/test_command_update.py`
- `tests/test_cli/test_command_doctor.py`
- `tests/test_cli/test_asset_type_architecture.py` updates
- TUI tests for command state/grid/sidebar
- docs generation/parity tests for the new matrix column

## Risks

- Claude/Codex now prefer skills, so commands can look like a second way to do the same job. Mitigation: docs explain commands are user-invoked prompt shortcuts; skills remain auto-invocable capability packages.
- Gemini TOML translation can corrupt multiline prompts if not escaped carefully. Mitigation: use `tomlkit`/standard writer and snapshot tests.
- Command argument syntax is not portable. Mitigation: docs recommend `$ARGUMENTS`; adapters translate only the safe subset.
- Cursor evidence is weaker than official docs. Mitigation: mark Cursor as a gap unless a worker records deterministic validation evidence.
- Symlink and translated-file projections can overwrite user-authored commands if ownership is vague. Mitigation: refuse unmanaged conflicts, use sidecar metadata for managed files, and uninstall only when ownership and expected content hash match.
- Gemini commands can execute `!{...}` shell injections or `@{...}` file injections. Mitigation: warn when installing Gemini commands containing those tokens, or require explicit opt-in metadata before projection.
- New matrix column touches generated docs broadly. Mitigation: regenerate via script and include parity tests in same PR.

## Autonomy recommendation

L3 Conditional. This is a large, cross-cutting feature with new asset-kind risk, harness research, docs generation, and version bump. Escalate if implementation discovers a target harness requires config mutation, if canonical format needs to change from `COMMAND.md`, or if versioning/release automation conflicts with a manual bump.
