# Shared catalogue: agents, commands and Pi extensions

Status: proposed; builder check incorporated, awaiting AJ's approval before implementation.
Date: 2026-10-25.

## Intent and basis

Extend the optional shared catalogue shipped in 6.1.0 so users can discover
agents, commands and Pi extensions alongside skills, then use each kind's real
lifecycle without manually copying upstream coordinates. This is one catalogue
with typed entries, not four subscriptions or a new package manager.

AJ requested this extension and delegated the design choices. The specific
choices below are the author's recommendations, not previously agreed behavior.
The deliverable here is a spec; implementation, remote catalogue edits, publishing
and release are not authorized by it.

Baseline: canonical GitHub repository `ajanderson1/agent-toolkit-cli`, tag
`v6.1.0`, commit `74a41448cab89586fc4b048bd4d423da455e61a1`. The task checkout
started at `92800e1de9704698d6619590d0514730e519c2a8`, behind that release;
release source was inspected separately without changing the checkout or AJ's
existing edits. Implementation must start from the then-current canonical base.

Despite the request's informal “well known” wording, 6.1.0 implements an explicit
Git subscription and `catalog.json`, not `.well-known` HTTP discovery. Retain that
transport. No HTTP endpoint, search service or new dependency is needed.

Follow `GLOSSARY.md`: add/remove concerns global library membership;
enable/disable concerns harness exposure. Native Pi npm installation is an
explicit exception, not a Toolkit library registration.

## Goals and boundaries

- One user-global subscription, shared across projects and the four kinds.
- Live, read-only discovery in CLI and existing per-kind TUI grids.
- Exact source matching, clear provenance and safe explicit acquisition.
- Preserve 6.1.0 skills behavior, command syntax, configuration and acquired data.
- Cover both Git-backed and native npm Pi extensions, without inventing an npm
  library or treating package installation as an exposure-only operation.
- Preserve local work, existing scope/backing, pins and unsupported-adapter limits.

Not included: MCPs, Instructions, bundle cataloguing, multiple catalogues,
project-specific subscriptions, full-text remote search, automatic updates,
background upstream checks, source adoption, dependency solving, CLI lifecycle
renames or a new TUI screen. No host access or catalogue hosting changes.

A technically working implementation is still a failure if browsing acquires
assets, enabling silently updates existing Git backing, npm rows recreate retired
Toolkit registrations, or catalogue metadata becomes authority to replace local
content or activate unsupported harnesses.

## Shared subscription and compatibility

Retain the existing `skillCatalog` configuration key and its URL/ref shape for
this increment. Its historical name is an implementation compatibility detail;
it now supplies the shared catalogue. Do not create a second setting or migrate
configuration on read. Retain config symlinks, modes and unrelated fields.

Add the utility group `agent-toolkit-cli catalog` with `subscribe URL [--ref REF]`,
`unsubscribe`, and `list [--kind KIND] [--json]`. `KIND` uses the plural CLI group
names: `skills`, `agents`, `commands`, `pi-extensions`. An omitted kind lists all.
Subscribe validates before replacing the single subscription. Unsubscribe only
removes that subscription; it does not remove acquired content or projections.

Existing `skills catalog subscribe` and `unsubscribe` remain compatibility
entrypoints to the same subscription; help must now state that they affect all
four kinds. Existing `skills catalog list [--json]` remains skills-only and keeps
its existing JSON fields. New per-kind `catalog list [--json]` commands filter
the shared snapshot; they do not create subscriptions. General JSON output adds
explicit kind and source-type information; no existing JSON shape is repurposed.
An unsubscribed list succeeds with an empty result; a failed/invalid subscribed
catalogue read exits nonzero, never masquerading as a successful empty listing.

Keep existing per-kind `list`, status and doctor contracts. Where 6.1.0 skills
inventory already includes catalogue candidates, preserve that behavior; extend
per-kind inventory deliberately with `origin: catalog` and source-type fields,
without labeling catalogue-only rows as local library records.

## Manifest

Read both the existing version 1 skill manifest and a new version 2 manifest.
Normalize version 1 entries internally as `kind: skill`, `sourceType: git`.
Version 1's validation and skills-only meaning stay unchanged.

