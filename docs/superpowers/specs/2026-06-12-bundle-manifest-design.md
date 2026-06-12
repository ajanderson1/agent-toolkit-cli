# Bundle manifest v1 — declare assets that install together (toolkit-native JSON)

**Issue:** #369
**Tier:** deep (new JSON schema/contract + new asset-grouping concept)
**Depends on:** #329 (MCP asset type — the `mcp` member type is reserved but inert until it ships)
**Date:** 2026-06-12

## Problem statement

The toolkit manages asset types (skills, agents, pi-extensions, instructions, and
the planned MCP kind) individually, but assets have cross-dependencies: an agent
told to use certain skills, or a skill that needs an MCP server, breaks silently
if its dependencies aren't installed alongside it. Native harnesses each have
their own grouping concept (Claude Code plugins, Pi packages, …), but there is no
toolkit-native, harness-neutral way to say *"these assets belong together and must
be installed together."*

At this stage the bundle is **a common language, not a new mechanism**: a simple
JSON manifest of pointers to assets (first- or third-party) declaring them as
co-install dependencies. The bundle is a **stateless shortcut** — installing one
fans out to the existing per-kind installers, the members appear individually in
their own locks and in the TUI/CLI exactly as if installed by hand, and the bundle
itself is recorded nowhere on disk.

### Motivating failure mode

Install an agent whose definition references skills that aren't installed → broken
agent. A bundle lets the agent and its skills travel and install as one unit.

## Scope decisions (read this before the schema)

Two narrowings were made during brainstorming relative to the original issue
braindump. Both are deliberate, not oversights:

1. **`instructions` is OUT of scope as a bundle member.** Unlike skills/agents/
   pi-extensions, an `instructions` asset has no arbitrary, shareable git source —
   its "source" is always the consuming project's own `AGENTS.md`, and its
   installer is `instructions install --scope --harness` (a per-project pointer
   reconciliation), not a `source + slug` clone. It is a project-local projection,
   not a portable asset you'd bundle and share. Forcing it into the member schema
   would mean a sourceless special-case member for no real use case. Excluded.

2. **`mcp` is RESERVED but inert.** The original braindump said "all current asset
   types from day one," but the MCP asset kind **does not exist yet** — `mcp add`
   is unbuilt and lives only in #329 (open, milestone v5.0.0). A bundle cannot fan
   out to an installer that does not exist. So `mcp` is a **valid member
   `asset_type` in the schema** (forward-compatibility), but the installer
   **hard-fails loudly** on an `mcp` member until #329 ships — it never silently
   skips. See §5.

**Net v1 fan-out surface: three source-backed kinds — `skill`, `agent`,
`pi-extension`** — which share one uniform `{source, slug, ref}` member shape.

## Acceptance criteria

1. A JSON manifest with `schema_version`, `name`, `description`, and a `members`
   array validates against a documented v1 schema; an unknown `schema_version`,
   a missing required member field, or an unknown `asset_type` is rejected with a
   clear error (not a silent pass).
2. `bundle install <ref>` reads a manifest from a **local file path** and installs
   every `skill`/`agent`/`pi-extension` member by fanning out to that kind's
   existing add+install sequence at the requested scope. (Resolving a manifest
   from a remote/repo-distributed reference is a thin v2 follow-up — see Out of
   scope; the braindump deferred *where* manifests live as "doesn't matter at this
   stage; it's pointers.")
3. Members land in their **own** per-kind locks and appear individually in the
   CLI/TUI panes — indistinguishable from a hand-installed asset. No bundle record
   is written anywhere on disk.
4. `bundle install` is **all-or-nothing**: if any member fails to install, every
   member installed *during this run* is rolled back and the command reports which
   member failed and why. A failed run leaves the system as it was before.
5. `bundle install --global | --project <ref>` applies a single scope to **all**
   members, passed through to each kind's installer. With no flag, the scope
   follows the toolkit's existing default (global outside a project, project
   inside one — the `read_only=False` `scope_and_roots` convention).
6. An `mcp` member causes `bundle install` and `bundle validate` to **fail loudly**
   with a message naming #329, rather than installing the other members or
   silently skipping the `mcp` one. (Once it hard-fails, AC4 rollback applies if
   any member was already installed.)
7. `bundle validate <ref>` performs the **same** schema-check + resolve pass as
   `install` (every source reachable, every ref resolvable, no unknown
   `asset_type`, `mcp` flagged per AC6) with **all disk writes suppressed** —
   it is the dry-run half of install, built from one shared codepath, not a
   parallel implementation. It reports per-member resolution status and exits
   non-zero if any member would fail.
8. `instructions` and any unrecognised `asset_type` in a manifest are rejected by
   validation with a clear message (instructions: "not a bundle member type").

## Architecture

### Components

