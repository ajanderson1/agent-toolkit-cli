# Bundle manifest

A bundle is a toolkit-native JSON manifest that declares a set of asset pointers
and installs them together in a single, all-or-nothing command.

## What a bundle is (and is not)

v1 is a **stateless shortcut**, not a package format.  Running `bundle install`
fans out to the existing per-kind installers (`skill`, `agent`, `pi-extension`)
exactly as if you had run each one by hand.  Installed members appear individually
in their own per-kind lock files and in the TUI/CLI — nothing is recorded on disk
that says "these came from a bundle."  The bundle itself is recorded nowhere.

The value v1 delivers is **atomic co-install of a known dependency set**: one
command to get the whole group onto disk, or nothing at all on failure.  It does
not durably prevent drift after install; if a member is later removed by hand,
nothing detects the gap.  Durable drift detection is a deliberate v2 concern.

## Verbs

```text
agent-toolkit-cli bundle install  <manifest.json> [--global | --project]
agent-toolkit-cli bundle validate <manifest.json>
```

### `bundle install`

Reads the manifest from a local file path, validates its structure (the same pass
`bundle validate` runs), then installs every member by fanning out to each kind's
`add` + `install` sequence.  All-or-nothing: if any member fails, every member
installed during this run is rolled back; the system is left as it was before.

`--global` / `--project` apply one scope to all members.  With no flag the scope
is determined by the presence of a per-kind lock file in the current directory:
project scope if any of `skills-lock.json`, `agents-lock.json`, or
`pi-extensions-lock.json` exists in cwd; global otherwise.

### `bundle validate`

Performs the same structural check as the install resolve pass — valid
`schema_version`, known and installable `asset_type` values, required fields
present, no option-injection characters — with **all disk writes suppressed**.
Exits zero when the manifest is structurally valid, non-zero otherwise.

`validate` does **not** probe source or ref reachability over the network.
Reachability is proven by the real `add` during install; validate is a static
manifest check.

## Schema (v1)

Manifests are JSON files.  The conventional extension is `.bundle.json` (any
`.json` file is accepted).

### Top-level fields

| Field | Required | Type | Notes |
|---|---|---|---|
| `schema_version` | yes | integer | Must be `1`. Unknown values are rejected (forward-compat guard). |
| `name` | yes | string | Human-readable label for the bundle. Not a lock key — bundles are not tracked. |
| `description` | no | string | Free text. |
| `members` | yes | array | Non-empty array of member objects (see below). |

### Member fields

| Field | Required | Type | Notes |
|---|---|---|---|
| `asset_type` | yes | string | One of `skill`, `agent`, `pi-extension` (installable in v1); `mcp` (reserved — see below); anything else is rejected. |
| `source` | yes | string | Repo (`owner/repo`) or monorepo subpath (`owner/repo/subpath`) — the same source string each kind's `add` accepts. Must not start with `-`. |
| `slug` | no | string | Override the derived slug, exactly as each kind's `--slug` does. Must not start with `-`. |
| `ref` | no | string | Branch, tag, or SHA pin.  Honoured for `skill` and `agent`.  **Not allowed on `pi-extension` members** — `pi-extension add` has no `--ref`; a manifest with `ref` on a `pi-extension` entry is rejected at parse. Must not start with `-`. |

### `mcp` and `instructions` member types

`mcp` is a valid `asset_type` value in the schema (reserved for forward
compatibility), but the installer hard-fails loudly on any `mcp` member — the MCP
asset kind is not built yet (tracked in [#329](https://github.com/ajanderson1/agent-toolkit-cli/issues/329)).
The failure happens in the resolve pass, before any install, so there is nothing to
roll back.

`instructions` is not a valid bundle member type.  Unlike skills and agents, an
`instructions` asset has no shareable git source — it is a per-project pointer
reconciliation, not a portable asset.  A manifest listing `instructions` is
rejected with a clear message.

## Example manifest

`team-review.bundle.json` — a code-review agent and the two skills it depends on:

```json
{
  "schema_version": 1,
  "name": "team-review",
  "description": "Code-review agent plus the skills it depends on.",
  "members": [
    {
      "asset_type": "agent",
      "source": "ajanderson1/skills/agents/code-reviewer",
      "slug": "code-reviewer",
      "ref": "v2.1.0"
    },
    {
      "asset_type": "skill",
      "source": "ajanderson1/skills/git-worktrees"
    },
    {
      "asset_type": "skill",
      "source": "ajanderson1/skills/tdd"
    }
  ]
}
```

Install at project scope:

```bash
agent-toolkit-cli bundle install --project ./team-review.bundle.json
```

Validate structure without installing:

```bash
agent-toolkit-cli bundle validate ./team-review.bundle.json
```

## Behaviour details

### Per-kind fan-out

Each member installs via the real per-kind `add` + `install` sequence:

- **`skill` members** — `skill add <source> [--slug] [--ref]` then `skill install
  <slug> --agents standard --scope <global|project>`.
- **`agent` members** — `agent add <source> [--slug] [--ref]` then `agent install
  <slug> [-g/-p]`.
- **`pi-extension` members** — `pi-extension add <source> [--slug]` (no `--ref`)
  then `pi-extension install <slug> [-g/-p]`.

No installer logic is duplicated; the bundle reuses the existing per-kind code
paths, so each member lands in exactly the state a hand-install would produce.

### All-or-nothing rollback

If any member fails to install, every member installed during this run is rolled
back.  Rollback calls the kind-level `remove --force` (a full undo — drops the
library lock entry, the canonical, and all projections), not just `uninstall`
(which is projection-only).

A member that was **already present** before the run (detected via a library-lock
pre-check before the install call) is **not** rolled back — it was not installed
by this run and is not ours to remove.

Rollback failures are never swallowed.  If a member's remove raises during
rollback, a warning is emitted to stderr naming the member(s) that may need manual
cleanup.  The original install error still propagates.

### Option-injection guard

`source`, `slug`, and `ref` values that begin with `-` are rejected at parse time.
The dispatcher also inserts a `--` end-of-options sentinel before any
manifest-derived positional argument, so a crafted field (e.g. `slug: "--force"`)
can never be read as a CLI flag.

## v2 roadmap

The following are explicitly out of scope for v1 and deferred to v2:

- `bundle uninstall` — re-reads the manifest and removes each member via its own
  kind's uninstall.
- `doctor` "bundle members present" drift check — post-install membership
  detection keyed on a `bundleId` stamp in `LockEntry.extras`.
- Remote / repo-distributed manifest resolution — v1 accepts local file paths
  only; fetching a manifest from a git ref is a thin v2 wrapper.
- Source/ref reachability probe in `validate` — a `git ls-remote` per-member
  check carries network cost not worth v1.
- Grouping-lock composite — one shared clone at
  `~/.agent-toolkit/bundles/<slug>/`, atomic group uninstall, a group id in each
  member's lock entry.  This is the bundle ADR's "step 3" and replaces v1's
  N-independent-clones install mechanism.

The full design, including the grouping-lock composite architecture, lives in the
spec:
`docs/superpowers/specs/2026-06-12-bundle-manifest-design.md`.

## See also

- [`cli.md`](cli.md) — full CLI reference for `skill`, `agent`, `instructions`,
  and `pi-extension`.
- [`schema.md`](schema.md) — asset frontmatter schema.
- [`skill-lock.md`](skill-lock.md) — skill lock-file format.