Version 2 uses `entries`; there is no parallel `skills` array:

```json
{
  "version": 2,
  "entries": [
    {
      "kind": "skill",
      "key": "review-workflow",
      "description": "A reusable review workflow",
      "sourceType": "git",
      "source": "example/workflows",
      "path": "skills/review-workflow",
      "ref": "main"
    },
    {
      "kind": "agent",
      "key": "reviewer",
      "description": "A review agent",
      "sourceType": "git",
      "source": "example/agents",
      "path": "agents/reviewer",
      "entryFile": "reviewer.md",
      "ref": "main"
    },
    {
      "kind": "command",
      "key": "summarize",
      "description": "A reusable summary prompt",
      "sourceType": "git",
      "source": "example/prompts",
      "path": "commands/summarize"
    },
    {
      "kind": "pi-extension",
      "key": "pi-tools",
      "description": "A Git-backed Pi extension",
      "sourceType": "git",
      "source": "example/pi-tools",
      "path": ".",
      "ref": "main"
    },
    {
      "kind": "pi-extension",
      "key": "pi-review-tools",
      "description": "A native Pi npm package",
      "sourceType": "npm",
      "source": "npm:@example/pi-review-tools@1.2.3"
    }
  ]
}
```

These coordinates illustrate the format; they are not verified recommendations.

Rules:

- `kind` is one of `skill`, `agent`, `command`, `pi-extension`; only the last
  accepts npm. `sourceType` is required in version 2.
- `(kind, key)` is unique. Keys follow the existing lowercase kebab-case rule
  and 64-character limit. The same key in different kinds is valid. Within one
  kind, duplicate normalized selectors are invalid rather than ambiguous aliases.
- Descriptions retain the existing nonempty, 1024-character limit. Reject unknown
  kinds/types/versions, duplicate identities, conflicting selector fields and
  malformed entries as an invalid snapshot, with a useful sanitized diagnostic.
- Git `source` selects a repository only; `path` is a required safe relative
  directory, `.` for root. `ref` is optional and sanitized separately. No embedded
  competing path/ref selector, traversal, absolute path, credentials or query.
- Skills select a directory containing `SKILL.md`; commands select one containing
  a regular `COMMAND.md`. Agent entries additionally require `entryFile`, exactly
  `<key>.md` for a flat agent or `AGENTS.md` for a complete-directory agent. Other
  kinds reject this field. It participates in selector identity, duplicate checks,
  provenance and queued-intent validation. Directory-agent keys need not equal
  the source directory basename; existing explicit slug support handles that.
- Agent shape is a catalogue claim, sufficient to restrict candidate harness cells
  but not proof of valid source content. Validate the declared file/shape before
  successful registration or projection. Preserve the current flat-file preference:
  an `AGENTS.md` declaration with a competing `<key>.md` file is refused, not
  silently flattened or forced into a different shape. Exact existing matches
  must have the same recorded entry file. No arbitrary entry-file selection or
  flat-agent rename mechanism is introduced.
- Git Pi extensions require `path: "."`; nested Git extension packages are not
  newly supported. Unsupported source/path forms must be refused, not fetched
  from some other directory or reinterpreted as npm.
- npm sources use native `npm:` syntax with an explicit exact published version;
  tags, ranges and unversioned recommendations are deferred. There is no `path`
  or `ref`, custom install alias or embedded registry credential. The catalogue
  key is only a listing ID; native package identity remains `@scope/name`.
- No payloads, machine paths, enabled state, credentials, shell commands or
  installer arguments in the manifest. Unknown non-selector metadata may be
  ignored; unknown source-selector fields must not silently change acquisition.

Old 6.1.0 clients reject version 2 rather than silently misread it. Updating the
actual shared repository to version 2 is a separate explicit operation after
client rollout; this feature does not rewrite or publish it. Version 1 remains
supported indefinitely within this increment.

## Acquisition and exposure

New per-kind catalogue commands are proposed syntax, not commands already shipped.
Keep the shipped skill commands unchanged. For the three new groups, use:

