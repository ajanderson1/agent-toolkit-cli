# Lock files

Source-backed asset types record state in a per-scope JSON **lock file**.
Instructions is intentionally different: actual symlinks to canonical `AGENTS.md`
are its installation truth, with no installation record. Pi npm packages also
have no Toolkit installation lock: native Pi settings and direct npm installations
are authoritative; Pi's Git-backed library extensions still use their source lock.

| Asset type | Lock file | Top-level key | Entry shape |
|---|---|---|---|
| [skill](../asset-types/skills.md) | `skills-lock.json` | `skills` | slug → entry |
| [agent](../asset-types/agents.md) | `agents-lock.json` | `skills` ⚠️ | slug → entry |
| [command](../asset-types/commands.md) | `commands-lock.json` | `skills` ⚠️ | slug → entry (`commandPath`) |
| [pi-extension](../asset-types/pi-extensions.md) | `pi-extensions-lock.json` (Git/library sources only) | `skills` ⚠️ | slug → entry |
| [mcp](../asset-types/mcp.md) | `mcps-lock.json` | `mcps` | slug → **list** of entries |
| [instructions](../asset-types/instructions.md) | none — actual symlinks | — | — |

> ⚠️ **The `agents`, `command`, and `pi-extension` lock files use a top-level key named
> `skills`, not `agents` / `pi-extensions`.** Their lock module re-exports the
> skill writer verbatim (`agent_lock.py` and `pi_extension_lock.py` import
> compatible serializers), which hard-code `"skills"`. The schema is
> asset-type-blind: the same envelope serves all four source-backed kinds, distinguished by
> which path field each entry populates. Don't be surprised reading the raw
> JSON.

## Scope and location

