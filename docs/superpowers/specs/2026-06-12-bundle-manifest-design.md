# Bundle manifest v1 — declare assets that install together (toolkit-native JSON)

**Issue:** #369
**Tier:** deep (new JSON schema/contract + new asset-grouping concept)
**Depends on:** #329 (MCP asset type — the `mcp` member type is reserved but inert
until it ships). **#393 (default `skill install --agents`) is DONE** — merged in
#394, so a skill member installs with no special-casing.
**Date:** 2026-06-12 (revised 2026-06-13 to resolve critical-review findings)

## Problem statement

The toolkit manages asset types (skills, agents, pi-extensions, and the planned
MCP kind) individually, but assets have cross-dependencies: an agent told to use
certain skills, or a skill that needs an MCP server, has no co-install story — you
install each by hand and it is easy to forget one. There is no toolkit-native,
harness-neutral way to say *"these assets belong together; install them as a unit."*

The bundle is **a common language, not a new mechanism**: a JSON manifest of
pointers to assets (first- or third-party) declaring them as co-install
dependencies. v1's value is precise and bounded: **co-install a known dependency
set in a single, all-or-nothing command.** The bundle is a **stateless shortcut** —
installing one fans out to the existing per-kind installers, the members appear
individually in their own locks and in the TUI/CLI exactly as if installed by hand,
and the bundle itself is recorded nowhere on disk.

### What v1 does NOT do (honest framing)

v1 protects you at the **moment of install** — it gets the whole dependency set onto
disk atomically. It does **not** durably prevent the "broken agent, missing skill"
state over time: because nothing is recorded, if a member is later uninstalled or
scoped away by hand, nothing detects that the agent is now broken. Durable
drift-detection is a deliberate **v2** concern (a `doctor` "bundle members present"
check, keyed on an `extras.bundleId` stamp — see Out of scope). Framing v1 as
"prevents silent breakage" would oversell it; v1 is **atomic co-install**, full stop.

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
   inside one), computed by a new shared `default_scope(cwd) -> str` helper added
   to `_paths_core` (the existing `scope_and_roots` convention is per-kind and
   keyed on a per-kind lock filename; there is no binding-neutral "in a project"
   today — see F3 in the architecture's scope note).
6. An `mcp` member causes `bundle install` and `bundle validate` to **fail loudly**
   with a message naming #329, rather than installing the other members or
   silently skipping the `mcp` one. The `mcp` check runs in the **resolve pass**
   (before any install), so a manifest containing `mcp` fails before anything lands
   — there is nothing to roll back. (If `mcp` somehow surfaced mid-install, AC4
   rollback still applies.)
7. `bundle validate <ref>` performs the **same schema + member-type validity**
   pass as `install`'s resolve phase (valid `schema_version`, every member a known
   installable `asset_type`, no `instructions`, `mcp` flagged per AC6), with **all
   disk writes suppressed** — one shared codepath, not a parallel implementation.
   It exits non-zero if any member is structurally invalid. **Source/ref network
   reachability is NOT probed by validate** — that is proven by the real `add`
   during install; validate is a static manifest check, not a connectivity test.
   (A `git ls-remote` reachability probe is a possible v2 enhancement — see Out of
   scope; it carries network cost and private-repo auth concerns not worth v1.)
8. `instructions` and any unrecognised `asset_type` in a manifest are rejected by
   validation with a clear message (instructions: "not a bundle member type").
9. Manifest-supplied member fields (`source`, `slug`, `ref`) that begin with `-`
   are rejected at parse time, and dispatch inserts a `--` end-of-options sentinel
   before any manifest-derived positional argument — so a crafted field (e.g.
   `slug: "--force"`) can never be interpreted by Click as a flag (option
   injection). See the security note in the architecture.

## Architecture

### Components

| Unit | Responsibility | Depends on |
|---|---|---|
| `bundle_manifest.py` | Parse + validate the JSON manifest into a typed `BundleManifest` (list of `BundleMember`). Pure data; no disk side-effects. | `json`, stdlib |
| `bundle_dispatch.py` | Map one `BundleMember` → the per-kind add+install argv, invoke in-process, lock-precheck for `already_present`. The only place that knows each kind's heterogeneous entrypoint. | `cli.main` (in-process), each kind's lock reader |
| `bundle_install.py` | Orchestrate: resolve-all (structural), order, rollback-on-failure (warn on rollback failure). Shared by both verbs; a `dry_run` flag stops after resolve. | `bundle_manifest`, `bundle_dispatch` |
| `_paths_core.default_scope(cwd)` | NEW shared helper: project-vs-global default (project if any per-kind lock present in cwd, else global). Resolves F3 — no such binding-neutral helper exists today. | stdlib |
| `commands/bundle/__init__.py` + `install_cmd.py` + `validate_cmd.py` | Click group + the two verbs. Thin — parse args, call `bundle_install`, render output. | `bundle_install`, `default_scope` |