```text
agent-toolkit-cli agents catalog add KEY
agent-toolkit-cli agents catalog enable KEY --scope project --harnesses pi
agent-toolkit-cli commands catalog add KEY
agent-toolkit-cli commands catalog enable KEY --scope project --harnesses standard
agent-toolkit-cli pi-extensions catalog add GIT_KEY
agent-toolkit-cli pi-extensions catalog enable GIT_KEY --scope project
agent-toolkit-cli pi-extensions catalog install NPM_KEY --scope project [--yes]
```

`--scope global|project` is required on these new exposure/installation commands,
so source type and existing lock inference cannot silently choose a target. Agent
and command catalogue enable require `--harnesses`; Pi accepts only its own target.
Validate scope, targets and supported package shape before acquisition where
possible. Existing native/per-kind verbs retain all current defaults and flags.

| Catalogue operation | Git skills / agents / commands / Pi extensions | Pi npm |
| --- | --- | --- |
| Browse | Metadata only | Metadata only; no registry probe |
| Add | Register global library backing; no exposure | Refuse with native-install guidance; no fake registration |
| Enable | Obtain if absent, then project only selected targets | Not offered as a catalogue operation; use native enable on installed identity |
| Install | Not added; existing shipped `install` verbs remain available | Explicit native scoped install/configure |
| Disable/remove/update | Existing per-kind commands | Existing native commands and Pi update guidance |

Npm installation prints the exact source and scope and warns that installation
may execute package-manager lifecycle code and activate bundled resources. Require
confirmation, or explicit `--yes`; noninteractive calls without it fail before
mutation. Delegate to the existing native Pi lifecycle, preserving filters,
project inheritance, settings locking and trust. Do not simulate “add disabled”
by installing then disabling, and do not claim an installation only enabled
extensions. After installation, native inventory/controls are authoritative.
Missing native prerequisites or ambiguous declarations fail visibly.

Git Add/Enable goes through per-kind engines, not a skills-lock-shaped generic
installer. Existing exact matches retain their slug, backing, ownership and local
HEAD. Agent monorepo re-add can currently refresh a shared parent; catalogue reuse
must instead use a non-advancing validation path. Catalogue enabling is not an
implicit update. Command/Pi facades also need explicit origin/ref/path/content
preflight where current idempotence shortcuts are weaker than this contract.
These are bounded safety seams, not a lifecycle redesign.

A failed projection may leave successfully acquired Git library content; report
acquisition and each target's outcome separately. Never claim successful exposure
for failed targets or delete preexisting/shared backing to roll back. Preserve
foreign files and local work. Retrying must not advance or replace existing sources.

## Identity, provenance and conflicts

Within a kind, match normalized repository URL + exact selected directory +
configured ref, including the kind's recorded entry-file identity. Use existing
conservative URL normalization; do not guess aliases. Consult stable recorded
catalogue URL/kind/key provenance before current selector equality, so a changed
listing remains associated with its existing entry rather than producing a second
acquisition. Multiple plausible local copies are ambiguous, not a dedup opportunity.

Read-only joins do not write. Explicit successful Git Add/Enable records catalogue
URL, kind, key and selector in that kind's existing lock metadata. Legacy skills
provenance without kind implies `skill` and is not bulk-rewritten. Browse must not
adopt unmanaged content. A name collision with a different source/ref/path blocks
acquisition; preserve the local row and display the conflict.

A changed Git catalogue selector is advisory. Keep acquired source/ref/path,
content and exposure; reject catalogue acquisition of the changed selector and
point to explicit CLI maintenance. Removing a listing, changing subscription or
unsubscribing never removes acquired content or exposure. Existing managed assets
remain operable offline through their ordinary commands.

Npm matching uses native package identity, requested source/version, selected
installation and actual scope/inheritance. Exact matching recommendations attach
read-only listing context to native inventory; never persist npm provenance in
Toolkit installation locks. A different installed/requested version is a visible
mismatch, not consent to upgrade, replace a declaration or select a local unused
copy. Catalogue install refuses incompatible existing declarations/installations
and directs users to native maintenance. Catalogue removal has no npm side effect.

## CLI/TUI discovery, pending changes and diagnostics