| Unit | Responsibility | Depends on |
|---|---|---|
| `bundle_manifest.py` | Parse + validate the JSON manifest into a typed `BundleManifest` (list of `BundleMember`). Pure data; no disk side-effects. | `json`, stdlib |
| `bundle_dispatch.py` | Map one `BundleMember` → the concrete add+install call for its kind. The only place that knows each kind's heterogeneous entrypoint. | the four kinds' `*_install` / `add` modules |
| `bundle_install.py` | Orchestrate: resolve-all (dry-run or real), order, rollback-on-failure. Shared by both verbs; a `dry_run` flag suppresses disk writes. | `bundle_manifest`, `bundle_dispatch` |
| `commands/bundle/__init__.py` + `install_cmd.py` + `validate_cmd.py` | Click group + the two verbs. Thin — parse args, call `bundle_install`, render output. | `bundle_install` |

The new `bundle` Click group is registered in `cli.py` alongside `skill`,
`agent`, `instructions`, `pi_extension`.

### Why a dispatch adapter (the heterogeneity problem)

The four (eventually five) kinds do **not** share a uniform install interface.
Verified against the current code:

- **`agent`** — `agent add <source> [--slug] [--ref]` (global-library clone, no
  scope flag) **then** `agent install <slug> [-g/-p] [--harnesses …]` (projection).
  A bundle agent member needs **both** steps.
- **`skill`** — import/wizard-shaped; a member resolves to the same clone-and-lock
  path `skill` uses, then projection.
- **`pi-extension`** — `pi-extension add` **then** `pi-extension install`.
- **`instructions`** — `instructions install --scope --harness` with a fixed
  `AGENTS.md` source. **Excluded** (see Scope decisions §1).
- **`mcp`** — does not exist. **Reserved, hard-fails** (Scope decisions §2).

`bundle_dispatch` is the single unit that absorbs this asymmetry: given a
`BundleMember`, it knows the add+install sequence for that kind and exposes one
uniform `(member, scope, dry_run) -> InstallOutcome` call to the orchestrator.
No new installer logic is written — dispatch calls the existing entrypoints
(preferring their underlying `*_install.apply()` / `add` functions over
shelling out to Click, so rollback and errors stay in-process).

### Manifest schema (v1)

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
      "asset_type": "pi-extension",
      "source": "ajanderson1/pi-extensions/token-meter",
      "slug": "token-meter"
    }
  ]
}
```

**Top-level fields**

| Field | Required | Notes |
|---|---|---|
| `schema_version` | yes | `1` for v1. Unknown values rejected (forward-compat guard). |
| `name` | yes | Human/identifier label for the bundle. Not a lock key — bundles aren't tracked. |
| `description` | no | Free text. |
| `members` | yes | Non-empty array of member objects. |

**Member fields** (uniform across the three source-backed kinds)

| Field | Required | Notes |
|---|---|---|
| `asset_type` | yes | One of `skill`, `agent`, `pi-extension` (installable in v1); `mcp` (reserved, hard-fails); anything else rejected. |
| `source` | yes for installable kinds | Repo (`owner/repo`) or monorepo subpath (`owner/repo/subpath`) — the **same** source string each kind's `add` already accepts. The monorepo subpath rides inside `source` (no separate `path` field) so the member string is byte-identical to what a human would type to `<kind> add`. |
| `slug` | no | Override the derived slug, exactly as each kind's `--slug` does. |
| `ref` | no | Branch/tag/SHA pin, passed to the kind's `--ref`. Omitted = the kind's default-ref behaviour. |

The schema is a strict, additive **subset** of the bundle-ADR composite
(`docs/solutions/architecture-patterns/clone-and-project-substrate-for-bundle-plugin-capability-2026-06-10.md`):
the composite later adds a **group id** (carried in `LockEntry.extras`, e.g.
`bundleId`) and cross-kind references into **one shared clone**. v1 adds neither —
each member is installed by its own kind into its own clone, with no group
bookkeeping. Because v1 only *omits* composite fields and never repurposes an
existing one, the composite is a clean upgrade, not a throwaway.

### Data flow

```
bundle install --project ./team-review.bundle.json
        │
        ▼
  bundle_manifest.load(ref) ──► BundleManifest (validated, typed)
        │                         ▲ rejects bad schema_version / member / asset_type
        ▼
  bundle_install.run(manifest, scope, dry_run=False)
        │
        ├─ resolve pass (always): for each member, bundle_dispatch.resolve()
        │     · mcp member        → raise BundleMemberError("…#329…")   (AC6)
        │     · unknown asset_type→ raise BundleMemberError              (AC1/AC8)
        │     · source/ref unreachable → raise (validate stops here; AC7)
        │
        ├─ if dry_run (validate): report per-member status, return.      (AC7)
        │
        └─ install pass (install only), members in manifest order:
              for each member:
                  outcome = bundle_dispatch.install(member, scope)
                  installed.append(member)
                  on failure:
                      for m in reversed(installed):
                          bundle_dispatch.uninstall(m, scope)   # roll back THIS run
                      raise BundleInstallError(member, cause)    (AC4)