Locks are scoped: one global library/user record and a separate project record in each consumer repository ([scope](../glossary.md#scope)):

- **Global lock:** `~/.agent-toolkit/<name>-lock.json` (e.g.
  `~/.agent-toolkit/agents-lock.json`).
- **Project lock:** `<project>/<name>-lock.json` — committed to git so the
  project's asset set travels with the repo.

The one exception is the skills global lock when written by `npx skills`: it
lands at `~/.agents/.skill-lock.json` for compatibility with that tool. See
[`skill-lock.md`](skill-lock.md) for the full skills/skills.sh interop story.

## Shared envelope (skill, agent, command, pi-extension)

These four share a serializer (`skill_lock.py`), so they have a compatible
structure. The top-level key is always `skills` regardless of asset type:

```json
{
  "version": 1,
  "skills": {
    "<slug>": {
      "source": "owner/repo",
      "sourceType": "github",
      "ref": "main",
      "skillPath": "SKILL.md",
      "agentPath": null,
      "piExtensionPath": null,
      "upstreamSha": "abc123…",
      "parentUrl": null,
      "readOnly": false
    }
  }
}
```

| Field | Type | Meaning |
|---|---|---|
| `source` | string | Repo identifier (`owner/repo`), URL, or local path |
| `sourceType` | string | Source category, including `github`, `gitlab`, `git`, `npm`, or `local` as supported by the kind. |
| `ref` | string \| null | Git ref pinned at add time (branch, tag, or SHA) |
| `skillPath` | string \| null | Path within the repo to the skill (populated for skills) |
| `agentPath` | string \| null | Path within the repo to the agent (populated for agents) |
| `commandPath` | string \| null | Relative path ending in `COMMAND.md` (populated for commands) |
| `piExtensionPath` | string \| null | Path within the repo to the pi-extension (populated for pi-extensions) |
| `upstreamSha` | string \| null | Upstream commit SHA observed at add time — **not** a user pin (see [pin-vs-observed](skill-lock.md)) |
| `localSha` | string \| null | Recorded local commit SHA where available; inspect live Git for current state. |
| `parentUrl` | string \| null | Monorepo parent URL when the canonical is a subpath import |
| `readOnly` | boolean | Whether the entry is read-only (e.g. a public third-party skill) |

What distinguishes entries across the four kinds is **which
path field is populated** — `skillPath`, `agentPath`, `commandPath`, or `piExtensionPath`. Unused path fields may be absent or null.

Unknown JSON keys are preserved on round-trip (kept in an `extras` map), so a
lock file written by a newer version of the tool — or by `npx skills` — is never
silently dropped on rewrite.

### Skills version 3

The skills global lock written by `npx skills` is **version 3**, which adds
`sourceUrl`, `skillFolderHash`, `installedAt` / `updatedAt` timestamps, and
wrapper-level `dismissed` / `lastSelectedAgents`. The reader accepts both v1 and
v3 transparently; the writer **preserves whichever version is already on disk
and never downgrades**. New files are written as v1 (clean VCS diffs). Full
detail in [`skill-lock.md`](skill-lock.md).

## `mcps-lock.json`

MCP library authority is the **global `mcps-library.json` manifest**, not this lock. Each `mcps/<slug>/config.json` and `mcps/<slug>.toolkit.yaml` pair is materialized output. `mcps migrate` explicitly adopts safe legacy entries; doctor is read-only. Remove retracts locked projections in the selected scope but retains library membership/files.

The MCP lock is the odd one out: a slug maps to a **list** of entries, one per
harness the server is projected into. This mirrors the fact that one MCP can be
installed into several harnesses independently.

```json
{
  "version": 1,
  "mcps": {
    "<slug>": [
      { "harness": "claude-code", "source": "npx", "pin": "1.2.0" },
      { "harness": "codex",       "source": "npx", "pin": "1.2.0" }
    ]
  }
}
```

| Field | Type | Meaning |
|---|---|---|
| `harness` | string | Harness the server is projected into (`claude-code`, `codex`, `opencode`, `pi`, `standard`, …) |
| `source` | string | Install method: `npx`, `uvx`, `docker`, `url`, or `local` |
| `pin` | string \| null | Resolved version at install time; `null` means floating (re-resolved on `update`) |

The list is sorted by harness, and slugs are sorted — deterministic diffs. The
`pin` key is omitted entirely when null. Unlike the shared envelope, the MCP
reader **fails loud** on malformed JSON rather than returning an empty lock. See
the [MCP asset-type page](../asset-types/mcp.md) for the projection mechanism.

## Pi npm packages: native state, no Toolkit lock

Native `packages[]` declarations/resource filters and direct npm installation
metadata define inventory and selection. npm's own dependency lockfiles remain
npm-owned. Retired `sourceType: "npm"` Toolkit entries do not keep rows visible or
grant permissions. Explicit `pi-extensions migrate-npm-records --apply` creates a
private original-byte backup and prunes only npm records; ordinary inventory,
upgrade and import do not activate packages. Old npm imports are skipped.
[Lifecycle, scope inheritance and compatibility](../asset-types/pi-extensions.md).

## Instructions: no lock

Instructions has no upstream clone/ref/SHA workflow. Canonical `AGENTS.md` and its
user-owned source chain remain on disk; only the assistant pointer symlinks are
installed or uninstalled. Legacy `instructions-lock.json` / `instructions.lock`
files are ignored and preserved, even when malformed. They can be removed manually
after checking that no older toolkit version still uses them.

## Toolkit package state is not an asset lock

The application package, shell integration and asset data have separate lifecycles.
Root `atc update` replaces Toolkit; it does not update any lock in the table above
or migrate existing backing. `atc skills update`, `atc agents update`, and the
other per-kind verbs act on assets instead.

| State | Default location | Owner/meaning |
|---|---|---|
| Shared CLI/TUI behavior | `~/.agent-toolkit/config.json` | Central/private backing choices and an optional catalogue subscription; not update-check settings. |
| TUI presentation | `~/.agent-toolkit/tui-settings.json` | Theme and main-harness columns; `AGENT_TOOLKIT_TUI_SETTINGS` can override the path. |
| Stable release observation | `~/.cache/agent-toolkit/update.json` | Shared six-hour cache / 15-minute failure backoff; `XDG_CACHE_HOME` changes the cache root. |
| Self-built package wheels and `receipt.json` | `~/.local/state/agent-toolkit/updates/<commit-prefix>-<unique-id>/` | Canonical source SHA, local wheel hash and build identity; `XDG_STATE_HOME` changes the state root. |
| Active package-update guard | `~/.local/state/agent-toolkit/updates/.update-lock/` | A directory preventing concurrent replacements, not an asset lock. |
| Completion integration | Shell-specific startup file | Explicit marked block; see [paths](shell-completion.md#options-and-default-paths). |

`AGENT_TOOLKIT_SKILLS_ROOT` relocates skill storage and associated asset state,
**not** package-update caches/receipts. `XDG_CONFIG_HOME` selects Fish's completion
configuration root, but does not relocate the shared behavior or default TUI
preferences files. Do not edit cache timestamps as an asset-management operation.
Use `atc update --check` for an explicit fresh release observation.

Keep the currently installed wheel/receipt when managing updater artifacts.
A self-update receipt is not a published GitHub `deployment-receipt.json` or an
asset source lock. [Build identity and recovery](updates.md#build-and-installation-provenance) ·
[Official release verification](installation.md#verify-a-published-wheel).

## Invariants

- **Source-backed kinds use locks.** `doctor` reconciles recorded and actual
  state. Instructions instead inventories actual pointers and protects any
  pointer participating in canonical's source chain.
- **A lock is not observed installation truth.** Source metadata may outlive missing or foreign projections; status/doctor and the TUI inspect actual paths/configs. Commands additionally records optional `harnesses` metadata only after successful mutations; reads do not backfill it.
- **Atomic file replacement is not a global transaction.** Lock writers use temporary-file replacement where implemented; it does not make all projections, manifests, sidecars or cross-kind Apply succeed/roll back together.
- **Sorted, newline-terminated JSON.** Keys are sorted and a trailing newline is
  written, for clean, stable VCS diffs.
- **Forward-compatible.** The shared envelope preserves unknown keys; the MCP
  reader tolerates unknown fields.

## See also

- [`skill-lock.md`](skill-lock.md) — the skills lock in depth: on-disk layout,
  monorepo imports, version 3 / `npx skills` interop, and merge-aware `update`.
- [CLI reference](cli.md) — the commands that read and write these locks.
- [Glossary](../glossary.md#scope) — scope, canonical, and pointer definitions.