Retain the four existing grids and their native target columns. Catalogue-only Git
rows are visibly not acquired and not enabled; npm recommendations are visibly not
installed, distinct from native rows. Catalogue membership never implies adapter
support. Directory agents remain Pi-only where that is the current supported form;
flat agents retain their existing adapter set. Commands project only their prompt
file; adjacent resources are not promised as portable. Git Pi links are labelled
Linked, not proof of code loaded in a running session.

Fetch one fresh shared snapshot per inventory-load/explicit-refresh generation,
not per kind, row, keystroke or tab render. Share it across all four grids; fetch
in a worker, keep local inventory usable, bound network waits, and reject late
results from an old scope/refresh generation. No subscription means no catalogue
network calls. A failed/invalid refresh drops all catalogue-only rows with one
shared warning; acquired/native inventory remains. Never serve stale listings as
a successful live catalogue. Do not fetch asset repositories or npm metadata to
render recommendations.

Git checkboxes queue intents only. Apply re-reads the live catalogue once for the
catalogue-dependent batch and validates the subscription URL/ref and each selected
kind/key/source/type/path/ref/entryFile against the queued snapshot before acquisition.
Description-only or unrelated listing changes need not block; a removed or changed
selected identity must fail pending with refresh/reselect guidance. Scope changes
must not retarget a queued intent. Revert causes no acquisition. Preserve failed
intents; clear only successful operations, following existing cross-kind queues.
Local-only operations do not depend on catalogue availability.

Npm catalogue-only rows are read-only in the TUI and excluded from single/All/None
queues. Info supplies the exact confirmed-install CLI command. This deliberately
avoids adding a second TUI package installation workflow. Once native installation
is observed, reuse the existing npm selection controls, mixed state and stale-Apply
safeguards; never download a package from a checkbox.

Info shows kind, description, source/type/path/ref or requested npm version,
catalogue provenance, acquisition state and relevant conflicts. Show exact existing
CLI maintenance commands, actual scope/backing, and native prerequisite/trust
caveats. No new layout or modal is necessary.

Doctor distinguishes unavailable catalogue data from unhealthy acquired content.
Catalogue-only means not acquired, not missing-content corruption. Doctor never
acquires, adopts, updates or changes a selector due to a listing, and does not
perform new upstream probes. Preserve each kind's existing repair/no-fix behavior.

## Upstream checks and updates

Keep 6.1.0 skills checks intact. Add `agents check`, `commands check` and Git-only
`pi-extensions check`, following `skills check [SLUGS...] -g|-p [--json]` and each
kind's existing read-scope selection. With no names, check only catalogue-associated
Git entries in that scope. Npm is excluded from batch Git checks; an explicitly
named npm identity returns a clear unsupported/native-guidance error.

Checks compare local backing with its recorded Git selector, not the current
catalogue recommendation, and work after unsubscription using provenance. Reuse
current/different/pinned/unknown semantics: a different revision is not proof a
monorepo child changed or that a safe fast-forward exists. Retain local edits,
timestamp results, invalidate observations after source/ref/path/entry-file/local-HEAD change,
and batch identical upstream queries where practical. Store per-kind local
observations adjacent to the global library lock, keyed to the actual backing;
these are not catalogue caches, project configuration or new installation locks.

TUI Info displays timestamped results and maintenance guidance only. No automatic
upstream checks, TUI update queue or implicit updates on enable. Use existing
per-kind update behavior, including current monorepo/read-only limitations; do not
promise unsupported updates. Native npm uses Pi's package update workflow, not
Git checks or a new Toolkit npm update mechanism.

## Implementation shape and builder discretion

Keep Python/Click, Textual and the current JSON/Git infrastructure. Extract shared
subscription, transport, typed manifest parsing and snapshots from
`skill_catalog.py`; retain compatibility imports/wrappers as useful. Keep per-kind
matching/acquisition/check adapters small and explicit, with real lock/native
contracts. Do not build a plugin registry, generic package manager or universal
lock schema just to remove a few conditionals.

Integration anchors in 6.1.0:

- CLI: `cli.py`, `commands/skill/catalog_cmd.py`, new per-kind catalogue commands.
- Catalogue: `skill_catalog.py`, `skill_catalog_ops.py`, `skill_update_check.py`.
- Kind engines: agent/command add and install commands, `pi_extension_add.py`,
  native `pi_npm.py` / `pi_npm_lifecycle.py`; their locks and path helpers.
- TUI: `app.py` snapshot orchestration/Apply, `*_state.py`, existing four grids,
  `asset_info.py` and cross-kind pending behavior.

The builder chooses exact module/class names, internal snapshot representation,
observation filenames, helper signatures and test decomposition. Safety contracts,
manifest shape, native npm boundary and proposed CLI above are design decisions,
not open implementation choices. A source form not safely supported by an existing
kind must be refused clearly; widen adapters only through a separately agreed scope.

## Acceptance and validation

Use disposable HOME/config/assets and local Git remotes; no production catalogue,
live library or Pi settings for tests. Include deterministic native fixtures and
installed-wheel verification against the supported native Pi SDK where npm behavior
is exercised; do not execute test extension code.

Required coverage:

1. Version 1 compatibility, unchanged skill JSON/verbs/provenance and no-subscription
   behavior; version 2 mixed manifests, cross-kind same keys, duplicate selectors,
   malformed types/versions/paths/refs and unsupported shapes.
2. One shared subscription and one fetch per refresh; all four inventories offline,
   auth failure, timeout, invalid manifest, late worker result and no stale fallback.
3. Git root/nested selection for supported sources; flat and directory agents;
   `COMMAND.md`; root-only Git Pi. No sibling activation or unsupported target
   writes. Content validation occurs before successful registration/exposure.
4. Exact reuse under different local slugs, legacy skill provenance, source/ref/path
   conflicts, ambiguous copies, changed/removed listing and unsubscription.
   Browsing writes no locks; repeated enabling leaves Git HEAD/local work unchanged,
   including agent shared parents. Foreign/orphan/missing backing fails safely.
5. Cross-kind pending Apply/Revert, scope retention, one batch revalidation, changed
   subscription/selector refusal, partial acquisition/projection failure and retry.
   Local operations work when the catalogue is offline.
6. Npm version parsing, metadata-only browsing, no npm lock entries, read-only
   catalogue TUI rows, explicit confirmation/noninteractive refusal, native install
   delegation, filter preservation, conflicting version/declaration refusal,
   inheritance, actual selected installation and missing SDK/Pi prerequisites.
7. CLI checks across Git kinds: pins, local edits, shared backing, unknown/error
   status, stale timestamps, post-unsubscribe checks and native npm exclusion.
8. Info/help/docs accurately state scopes, acquisition vs exposure, Git-vs-npm
   differences, directory-agent limits, command resource limits and native trust.
   Doctor retains kind-specific safety and performs no catalogue-driven repair.

Before shipping implementation: run focused tests, full `uv run pytest -q`, and
strict `make docs-build`. Update current CLI/TUI and affected asset reference docs;
keep historical plans/release notes intact. Use generated harness docs only if
machine-read harness data actually changes; never hand-edit generated outputs.
No hand-authored version bump or release changes. Record canonical source commit
and wheel hash if building/installing a validation artifact.

## Suggested delivery order

1. Shared snapshot/version 2 parser and subscription CLI, with all version 1 and
   existing skills regression tests green.
2. Git agent/command/Pi adapters and safe reuse, CLI acquisition and checks.
3. Shared TUI discovery/Apply/Info across four grids, preserving pending semantics.
4. Npm recommendation matching and explicit confirmed native CLI installation.
5. End-to-end tests, current reference docs, installed-artifact verification.

These are planning seams, not authorization to implement or edit the hosted
catalogue. After design approval, write the implementation plan against the
current canonical base.

## Builder check disposition

A fresh read-only builder check identified one consequential gap: without a declared
agent shape, metadata-only discovery cannot determine supported targets or include
entry-file identity in matching. The author resolved this with the required agent
`entryFile` field and acquisition-time verification above, grounded in the shipped
flat-file preference and Pi-only directory adapter. Directory keys may differ from
source directory names; flat entries retain the existing filename constraint. This
is an author decision for AJ to review, not a new question or an agreed requirement.
No other important planning questions were reported.