```

### Rollback semantics (AC4)

- "Roll back" = call the member's own kind-level uninstall for **only** the
  members this run installed, newest-first. It does **not** touch assets that were
  already present before the run (a member that was a no-op "already installed"
  is not rolled back — dispatch reports `already_present` and the orchestrator
  excludes it from the rollback set).
- Mirrors the write-then-roll-back-on-failure contract already used in
  `instructions_install` and `agent_install`. Bundle adds no new rollback
  primitive — it sequences the existing per-kind ones.

### Error handling

| Condition | Behaviour |
|---|---|
| Manifest file unreadable / not JSON | `bundle install`/`validate` fail with a clear file error before any resolution. |
| Bad `schema_version` / missing required field / unknown `asset_type` | Rejected at parse (AC1). |
| `instructions` member | Rejected: "not a bundle member type" (AC8). |
| `mcp` member | Hard-fail naming #329 (AC6); rollback if anything already landed. |
| Source/ref unresolvable | `validate` reports it and exits non-zero; `install` fails on that member and rolls back. |
| Member install raises mid-run | Roll back this run's installs, report the failing member (AC4). |

## Out of scope (explicit non-goals)

- **`instructions` as a bundle member** — see Scope decisions §1. Not a portable
  asset; excluded by nature, not deferred.
- **`bundle uninstall`** — deferred to v2. Because v1 is stateless, a member is
  removed today via its own kind's uninstall. A bundle-level uninstall that
  re-reads the manifest and removes each member is a clean v2 addition; it needs
  no stored state but is extra surface the v1 "shortcut" doesn't require.
- **doctor "bundle members present" check** — deferred to v2. `validate` already
  covers the *pre-install* case. Post-install drift detection needs membership
  memory; the ADR-sanctioned path is stamping members with a `bundleId` in
  `LockEntry.extras` (which already round-trips arbitrary keys) — a v2 mechanism.
- **`bundle init` / scaffold** — deferred (YAGNI). A hand-written JSON file is
  fine for v1; don't scaffold an unfrozen schema.
- **Remote / repo-distributed manifest resolution** — v1 reads a local manifest
  file only. Fetching a manifest from a git ref (clone repo → read the manifest
  file → proceed) is a thin v2 wrapper around the same `bundle_install.run`; the
  braindump deferred manifest location as not mattering at this stage.
- **Grouping-lock composite** (group id in the lock, one shared clone across
  kinds, atomic group uninstall) — this is the bundle ADR's "step 3," genuinely
  new ground, sequenced after the `mcp` and `claude-plugin` kinds. v1 is the
  stateless precursor, designed as its subset.
- **Per-member scope override** — one bundle-wide scope only (AC5). YAGNI.
- **Exporting bundles to harness-native plugin formats** (Claude Code plugins, Pi
  packages, npm packages) — explicit non-goal. The bundle is toolkit-native and
  stays so; cross-harness *plugin* translation is the separate claude-plugin-kind
  track, not this issue.

## Test surface

- `bundle_manifest` parse/validate: valid manifest; bad `schema_version`; missing
  `members`; empty `members`; unknown `asset_type`; `instructions` rejected;
  member missing `source` for an installable kind.
- `bundle_dispatch`: each of skill/agent/pi-extension maps to the right add+install
  sequence (mocked at the `*_install` boundary); `mcp` raises naming #329; scope
  is threaded to the installer.
- `bundle_install` orchestration: happy-path all-members install (hermetic
  `file://` git sources, mirroring existing add tests); mid-run failure rolls back
  prior members and leaves the tree clean; an already-present member is not rolled
  back; `dry_run` writes nothing to disk.
- CLI: `bundle install --global` and `--project` thread scope; `bundle validate`
  exits non-zero on an unresolvable member and zero on a clean manifest; `mcp`
  member exits non-zero for both verbs with the #329 message.
- Scope default: outside a project → global; inside → project (AC5).

## Skills / tools required

- `superpowers:test-driven-development` (red-green per AC).
- Existing per-kind install modules (`agent_install`, `skill_install`,
  `pi_extension_install`) and `skill_git` hermetic-clone test helpers (`file://`
  bare-repo fixtures) as the dispatch/orchestration test substrate.
- No new runtime dependency (pure stdlib `json` + existing modules) — note this
  keeps the change off the "new runtime dependency" deep-trigger, though the issue
  is already deep on the schema-contract trigger.

## Trust-level recommendation (advisory)

**L3 (conditional).** New asset-grouping concept and a new top-level Click group,
but the fan-out reuses existing, well-tested installers and adds no new install or
rollback primitive. Divergence from this spec (especially around the
dispatch-adapter boundary or rollback set) should raise.

## Links

- Issue #369.
- Depends on #329 (MCP asset type).
- Bundle composite ADR (the superset this is a subset of):
  `docs/solutions/architecture-patterns/clone-and-project-substrate-for-bundle-plugin-capability-2026-06-10.md`
- Cross-harness plugin/bundle landscape survey:
  `docs/solutions/tooling-decisions/cross-harness-plugin-bundle-landscape-2026-06-10.md`
- STRATEGY.md → "Cross-machine / cross-harness reach" track (portable owned
  library) is the strategic home for bundles.
