# Lock files

Every asset type records its installation state in a per-scope JSON **lock
file** — the source of truth for what is installed, never the filesystem. There
is one lock file per asset type per scope:

| Asset type | Lock file | Top-level key | Entry shape |
|---|---|---|---|
| [skill](../asset-types/skills.md) | `skills-lock.json` | `skills` | slug → entry |
| [agent](../asset-types/agents.md) | `agents-lock.json` | `skills` ⚠️ | slug → entry |
| [command](../asset-types/commands.md) | `commands-lock.json` | `skills` ⚠️ | slug → entry (`commandPath`) |
| [pi-extension](../asset-types/pi-extensions.md) | `pi-extensions-lock.json` | `skills` ⚠️ | slug → entry |
| [mcp](../asset-types/mcp.md) | `mcps-lock.json` | `mcps` | slug → **list** of entries |
| [instructions](../asset-types/instructions.md) | `instructions-lock.json` | `instructions` | slug → entry |

> ⚠️ **The `agents`, `command`, and `pi-extension` lock files use a top-level key named
> `skills`, not `agents` / `pi-extensions`.** Their lock module re-exports the
> skill writer verbatim (`agent_lock.py` and `pi_extension_lock.py` import
> compatible serializers), which hard-code `"skills"`. The schema is
> asset-type-blind: the same envelope serves all three, distinguished only by
> which path field each entry populates. Don't be surprised reading the raw
> JSON.

## Scope and location

Each lock file exists at most twice — once per [scope](../glossary.md#scope):

- **Global lock:** `~/.agent-toolkit/<name>-lock.json` (e.g.
  `~/.agent-toolkit/agents-lock.json`).
- **Project lock:** `<project>/<name>-lock.json` — committed to git so the
  project's asset set travels with the repo.

The one exception is the skills global lock when written by `npx skills`: it
lands at `~/.agents/.skill-lock.json` for compatibility with that tool. See
[`skill-lock.md`](skill-lock.md) for the full skills/skills.sh interop story.

## Shared envelope (skill, agent, command, pi-extension)

These three share one serializer (`skill_lock.py`), so they have an identical
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
| `sourceType` | string | `github`, `gitlab`, `npm`, or `local` |
| `ref` | string \| null | Git ref pinned at add time (branch, tag, or SHA) |
| `skillPath` | string \| null | Path within the repo to the skill (populated for skills) |
| `agentPath` | string \| null | Path within the repo to the agent (populated for agents) |
| `commandPath` | string \| null | Relative path ending in `COMMAND.md` (populated for commands) |
| `piExtensionPath` | string \| null | Path within the repo to the pi-extension (populated for pi-extensions) |
| `upstreamSha` | string \| null | Upstream commit SHA observed at add time — **not** a user pin (see [pin-vs-observed](skill-lock.md)) |
| `localSha` | string \| null | Local commit SHA (v1 skills only) |
| `parentUrl` | string \| null | Monorepo parent URL when the canonical is a subpath import |
| `readOnly` | boolean | Whether the entry is read-only (e.g. a public third-party skill) |

What distinguishes an agent entry from a skill or pi-extension entry is **which
path field is populated** — `skillPath`, `agentPath`, `commandPath`, or `piExtensionPath`. The
other two are `null`.

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

## `instructions-lock.json`

Instructions have no upstream repo — they are whole-scope `AGENTS.md` pointers —
so this lock has no `source`/`ref`/SHA fields. It records scope and which
harnesses received the pointer.

```json
{
  "version": 1,
  "instructions": {
    "<slug>": {
      "scope": "project",
      "source": "AGENTS.md",
      "harnesses": ["claude-code", "gemini-cli"]
    }
  }
}
```

| Field | Type | Meaning |
|---|---|---|
| `scope` | `"project"` \| `"global"` | Where the canonical `AGENTS.md` lives |
| `source` | string | Relative path to the source file (typically `AGENTS.md`) |
| `harnesses` | string[] | Harnesses this entry is installed to (defaults to `[]`) |

The reader is strict: an unsupported `version` raises rather than degrading.

## Invariants

- **Lock is the source of truth.** Installation state is read from the lock, not
  inferred from the filesystem. `doctor` is what reconciles the two.
- **Atomic writes.** skill / agent / pi-extension / mcp locks write to a temp
  file and `os.replace()` so a crash mid-write can't corrupt the lock.
- **Sorted, newline-terminated JSON.** Keys are sorted and a trailing newline is
  written, for clean, stable VCS diffs.
- **Forward-compatible.** The shared envelope preserves unknown keys; the MCP
  reader tolerates unknown fields.

## See also

- [`skill-lock.md`](skill-lock.md) — the skills lock in depth: on-disk layout,
  monorepo imports, version 3 / `npx skills` interop, and merge-aware `update`.
- [CLI reference](cli.md) — the commands that read and write these locks.
- [Glossary](../glossary.md#scope) — scope, canonical, and pointer definitions.