The new `bundle` Click group is registered in `cli.py` alongside `skill`,
`agent`, `instructions`, `pi_extension`.

### Why a dispatch adapter (the heterogeneity problem)

The kinds do **not** share a uniform install interface. Verified against the
current code (post-#394):

- **`agent`** — `agent add <source> [--slug] [--ref]` (global-library clone, no
  scope flag) **then** `agent install <slug> [-g/-p]` (projection). Two steps.
- **`skill`** — `skill add <source> [--slug] [--ref]` **then** `skill install
  <slug> --agents standard --scope <global|project>`. NOTE the asymmetry the
  review caught: skill uses `--scope` + `--agents` (now defaulting to `standard`
  since #393/#394), **not** `-g/-p`. So dispatch is **per-kind, not one uniform
  argv builder**.
- **`pi-extension`** — `pi-extension add <source> [--slug]` (**no `--ref`** — F6:
  the option does not exist) **then** `pi-extension install <slug> [-g/-p]`.
- **`instructions`** — excluded (Scope decisions §1).
- **`mcp`** — reserved, hard-fails in the resolve pass (Scope decisions §2).

`bundle_dispatch` absorbs this asymmetry with a **per-kind argv table**, then
invokes the toolkit CLI **in-process** via `cli.main.main(args=argv,
standalone_mode=False)` (Click's programmatic mode: it raises on failure instead
of `sys.exit`, so the orchestrator catches and rolls back). This reuses every
kind's real validation, clone, projection, and lock-write exactly as a human
invocation would — no installer logic is duplicated.

**On the seam choice (F10 — decided, not deferred):** the in-process-CLI seam is
chosen over importing each kind's `apply()`/add core directly. The install cores
(`skill_install.apply`, `agent_install.apply`, `pi_extension_install.apply`) ARE
importable, but the **add** halves are largely Click-command-bound (`_add_single`/
`_add_monorepo` live under the command), so a "pure function" seam would require
extracting add cores first — widening v1 beyond a "common language" shortcut. The
in-process CLI is the smaller, reuse-maximising choice for v1. Its risks are
bounded and mitigated:

- **Per-member ordering / no shared `ctx`.** Each `main.main()` call is an
  independent Click parse with a fresh root context — no `ctx.obj` leakage between
  members (a property, not a hazard). The top-level `--project` is NOT inherited,
  so dispatch **explicitly prepends `--project <root>` to the child argv when
  project scope is active** (F8), rather than relying on cwd.
- **Option injection (F5).** Member fields are placed into argv. `_parse_member`
  rejects any `source`/`slug`/`ref` starting with `-`, and dispatch inserts a `--`
  end-of-options sentinel before any manifest-derived positional, so a value like
  `--force` can never be read as a flag.
- **`already_present` detection (F2).** The in-process call returns `None` and the
  kinds only `click.echo` "already in library", so dispatch CANNOT scrape a no-op
  from the return. Instead it **reads the kind's library lock for the slug BEFORE
  calling add**; if present with the same source, the member is marked
  `already_present` and excluded from the rollback set (satisfies AC4's
  "already-present member not rolled back").

`bundle_dispatch` exposes `resolve(member)`, `install(member, scope)`, and
`uninstall(member, scope)` to the orchestrator (these are the function names the
plan uses; the orchestrator suffixes them `_member` to avoid shadowing — see the
plan's file table).

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
| `source` | yes for installable kinds | Repo (`owner/repo`) or monorepo subpath (`owner/repo/subpath`) — the **same** source string each kind's `add` already accepts. The monorepo subpath rides inside `source` (no separate `path` field) so the member string is byte-identical to what a human would type to `<kind> add`. Must not start with `-` (F5). |
| `slug` | no | Override the derived slug, exactly as each kind's `--slug` does. Must not start with `-` (F5). |
| `ref` | no | Branch/tag/SHA pin. Honoured for `skill` and `agent` (their `add` has `--ref`). **A `pi-extension` member with `ref` is rejected at parse** — `pi-extension add` has no `--ref` (F6). Must not start with `-` (F5). |

**Schema vs the bundle-ADR composite (F7 — honest framing).** The v1 manifest's
*field names* (`source`, `ref`, `slug`) overlap with the eventual composite, but
v1 is **not** a forward-compatible subset of the composite's install *shape*. The
ADR composite installs **one shared clone** at `~/.agent-toolkit/bundles/<slug>/`
and decomposes it via cross-kind subpaths with a shared group id; v1 installs **N
independent clones** via N independent `<kind> add`s, where `source` is a
standalone repo. The composite would re-point every member's `source` from a
standalone repo to a subpath-into-the-bundle-clone — i.e. the install path and the
*meaning* of `source` change. So: the JSON field names carry over, but the composite
will replace v1's install mechanism, not merely add fields to it. v1 is the
stateless precursor; do not rely on install-path forward-compatibility.

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
        │   (structural only — NO network probe; reachability proven on install, AC7)
        │
        ├─ if dry_run (validate): report per-member status, return.      (AC7)
        │
        └─ install pass (install only), members in manifest order:
              for each member:
                  outcome = bundle_dispatch.install(member, scope)   # lock-precheck → already_present?
                  if outcome != already_present: installed.append(member)
                  on failure:
                      for m in reversed(installed):
                          try: bundle_dispatch.uninstall(m, scope)   # roll back THIS run
                          except: warn(err) naming m                 # F9 — never silent
                      raise BundleInstallError(member, cause)         (AC4)
```

### Rollback semantics (AC4)

- "Roll back" = call the member's own kind-level uninstall for **only** the
  members this run actually installed, newest-first. A member the lock-precheck
  found `already_present` (present before the run) is **excluded** from the
  rollback set — it is not ours to remove.
- **Rollback failures are never swallowed (F9).** If a member's uninstall raises
  during rollback, dispatch emits a `warning:` line to stderr naming the member(s)
  that may need manual cleanup, and the original `BundleInstallError` still
  propagates. A silent `except: pass` would leave partial state invisible,
  undermining the all-or-nothing guarantee.
- Mirrors the write-then-roll-back-on-failure contract already used in
  `instructions_install` and `agent_install`. Bundle adds no new rollback
  primitive — it sequences the existing per-kind ones.

### Error handling

| Condition | Behaviour |
|---|---|
| Manifest file unreadable / not JSON | `bundle install`/`validate` fail with a clear file error before any resolution. |
| Bad `schema_version` / missing required field / unknown `asset_type` | Rejected at parse (AC1). |
| `instructions` member | Rejected: "not a bundle member type" (AC8). |
| `mcp` member | Hard-fail naming #329 in the resolve pass (AC6) — before any install, so nothing to roll back. |
| Field starting with `-` (`source`/`slug`/`ref`) | Rejected at parse (F5 option-injection guard). |
| `ref` on a `pi-extension` member | Rejected at parse — `pi-extension add` has no `--ref` (F6). |
| Source/ref unresolvable at install | `validate` does NOT catch this (no network probe, AC7); `install`'s real `add` fails on that member and rolls back this run (AC4). |
| Member install raises mid-run | Roll back this run's installs (warn on any rollback failure, F9), report the failing member (AC4). |

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
- **Source/ref reachability probe in `validate`** — deferred to v2 (F4). v1
  `validate` is a static schema + member-type check; a `git ls-remote`-per-member
  reachability probe carries network cost and private-repo auth concerns not worth
  v1. Install proves reachability via the real `add`.
- **Grouping-lock composite** (group id in the lock, one shared clone across
  kinds, atomic group uninstall) — this is the bundle ADR's "step 3," genuinely
  new ground, sequenced after the `mcp` and `claude-plugin` kinds. v1 is the
  stateless precursor; per F7 above, the composite will replace v1's install
  mechanism (one-clone decompose), reusing only the JSON field names.
- **Per-member scope override** — one bundle-wide scope only (AC5). YAGNI.
- **Exporting bundles to harness-native plugin formats** (Claude Code plugins, Pi
  packages, npm packages) — explicit non-goal. The bundle is toolkit-native and
  stays so; cross-harness *plugin* translation is the separate claude-plugin-kind
  track, not this issue.

## Test surface

- `bundle_manifest` parse/validate: valid manifest; bad `schema_version`; missing
  `members`; empty `members`; unknown `asset_type`; `instructions` rejected;
  member missing `source` for an installable kind; **field starting with `-`
  rejected (F5)**; **`ref` on a `pi-extension` member rejected (F6)**.
- `bundle_dispatch`: skill maps to `skill install <slug> --agents standard --scope
  <s>` (NOT `-g/-p`); agent/pi-ext map to `-g/-p`; pi-ext add omits `--ref`; the
  per-kind argv is asserted in full (not just the scope flag); `mcp` raises naming
  #329; **a `--` sentinel precedes manifest-derived positionals (F5)**.
- `default_scope(cwd)` (new `_paths_core` helper, F3): inside a project → project,
  outside → global; pinned by a from-inside vs from-outside test.
- `bundle_install` orchestration (dispatch stubbed): happy-path all-members
  install; mid-run failure rolls back prior members and leaves the tree clean; an
  **already-present (lock-precheck) member is not rolled back (F2)**; a **rollback
  failure emits a warning and does not swallow it (F9)**; `dry_run` writes nothing.
- End-to-end hermetic (`file://` bare repos, real installers): a 2-member
  skill+agent bundle lands both in their real locks; a bundle whose 2nd member is
  unresolvable rolls the 1st back.
- CLI: `bundle install --global` / `--project` thread scope to every member;
  **`bundle install --project <path>` threads the top-level `--project` into the
  fan-out (F8)**; `bundle validate` exits zero on a structurally-valid manifest and
  non-zero on a bad `asset_type`/`instructions`/`mcp`; `mcp` exits non-zero for
  both verbs with the #329 message.
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
